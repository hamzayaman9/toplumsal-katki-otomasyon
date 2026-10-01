"""Kaynakları tarar ve yeni haberleri veritabanına yazar."""

import asyncio
import hashlib
import html
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

import feedparser
import httpx
import lxml.html
import trafilatura
from sqlalchemy import select

from .db import Article, CrawlRun, Session, Source, utcnow
from .discover import fetch_wp_categories
from .events import EventFn, noop
from .http import Fetcher
from .list_rules import collect_links, links_for_rule

log = logging.getLogger(__name__)

TRACKING_PARAMS = re.compile(r"^(utm_|fbclid|gclid)")
MONTHS = {name: i for i, name in enumerate(
    ("ocak", "şubat", "mart", "nisan", "mayıs", "haziran", "temmuz", "ağustos",
     "eylül", "ekim", "kasım", "aralık"), 1)}
GENERIC_TITLES = {"haberler", "haber", "duyurular", "duyuru", "etkinlikler", "etkinlik",
                  "bağlantı gezgini", "main navigation"}
TITLE_STOP = {"yili", "yil", "haber", "duyuru", "etkinlik", "bayrami", "tarih", "sayili"}


@dataclass
class Item:
    url: str
    title: str
    text: str
    published_at: datetime | None
    categories: list[str] = field(default_factory=list)
    external_id: str | None = None


def canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query) if not TRACKING_PARAMS.match(k)])
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", query, ""))


def html_to_text(fragment: str) -> str:
    if not fragment or not fragment.strip():
        return ""
    doc = lxml.html.fromstring(fragment)
    for bad in doc.xpath("//script|//style"):
        bad.drop_tree()
    for br in doc.xpath("//br|//p|//li|//h1|//h2|//h3|//h4|//div"):
        br.tail = "\n" + (br.tail or "")
    text = doc.text_content()
    return re.sub(r"\n\s*\n+", "\n\n", re.sub(r"[ \t\xa0]+", " ", text)).strip()


