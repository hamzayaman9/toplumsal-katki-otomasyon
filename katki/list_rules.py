"""HTML liste sayfasında haber bağlantılarını tanıyan kalıcı kurallar."""

import re
from collections import Counter, defaultdict
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import lxml.html
from pydantic import BaseModel, Field

from .llm import LLMError, chat_json


def canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query) if not re.match(r"^(utm_|fbclid|gclid)", k)])
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", query, ""))

SKIP_PATH = re.compile(
    r"/(?:category|kategori|tag|etiket|page|sayfa|feed|wp-|author|iletisim|hakkinda|"
    r"about|contact|login|arama|search|arsiv|archive)(?:/|$)", re.I
)
SKIP_EXT = re.compile(r"\.(?:pdf|jpg|jpeg|png|webp|gif|docx?|xlsx?|zip|mp4)$", re.I)
NOISE = ("//header|//nav|//footer|//aside|"
         "//*[contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'menu')]")


class RuleProposal(BaseModel):
    liste_url: str
    link_regex: str
    css: str | None = None
    ornek: list[str] = Field(default_factory=list)


class RuleProposals(BaseModel):
    kurallar: list[RuleProposal] = Field(default_factory=list)


def _selector(a) -> str | None:
    for parent in list(a.iterancestors())[:4]:
        if parent.tag not in ("article", "li", "div", "section"):
            continue
        tokens = [c for c in (parent.get("class") or "").split() if re.fullmatch(r"[\w-]+", c)]
        useful = next((c for c in tokens if re.search(r"haber|news|duyuru|event|etkinlik|post|card|item|list", c, re.I)), None)
        if useful:
            return f"{parent.tag}.{useful} a"
        if parent.tag == "article":
            return "article a"
    return None


def collect_links(page_html: bytes, page_url: str) -> list[dict[str, str]]:
    doc = lxml.html.fromstring(page_html)
    doc.make_links_absolute(page_url)
    for node in doc.xpath(NOISE):
        node.drop_tree()
    host = urlsplit(page_url).hostname
    found = {}
    for a in doc.xpath("//a[@href]"):
        url = canonical_url(a.get("href"))
        parts = urlsplit(url)
        title = " ".join(a.text_content().split())
        if not title:
            title = " ".join((a.get("title") or a.xpath("string(.//img/@alt)") or "").split())
        if (parts.scheme not in ("http", "https") or parts.hostname != host or
                url == canonical_url(page_url) or SKIP_PATH.search(parts.path) or
                SKIP_EXT.search(parts.path) or ".pdf" in parts.query.lower() or len(title) < 12):
            continue
        if url not in found:
            found[url] = {"url": url, "text": title[:160], "css": _selector(a) or ""}
    return list(found.values())


def _path_pattern(url: str) -> tuple[str, str]:
    parts = urlsplit(url)
    path = parts.path.rstrip("/") or "/"
    parent, _, leaf = path.rpartition("/")
    if not leaf or leaf.lower() in ("haber", "haberler", "duyuru", "duyurular", "etkinlikler"):
        return "", ""
    if parts.query:
        keys = tuple(sorted(k.split("=", 1)[0] for k in parts.query.split("&")))
        ids = [k for k in keys if k.lower().endswith("id") or k.lower() == "p"]
        if ids:
            key = ids[0]
            return f"query:{path}:{key.lower()}", rf"^{re.escape(path)}\?[^#]*\b{re.escape(key)}=\d+(?:&|$)"
    if parent in ("", "/"):
        return "root", r"^/[^/?#]+/?$"
    normalized = re.sub(r"\d+", "#", parent)
    escaped = re.sub(r"\d+", r"\\d+", re.escape(parent))
    return f"path:{normalized}", rf"^{escaped}/[^/?#]+/?$"


