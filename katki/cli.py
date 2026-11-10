"""Komut satırı: python -m katki <komut>"""

import argparse
import asyncio
import csv
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import func, select

from .classify import classify_pending
from .config import ROOT, settings
from .crawl import crawl_all
from .db import Article, Classification, Session, Source, backup_db, init_db
from .discover import discover_all
from .events import Forwarder

RECON_FILE = ROOT / "config" / "kaynaklar_ankara.json"


def load_recon() -> dict:
    return {r["host"]: r for r in json.loads(RECON_FILE.read_text(encoding="utf-8"))}


def cmd_seed(args) -> None:
    init_db()
    recon = load_recon()
    added = 0
    with Session() as session:
        existing = set(session.scalars(select(Source.host)))
        for host, r in recon.items():
            if host in existing:
                continue
            session.add(
                Source(
                    host=host,
                    name=r.get("ad"),
                    org_type="devlet_universitesi",
                    city="Ankara",
                    kind=r.get("tur"),
                    cms=r.get("cms"),
                    active=bool(r.get("canli")),
                    feed_url=r.get("rss_url"),
                )
            )
            added += 1
        session.commit()
    print(f"{added} kaynak eklendi ({len(recon)} kayıt okundu)")


def cmd_harita_yukle(args) -> None:
    init_db()
    files = [Path(p) for p in args.dosya] if args.dosya else [
        ROOT / "research" / folder / "harita.json"
        for folder in ("uni-devlet", "uni-vakif", "stk")
    ]
    stats: dict[str, dict[str, int]] = {}
    with Session() as session:
        existing = set(session.scalars(select(Source.host)))
        for path in files:
            for org in json.loads(path.read_text(encoding="utf-8")):
                org_type = org.get("kurum_turu") or "belirsiz"
                counts = stats.setdefault(org_type, {"eklendi": 0, "atlandi": 0})
                for item in org.get("kaynaklar") or []:
                    host = (item.get("host") or "").strip().lower().rstrip(".")
                    if "://" in host:
                        host = urlsplit(host).hostname or ""
                    if (not host or host == "ankara.edu.tr" or host.endswith(".ankara.edu.tr")
                            or (args.sadece_kolay and not (item.get("wp_rest") is True or item.get("rss_url")))):
                        counts["atlandi"] += 1
                        continue
                    if host in existing:
                        counts["atlandi"] += 1
                        continue
                    urls = {label: item[key] for key, label in (
                        ("haber_url", "haber"), ("duyuru_url", "duyuru"), ("etkinlik_url", "etkinlik")
                    ) if item.get(key)}
                    session.add(Source(
                        host=host,
                        name=item.get("birim") or org.get("kisa_ad") or org["kurum"],
                        org=org["kurum"],
                        org_type=org_type,
                        city=org.get("il"),
                        focus=bool(item.get("toplumsal_katki_odakli")),
                        js_render_required=bool(item.get("js_render_gerekli")),
                        cms=item.get("cms"),
                        active=bool(org.get("canli")),
                        feed_url=item.get("rss_url"),
                        list_urls=urls,
                    ))
                    existing.add(host)
                    counts["eklendi"] += 1
        session.commit()
    for org_type, counts in sorted(stats.items()):
        print(f"{org_type}: {counts['eklendi']} eklendi, {counts['atlandi']} atlandı")
    print(f"Toplam: {sum(v['eklendi'] for v in stats.values())} eklendi, "
          f"{sum(v['atlandi'] for v in stats.values())} atlandı")


def cmd_discover(args) -> None:
    init_db()
    asyncio.run(discover_all(args.host or None, load_recon()))
    cmd_sources(args)


_forwarder: Forwarder | None = None


def _events() -> Forwarder:
    """Olayları açık paneldeki canlı sayfaya ilet (panel kapalıysa etkisiz)."""
    global _forwarder
    if _forwarder is None:
        _forwarder = Forwarder()
    return _forwarder


def _son_tarama():
    """Son tamamlanan taramanın başlangıç zamanı (yoksa None)."""
    from sqlalchemy import select

    from .db import CrawlRun, Session

    with Session() as s:
        return s.scalar(select(CrawlRun.started_at).where(CrawlRun.finished_at.is_not(None))
                        .order_by(CrawlRun.started_at.desc()).limit(1))


