"""Basit yerel panel: python -m katki web  ->  http://127.0.0.1:8000"""

import asyncio
import hashlib
import hmac
import random
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import defer

from .config import settings
from .db import Article, Baglanti, Classification, CrawlRun, Session, Source, init_db
from .events import Bus
from .sorular import GENEL_KAPSAMLAR

STATIC = Path(__file__).parent / "static"
app = FastAPI(title="Toplumsal Katkı Paneli")
bus = Bus()
_job: asyncio.Task | None = None

# --- giriş (PANEL_SIFRE tanımlıysa) ---------------------------------------------

OTURUM_CEREZI = "katki_oturum"
_ACIK_YOLLAR = {"/giris", "/favicon.ico"}


def _oturum_degeri() -> str:
    return hmac.new(settings.panel_sifre.encode(), b"katki-panel-oturum", hashlib.sha256).hexdigest()


@app.middleware("http")
async def sifre_kontrolu(request: Request, call_next):
    if not settings.panel_sifre or request.url.path in _ACIK_YOLLAR:
        return await call_next(request)
    if hmac.compare_digest(request.cookies.get(OTURUM_CEREZI, ""), _oturum_degeri()):
        return await call_next(request)
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": "Giriş gerekli"}, status_code=401)
    return RedirectResponse("/giris", status_code=303)


class Giris(BaseModel):
    sifre: str


@app.get("/giris")
def giris_sayfasi() -> FileResponse:
    return FileResponse(STATIC / "giris.html")


@app.post("/giris")
def giris(body: Giris, request: Request) -> JSONResponse:
    if not settings.panel_sifre or not hmac.compare_digest(body.sifre.encode(), settings.panel_sifre.encode()):
        raise HTTPException(401, "Şifre yanlış")
    resp = JSONResponse({"ok": True})
    resp.set_cookie(OTURUM_CEREZI, _oturum_degeri(), max_age=60 * 60 * 24 * 30, httponly=True,
                    samesite="lax", secure=request.url.scheme == "https")
    return resp


@app.post("/cikis")
def cikis() -> RedirectResponse:
    resp = RedirectResponse("/giris", status_code=303)
    resp.delete_cookie(OTURUM_CEREZI)
    return resp


def _yerel_ozellik() -> None:
    """Tarama ve canlı izleme yalnız yerel panelde çalışır (Vercel'de uzun iş ve Playwright yok)."""
    if settings.bulut:
        raise HTTPException(404, "Bu özellik yalnız yerel panelde var")


def _period_filter(query, gun: int | None):
    if gun:
        since = datetime.now(timezone.utc) - timedelta(days=gun)
        # tarihi bulunamayan kayıtlar ilk görüldükleri tarihle sayılır
        query = query.where(func.coalesce(Article.published_at, Article.first_seen_at) >= since)
    return query


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


def _scope(query, birim: int | None, org_type: str, org: str):
    """Kurum türü / kurum / birim süzgeçleri (Source ile birleştirilmiş sorgulara)."""
    if birim:
        query = query.where(Source.id == birim)
    if org_type:
        query = query.where(Source.org_type == org_type)
    if org:
        query = query.where(Source.org == org)
    return query


def _aware(dt: datetime | None) -> datetime | None:
    # SQLite saat dilimini saklamaz; UTC yazıyoruz
    return dt.replace(tzinfo=timezone.utc) if dt and dt.tzinfo is None else dt


