"""Sayısal özet raporu: raporlar/ altına tarihli JSON + Markdown yazar, haftalık CSV'ye satır ekler."""

import csv
import json
from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from .config import ROOT
from .db import Article, Classification, CrawlRun, Session, Source

RAPOR_DIR = ROOT / "raporlar"
TUR_ADI = {
    "devlet_universitesi": "Devlet üniversitesi",
    "vakif_universitesi": "Vakıf üniversitesi",
    "vakif": "Vakıf",
    "dernek": "Dernek",
    "kamu_kurumu": "Kamu kurumu",
    "stk_diger": "Diğer STK",
}


def _pct(a: int, b: int) -> float:
    return round(100 * a / b, 1) if b else 0.0


def build_report() -> dict:
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    with Session() as s:
        rows = s.execute(select(Article, Classification, Source).join(Source).outerjoin(Classification)).all()
        sources = s.scalars(select(Source)).all()
        last_run = s.scalars(select(CrawlRun).order_by(CrawlRun.id.desc()).limit(1)).first()

    def aware(dt):
        return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    classified = [(a, c, src) for a, c, src in rows if c is not None]
    katki = [(a, c, src) for a, c, src in classified if c.is_contribution]
    new_week = [(a, c, src) for a, c, src in rows if aware(a.first_seen_at) >= week_ago]
    active = [x for x in sources if x.active]

    by_type: dict[str, dict] = {}
    for a, c, src in rows:
        t = by_type.setdefault(src.org_type or "belirsiz", {"kurum": set(), "kayit": 0, "katki": 0})
        t["kurum"].add(src.org)
        t["kayit"] += 1
        t["katki"] += bool(c and c.is_contribution)
    tur = [
        {"tur": TUR_ADI.get(k, k), "kurum": len(v["kurum"]), "kayit": v["kayit"], "katki": v["katki"],
         "oran_yuzde": _pct(v["katki"], v["kayit"])}
        for k, v in sorted(by_type.items(), key=lambda kv: -kv[1]["kayit"])
    ]

    org_katki = Counter(src.org for _, _, src in katki)
    partners = Counter(p.strip() for _, c, _ in katki for p in (c.partners or []) if p and p.strip())
    dates = [aware(a.published_at) for a, _, _ in rows if a.published_at]
    cost = sum(c.cost_usd or 0 for _, c, _ in classified)
    jev_used = sum(1 for _, c, _ in classified if (c.model or "").startswith("typesafe/jev"))

    return {
        "rapor_tarihi": now.astimezone().strftime("%Y-%m-%d %H:%M"),
        "genel": {
            "toplam_kayit": len(rows),
            "siniflandirilan": len(classified),
            "toplumsal_katki": len(katki),
            "katki_orani_yuzde": _pct(len(katki), len(classified)),
            "kaydi_olan_kurum": len({src.org for _, _, src in rows}),
            "katki_ureten_kurum": len(org_katki),
            "insan_onayli_kayit": sum(1 for _, c, _ in classified if c.human_label is not None),
            "yayin_tarihi_araligi": [min(dates).date().isoformat(), max(dates).date().isoformat()] if dates else None,
        },
        "son_7_gun": {
            "yeni_kayit": len(new_week),
            "yeni_katki": sum(1 for _, c, _ in new_week if c and c.is_contribution),
        },
        "kaynaklar": {
            "toplam": len(sources),
            "aktif": len(active),
            "yonteme_gore": dict(Counter(x.adapter or "kesfedilmedi" for x in active).most_common()),
            "kayit_getiren": len({src.id for _, _, src in rows}),
        },
        "son_tarama": {
            "baslangic": aware(last_run.started_at).astimezone().strftime("%Y-%m-%d %H:%M") if last_run else None,
            "basarili_site": last_run.sources_ok if last_run else None,
            "hatali_site": last_run.sources_failed if last_run else None,
            "yeni_kayit": last_run.new_articles if last_run else None,
        },
        "kurum_turune_gore": tur,
        "kategori": dict(Counter(c.category or "Belirtilmemiş" for _, c, _ in katki).most_common()),
        "faaliyet_turu": dict(Counter(c.activity_type or "Belirtilmemiş" for _, c, _ in katki).most_common()),
        "sdg": {f"SDG {k}": v for k, v in sorted(Counter(n for _, c, _ in katki for n in (c.sdgs or [])).items())},
        "tarama_yontemi": dict(Counter(a.via for a, _, _ in rows).most_common()),
        "en_cok_katki_ureten_kurumlar": dict(org_katki.most_common(15)),
        "en_sik_paydaslar": dict(partners.most_common(15)),
        "maliyet": {
            "toplam_usd": round(cost, 4),
            "kayit_basina_usd": round(cost / len(classified), 6) if classified else 0,
            "jev_ile_siniflandirilan": jev_used,
            "not": "Sınıflandırma (LLM/Jev) maliyeti; tarama ücretsiz.",
        },
    }


