"""Haberleri toplumsal katkı açısından sınıflandırır."""

import asyncio
import logging

from pydantic import BaseModel, Field
from sqlalchemy import func, select

from .config import settings
from .db import Article, Classification, Session, Source
from .events import EventFn, noop
from . import jev as jev_model, laya
from .llm import LLMError, Usage, chat_json
from .sorular import BOLGE_ILLERI, BOLGE_SORUSU, KARAR_SORULARI, FaaliyetTuru, Kategori, il_sorusu

log = logging.getLogger(__name__)


class KatkiSinifi(BaseModel):
    toplumsal_katki_mi: bool = Field(
        description="Haber, kurumun topluma doğrudan fayda sağlayan bir faaliyetini anlatıyor mu? "
        "Salt kurum içi işleyiş (akademik ödül, atama, tören, sınav/ders programı, ihale, genel kurul) HAYIR; "
        "öğrencilere yönelik sosyal destekler (burs, yemek, barınma) EVET."
    )
    guven: float = Field(ge=0, le=1, description="Kararın güveni, 0-1 arası")
    kategori: Kategori | None = Field(description="Toplumsal katkı değilse null")
    faaliyet_turu: FaaliyetTuru | None = Field(description="Toplumsal katkı değilse null")
    sdg: list[int] = Field(default_factory=list, description="İlgili BM Sürdürülebilir Kalkınma Amaçları (1-17)")
    hedef_kitle: list[str] = Field(default_factory=list, description="Faydalanan gruplar, ör. 'çocuklar', 'yaşlılar'")
    paydaslar: list[str] = Field(default_factory=list, description="Dış paydaş kurum adları (belediye, STK, okul...)")
    ozet: str = Field(description="Faaliyetin 1-2 cümlelik Türkçe özeti")


SYSTEM = (
    "Ankara Üniversitesi Toplumsal Katkı Koordinatörlüğü için çalışıyorsun. Sana bir kurumun (üniversite, "
    "vakıf, dernek, STK veya kamu kurumu) web sitesinden alınan bir haber/duyuru/etkinlik veriliyor. Bu içeriğin "
    "bir toplumsal katkı faaliyeti olup olmadığına karar ver ve sınıflandır. Toplumsal katkı: kurumun bilgi, "
    "uzmanlık ve kaynaklarını toplumun (yerel halk, dezavantajlı gruplar, öğrenciler, kamu kurumları, okullar, "
    "STK'lar vb.) yararına kullandığı faaliyetlerdir. Öğrencilere yönelik sosyal destekler (burs, yemek, barınma "
    "yardımı) toplumsal katkıdır. Salt kurum içi işleyiş (sınav tarihi, kayıt, atama, ihale, genel kurul, "
    "akademik ödül/terfi) toplumsal katkı değildir. Paydaşlar alanına içerikte geçen dış kurumları (özellikle "
    "üniversiteler, STK'lar, belediyeler, bakanlıklar) resmî adlarıyla yaz."
)


# --- Jev (karar) + LLM (metin) hibrit yöntemi -------------------------------------

JEV_QUESTIONS = KARAR_SORULARI
# Laya Jev'in olasılığından damıtıldı: aynı eşik ikisine de geçerli (Laya v1'in calib'de F1 için seçtiği
# 0,35 Jev'le uyumu %82,4'ten %78,6'ya düşürüyordu)
KATKI_ESIGI = 0.5


async def decide(state: dict, questions: dict):
    """Karar modeli: CLASSIFIER=laya ise yerel Laya (belirsizler Jev'e), değilse Jev."""
    if settings.classifier == "laya":
        return await laya.decide(state, questions)
    return await jev_model.decide(state, questions)


class KatkiDetay(BaseModel):
    """Jev'in üretemediği metin alanları; yalnız katkı çıkan kayıtlar için LLM'e sorulur."""

    sdg: list[int] = Field(default_factory=list, description="İlgili BM Sürdürülebilir Kalkınma Amaçları (1-17)")
    hedef_kitle: list[str] = Field(default_factory=list, description="Faydalanan gruplar, ör. 'çocuklar', 'yaşlılar'")
    paydaslar: list[str] = Field(default_factory=list, description="İçerikte geçen dış kurumların resmî adları")
    ozet: str = Field(description="Faaliyetin 1-2 cümlelik Türkçe özeti")


DETAY_SYSTEM = (
    "Sana bir kurumun toplumsal katkı faaliyetini anlatan haber veriliyor. Faaliyetin kısa özetini yaz, ilgili "
    "SDG'leri, faydalanan grupları ve içerikte geçen dış paydaş kurumları (üniversite, STK, belediye, bakanlık...) "
    "resmî adlarıyla çıkar."
)