def deterministic_rule(links: list[dict[str, str]]) -> dict | None:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    patterns = {}
    for link in links:
        key, pattern = _path_pattern(link["url"])
        if key:
            groups[key].append(link)
            patterns[key] = pattern
    for key, group in sorted(groups.items(), key=lambda kv: len(kv[1]), reverse=True):
        if len(group) < 3:
            continue
        css, css_count = Counter(x["css"] for x in group if x["css"]).most_common(1)[0] if any(x["css"] for x in group) else ("", 0)
        # Kök yol kalıbı tek başına menü bağlantılarını ayıramaz.
        if css_count < 3 and not re.search(r"haber|news|duyuru|etkinlik|event|blog|post", key, re.I):
            continue
        selected = [x for x in group if not css or x["css"] == css]
        if len(selected) < 3:
            continue
        return {"link_regex": patterns[key], "css": css or None,
                "ornek": [x["url"] for x in selected[:5]], "method": "deterministic", "version": 2}
    return None


def _css_match(link: dict[str, str], css: str | None) -> bool:
    return not css or link["css"] == css


def links_for_rule(links: list[dict[str, str]], rule: dict) -> list[str]:
    pattern = rule.get("link_regex")
    if not pattern or len(pattern) > 300:
        return []
    try:
        regex = re.compile(pattern, re.I)
    except re.error:
        return []
    css = rule.get("css")
    if not css and rule.get("ornek"):
        examples = {canonical_url(x) for x in rule["ornek"]}
        contexts = {x["css"] for x in links if x["url"] in examples and x["css"]}
        if len(contexts) == 1:
            css = contexts.pop()
    return [link["url"] for link in links if _css_match(link, css) and
            (regex.search(urlsplit(link["url"]).path) or regex.search(
                urlsplit(link["url"]).path + "?" + urlsplit(link["url"]).query))]


async def learn_list_rules(fetcher, source) -> None:
    """Her liste URL'sini bir kez inceler; LLM bütün belirsiz sayfalar için tek çağrılır."""
    rules = dict(source.list_rules or {})
    pending = [(label, url) for label, url in (source.list_urls or {}).items()
               if url not in rules or rules[url].get("error") or
               (rules[url].get("method") == "deterministic" and rules[url].get("version") != 2)]
    if not pending:
        return
    uncertain = []
    for _, url in pending:
        try:
            resp = await fetcher.get(url)
            resp.raise_for_status()
            links = collect_links(resp.content, str(resp.url))
        except Exception as exc:
            rules[url] = {"link_regex": "", "css": None, "ornek": [], "error": str(exc)[:150], "version": 2}
            continue
        rule = deterministic_rule(links)
        if rule:
            rules[url] = rule
        else:
            uncertain.append((url, links))
    uncertain = [(url, links) for url, links in uncertain if links]
    if uncertain and not any(r.get("llm_attempted") for r in rules.values()):
        prompt = "\n".join(
            f"Liste: {url}\n" + "\n".join(f"{x['text']} -> {x['url']}" for x in links[:200])
            for url, links in uncertain
        )
        try:
            proposals = (await chat_json(
                "Türkçe kurum haber liste sayfalarındaki gerçek haber detay linklerini ayır. "
                "Her liste için yalnız verilen linklerden örnek ver. link_regex URL'nin yol ve sorgusuna "
                "uygulanan dar bir Python regex olsun. Kategori, menü, liste, arşiv ve sayfalama "
                "linklerini dışla. Emin değilsen o listeye kural üretme. css alanını boş bırakabilirsin.",
                prompt, RuleProposals, retries=0,
            )).value.kurallar
        except LLMError as exc:
            source.notes = [*(source.notes or []), f"Liste kuralı LLM hatası: {exc}"]
            proposals = []
        for url, links in uncertain:
            rule = {"link_regex": "", "css": None, "ornek": [], "method": "llm", "llm_attempted": True, "version": 2}
            proposal = next((p for p in proposals if p.liste_url == url), None)
            if proposal and len(proposal.link_regex) <= 300 and len(proposal.ornek) >= 2:
                css = proposal.css if proposal.css in {x["css"] for x in links} else None
                candidate = {"link_regex": proposal.link_regex, "css": css,
                             "ornek": proposal.ornek[:5], "method": "llm", "llm_attempted": True, "version": 2}
                matched = links_for_rule(links, candidate)
                if len(matched) >= 2 and all(canonical_url(x) in matched for x in proposal.ornek[:5]):
                    rule = candidate
            rules[url] = rule
    for url, _ in uncertain:
        rules.setdefault(url, {"link_regex": "", "css": None, "ornek": [], "llm_attempted": True, "version": 2})
    source.list_rules = rules