def _table(headers: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" if i == 0 else "---:" for i in range(len(headers))) + "|"]
    out += ["| " + " | ".join(str(x) for x in r) + " |" for r in rows]
    return "\n".join(out)


def to_markdown(r: dict) -> str:
    g, w, k, t, m = r["genel"], r["son_7_gun"], r["kaynaklar"], r["son_tarama"], r["maliyet"]
    parts = [
        f"# Toplumsal Katkı Tarama Raporu — {r['rapor_tarihi']}",
        "## Genel",
        _table(["Ölçü", "Değer"], [
            ["Toplam kayıt", g["toplam_kayit"]],
            ["Sınıflandırılan", g["siniflandirilan"]],
            ["Toplumsal katkı", f"{g['toplumsal_katki']} (%{g['katki_orani_yuzde']})"],
            ["Kaydı olan kurum", g["kaydi_olan_kurum"]],
            ["Katkı üreten kurum", g["katki_ureten_kurum"]],
            ["İnsan onaylı kayıt", g["insan_onayli_kayit"]],
            ["Son 7 günde yeni kayıt / katkı", f"{w['yeni_kayit']} / {w['yeni_katki']}"],
            ["Yayın tarihi aralığı", " – ".join(g["yayin_tarihi_araligi"] or ["-"])],
        ]),
        "## Kaynaklar ve son tarama",
        _table(["Ölçü", "Değer"], [
            ["Aktif kaynak / toplam", f"{k['aktif']} / {k['toplam']}"],
            ["Kayıt getiren kaynak", k["kayit_getiren"]],
            ["Yönteme göre aktif kaynak", ", ".join(f"{a}: {n}" for a, n in k["yonteme_gore"].items())],
            ["Son tarama", f"{t['baslangic']} · {t['basarili_site']} başarılı, {t['hatali_site']} hatalı, {t['yeni_kayit']} yeni"],
        ]),
        "## Kurum türüne göre",
        _table(["Tür", "Kurum", "Kayıt", "Katkı", "Oran %"],
               [[x["tur"], x["kurum"], x["kayit"], x["katki"], x["oran_yuzde"]] for x in r["kurum_turune_gore"]]),
        "## Katkıların kategorisi",
        _table(["Kategori", "Katkı"], [[a, n] for a, n in r["kategori"].items()]),
        "## Faaliyet türü",
        _table(["Faaliyet türü", "Katkı"], [[a, n] for a, n in r["faaliyet_turu"].items()]),
        "## Sürdürülebilir Kalkınma Amaçları",
        _table(["SDG", "Katkı"], [[a, n] for a, n in sorted(r["sdg"].items(), key=lambda kv: -kv[1])]),
        "## En çok katkı üreten 15 kurum",
        _table(["Kurum", "Katkı"], [[a, n] for a, n in r["en_cok_katki_ureten_kurumlar"].items()]),
        "## En sık geçen 15 paydaş",
        _table(["Paydaş", "Katkı haberi"], [[a, n] for a, n in r["en_sik_paydaslar"].items()]),
        "## Tarama yöntemi (kayıt)",
        _table(["Yöntem", "Kayıt"], [[a, n] for a, n in r["tarama_yontemi"].items()]),
        "## Maliyet",
        _table(["Ölçü", "Değer"], [
            ["Toplam sınıflandırma maliyeti", f"${m['toplam_usd']}"],
            ["Kayıt başına", f"${m['kayit_basina_usd']}"],
            ["Jev ile sınıflandırılan", m["jev_ile_siniflandirilan"]],
        ]),
        f"\n_{m['not']}_\n",
    ]
    return "\n\n".join(parts)


def write_report() -> dict:
    r = build_report()
    RAPOR_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    (RAPOR_DIR / f"{stamp}_ozet.json").write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    (RAPOR_DIR / f"{stamp}_ozet.md").write_text(to_markdown(r), encoding="utf-8")

    # haftalık karşılaştırma: her rapor tek satır
    csv_path = RAPOR_DIR / "haftalik_ozet.csv"
    g, w, t = r["genel"], r["son_7_gun"], r["son_tarama"]
    row = {
        "tarih": r["rapor_tarihi"], "toplam_kayit": g["toplam_kayit"], "siniflandirilan": g["siniflandirilan"],
        "toplumsal_katki": g["toplumsal_katki"], "katki_orani_yuzde": g["katki_orani_yuzde"],
        "kaydi_olan_kurum": g["kaydi_olan_kurum"], "katki_ureten_kurum": g["katki_ureten_kurum"],
        "son7gun_yeni_kayit": w["yeni_kayit"], "son7gun_yeni_katki": w["yeni_katki"],
        "aktif_kaynak": r["kaynaklar"]["aktif"], "son_tarama_basarili": t["basarili_site"],
        "son_tarama_hatali": t["hatali_site"], "son_tarama_yeni": t["yeni_kayit"],
        "toplam_maliyet_usd": r["maliyet"]["toplam_usd"],
        **{f"tur_{x['tur']}_katki": x["katki"] for x in r["kurum_turune_gore"]},
    }
    exists = csv_path.exists()
    fields = list(row)
    if exists:
        with csv_path.open(encoding="utf-8-sig") as f:
            old_fields = next(csv.reader(f), [])
        fields = old_fields  # başlık sabit kalsın; yeni sütunlar yeni dosyada başlar
    with csv_path.open("a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        writer.writerow(row)
    r["_dosyalar"] = [str(RAPOR_DIR / f"{stamp}_ozet.md"), str(RAPOR_DIR / f"{stamp}_ozet.json"), str(csv_path)]
    return r
