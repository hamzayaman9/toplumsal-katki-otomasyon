"""Veritabanındaki Jev kararlarından Laya eğitim veri seti (damıtma).

Biçim `LocalLLaMA/typed-decisions` ile aynı ({id, workflow, split, state, questions, gold, meta}; state,
questions ve gold JSON metni) — chatbot/laya_ft'nin Kaggle notebook'u değişmeden okur.

Etiketler yumuşak: Jev'in seçenek olasılıkları. Koordinatörlüğün onayı (human_label) varsa katkı
sorusunda kesin etiket olur. Bölünme kaynak sitesine göre (aynı sitenin haberleri tek bölümde).

    <uv python> -m laya_katki.veri
"""
from __future__ import annotations

import hashlib
import json
import math
import site
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
site.addsitedir(str(ROOT / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import selectinload  # noqa: E402

from katki.classify import _state  # noqa: E402
from katki.db import Article, Classification, Session  # noqa: E402
from katki.sorular import BOLGE_ILLERI, BOLGE_SORUSU, KARAR_SORULARI, il_sorusu  # noqa: E402

DATA_DIR = Path(__file__).resolve().parent / "data"
WORKFLOW = "toplumsal_katki_tr"
SPLITS = ("train", "calib", "test")
INSAN_P = 0.97  # insan onayı kesin etiket; tam 0/1 yerine küçük pay (aşırı güvenli model olmasın)

ASCII = str.maketrans("ıİşŞğĞçÇöÖüÜ ", "iIsSgGcCoOuU_")


def il_soru_id(bolge: str) -> str:
    return "il_" + bolge.translate(ASCII).lower()


def sorular() -> dict:
    """Notebook'un tek soru seti: her satırın gold'u yalnız kendisine uyan soruları içerir."""
    return {**KARAR_SORULARI, **BOLGE_SORUSU, **{il_soru_id(b): il_sorusu(b)["il"] for b in BOLGE_ILLERI}}


def _guven(p: list[float]) -> float:
    h = -sum(x * math.log(x) for x in p if x > 0)
    return round(1.0 - h / math.log(len(p)), 6) if len(p) > 1 else 1.0


def noul_gold(p: float) -> dict:
    p = min(max(float(p), 0.0), 1.0)
    return {"type": "noul", "label": "true" if p >= 0.5 else "false", "noul": round(p, 6),
            "probabilities": {"false": round(1 - p, 6), "true": round(p, 6)}, "confidence": round(abs(2 * p - 1), 6)}


def choice_gold(cevap: dict, secenekler: list[str]) -> dict | None:
    olas = cevap.get("probabilities") or {}
    p = [max(float(olas.get(k, 0.0)), 0.0) for k in secenekler]
    s = sum(p)
    if s <= 0:
        if cevap.get("choice") not in secenekler:
            return None
        p, s = [float(k == cevap["choice"]) for k in secenekler], 1.0
    p = [x / s for x in p]
    return {"type": "choice", "label": secenekler[p.index(max(p))],
            "probabilities": {k: round(v, 6) for k, v in zip(secenekler, p)}, "confidence": _guven(p)}


def bolum(host: str) -> str:
    h = int(hashlib.md5(host.encode()).hexdigest(), 16) % 10
    return "test" if h == 9 else "calib" if h == 8 else "train"


def gold_olustur(c: Classification, qs: dict) -> tuple[dict, str]:
    """(gold, kaynak) — kaynak: jev | insan | yalniz_konum"""
    jev = (c.raw or {}).get("jev") or {}
    gold, kaynak = {}, "yalniz_konum"
    if c.model.startswith("typesafe/jev") and "katki" in jev:
        gold["katki"] = noul_gold(jev["katki"]["noul"])
        kaynak = "jev"
        if c.is_contribution:
            for q in ("kategori", "faaliyet"):
                if q in jev and (g := choice_gold(jev[q], list(qs[q]["criteria"]))):
                    gold[q] = g
    if c.human_label is not None:
        gold["katki"] = noul_gold(INSAN_P if c.human_label else 1 - INSAN_P)
        kaynak = "insan"
    if "bolge" in jev and (g := choice_gold(jev["bolge"], list(qs["bolge"]["criteria"]))):
        gold["bolge"] = g
        b = jev["bolge"].get("choice")
        if b in BOLGE_ILLERI and "il" in jev:
            qid = il_soru_id(b)
            if g2 := choice_gold(jev["il"], list(qs[qid]["criteria"])):
                gold[qid] = g2
    return gold, kaynak


def build() -> dict:
    qs = sorular()
    rows = {s: [] for s in SPLITS}
    gorulen, kopya, etiketsiz = set(), 0, 0
    kaynaklar = Counter()
    with Session() as s:
        kayitlar = s.execute(
            select(Classification, Article).join(Article).options(selectinload(Article.source))
            .order_by(Article.id)
        ).all()
        for c, a in kayitlar:
            gold, kaynak = gold_olustur(c, qs)
            if not gold:
                etiketsiz += 1
                continue
            if a.content_hash in gorulen:  # aynı haber birden çok sitede: bölümler arası sızıntı olmasın
                kopya += 1
                continue
            gorulen.add(a.content_hash)
            split = bolum(a.source.host)
            kaynaklar[kaynak] += 1
            rows[split].append({
                "id": f"a{a.id}", "workflow": WORKFLOW, "split": split,
                "state": json.dumps(_state(a), ensure_ascii=False),
                "questions": json.dumps({q: qs[q] for q in gold}, ensure_ascii=False),
                "gold": json.dumps(gold, ensure_ascii=False),
                "meta": json.dumps({"kaynak": kaynak, "org_type": a.source.org_type, "host": a.source.host},
                                   ensure_ascii=False),
            })

    upload = DATA_DIR / "kaggle_upload"
    upload.mkdir(parents=True, exist_ok=True)
    for split in SPLITS:
        with open(upload / f"{split}.jsonl", "w", encoding="utf-8") as f:
            for r in rows[split]:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    (upload / "questions_tr.json").write_text(json.dumps(qs, ensure_ascii=False, indent=1), encoding="utf-8")

    karar = {split: Counter(q for r in rows[split] for q in json.loads(r["gold"])) for split in SPLITS}
    pozitif = {split: sum(json.loads(r["gold"]).get("katki", {}).get("label") == "true" for r in rows[split])
               for split in SPLITS}
    rapor = {
        "satir": {split: len(rows[split]) for split in SPLITS},
        "karar_sayisi": {split: dict(karar[split]) for split in SPLITS},
        "katki_pozitif": pozitif,
        "etiket_kaynagi": dict(kaynaklar),
        "kopya_atilan": kopya, "etiketsiz": etiketsiz,
        "kaynak_site": {split: len({json.loads(r["meta"])["host"] for r in rows[split]}) for split in SPLITS},
    }
    (DATA_DIR / "veri_raporu.json").write_text(json.dumps(rapor, ensure_ascii=False, indent=2), encoding="utf-8")
    return rapor


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
