"""Her kaynak için en iyi tarama yöntemini belirler.

Öncelik: WordPress REST API > RSS/Atom > liste sayfası (gerekirse LLM ile bulunur).
"""

import asyncio
import logging
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import feedparser
import httpx
import lxml.html
from pydantic import BaseModel
from sqlalchemy import select

from .browser import is_ubys_cms
from .config import settings
from .db import Session, Source, utcnow
from .http import Fetcher
from .llm import LLMError, chat_json
from .list_rules import learn_list_rules

log = logging.getLogger(__name__)

# keşif JSON'undaki alan adı -> list_urls anahtarı
RECON_LIST_KEYS = {"haber_url": "haber", "duyuru_url": "duyuru", "etkinlik_url": "etkinlik"}


async def _resolve_base_url(fetcher: Fetcher, host: str) -> str | None:
    candidates = [f"https://{host}/"]
    if not host.startswith("www."):
        candidates.append(f"https://www.{host}/")
    candidates.append(f"http://{host}/")
    for url in candidates:
        try:
            resp = await fetcher.get(url)
        except httpx.HTTPError:
            continue
        if resp.status_code < 400:
            final = urlsplit(str(resp.url))
            return f"{final.scheme}://{final.netloc}"
    return None


async def _read_robots(fetcher: Fetcher, source: Source) -> None:
    rp = RobotFileParser()
    try:
        resp = await fetcher.get(f"{source.base_url}/robots.txt")
        rp.parse(resp.text.splitlines() if resp.status_code == 200 else [])
        if resp.status_code != 200:
            source.notes.append(f"robots.txt HTTP {resp.status_code}")
    except httpx.HTTPError as exc:
        rp.parse([])
        source.notes.append(f"robots.txt okunamadı: {type(exc).__name__}")
    agent = settings.user_agent.split("/")[0]
    source.robots_disallow_all = not rp.can_fetch(agent, f"{source.base_url}/")
    delay = rp.crawl_delay(agent)
    source.crawl_delay = float(delay) if delay else None
    fetcher.set_host_delay(urlsplit(source.base_url).hostname, source.crawl_delay)


async def _try_wp_rest(fetcher: Fetcher, source: Source) -> bool:
    url = f"{source.base_url}/wp-json/wp/v2/posts?per_page=1&_fields=id"
    try:
        resp = await fetcher.get(url)
        if resp.status_code != 200 or not isinstance(resp.json(), list):
            return False
    except (httpx.HTTPError, ValueError):
        return False
    source.wp_categories = await fetch_wp_categories(fetcher, source.base_url)
    return True


async def fetch_wp_categories(fetcher: Fetcher, base_url: str) -> dict:
    cats: dict[str, str] = {}
    try:
        resp = await fetcher.get(f"{base_url}/wp-json/wp/v2/categories?per_page=100&_fields=id,name")
        if resp.status_code == 200:
            cats = {str(c["id"]): c["name"] for c in resp.json()}
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        pass
    return cats


async def _try_feed(fetcher: Fetcher, source: Source, homepage: bytes | None) -> bool:
    candidates: list[str] = []
    if source.feed_url:
        candidates.append(source.feed_url)
    if homepage:
        doc = lxml.html.fromstring(homepage)
        for href in doc.xpath(
            '//link[@rel="alternate"][contains(@type,"rss") or contains(@type,"atom")]/@href'
        ):
            candidates.append(urljoin(source.base_url + "/", href))
    candidates.append(f"{source.base_url}/feed/")
    for url in dict.fromkeys(candidates):
        try:
            resp = await fetcher.get(url)
        except httpx.HTTPError:
            continue
        if resp.status_code == 200 and feedparser.parse(resp.content).entries:
            source.feed_url = url
            return True
    return False


class ListPages(BaseModel):
    haber: str | None = None
    duyuru: str | None = None
    etkinlik: str | None = None


async def _find_list_pages_with_llm(source: Source, homepage: bytes) -> dict:
    doc = lxml.html.fromstring(homepage)
    doc.make_links_absolute(source.base_url + "/")
    host = urlsplit(source.base_url).hostname
    links = []
    for a in doc.xpath("//a[@href]"):
        href = a.get("href").split("#")[0]
        text = " ".join(a.text_content().split())[:80]
        if text and urlsplit(href).hostname == host:
            links.append(f"{text} -> {href}")
    if not links:
        return {}
    user = "Site: " + source.base_url + "\nLinkler:\n" + "\n".join(list(dict.fromkeys(links))[:200])
    result = (await chat_json(
        "Bir üniversite biriminin web sitesindeki linkleri inceliyorsun. Tüm haberlerin, tüm duyuruların ve "
        "tüm etkinliklerin listelendiği sayfaların URL'lerini seç. Tek bir haberin detay sayfasını seçme. "
        "Emin değilsen null yaz. Sadece verilen listedeki URL'leri kullan.",
        user,
        ListPages,
        retries=0,
    )).value
    allowed = {line.rsplit(" -> ", 1)[1] for line in links}
    return {k: v for k, v in result.model_dump().items() if v and v in allowed}