def cmd_crawl(args) -> None:
    init_db()
    ev = _events()
    sonra = _son_tarama() if getattr(args, "son_taramadan_sonra", False) else None
    if sonra:
        print(f"Yalnız {sonra:%Y-%m-%d %H:%M} (UTC) sonrası yayımlananlar alınacak")
    run = asyncio.run(crawl_all(args.host or None, args.limit, on_event=ev, sonra=sonra))
    print(f"Tarama: {run.sources_ok} site başarılı, {run.sources_failed} hatalı, {run.new_articles} yeni kayıt")
    ev.flush()
    return run


def cmd_classify(args) -> None:
    init_db()
    ev = _events()
    ok, failed, failed_cost = asyncio.run(classify_pending(args.limit, mixed=args.karisik, on_event=ev))
    print(f"Sınıflandırma: {ok} başarılı, {failed} hatalı (model: {settings.llm_model}, başarısız çağrı maliyeti ${failed_cost:.4f})")
    ev("is_bitti")
    ev.flush()


def cmd_konum_belirle(args) -> None:
    from .classify import konumlari_doldur

    init_db()
    ok, hata, usd = asyncio.run(konumlari_doldur(args.limit, args.paralel, rastgele=args.rastgele))
    print(f"Konum: {ok} katkı belirlendi, {hata} hatalı, maliyet ${usd:.4f}")


def cmd_rapor(args) -> None:
    from .rapor import write_report

    init_db()
    r = write_report()
    g = r["genel"]
    print(f"Rapor: {g['toplam_kayit']} kayıt, {g['toplumsal_katki']} katkı (%{g['katki_orani_yuzde']}), "
          f"{g['kaydi_olan_kurum']} kurum")
    for path in r["_dosyalar"]:
        print("  ->", path)


def cmd_yedekle(args) -> None:
    init_db()
    print("Yedek:", backup_db())


def cmd_run(args) -> None:
    init_db()
    print("Yedek:", backup_db())
    args.karisik = False
    run = cmd_crawl(args)
    args.limit = run.new_articles + 50  # yeni gelenlerin hepsini sınıflandır
    cmd_classify(args)


def cmd_sources(args) -> None:
    with Session() as session:
        rows = session.execute(
            select(Source.adapter, func.count()).where(Source.active).group_by(Source.adapter)
        ).all()
        blocked = session.scalar(select(func.count()).where(Source.active, Source.robots_disallow_all))
    print("Aktif kaynaklar, tarama yöntemine göre:")
    for adapter, n in rows:
        print(f"  {adapter or 'keşfedilmedi':12} {n}")
    print(f"  (robots.txt ile tamamen kapalı: {blocked}, ROBOTS_POLICY={settings.robots_policy})")


def cmd_stats(args) -> None:
    with Session() as session:
        total = session.scalar(select(func.count(Article.id)))
        classified = session.scalar(select(func.count(Classification.id)))
        katki = session.scalar(select(func.count()).where(Classification.is_contribution))
        by_cat = session.execute(
            select(Classification.category, func.count())
            .where(Classification.is_contribution)
            .group_by(Classification.category)
            .order_by(func.count().desc())
        ).all()
    print(f"Toplam kayıt: {total} | sınıflandırılan: {classified} | toplumsal katkı: {katki}")
    for cat, n in by_cat:
        print(f"  {n:4}  {cat}")


def cmd_export(args) -> None:
    since = datetime.now(timezone.utc) - timedelta(days=args.days)
    with Session() as session:
        q = (
            select(Article, Classification, Source)
            .join(Source)
            .outerjoin(Classification)
            .where((Article.published_at >= since) | Article.published_at.is_(None))
            .order_by(Article.published_at.desc().nulls_last())
        )
        if args.only_katki:
            q = q.where(Classification.is_contribution)
        rows = [
            {
                "tarih": a.published_at.date().isoformat() if a.published_at else "",
                "birim": s.name or s.host,
                "baslik": a.title,
                "url": a.url,
                "toplumsal_katki": None if c is None else c.is_contribution,
                "guven": None if c is None else c.confidence,
                "kategori": c.category if c else None,
                "faaliyet_turu": c.activity_type if c else None,
                "konular": (c.konular or []) if c else [],
                "sdg": c.sdgs if c else [],
                "hedef_kitle": c.beneficiaries if c else [],
                "paydaslar": c.partners if c else [],
                "ozet": c.summary if c else None,
            }
            for a, c, s in session.execute(q).all()
        ]
    out = args.out or str(ROOT / "data" / f"disa_aktarim.{args.format}")
    if args.format == "json":
        with open(out, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=1)
    else:
        with open(out, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["tarih"])
            w.writeheader()
            for r in rows:
                w.writerow({k: "; ".join(map(str, v)) if isinstance(v, list) else v for k, v in r.items()})
    print(f"{len(rows)} kayıt -> {out}")