@app.get("/api/ozet")
def ozet(gun: int | None = None, birim: int | None = None,
         org_type: str = "", org: str = "") -> dict:
    with Session() as s:
        # yalnız gereken sütunlar: haber metni ve ham model çıktısı uzak veritabanından taşınmasın
        base = _period_filter(
            select(Article.source_id, Article.published_at, Source.org, Classification.id.label("cid"),
                   Classification.is_contribution, Classification.category, Classification.sdgs,
                   Classification.activity_type, Classification.human_label, Classification.confidence)
            .join(Source).outerjoin(Classification),
            gun,
        )
        rows = s.execute(_scope(base, birim, org_type, org)).all()

        toplam = len(rows)
        siniflanan = [r for r in rows if r.cid is not None]
        katki = [r for r in siniflanan if r.is_contribution]

        kategori = Counter(c.category or "Belirtilmemiş" for c in katki)
        sdg = Counter(n for c in katki for n in (c.sdgs or []))
        faaliyet = Counter(c.activity_type or "Belirtilmemiş" for c in katki)
        birim_say = Counter(c.source_id for c in katki)
        aylik_toplam = Counter(r.published_at.strftime("%Y-%m") for r in siniflanan if r.published_at)
        aylik_katki = Counter(c.published_at.strftime("%Y-%m") for c in katki if c.published_at)

        names = {i: f"{org_name} · {name or host}" for i, org_name, name, host in
                 s.execute(select(Source.id, Source.org, Source.name, Source.host)).all()}
        aylar = sorted(aylik_toplam)[-12:]

        return {
            "toplam": toplam,
            "siniflanan": len(siniflanan),
            "katki": len(katki),
            "kurum_katki": len({c.org for c in katki}),
            "insan_onayli": sum(1 for c in katki if c.human_label is not None),
            "onay_bekleyen": sum(1 for c in katki if c.human_label is None and (c.confidence or 0) < 0.7),
            "kategori": kategori.most_common(),
            "faaliyet": faaliyet.most_common(),
            "sdg": sorted(sdg.items()),
            "birim": [(names.get(i, str(i)), n) for i, n in birim_say.most_common(10)],
            "aylik": [(m, aylik_katki.get(m, 0), aylik_toplam[m]) for m in aylar],
        }


@app.get("/static/tr-iller.json")
def il_sinirlari() -> FileResponse:
    # il sınırları: github.com/alpers/Turkey-Maps-GeoJSON (Apache-2.0); "Afyon" -> "Afyonkarahisar"
    return FileResponse(STATIC / "tr-iller.json", media_type="application/json",
                        headers={"Cache-Control": "private, max-age=86400"})


@app.get("/api/harita")
def harita(gun: int | None = None, birim: int | None = None, org_type: str = "", org: str = "",
           kategori: str = "") -> dict:
    """Katkıların il dağılımı; il dışı kapsamlar (Türkiye geneli, yurt dışı, çevrimiçi) ayrı sayılır."""
    with Session() as s:
        query = _period_filter(
            select(Classification.bolge, Classification.il).join(Article, Classification.article_id == Article.id)
            .join(Source).where(Classification.is_contribution),
            gun,
        )
        if kategori:
            query = query.where(Classification.category == kategori)
        rows = s.execute(_scope(query, birim, org_type, org)).all()
    return {
        "toplam": len(rows),
        "iller": Counter(r.il for r in rows if r.il),
        "genel": Counter(r.bolge for r in rows if r.bolge in GENEL_KAPSAMLAR),
        "belirlenmedi": sum(1 for r in rows if not r.bolge),
    }


AU = "Ankara Üniversitesi"
# fırsat kartlarında uygulanabilirlik: AÜ'nün benzerini kurabileceği kalıcı işler öne, rapor/tek etkinlik geriye
FIRSAT_AGIRLIK = {
    "Toplumsal proje": 1.0, "Ücretsiz hizmet (sağlık taraması, hukuki destek vb.)": 1.0, "Gönüllülük faaliyeti": 1.0,
    "Halka açık eğitim / kurs / seminer": 0.9, "Kurumlarla protokol / iş birliği": 0.9,
    "Bağış / yardım kampanyası": 0.8, "Halka açık etkinlik (konferans, sergi, festival)": 0.6,
    "Rapor / yayın / politika önerisi": 0.4, "Diğer": 0.5,
}


