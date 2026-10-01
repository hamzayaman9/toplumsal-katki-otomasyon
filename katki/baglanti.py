"""Ankara Üniversitesi bağlantısı: diğer kurumların katkılarını AÜ'nün faaliyetleriyle anlamca eşleştirir.

Yerel benzerlik modeli (intfloat/multilingual-e5-small, CPU, ücretsiz). Her dış katkı için en yakın AÜ
faaliyetleri, en ilgili AÜ birimi ve "fırsat skoru" (AÜ'de yakın benzeri ne kadar az) hesaplanıp
`baglantilar` tablosuna yazılır; panel fırsat kartlarını, ortak kurum önerilerini buradan üretir.

    <python> katki_calistir.py baglanti-kur
"""

import hashlib
import logging
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import selectinload

from .config import ROOT
from .db import Article, Baglanti, Classification, Session

log = logging.getLogger(__name__)

MODEL_DIR = ROOT / "models" / "multilingual-e5-small"
ONBELLEK = ROOT / "data" / "vektorler.npz"
AU = "Ankara Üniversitesi"
EN_YAKIN = 3
BIRIMSIZ_YUZDELIK = 15


def _metin(a: Article, c: Classification) -> str:
    # e5 simetrik benzerlikte iki tarafa da "query: " ister
    return f"query: {a.title}. {c.summary or (a.text or '')[:600]}"


def _anahtar(metin: str) -> str:
    return hashlib.sha1(metin.encode()).hexdigest()[:16]


def vektorle(metinler: list[str], batch: int = 32) -> np.ndarray:
    import torch
    from transformers import AutoModel, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(MODEL_DIR)
    model = AutoModel.from_pretrained(MODEL_DIR).eval()
    out = []
    with torch.inference_mode():
        for i in range(0, len(metinler), batch):
            enc = tok(metinler[i:i + batch], padding=True, truncation=True, max_length=256, return_tensors="pt")
            h = model(**enc).last_hidden_state
            m = enc["attention_mask"].unsqueeze(-1).float()
            v = (h * m).sum(1) / m.sum(1)  # ortalama havuzlama (e5 böyle eğitildi)
            out.append(torch.nn.functional.normalize(v, dim=-1).numpy())
            if (i // batch) % 20 == 0:
                log.info("vektör: %s / %s", min(i + batch, len(metinler)), len(metinler))
    return np.concatenate(out) if out else np.zeros((0, 384), dtype=np.float32)


def katki_vektorleri() -> tuple[list[tuple[Article, Classification]], np.ndarray]:
    """Katkıların (insan 'değil' dedikleri hariç) vektörleri; önbellekte olanlar yeniden hesaplanmaz."""
    with Session() as s:
        rows = s.execute(
            select(Article, Classification).join(Classification)
            .where(or_(Classification.is_contribution, Classification.human_label.is_(True)))
            .where(or_(Classification.human_label.is_(None), Classification.human_label.is_(True)))
            .options(selectinload(Article.source)).order_by(Article.id)
        ).all()
    metinler = [_metin(a, c) for a, c in rows]
    anahtarlar = [_anahtar(m) for m in metinler]
    onbellek = {}
    if ONBELLEK.exists():
        z = np.load(ONBELLEK)
        onbellek = dict(zip(z["anahtar"].tolist(), z["vektor"]))
    eksik = [i for i, k in enumerate(anahtarlar) if k not in onbellek]
    if eksik:
        log.info("%s katkı vektörlenecek (%s önbellekte)", len(eksik), len(rows) - len(eksik))
        for i, v in zip(eksik, vektorle([metinler[i] for i in eksik])):
            onbellek[anahtarlar[i]] = v
        ONBELLEK.parent.mkdir(exist_ok=True)
        np.savez_compressed(ONBELLEK, anahtar=np.array(list(onbellek)), vektor=np.stack(list(onbellek.values())))
    return [tuple(r) for r in rows], np.stack([onbellek[k] for k in anahtarlar])


GENEL_AU_SITELERI = {"ankara.edu.tr", "www.ankara.edu.tr"}  # rektörlük/ana site: birim önerisi için fazla genel


def kur() -> dict:
    """Dış katkıların AÜ bağlarını baştan hesaplar ve `baglantilar` tablosunu yeniler."""
    rows, V = katki_vektorleri()
    au = np.array([a.source.org == AU for a, _ in rows])
    if not au.any() or au.all():
        raise SystemExit("Hem AÜ hem dış kurum katkısı gerekli")
    au_rows = [r for r, x in zip(rows, au) if x]
    dis_rows = [r for r, x in zip(rows, au) if not x]
    S = V[~au] @ V[au].T

    # birim önerisi: tek bir habere değil, birimin tüm faaliyetlerinin ortalamasına (merkez) göre
    birim_idx = defaultdict(list)
    for j, (a, _) in enumerate(au_rows):
        if a.source.host not in GENEL_AU_SITELERI:
            birim_idx[a.source_id].append(j)
    birimler = [b for b, idx in birim_idx.items() if len(idx) >= 2]
    merkez = np.stack([V[au][birim_idx[b]].mean(0) for b in birimler])
    merkez /= np.linalg.norm(merkez, axis=1, keepdims=True)
    # ham benzerlik: ortalamaya göre düzeltme ve CSLS denendi, niş birimleri öne çıkarıp daha kötü eşleştirdi;
    # AÜ'nün taranan katkısı az (53 birim, ~350 haber) olduğundan öneri yaklaşıktır, panelde öyle gösterilir
    birim_skor = V[~au] @ merkez.T

    # hiçbir birimin işlerine benzemeyen (en alt %15) katkıda birim önerme: "AÜ'de yeni alan" olarak gösterilir
    birim_en = birim_skor.max(1)
    birim_esik = np.percentile(birim_en, BIRIMSIZ_YUZDELIK)
    en_yakin = S.max(1)
    # e5 benzerlikleri dar aralıkta (0,8-0,97): mutlak eşik yerine sıra; 1 = AÜ'de en az benzeri olan
    firsat = 1 - en_yakin.argsort().argsort() / max(1, len(en_yakin) - 1)
    simdi = datetime.now(timezone.utc)
    kayitlar = []
    for i, (a, _) in enumerate(dis_rows):
        top = np.argsort(-S[i])[:EN_YAKIN]
        kayitlar.append(Baglanti(
            article_id=a.id,
            benzer=[{"id": au_rows[j][0].id, "skor": round(float(S[i, j]), 4)} for j in top],
            en_yakin=round(float(en_yakin[i]), 4),
            au_birim_id=birimler[int(birim_skor[i].argmax())] if birim_en[i] >= birim_esik else None,
            firsat=round(float(firsat[i]), 4),
            created_at=simdi,
        ))
    with Session() as s:
        s.execute(delete(Baglanti))
        s.add_all(kayitlar)
        s.commit()
    return {"dis_katki": len(dis_rows), "au_katki": len(au_rows), "au_birim": len(birimler),
            "benzerlik_medyan": round(float(np.median(en_yakin)), 3)}