def _state(article: Article) -> dict:
    src = article.source
    return {
        "kurum": src.org,
        "kurum_turu": src.org_type,
        "il": src.city,
        "birim": src.name or src.host,
        "baslik": article.title,
        "site_kategorileri": article.categories or [],
        "tarih": f"{article.published_at:%Y-%m-%d}" if article.published_at else None,
        "metin": (article.text or "")[:6000],
    }


def _add_usage(total: Usage, part: Usage) -> None:
    for k in ("prompt_tokens", "completion_tokens", "reasoning_tokens", "cached_tokens", "cost_usd", "attempts"):
        setattr(total, k, getattr(total, k) + getattr(part, k))


async def konum_sor(state: dict) -> tuple[dict, dict, Usage]:
    """Faaliyetin yeri: önce bölge, tek bölgeyse il (Jev). (alanlar, ham cevaplar, kullanım)"""
    jev = await decide(state, BOLGE_SORUSU)
    usage, b = jev.usage, jev.answers["bolge"]
    fields = {"bolge": b["choice"], "il": None, "konum_guven": b.get("confidence")}
    raw = {"bolge": b}
    if b["choice"] in BOLGE_ILLERI:
        il_jev = await decide(state, il_sorusu(b["choice"]))
        i = il_jev.answers["il"]
        fields["il"] = i["choice"]
        fields["konum_guven"] = (b.get("confidence") or 0) * (i.get("confidence") or 0)
        raw["il"] = i
        _add_usage(usage, il_jev.usage)
    return fields, raw, usage


async def _classify_jev(article: Article) -> tuple[dict, str, Usage, int]:
    """Kararlar Jev'den ya da Laya'dan; katkıysa özet/paydaş LLM'den. (alanlar, model, kullanım, girdi_karakter)"""
    state = _state(article)
    jev = await decide(state, JEV_QUESTIONS)
    a = jev.answers
    p = float(a["katki"]["noul"])
    katki = p >= KATKI_ESIGI
    fields = {
        "is_contribution": katki,
        "confidence": max(p, 1 - p),  # verilen kararın olasılığı
        "category": a["kategori"]["choice"] if katki else None,
        "activity_type": a["faaliyet"]["choice"] if katki else None,
        "sdgs": [], "beneficiaries": [], "partners": [], "summary": None,
        "raw": {"jev": a, "katki_olasiligi": p},
    }
    usage, model, chars = jev.usage, jev.model, len(str(state))
    if katki:
        prompt = _prompt(article) + f"\nKategori (Jev): {fields['category']}"
        det = await chat_json(DETAY_SYSTEM, prompt, KatkiDetay)
        d = det.value
        fields.update(
            sdgs=sorted({x for x in d.sdg if 1 <= x <= 17}),
            beneficiaries=d.hedef_kitle,
            partners=d.paydaslar,
            summary=d.ozet,
        )
        fields["raw"]["detay"] = d.model_dump()
        _add_usage(usage, det.usage)
        model = f"{jev.model} + {det.model}"
        chars += len(DETAY_SYSTEM) + len(prompt)
        konum, konum_raw, konum_usage = await konum_sor(state)
        fields.update(konum)
        fields["raw"]["jev"].update(konum_raw)
        _add_usage(usage, konum_usage)
    return fields, model, usage, chars


async def _classify_llm(article: Article) -> tuple[dict, str, Usage, int]:
    """Eski yöntem: tüm alanlar tek LLM çağrısından."""
    prompt = _prompt(article)
    res = await chat_json(SYSTEM, prompt, KatkiSinifi)
    r = res.value
    fields = {
        "is_contribution": r.toplumsal_katki_mi, "confidence": r.guven, "category": r.kategori,
        "activity_type": r.faaliyet_turu, "sdgs": sorted({x for x in r.sdg if 1 <= x <= 17}),
        "beneficiaries": r.hedef_kitle, "partners": r.paydaslar, "summary": r.ozet, "raw": r.model_dump(),
    }
    return fields, res.model, res.usage, len(SYSTEM) + len(prompt)


def _prompt(article: Article) -> str:
    tarih = f"{article.published_at:%Y-%m-%d}" if article.published_at else "-"
    return (
        f"Kurum: {article.source.org} ({article.source.org_type or '-'}, {article.source.city or '-'})\n"
        f"Birim: {article.source.name or article.source.host}\n"
        f"Başlık: {article.title}\n"
        f"Kategoriler: {', '.join(article.categories or []) or '-'}\n"
        f"Tarih: {tarih}\n"
        f"Metin:\n{article.text[:6000]}"
    )


def _pending_ids(session, limit: int, mixed: bool) -> list[int]:
    pending = select(Article.id).outerjoin(Classification).where(Classification.id.is_(None))
    if not mixed:
        return list(session.scalars(pending.order_by(Article.published_at.desc().nulls_last()).limit(limit)))
    # karışık örnek: her kurum türünden eşit sayıda rastgele kayıt (azsa kalan pay diğerlerine)
    types = list(session.scalars(select(Source.org_type).distinct()))
    ids: list[int] = []
    for i, t in enumerate(sorted(types, key=lambda t: t or "")):
        share = (limit - len(ids)) // (len(types) - i)
        ids += session.scalars(
            pending.join(Source).where(Source.org_type.is_(t) if t is None else Source.org_type == t)
            .order_by(func.random()).limit(share)
        )
    return ids


