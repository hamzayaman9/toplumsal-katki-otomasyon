"""JS ile yüklenen siteler için tarayıcı (Playwright) adaptörü.

www.ankara.edu.tr Angular ile çalışır; içerik sayfa açıldığında tarayıcının
ubys.ankara.edu.tr/api/CMS/... isteklerinden gelir. Burada sayfayı normal bir
ziyaretçi gibi açıp tarayıcının aldığı JSON yanıtlarını okuruz. API'ye ayrıca
istek atılmaz, kimlik bilgisi kullanılmaz.
"""

import asyncio
import logging
import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from .db import Source

log = logging.getLogger(__name__)

TR = ZoneInfo("Europe/Istanbul")
NAV_INTERVAL = 2.2  # üst düzey sayfa ziyaretleri arası en az süre (sn)
LIST_LINK = ".post-title a.site-text-secondry"
DETAIL_BODY = ".wt-post-info .wt-post-text"

# kategori yolu -> (tarayıcının çağırdığı API adı, kayıt etiketi)
UBYS_CATEGORIES = {
    "haberler": ("GetMainNews", "haber"),
    "duyurular": ("GetMainNotices", "duyuru"),
    "etkinlikler": ("GetMainevents", "etkinlik"),
}
UBYS_CMS_HOSTS = {"www.ankara.edu.tr"}


def _norm(text: str) -> str:
    return re.sub(r"\W+", " ", (text or "").lower()).strip()


def _parse_publish_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=TR)).astimezone(timezone.utc)


async def crawl_ubys_cms(source: Source, limit: int, known_urls: set[str]):
    from playwright.async_api import async_playwright  # isteğe bağlı bağımlılık

    from .crawl import Item, canonical_url, html_to_text

    base = source.base_url.rstrip("/")
    items: list[Item] = []
    last_nav = 0.0

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page(user_agent=None, locale="tr-TR")

        async def visit(path: str, selector: str) -> None:
            nonlocal last_nav
            wait = last_nav + NAV_INTERVAL - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            last_nav = time.monotonic()
            await page.goto(base + path, wait_until="domcontentloaded", timeout=45000)
            await page.locator(selector).first.wait_for(state="visible", timeout=30000)

        try:
            for category, (api_name, label) in UBYS_CATEGORIES.items():
                async with page.expect_response(
                    lambda r: f"/api/CMS/{api_name}?" in r.url and r.status == 200, timeout=45000
                ) as resp_info:
                    await visit(f"/kategori/{category}/1", LIST_LINK)
                data = await (await resp_info.value).json()

                # API öğesinin sayfa adresini DOM'daki kart linklerinden başlığa göre eşleştir
                links = await page.locator(LIST_LINK).evaluate_all(
                    "as => as.map(a => [a.innerText, a.getAttribute('href')])"
                )
                url_by_title = {_norm(t): urljoin(base + "/", h.strip()) for t, h in links if t and h}

                for entry in (data.get("items") or [])[:limit]:
                    title = (entry.get("baslik") or "").strip()
                    url = url_by_title.get(_norm(title))
                    if not url:
                        log.debug("ubys: başlık DOM'da eşleşmedi: %s", title)
                        continue
                    url = canonical_url(url)
                    if url in known_urls:
                        continue
                    text = html_to_text(entry.get("icerik") or "")
                    if len(text) < 300:  # listede özet gelmişse detayı aç
                        await visit(url.removeprefix(base), DETAIL_BODY)
                        text = (await page.locator(DETAIL_BODY).first.inner_text()).strip() or text
                    items.append(
                        Item(
                            url=url,
                            title=title,
                            text=text,
                            published_at=_parse_publish_date(entry.get("publishDate")),
                            categories=[label],
                        )
                    )
        finally:
            await browser.close()
    return items


def is_ubys_cms(host: str) -> bool:
    return host in UBYS_CMS_HOSTS