@app.get("/api/firsatlar")
def firsatlar(gun: int | None = None, org_type: str = "", org: str = "", kategori: str = "",
              adet: int = 24) -> dict:
    """AÜ bağlantısı: fırsat kartları, ortak kurum önerileri, kategori payları ve boşluklar (katki/baglanti.py)."""
    with Session() as s:
        query = _period_filter(
            select(Baglanti, Article.id, Article.title, Article.url, Article.published_at, Source.org,
                   Source.org_type, Classification.category, Classification.activity_type, Classification.il,
                   Classification.bolge, Classification.summary, Classification.confidence,
                   Classification.human_label, Classification.partners)
            .join(Article, Baglanti.article_id == Article.id).join(Source)
            .join(Classification, Classification.article_id == Article.id),
            gun,
        )
        query = _scope(query, None, org_type, org)
        if kategori:
            query = query.where(Classification.category == kategori)
        rows = s.execute(query).all()
        au_ids = {b["id"] for r in rows for b in r.Baglanti.benzer[:1]}
        au_ids |= {r.Baglanti.au_birim_id for r in rows if r.Baglanti.au_birim_id}
        au_haber = {a.id: a for a in s.scalars(select(Article).where(Article.id.in_(au_ids)).options(
            defer(Article.text)))} if au_ids else {}
        birim_adi = dict(s.execute(select(Source.id, func.coalesce(Source.name, Source.host))
                                   .where(Source.org == AU)).all())
        # AÜ'nün kendi katkıları: kategori payı ve boşluk karşılaştırması için (aynı dönem)
        au_katki = s.execute(_period_filter(
            select(Classification.category, Classification.activity_type)
            .join(Article, Classification.article_id == Article.id)
            .join(Source).where(Source.org == AU, Classification.is_contribution), gun)).all()

    def kart(r) -> dict:
        b = r.Baglanti
        yakin = au_haber.get(b.benzer[0]["id"]) if b.benzer else None
        return {
            "id": r.id, "baslik": r.title, "url": r.url, "kurum": r.org, "org_type": r.org_type,
            "tarih": r.published_at.date().isoformat() if r.published_at else None,
            "kategori": r.category, "faaliyet": r.activity_type, "konum": r.il or r.bolge, "ozet": r.summary,
            "firsat": round(b.firsat * FIRSAT_AGIRLIK.get(r.activity_type, 0.5), 4), "benzerlik": b.en_yakin,
            "au_birim": birim_adi.get(b.au_birim_id),
            "au_yakin": {"baslik": yakin.title, "url": yakin.url, "birim": birim_adi.get(yakin.source_id),
                         "skor": b.benzer[0]["skor"]} if yakin else None,
        }

    # fırsat kartları: ilgili bir AÜ birimi var ama AÜ bu işin benzerini yapmamış (birimsiz olanlar AÜ'nün
    # alanı dışında kalıyor: park yenileme, cami açılışı...); güvenilir katkılar, kurum başına en fazla 2 kart
    guvenilir = [r for r in rows if r.Baglanti.au_birim_id and (
        r.human_label is True or (r.human_label is None and (r.confidence or 0) >= 0.7))]
    kartlar, kurum_say = [], Counter()
    for r in sorted(guvenilir, key=lambda r: -r.Baglanti.firsat * FIRSAT_AGIRLIK.get(r.activity_type, 0.5)):
        if kurum_say[r.org] < 2:
            kartlar.append(kart(r))
            kurum_say[r.org] += 1
        if len(kartlar) >= adet:
            break

    # ortak kurum önerisi: AÜ'nün yaptıklarına en çok benzeyen işleri yapan kurumlar (benzerlikte üst çeyrek)
    esik = sorted(r.Baglanti.en_yakin for r in rows)[int(len(rows) * 0.75)] if rows else 1
    ortak: dict[str, dict] = {}
    for r in rows:
        if r.Baglanti.en_yakin < esik:
            continue
        o = ortak.setdefault(r.org, {"kurum": r.org, "org_type": r.org_type, "adet": 0, "kategoriler": Counter(),
                                     "zaten_ortak": False, "ornek": None, "_skor": 0})
        o["adet"] += 1
        o["kategoriler"][r.category or "Diğer"] += 1
        o["zaten_ortak"] |= any(AU.lower() in (p or "").lower() for p in (r.partners or []))
        if r.Baglanti.en_yakin > o["_skor"]:
            o["_skor"], o["ornek"] = r.Baglanti.en_yakin, kart(r)
    ortaklar = sorted(ortak.values(), key=lambda o: -o["adet"])[:12]
    for o in ortaklar:
        o["kategoriler"] = [k for k, _ in o["kategoriler"].most_common(3)]
        o.pop("_skor")

    # kategori payı ve boşluklar: diğer kurumlarda yoğun, AÜ'de hiç olmayan kategori × faaliyet türü
    dis_kat, au_kat = Counter(r.category for r in rows), Counter(k for k, _ in au_katki)
    dis_tur = Counter((r.category, r.activity_type) for r in rows if r.category and r.activity_type)
    au_tur = Counter(au_katki)
    bosluklar = sorted(([k, t, n] for (k, t), n in dis_tur.items() if n >= 3 and not au_tur[(k, t)]),
                       key=lambda x: -x[2])[:15]
    return {
        "dis_katki": len(rows),
        "kartlar": kartlar,
        "ortaklar": ortaklar,
        "kategori_payi": sorted(([k or "Diğer", au_kat[k], n] for k, n in dis_kat.items()), key=lambda x: -x[2]),
        "bosluklar": bosluklar,
        "hesaplandi": _aware(max((r.Baglanti.created_at for r in rows), default=None)) and
        _aware(max(r.Baglanti.created_at for r in rows)).isoformat(),
    }