async def discover_source(fetcher: Fetcher, source: Source, recon: dict | None = None) -> None:
    source.notes = []
    source.last_error = None
    if source.js_render_required:
        source.adapter = "none"
        source.discovered_at = utcnow()
        source.notes.append("Haritada JS render gerekli; tarayıcı adaptörü bekleniyor")
        return
    source.base_url = await _resolve_base_url(fetcher, source.host)
    source.discovered_at = utcnow()
    if not source.base_url:
        source.adapter = "none"
        source.last_error = "Siteye bağlanılamadı"
        return

    await _read_robots(fetcher, source)
    if source.robots_disallow_all and settings.robots_policy == "respect":
        source.adapter = "none"
        source.notes.append("robots.txt tüm siteyi yasaklıyor (ROBOTS_POLICY=respect)")
        return

    if await _try_wp_rest(fetcher, source):
        source.adapter = "wp_rest"
        return

    homepage = None
    try:
        resp = await fetcher.get(source.base_url + "/")
        if resp.status_code == 200 and "html" in resp.headers.get("content-type", ""):
            homepage = resp.content
    except httpx.HTTPError:
        pass

    if await _try_feed(fetcher, source, homepage):
        source.adapter = "rss"
        return

    if homepage and (b"<app-root" in homepage or b"ng-version" in homepage):
        if is_ubys_cms(urlsplit(source.base_url).hostname):
            source.adapter = "ubys_cms"
            source.notes.append("Angular ana site: tarayıcı (Playwright) ile okunuyor")
            return
        source.adapter = "none"
        source.notes.append("Angular/JS ile yüklenen site: tarayıcı (Playwright) adaptörü gerekli")
        return

    list_urls = {v: recon[k] for k, v in RECON_LIST_KEYS.items() if recon and recon.get(k)}
    list_urls.update(source.list_urls or {})
    if not list_urls and homepage and not (source.list_rules or {}).get("_list_page_llm"):
        source.list_rules = {**(source.list_rules or {}), "_list_page_llm": {"llm_attempted": True}}
        try:
            list_urls = await _find_list_pages_with_llm(source, homepage)
            if list_urls:
                source.notes.append("Liste sayfaları LLM ile bulundu")
        except LLMError as exc:
            source.notes.append(f"LLM ile liste bulunamadı: {exc}")
    source.list_urls = list_urls
    source.adapter = "list" if list_urls else "none"
    if list_urls:
        await learn_list_rules(fetcher, source)
    if not list_urls:
        source.notes.append("Uygun tarama yöntemi bulunamadı (JS ile yüklenen site olabilir)")


async def discover_all(hosts: list[str] | None = None, recon_by_host: dict | None = None) -> None:
    fetcher = Fetcher()
    try:
        with Session() as session:
            query = select(Source).where(Source.active)
            if hosts:
                query = select(Source).where(Source.host.in_(hosts))
            sources = session.scalars(query).all()

            async def run(src: Source) -> None:
                try:
                    await discover_source(fetcher, src, (recon_by_host or {}).get(src.host))
                except Exception as exc:  # tek bir site tüm keşfi durdurmasın
                    log.exception("keşif hatası: %s", src.host)
                    src.adapter, src.last_error = "none", f"{type(exc).__name__}: {exc}"
                reason = f"  ({src.last_error or (src.notes or [''])[-1]})" if src.adapter == "none" else ""
                log.info("%-40s -> %s%s", src.host, src.adapter, reason[:120])
                session.commit()  # site bitince kaydet: uzun keşif yarıda kesilirse emek kaybolmasın

            await asyncio.gather(*(run(s) for s in sources))

            # aynı adrese yönlenen takma adları pasifleştir; adresin asıl sahibi olan host kalsın
            def owner_first(s: Source) -> tuple:
                final_host = urlsplit(s.base_url).hostname
                return (final_host.removeprefix("www."), s.host != final_host, s.host.startswith("www."), s.host)

            seen: dict[str, Source] = {}
            for src in sorted((s for s in sources if s.base_url), key=owner_first):
                key = urlsplit(src.base_url).hostname.removeprefix("www.")
                if key in seen:
                    src.active = False
                    src.notes = [*src.notes, f"{seen[key].host} ile aynı siteye yönleniyor, pasif"]
                else:
                    src.active = True
                    seen[key] = src
            session.commit()
    finally:
        await fetcher.aclose()
