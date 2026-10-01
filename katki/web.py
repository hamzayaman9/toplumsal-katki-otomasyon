"""Basit yerel panel: python -m katki web  ->  http://127.0.0.1:8000"""

import asyncio
import random
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, or_, select

from .classify import classify_pending
from .crawl import crawl_all
from .db import Article, Classification, CrawlRun, Session, Source, init_db
from .events import Bus

STATIC = Path(__file__).parent / "static"
app = FastAPI(title="Toplumsal Katkı Paneli")
bus = Bus()
_job: asyncio.Task | None = None


def _period_filter(query, gun: int | None):
    if gun:
        since = datetime.now(timezone.utc) - timedelta(days=gun)
        query = query.where(Article.published_at >= since)
    return query


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/ozet")
def ozet(gun: int | None = None, birim: int | None = None,
         org_type: str = "", org: str = "") -> dict:
    with Session() as s:
        base = _period_filter(select(Article, Classification).join(Source).outerjoin(Classification), gun)
        if birim:
            base = base.where(Article.source_id == birim)
        if org_type:
            base = base.where(Source.org_type == org_type)
        if org:
            base = base.where(Source.org == org)
        rows = s.execute(base).all()

        toplam = len(rows)
        siniflanan = [c for _, c in rows if c is not None]
        katki = [(a, c) for a, c in rows if c is not None and c.is_contribution]

        kategori = Counter(c.category or "Belirtilmemiş" for _, c in katki)
        sdg = Counter(n for _, c in katki for n in (c.sdgs or []))
        faaliyet = Counter(c.activity_type or "Belirtilmemiş" for _, c in katki)
        birim_say = Counter(a.source_id for a, _ in katki)
        aylik_toplam = Counter(a.published_at.strftime("%Y-%m") for a, c in rows if a.published_at and c)
        aylik_katki = Counter(a.published_at.strftime("%Y-%m") for a, _ in katki if a.published_at)

        names = {i: f"{org_name} · {name or host}" for i, org_name, name, host in
                 s.execute(select(Source.id, Source.org, Source.name, Source.host)).all()}
        son_tarama = s.scalar(select(func.max(CrawlRun.finished_at)))
        if son_tarama and son_tarama.tzinfo is None:  # SQLite saat dilimini saklamaz; UTC yazıyoruz
            son_tarama = son_tarama.replace(tzinfo=timezone.utc)
        aylar = sorted(aylik_toplam)[-12:]

        return {
            "toplam": toplam,
            "siniflanan": len(siniflanan),
            "katki": len(katki),
            "onay_bekleyen": sum(1 for _, c in katki if c.human_label is None and (c.confidence or 0) < 0.7),
            "maliyet_usd": round(sum(c.cost_usd or 0 for c in siniflanan), 4),
            "maliyet_olculen": sum(1 for c in siniflanan if c.cost_usd is not None),
            "son_tarama": son_tarama.isoformat() if son_tarama else None,
            "kategori": kategori.most_common(),
            "faaliyet": faaliyet.most_common(),
            "sdg": sorted(sdg.items()),
            "birim": [(names.get(i, str(i)), n) for i, n in birim_say.most_common(10)],
            "aylik": [(m, aylik_katki.get(m, 0), aylik_toplam[m]) for m in aylar],
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
    durum: str = "katki",  # katki | hepsi | inceleme | siniflanmamis
    kategori: str = "",
    sayfa: int = 1,
    boyut: int = 50,
) -> dict:
    with Session() as s:
        query = _period_filter(select(Article, Classification, Source).join(Source).outerjoin(Classification), gun)
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
        if durum == "katki":
            query = query.where(Classification.is_contribution)
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
    return FileResponse(STATIC / "canli.html")


@app.get("/api/olaylar")
async def olaylar() -> StreamingResponse:
    return StreamingResponse(bus.stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.post("/api/olay")
async def olay(events: list[dict]) -> dict:
    """Komut satırından çalışan tarama/sınıflandırmanın olaylarını canlı sayfaya aktarır (yalnız localhost)."""
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
    if _busy():
        raise HTTPException(409, "Zaten çalışan bir iş var")

    async def job() -> None:
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