@app.get("/api/durum")
def durum() -> dict:
    """Başlık satırı: son tarama zamanı ve bulutta mı çalışıyoruz."""
    with Session() as s:
        son_tarama = _aware(s.scalar(select(func.max(CrawlRun.finished_at))))
    return {"son_tarama": son_tarama.isoformat() if son_tarama else None, "bulut": settings.bulut}


@app.get("/api/veriler")
def veriler(gun: int | None = None, birim: int | None = None, org_type: str = "", org: str = "") -> dict:
    """Taranan veriler sekmesi: kayıtların yönteme / kurum türüne göre dağılımı, kaynaklar, son taramalar."""
    with Session() as s:
        base = _period_filter(
            select(Article.via, Source.org_type, Classification.id.label("cid"), Classification.is_contribution)
            .join(Source).outerjoin(Classification),
            gun,
        )
        rows = s.execute(_scope(base, birim, org_type, org)).all()
        tur: dict[str, list[int]] = {}
        for r in rows:
            t = tur.setdefault(r.org_type or "belirsiz", [0, 0, 0])
            t[0] += 1
            t[1] += r.cid is not None
            t[2] += bool(r.is_contribution)

        kayit_say = dict(s.execute(select(Article.source_id, func.count()).group_by(Article.source_id)).all())
        kaynaklar = s.execute(_scope(select(Source.id, Source.active, Source.adapter, Source.last_error),
                                     birim, org_type, org)).all()
        aktif = [k for k in kaynaklar if k.active]
        taramalar = s.scalars(select(CrawlRun).order_by(CrawlRun.started_at.desc()).limit(6)).all()

    return {
        "toplam": len(rows),
        "siniflanan": sum(r.cid is not None for r in rows),
        "katki": sum(bool(r.is_contribution) for r in rows),
        "yontem": Counter(r.via or "belirsiz" for r in rows).most_common(),
        "kurum_turu": sorted(([k, *v] for k, v in tur.items()), key=lambda x: -x[1]),
        "kaynak": {
            "toplam": len(kaynaklar),
            "aktif": len(aktif),
            "kayit_getiren": sum(1 for k in aktif if kayit_say.get(k.id)),
            "hatali": sum(1 for k in aktif if k.last_error),
            "yontem": Counter(k.adapter or "none" for k in aktif).most_common(),
        },
        "taramalar": [
            {"baslangic": _aware(t.started_at).isoformat(), "bitis": t.finished_at and _aware(t.finished_at).isoformat(),
             "basarili": t.sources_ok, "hatali": t.sources_failed, "yeni": t.new_articles}
            for t in taramalar
        ],
    }