async def classify_pending(
    limit: int = 50, concurrency: int = 4, on_event: EventFn = noop, mixed: bool = False
) -> tuple[int, int, float]:
    """Henüz sınıflandırılmamış haberleri sınıflandırır. (başarılı, hatalı, başarısız çağrıların maliyeti $)

    mixed=True: en yeniler yerine kurum türlerinden dengeli rastgele örnek alır.
    """
    with Session() as session:
        ids = _pending_ids(session, limit, mixed)
        articles = session.scalars(select(Article).where(Article.id.in_(ids))).all()
        for a in articles:
            _ = a.source  # ilişkiyi oturum açıkken yükle

    sem = asyncio.Semaphore(concurrency)
    failed_cost = 0.0
    on_event("siniflandirma_basladi", adet=len(articles))

    classify_one = _classify_jev if settings.classifier in ("jev", "laya") else _classify_llm

    async def one(article: Article) -> Classification | None:
        nonlocal failed_cost
        async with sem:
            try:
                fields, model, u, chars = await classify_one(article)
            except (LLMError, KeyError, ValueError, TypeError) as exc:
                log.warning("sınıflandırılamadı #%s: %s", article.id, exc)
                if isinstance(exc, LLMError) and exc.usage:
                    failed_cost += exc.usage.cost_usd
                on_event("siniflandirma_hatasi", id=article.id, kaynak=article.source_id)
                return None
        on_event(
            "siniflandirildi",
            id=article.id,
            kaynak=article.source_id,
            birim=article.source.name or article.source.host,
            baslik=article.title,
            katki=fields["is_contribution"],
            guven=fields["confidence"],
            kategori=fields["category"],
            ozet=fields["summary"],
            model=model,
            maliyet=u.cost_usd,
        )
        c = Classification(
            article_id=article.id,
            model=model,
            **fields,
            prompt_tokens=u.prompt_tokens,
            completion_tokens=u.completion_tokens,
            reasoning_tokens=u.reasoning_tokens,
            cached_tokens=u.cached_tokens,
            cost_usd=u.cost_usd,
            input_chars=chars,
            attempts=u.attempts,
        )
        # hemen kaydet: süreç yarıda kesilirse (uyku, internet, kapanma) ödenmiş sonuçlar kaybolmasın
        with Session() as session:
            session.add(c)
            session.commit()
        return c

    results = await asyncio.gather(*(one(a) for a in articles))
    ok = sum(c is not None for c in results)
    on_event("siniflandirma_bitti", basarili=ok, hatali=len(results) - ok)
    return ok, len(results) - ok, failed_cost


async def konumlari_doldur(limit: int = 10000, concurrency: int = 4, rastgele: bool = False) -> tuple[int, int, float]:
    """Konumu sorulmamış katkılara bölge/il sorar (eski kayıtlar için). (başarılı, hatalı, maliyet $)

    rastgele=True: en yeniler yerine rastgele örnek (Laya'nın eğitim verisi çeşitli olsun).
    """
    with Session() as session:
        rows = session.execute(
            select(Classification, Article).join(Article)
            .where(Classification.is_contribution, Classification.bolge.is_(None))
            .order_by(func.random() if rastgele else Article.published_at.desc().nulls_last()).limit(limit)
        ).all()
        for _, a in rows:
            _ = a.source  # ilişkiyi oturum açıkken yükle

    sem = asyncio.Semaphore(concurrency)
    toplam = {"ok": 0, "hata": 0, "usd": 0.0}

    async def one(c: Classification, article: Article) -> None:
        async with sem:
            try:
                fields, raw, usage = await konum_sor(_state(article))
            except (LLMError, KeyError, ValueError, TypeError) as exc:
                log.warning("konum belirlenemedi #%s: %s", article.id, exc)
                toplam["hata"] += 1
                return
        with Session() as session:
            row = session.get(Classification, c.id)
            for k, v in fields.items():
                setattr(row, k, v)
            row.raw = {**(row.raw or {}), "jev": {**(row.raw or {}).get("jev", {}), **raw}}
            row.cost_usd = (row.cost_usd or 0) + usage.cost_usd  # maliyet sekmesi gerçek harcamayı göstersin
            session.commit()
        toplam["ok"] += 1
        toplam["usd"] += usage.cost_usd
        if toplam["ok"] % 100 == 0:
            log.info("konum: %s / %s ($%.4f)", toplam["ok"], len(rows), toplam["usd"])

    await asyncio.gather(*(one(c, a) for c, a in rows))
    return toplam["ok"], toplam["hata"], toplam["usd"]
