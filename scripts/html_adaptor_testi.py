"""Haritalardan dengeli HTML kaynak örneğinde keşif ve sınırlı tarama ölçümü."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from katki.config import ROOT
from katki.crawl import crawl_all
from katki.db import Session, Source, init_db
from katki.discover import discover_all

MAPS = ("uni-devlet", "uni-vakif", "stk")


def select_hosts(n: int) -> list[tuple[str, str]]:
    chosen = []
    seen = set()
    with Session() as session:
        sources = {s.host: s for s in session.scalars(select(Source).where(Source.active))}
        for index, folder in enumerate(MAPS):
            target = n // len(MAPS) + (index < n % len(MAPS))
            found = 0
            path = ROOT / "research" / folder / "harita.json"
            for org in json.loads(path.read_text(encoding="utf-8")):
                if not org.get("canli"):
                    continue
                for item in org.get("kaynaklar") or []:
                    host = (item.get("host") or "").lower().rstrip(".")
                    src = sources.get(host)
                    if (host in seen or not src or not src.list_urls or src.js_render_required or
                            src.adapter not in (None, "list") or
                            not (item.get("haber_url") or item.get("duyuru_url")) or
                            item.get("wp_rest") is True or item.get("rss_url")):
                        continue
                    chosen.append((folder, host))
                    seen.add(host)
                    found += 1
                    if found == target:
                        break
                if found == target:
                    break
            if found < target:
                raise RuntimeError(f"{folder}: {target} HTML kaynak isteniyor, yalnız {found} uygun kaynak bulundu")
    return chosen


async def measure(n: int, limit: int, report_only: bool = False) -> None:
    checked = set()
    while True:
        chosen = select_hosts(n)
        hosts = [host for _, host in chosen]
        if report_only:
            break
        pending = [host for host in hosts if host not in checked]
        if not pending:
            break
        await discover_all(pending)
        checked.update(pending)
    with Session() as session:
        adapters = {s.host: s.adapter for s in session.scalars(select(Source).where(Source.host.in_(hosts)))}
    if any(adapters[host] != "list" for host in hosts):
        raise RuntimeError("30 kaynak içinde HTML liste adaptörü olmayan kaynak kaldı")
    if not report_only:
        await crawl_all(hosts, limit=limit, recheck_known=True)
    total_extracted = total_dated = llm_sources = successes = 0
    print("harita | host | adaptör | link | kayıt | tarih % | ort. metin | LLM | hata")
    with Session() as session:
        sources = {s.host: s for s in session.scalars(select(Source).where(Source.host.in_(hosts)))}
        for folder, host in chosen:
            src = sources[host]
            rules = list((src.list_rules or {}).values())
            links = sum(r.get("last_link_count", 0) for r in rules)
            extracted = sum(r.get("last_extracted_count", 0) for r in rules)
            dated = sum(r.get("last_dated_count", 0) for r in rules)
            chars = sum(r.get("last_text_chars", 0) for r in rules)
            llm = any(r.get("llm_attempted") for r in rules)
            total_extracted += extracted
            total_dated += dated
            llm_sources += llm
            successes += extracted > 0
            print(f"{folder} | {host} | {src.adapter} | {links} | {extracted} | "
                  f"{100 * dated / extracted:.0f} | {chars / extracted:.0f} | "
                  f"{'evet' if llm else 'hayır'} | {(src.last_error or '')[:80]}" if extracted else
                  f"{folder} | {host} | {src.adapter} | {links} | 0 | 0 | 0 | "
                  f"{'evet' if llm else 'hayır'} | {(src.last_error or '')[:80]}")
    print(f"GENEL | {successes}/{len(chosen)} başarılı (%{100 * successes / len(chosen):.1f}) | "
          f"{total_extracted} kayıt | tarihli %{100 * total_dated / total_extracted if total_extracted else 0:.1f} | "
          f"LLM {llm_sources} kaynak")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=30, help="Üç haritaya dengeli dağıtılacak kaynak sayısı")
    parser.add_argument("--limit", type=int, default=5, help="Kaynak başına azami detay kaydı")
    parser.add_argument("--report-only", action="store_true", help="Son taramanın saklanan ölçümlerini yazdır")
    args = parser.parse_args()
    if args.n < 3 or args.limit < 1:
        parser.error("--n en az 3, --limit en az 1 olmalı")
    init_db()
    asyncio.run(measure(args.n, args.limit, args.report_only))


if __name__ == "__main__":
    main()