@app.get("/api/maliyet")
def maliyet(gun: int | None = None, birim: int | None = None, org_type: str = "", org: str = "") -> dict:
    """Maliyet sekmesi: sınıflandırma harcaması; dönem, sınıflandırmanın yapıldığı tarihe göre."""
    with Session() as s:
        query = (select(Classification.model, Classification.cost_usd, Classification.created_at,
                        Classification.is_contribution, Classification.prompt_tokens,
                        Classification.completion_tokens, Source.org_type)
                 .join(Article, Classification.article_id == Article.id).join(Source))
        if gun:
            query = query.where(Classification.created_at >= datetime.now(timezone.utc) - timedelta(days=gun))
        rows = s.execute(_scope(query, birim, org_type, org)).all()

    olculen = [r for r in rows if r.cost_usd is not None]
    toplam = sum(r.cost_usd for r in olculen)
    katki = sum(1 for r in rows if r.is_contribution)

    def grupla(key) -> list:
        g: dict[str, list] = {}
        for r in olculen:
            x = g.setdefault(key(r), [0, 0.0])
            x[0] += 1
            x[1] += r.cost_usd
        return sorted(([k, n, round(usd, 4)] for k, (n, usd) in g.items()), key=lambda x: -x[2])

    return {
        "toplam_usd": round(toplam, 4),
        "siniflanan": len(rows),
        "olculen": len(olculen),
        "kayit_basi": toplam / len(olculen) if olculen else None,
        "katki_basi": toplam / katki if katki else None,
        "girdi_token": sum(r.prompt_tokens or 0 for r in rows),
        "cikti_token": sum(r.completion_tokens or 0 for r in rows),
        "aylik": sorted(grupla(lambda r: _aware(r.created_at).strftime("%Y-%m")))[-12:],
        "model": grupla(lambda r: r.model),
        "kurum_turu": grupla(lambda r: r.org_type or "belirsiz"),
    }


@app.get("/api/birimler")
def birimler(org_type: str = "", org: str = "") -> list[dict]:
    with Session() as s:
        query = (
            select(Source.id, Source.org, func.coalesce(Source.name, Source.host), func.count(Article.id))
            .join(Article)
            .group_by(Source.id)
            .order_by(func.coalesce(Source.name, Source.host))
        )
        if org_type:
            query = query.where(Source.org_type == org_type)
        if org:
            query = query.where(Source.org == org)
        rows = s.execute(query).all()
    return [{"id": i, "kurum": kurum, "ad": ad, "kayit": n} for i, kurum, ad, n in rows]


@app.get("/api/kurumlar")
def kurumlar(org_type: str = "") -> list[dict]:
    with Session() as s:
        query = (select(Source.org, Source.org_type, func.count(Source.id))
                 .group_by(Source.org, Source.org_type).order_by(Source.org))
        if org_type:
            query = query.where(Source.org_type == org_type)
        rows = s.execute(query).all()
    return [{"org": org, "org_type": kind, "kaynak": n} for org, kind, n in rows]