def cmd_web(args) -> None:
    from .web import run

    run(port=args.port)


def cmd_baglanti_kur(args) -> None:
    from .baglanti import kur

    init_db()
    r = kur()
    print(f"AÜ bağlantısı: {r['dis_katki']} dış katkı, {r['au_katki']} AÜ katkısı, {r['au_birim']} AÜ birimiyle eşleştirildi")


def cmd_bulut_esitle(args) -> None:
    from .bulut import esitle

    init_db()
    esitle(tam=args.tam)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("trafilatura").setLevel(logging.ERROR)

    p = argparse.ArgumentParser(prog="katki", description="Toplumsal katkı haber tarayıcısı")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("seed", help="Keşif JSON'undan kaynakları veritabanına ekle").set_defaults(fn=cmd_seed)

    h = sub.add_parser("harita-yukle", help="Türkiye kaynak haritalarını veritabanına yükle")
    h.add_argument("--dosya", action="append", help="Yüklenecek harita JSON'u (tekrarlanabilir)")
    h.add_argument("--sadece-kolay", action="store_true", help="Yalnız WordPress REST veya RSS kaynakları")
    h.set_defaults(fn=cmd_harita_yukle)

    d = sub.add_parser("discover", help="Her kaynak için tarama yöntemini belirle")
    d.add_argument("--host", action="append")
    d.set_defaults(fn=cmd_discover)

    for name, fn, help_ in [
        ("crawl", cmd_crawl, "Kaynakları tara, yeni haberleri kaydet"),
        ("run", cmd_run, "Tara + sınıflandır (zamanlanmış görev bunu çalıştırır)"),
    ]:
        c = sub.add_parser(name, help=help_)
        c.add_argument("--host", action="append")
        c.add_argument("--limit", type=int, default=20, help="Kaynak başına en fazla kayıt / sınıflandırma sayısı")
        c.add_argument("--son-taramadan-sonra", action="store_true",
                       help="Son tamamlanan taramadan önce yayımlananları alma (tarihsizler alınır)")
        c.set_defaults(fn=fn)

    c = sub.add_parser("classify", help="Sınıflandırılmamış haberleri sınıflandır")
    c.add_argument("--limit", type=int, default=50)
    c.add_argument("--karisik", action="store_true", help="Kurum türlerinden dengeli rastgele örnek")
    c.set_defaults(fn=cmd_classify)

    k = sub.add_parser("konum-belirle", help="Konumu sorulmamış katkılara bölge/il sor (Jev)")
    k.add_argument("--limit", type=int, default=10000)
    k.add_argument("--rastgele", action="store_true", help="en yeniler yerine rastgele örnek")
    k.add_argument("--paralel", type=int, default=4, help="aynı anda kaç istek (Jev için 16-24 sorunsuz)")
    k.set_defaults(fn=cmd_konum_belirle)

    sub.add_parser("sources", help="Kaynak durumunu göster").set_defaults(fn=cmd_sources)
    sub.add_parser("rapor", help="Sayısal özet raporu (raporlar/ altına md + json, haftalık CSV'ye satır)").set_defaults(fn=cmd_rapor)
    sub.add_parser("yedekle", help="Veritabanını data/yedek/ altına yedekle (son 5 tutulur)").set_defaults(fn=cmd_yedekle)
    sub.add_parser("stats", help="Özet istatistik").set_defaults(fn=cmd_stats)

    e = sub.add_parser("export", help="Rapor için dışa aktar")
    e.add_argument("--days", type=int, default=30)
    e.add_argument("--format", choices=["csv", "json"], default="csv")
    e.add_argument("--only-katki", action="store_true")
    e.add_argument("--out")
    e.set_defaults(fn=cmd_export)

    w = sub.add_parser("web", help="Yerel paneli başlat (http://127.0.0.1:8000)")
    w.add_argument("--port", type=int, default=8000)
    w.set_defaults(fn=cmd_web)

    sub.add_parser("baglanti-kur", help="Dış katkıları AÜ faaliyetleriyle eşleştir (yerel benzerlik modeli)").set_defaults(
        fn=cmd_baglanti_kur)

    b = sub.add_parser("bulut-esitle", help="Yeni kayıtları Vercel paneli için bulut veritabanına (Neon) gönder")
    b.add_argument("--tam", action="store_true", help="yalnız yenileri değil tüm satırları gönder")
    b.set_defaults(fn=cmd_bulut_esitle)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