def content_hash(title: str, text: str) -> str:
    norm = re.sub(r"\W+", " ", f"{title} {text[:3000]}".lower()).strip()
    return hashlib.sha256(norm.encode()).hexdigest()


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    value = value.strip()
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        numeric = re.search(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b", value)
        turkish = re.search(r"\b(\d{1,2})\s+(" + "|".join(MONTHS) + r")\s+(\d{4})\b", value, re.I)
        try:
            if numeric:
                dt = datetime(int(numeric[3]), int(numeric[2]), int(numeric[1]))
            elif turkish:
                dt = datetime(int(turkish[3]), MONTHS[turkish[2].lower()], int(turkish[1]))
            else:
                return None
        except ValueError:
            return None
    dt = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    # metindeki tarih benzeri ifadeler (ör. "26.08.1071") ve ileri tarihli etkinlik günleri
    # (ör. "3 Ekim 2026 sempozyumu") yayın tarihi sanılmasın; saat dilimi payı 2 gün
    if not (datetime(2000, 1, 1, tzinfo=timezone.utc) <= dt <= datetime.now(timezone.utc) + timedelta(days=2)):
        return None
    return dt


def _detail_date(page_html: str) -> datetime | None:
    doc = lxml.html.fromstring(page_html)
    values = doc.xpath(
        "//meta[@property='article:published_time' or @name='article:published_time' "
        "or @name='date' or @name='pubdate']/@content | //time/@datetime | //time/text()"
    )
    values += [" ".join(node.text_content().split()) for node in doc.xpath(
        "//*[contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'date') "
        "or contains(@class,'tarih') or contains(@class,'Tarih') or @id='date' or @id='tarih']"
    )[:8]]
    return next((date for value in values if (date := _parse_dt(value))), None)


def normalize_title(title: str) -> str:
    title = unicodedata.normalize("NFKC", html.unescape(title)).casefold().replace("ı", "i")
    title = "".join(c for c in unicodedata.normalize("NFKD", title) if not unicodedata.combining(c))
    return re.sub(r"\W+", " ", title, flags=re.U).strip()


def _body_matches_title(title: str, body: str) -> bool:
    words = {word[:5] for word in normalize_title(title).split()
             if len(word) >= 4 and not word.isdigit() and word not in TITLE_STOP}
    text = normalize_title(body)
    return bool(words) and any(word in text for word in words)


# --- adaptörler -------------------------------------------------------------


async def crawl_wp_rest(fetcher: Fetcher, source: Source, limit: int) -> list[Item]:
    url = (
        f"{source.base_url}/wp-json/wp/v2/posts?per_page={limit}"
        "&_fields=id,date_gmt,link,title,content,excerpt,categories"
    )
    resp = await fetcher.get(url)
    resp.raise_for_status()
    posts = resp.json()

    known = source.wp_categories or {}
    if any(str(c) not in known for p in posts for c in p.get("categories", [])):
        source.wp_categories = known = await fetch_wp_categories(fetcher, source.base_url)

    items = []
    for p in posts:
        text = html_to_text(p.get("content", {}).get("rendered", "")) or html_to_text(
            p.get("excerpt", {}).get("rendered", "")
        )
        items.append(
            Item(
                url=p["link"],
                title=html.unescape(html_to_text(p["title"]["rendered"])),
                text=text,
                published_at=_parse_dt(p.get("date_gmt") and p["date_gmt"] + "+00:00"),
                categories=[known.get(str(c), str(c)) for c in p.get("categories", [])],
                external_id=str(p["id"]),
            )
        )
    return items


async def crawl_rss(fetcher: Fetcher, source: Source, limit: int) -> list[Item]:
    resp = await fetcher.get(source.feed_url)
    resp.raise_for_status()
    feed = feedparser.parse(resp.content)
    items = []
    for e in feed.entries[:limit]:
        body = e.get("content", [{}])[0].get("value") or e.get("summary", "")
        published = e.get("published_parsed") or e.get("updated_parsed")
        items.append(
            Item(
                url=e.get("link", ""),
                title=html.unescape(e.get("title", "")).strip(),
                text=html_to_text(body),
                published_at=datetime(*published[:6], tzinfo=timezone.utc) if published else None,
                categories=[t.get("term") for t in e.get("tags", []) if t.get("term")],
                external_id=e.get("id"),
            )
        )
    return [i for i in items if i.url]


async def crawl_list(fetcher: Fetcher, source: Source, limit: int, known_urls: set[str]) -> list[Item]:
    items = []
    rules = {url: {**rule, "last_link_count": 0, "last_extracted_count": 0,
                   "last_dated_count": 0, "last_text_chars": 0}
             for url, rule in (source.list_rules or {}).items()}
    for label, list_url in (source.list_urls or {}).items():
        if len(items) >= limit:
            break
        rule = rules.get(list_url) or {}
        rules.setdefault(list_url, {**rule, "last_link_count": 0, "last_extracted_count": 0,
                                    "last_dated_count": 0, "last_text_chars": 0})
        if not rule.get("link_regex"):
            continue
        resp = await fetcher.get(list_url)
        resp.raise_for_status()
        candidates = collect_links(resp.content, str(resp.url))
        links = links_for_rule(candidates, rule)
        link_text = {x["url"]: x["text"] for x in candidates}
        rules[list_url]["last_link_count"] = len(links)
        for url in links:
            if len(items) >= limit:
                break
            if url in known_urls:
                continue
            try:
                detail = await fetcher.get(url)
            except httpx.HTTPError:
                continue
            if detail.status_code != 200:
                continue
            data = trafilatura.bare_extraction(detail.text, url=url, with_metadata=True, as_dict=True) or {}
            doc = lxml.html.fromstring(detail.text)
            body = (data.get("text") or "").strip()
            content_nodes = doc.xpath(
                "//*[contains(concat(' ',normalize-space(@class),' '),' contentText ')]"
            )
            if content_nodes:
                body = max((html_to_text(lxml.html.tostring(node, encoding="unicode"))
                            for node in content_nodes), key=len)
            if len(body) < 100:
                continue
            title = (data.get("title") or "").strip()
            h1 = " ".join(doc.xpath("string(//h1[1])").split())
            h2 = " ".join(doc.xpath("string(//h2[1])").split())
            generic = (not title or normalize_title(title) in {normalize_title(x) for x in GENERIC_TITLES}
                       or normalize_title(title) == normalize_title(source.org))
            if generic and len(h1) >= 20 and normalize_title(h1) not in {
                    normalize_title(x) for x in GENERIC_TITLES}:
                title = h1
            elif generic and len(h2) >= 20 and normalize_title(h2) not in {
                    normalize_title(x) for x in GENERIC_TITLES}:
                title = h2
            elif generic and len(link_text.get(url, "")) >= 20:
                title = link_text[url]
            headline = re.sub(r"^\s*\d{1,2}[./]\d{1,2}[./]\d{4}\s*", "", link_text.get(url, ""))
            if len(headline) >= 15 and normalize_title(headline) in normalize_title(title):
                title = headline
            if not title or normalize_title(title) in {normalize_title(x) for x in GENERIC_TITLES}:
                continue
            if not _body_matches_title(title, body):
                continue
            explicit_date = _detail_date(detail.text)
            card_date = _parse_dt(link_text.get(url))
            # trafilatura sayfada yalnızca yıl bulursa (ör. "© 2026") 1 Ocak döndürür: tarih yok say
            guessed = None if content_nodes or str(data.get("date") or "")[5:10] == "01-01" else _parse_dt(data.get("date"))
            published = explicit_date or card_date or guessed
            years = [int(x) for x in re.findall(r"\b20\d{2}\b", title)]
            if published and not explicit_date and years and all(abs(published.year - year) > 1 for year in years):
                published = None
            items.append(
                Item(
                    url=url,
                    title=title,
                    text=body,
                    published_at=published,
                    categories=[label],
                )
            )
            rules[list_url]["last_extracted_count"] += 1
            rules[list_url]["last_dated_count"] += bool(items[-1].published_at)
            rules[list_url]["last_text_chars"] += len(body)
    source.list_rules = rules
    return items


# --- ana akış ---------------------------------------------------------------


async def crawl_source(fetcher: Fetcher, source: Source, limit: int, known_urls: set[str]) -> list[Item]:
    if source.adapter == "wp_rest":
        return await crawl_wp_rest(fetcher, source, limit)
    if source.adapter == "rss":
        return await crawl_rss(fetcher, source, limit)
    if source.adapter == "list":
        return await crawl_list(fetcher, source, limit, known_urls)
    if source.adapter == "ubys_cms":
        from .browser import crawl_ubys_cms

        return await crawl_ubys_cms(source, limit, known_urls)
    return []


async def crawl_all(hosts: list[str] | None = None, limit: int = 20, on_event: EventFn = noop,
                    recheck_known: bool = False) -> CrawlRun:
    fetcher = Fetcher()
    try:
        with Session() as session:
            run = CrawlRun()
            session.add(run)
            query = select(Source).where(Source.active, Source.adapter.in_(["wp_rest", "rss", "list", "ubys_cms"]))
            if hosts:
                query = query.where(Source.host.in_(hosts))
            sources = session.scalars(query).all()
            for src in sources:
                fetcher.set_host_delay(urlsplit(src.base_url).hostname, src.crawl_delay)

            known_urls = set(session.scalars(select(Article.url)))
            known_hashes = set(session.scalars(select(Article.content_hash)))
            recent_titles: dict[str, set[str]] = {}
            for org, title in session.execute(
                select(Source.org, Article.title).join(Article, Article.source_id == Source.id)
                .where(Article.first_seen_at >= utcnow() - timedelta(days=60))
            ):
                recent_titles.setdefault(org, set()).add(normalize_title(title))
            on_event(
                "tarama_basladi",
                kaynaklar=[{"id": s.id, "ad": s.name or s.host, "host": s.host,
                            "kurum": s.org, "org_type": s.org_type, "yontem": s.adapter} for s in sources],
            )

            def store(src: Source, result: list[Item] | Exception) -> None:
                """Bir sitenin sonucunu kaydeder. await içermez: oturum tek seferde, sırayla kullanılır."""
                src.last_crawled_at = utcnow()
                if isinstance(result, Exception):
                    src.last_error = f"{type(result).__name__}: {result}"[:1000]
                    run.sources_failed += 1
                    log.warning("%-40s HATA %s", src.host, src.last_error)
                    on_event("kaynak_bitti", id=src.id, yeni=[], hata=src.last_error[:200])
                    return
                src.last_error = None
                run.sources_ok += 1
                added = []
                for item in result:
                    url = canonical_url(item.url)
                    digest = content_hash(item.title, item.text)
                    if url in known_urls or digest in known_hashes:
                        continue
                    normalized = normalize_title(item.title)
                    org_titles = recent_titles.setdefault(src.org, set())
                    if normalized and normalized in org_titles:
                        continue
                    known_urls.add(url)
                    known_hashes.add(digest)
                    if normalized:
                        org_titles.add(normalized)
                    article = Article(
                        source_id=src.id,
                        url=url,
                        external_id=item.external_id,
                        title=item.title.replace("\x00", ""),  # Postgres metinde NUL kabul etmez
                        published_at=item.published_at,
                        text=item.text.replace("\x00", ""),
                        categories=item.categories,
                        content_hash=digest,
                        via=src.adapter,
                    )
                    session.add(article)
                    added.append(article)
                run.new_articles += len(added)
                session.commit()  # site bitince kaydet: uzun tarama yarıda kesilirse emek kaybolmasın
                if added:
                    log.info("%-40s +%d yeni", src.host, len(added))
                on_event("kaynak_bitti", id=src.id, yeni=[{"id": a.id, "baslik": a.title} for a in added])

            async def run_one(src: Source) -> None:
                on_event("kaynak_basladi", id=src.id)
                try:
                    known = set() if recheck_known and src.adapter == "list" else known_urls
                    result: list[Item] | Exception = await crawl_source(fetcher, src, limit, known)
                except Exception as exc:
                    result = exc
                store(src, result)  # site biter bitmez kaydet: canlı izleme sayfası anında görsün

            await asyncio.gather(*(run_one(s) for s in sources))

            run.finished_at = utcnow()
            session.commit()
            on_event(
                "tarama_bitti", basarili=run.sources_ok, hatali=run.sources_failed, yeni=run.new_articles
            )
            return run
    finally:
        await fetcher.aclose()