@app.get("/api/kayitlar")
def kayitlar(
    gun: int | None = None,
    birim: int | None = None,
    org_type: str = "",
    org: str = "",
    q: str = "",
    durum: str = "katki",  # katki | degil | hepsi | inceleme | siniflanmamis
    kategori: str = "",
    il: str = "",  # il adı ya da Türkiye geneli / Yurt dışı / Çevrimiçi
    sayfa: int = 1,
    boyut: int = 50,
) -> dict:
    with Session() as s:
        query = _period_filter(
            select(Article, Classification, Source).join(Source).outerjoin(Classification)
            .options(defer(Article.text), defer(Classification.raw), defer(Source.list_rules)),
            gun,
        )
        if birim:
            query = query.where(Article.source_id == birim)
        if org_type:
            query = query.where(Source.org_type == org_type)
        if org:
            query = query.where(Source.org == org)
        if q:
            like = f"%{q}%"
            query = query.where(or_(Article.title.ilike(like), Classification.summary.ilike(like)))
        if kategori:
            query = query.where(Classification.category == kategori)
        if il:
            query = query.where(Classification.bolge == il if il in GENEL_KAPSAMLAR else Classification.il == il)
        if durum == "katki":
            query = query.where(Classification.is_contribution)
        elif durum == "degil":
            query = query.where(Classification.is_contribution.is_(False))
        elif durum == "inceleme":
            query = query.where(Classification.human_label.is_(None), Classification.confidence < 0.7)
        elif durum == "siniflanmamis":
            query = query.where(Classification.id.is_(None))

        toplam = s.scalar(select(func.count()).select_from(query.subquery()))
        rows = s.execute(
            query.order_by(Article.published_at.desc().nulls_last()).offset((sayfa - 1) * boyut).limit(boyut)
        ).all()
        return {
            "toplam": toplam,
            "kayitlar": [
                {
                    "id": a.id,
                    "tarih": a.published_at.date().isoformat() if a.published_at else None,
                    "birim": src.name or src.host,
                    "kurum": src.org,
                    "org_type": src.org_type,
                    "baslik": a.title,
                    "url": a.url,
                    "katki": c.is_contribution if c else None,
                    "guven": c.confidence if c else None,
                    "kategori": c.category if c else None,
                    "faaliyet": c.activity_type if c else None,
                    "sdg": c.sdgs if c else [],
                    "paydaslar": c.partners if c else [],
                    "ozet": c.summary if c else None,
                    "insan": c.human_label if c else None,
                    "konum": (c.il or c.bolge) if c else None,
                    "model": c.model if c else None,
                }
                for a, c, src in rows
            ],
        }


class Etiket(BaseModel):
    etiket: bool | None


@app.post("/api/etiket/{article_id}")
def etiketle(article_id: int, body: Etiket) -> dict:
    with Session() as s:
        c = s.scalar(select(Classification).where(Classification.article_id == article_id))
        if c is None:
            raise HTTPException(404, "Bu kayıt henüz sınıflandırılmamış")
        c.human_label = body.etiket
        s.commit()
    return {"ok": True}


# --- canlı izleme ---------------------------------------------------------------


@app.get("/canli")
def canli() -> FileResponse:
    _yerel_ozellik()
    return FileResponse(STATIC / "canli.html")


