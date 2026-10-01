"""Haberleri toplumsal katkı açısından sınıflandırır."""

import asyncio
import logging
from typing import Literal, get_args

from pydantic import BaseModel, Field
from sqlalchemy import func, select

from .config import settings
from .db import Article, Classification, Session, Source
from .events import EventFn, noop
from .jev import decide
from .llm import LLMError, Usage, chat_json

log = logging.getLogger(__name__)

Kategori = Literal[
    "Sağlık ve iyi yaşam",
    "Eğitim ve yaşam boyu öğrenme",
    "Çevre, iklim ve sürdürülebilirlik",
    "Kültür, sanat ve miras",
    "Sosyal içerme ve dezavantajlı gruplar",
    "Ekonomik kalkınma, girişimcilik ve istihdam",
    "Bilim iletişimi ve halkı bilgilendirme",
    "Afet, acil durum ve insani yardım",
    "Kamu politikası ve kurumlara danışmanlık",
    "Uluslararası iş birliği ve kalkınma",
    "Diğer",
]

FaaliyetTuru = Literal[
    "Toplumsal proje",
    "Gönüllülük faaliyeti",
    "Halka açık eğitim / kurs / seminer",
    "Ücretsiz hizmet (sağlık taraması, hukuki destek vb.)",
    "Bağış / yardım kampanyası",
    "Kurumlarla protokol / iş birliği",
    "Halka açık etkinlik (konferans, sergi, festival)",
    "Rapor / yayın / politika önerisi",
    "Diğer",
]


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

JEV_QUESTIONS = {
    "katki": {
        "type": "noul",
        "instructions": "Bu haber, kurumun (üniversite, vakıf, dernek, STK, kamu kurumu) bilgi, uzmanlık veya "
        "kaynaklarını toplumun yararına kullandığı bir toplumsal katkı faaliyetini mi anlatıyor?",
        "criteria": {
            "true": "Topluma doğrudan fayda: halka açık etkinlik/eğitim, ücretsiz hizmet, sosyal proje, yardım, "
            "gönüllülük, dezavantajlı gruplara destek, öğrencilere burs/yemek/barınma desteği, kurumlarla topluma "
            "yönelik iş birliği.",
            "false": "Kurum içi işleyiş: sınav/kayıt/ders programı, atama, ihale, genel kurul, akademik ödül veya "
            "sıralama başarısı, iş ilanı, taziye, tören.",
        },
    },
    "kategori": {
        "type": "choice",
        "instructions": "Faaliyet en çok hangi alana giriyor?",
        "criteria": {k: k for k in get_args(Kategori)},
    },
    "faaliyet": {
        "type": "choice",
        "instructions": "Faaliyetin türü nedir?",
        "criteria": {k: k for k in get_args(FaaliyetTuru)},
    },
}
KATKI_ESIGI = 0.5


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


async def _classify_jev(article: Article) -> tuple[dict, str, Usage, int]:
    """Kararlar Jev'den; katkıysa özet/paydaş LLM'den. (alanlar, model, kullanım, girdi_karakter)"""
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

    classify_one = _classify_jev if settings.classifier == "jev" else _classify_llm

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