@app.get("/api/olaylar")
async def olaylar() -> StreamingResponse:
    _yerel_ozellik()
    return StreamingResponse(bus.stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.post("/api/olay")
async def olay(events: list[dict]) -> dict:
    """Komut satırından çalışan tarama/sınıflandırmanın olaylarını canlı sayfaya aktarır (yalnız localhost)."""
    _yerel_ozellik()
    for e in events:
        if isinstance(e, dict) and isinstance(e.get("tip"), str):
            bus.emit(e["tip"], **{k: v for k, v in e.items() if k != "tip"})
    return {"ok": True, "adet": len(events)}


def _busy() -> bool:
    return _job is not None and not _job.done()


class Calistir(BaseModel):
    limit: int = 20  # kaynak başına en fazla kayıt
    siniflandir: int | None = None  # None: yeni kayıtların hepsi
    karisik: bool = False  # sınıflandırılacakları kurum türlerinden dengeli seç


@app.post("/api/calistir")
async def calistir(body: Calistir) -> dict:
    """Gerçek tarama + sınıflandırma başlatır; ilerleme /api/olaylar üzerinden izlenir."""
    global _job
    _yerel_ozellik()
    if _busy():
        raise HTTPException(409, "Zaten çalışan bir iş var")

    async def job() -> None:
        # ağır bağımlılıklar (Playwright, trafilatura) yalnız yerelde yüklenir
        from .classify import classify_pending
        from .crawl import crawl_all

        try:
            run = await crawl_all(limit=body.limit, on_event=bus.emit)
            if run.new_articles:
                await classify_pending(
                    limit=body.siniflandir or run.new_articles + 50, on_event=bus.emit, mixed=body.karisik
                )
            else:
                bus.emit("siniflandirma_bitti", basarili=0, hatali=0, not_="Yeni kayıt yok")
        except Exception as exc:
            bus.emit("hata", mesaj=f"{type(exc).__name__}: {exc}")
        finally:
            bus.emit("is_bitti")

    _job = asyncio.create_task(job())
    return {"ok": True}


class Tekrar(BaseModel):
    adet: int = 80
    hiz: float = 1.0


@app.post("/api/tekrar")
async def tekrar(body: Tekrar) -> dict:
    """Veritabanındaki gerçek sonuçları kayıttan oynatır (tanıtım için; yeni istek atmaz)."""
    global _job
    _yerel_ozellik()
    if _busy():
        raise HTTPException(409, "Zaten çalışan bir iş var")

    with Session() as s:
        sources = s.scalars(select(Source).where(Source.active, Source.adapter.in_(["wp_rest", "rss", "list", "ubys_cms"]))).all()
        rows = s.execute(
            select(Article, Classification, Source)
            .join(Classification)
            .join(Source)
            .order_by(Article.published_at.desc().nulls_last())
            .limit(body.adet)
        ).all()
        kaynaklar = [{"id": x.id, "ad": x.name or x.host, "host": x.host,
                     "kurum": x.org, "org_type": x.org_type, "yontem": x.adapter} for x in sources]
        by_source: dict[int, list] = {}
        for a, c, src in rows:
            by_source.setdefault(src.id, []).append(
                {
                    "id": a.id, "kaynak": src.id, "birim": src.name or src.host, "baslik": a.title,
                    "katki": c.is_contribution, "guven": c.confidence, "kategori": c.category,
                    "ozet": c.summary, "model": c.model, "maliyet": c.cost_usd or 0,
                }
            )

    async def job() -> None:
        d = 1 / max(body.hiz, 0.1)
        try:
            bus.emit("tekrar_basladi", kaynaklar=kaynaklar)
            bus.emit("tarama_basladi", kaynaklar=kaynaklar, tekrar=True)
            order = [k["id"] for k in kaynaklar]
            random.shuffle(order)
            pending: list[dict] = []
            for sid in order:
                bus.emit("kaynak_basladi", id=sid)
                await asyncio.sleep(0.12 * d)
                items = by_source.get(sid, [])
                bus.emit("kaynak_bitti", id=sid, yeni=[{"id": i["id"], "baslik": i["baslik"]} for i in items])
                pending += items
            bus.emit("tarama_bitti", basarili=len(order), hatali=0, yeni=len(pending))
            bus.emit("siniflandirma_basladi", adet=len(pending))
            for item in pending:
                await asyncio.sleep(0.35 * d)
                bus.emit("siniflandirildi", **item)
            bus.emit("siniflandirma_bitti", basarili=len(pending), hatali=0)
        finally:
            bus.emit("is_bitti")

    _job = asyncio.create_task(job())
    return {"ok": True}


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    import uvicorn

    init_db()
    uvicorn.run(app, host=host, port=port)
