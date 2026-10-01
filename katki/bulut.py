"""Yerel SQLite -> bulut Postgres (Neon) eşitlemesi, HTTPS üzerinden.

Bu PC'nin ağı Postgres'in 5432 portundaki TLS bağlantısını kesiyor; Neon'un HTTP SQL
uç noktası (443) açık. Tarama yerel SQLite'a yazmaya devam eder, haftalık turun sonunda
yeni kayıtlar buraya gönderilir. Sitede verilen insan onayları (human_label) önce geri çekilir.
"""

import json
from datetime import date, datetime, timezone
from urllib.parse import urlsplit

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from .config import settings
from .db import Base, Classification, Session

PARCA_BAYT = 1_500_000
# bulutta düzenlenen sütunlar: gönderirken üzerine yazılmaz
BULUTTA_DUZENLENEN = {"classifications": {"human_label"}}
# her seferinde tamamı gönderilen küçük/güncellenen tablolar; diğerleri yalnız yeni id'ler
TAM_GONDERILEN = {"sources", "crawl_runs"}
# yerelde her hafta baştan hesaplanan tablolar: bulutta önce boşaltılır (silinen satırlar kalmasın)
YENIDEN_KURULAN = {"baglantilar"}


class Neon:
    def __init__(self, url: str) -> None:
        self.url = url.replace("postgresql+psycopg://", "postgresql://").replace("postgres://", "postgresql://")
        self.client = httpx.Client(timeout=120)
        self.endpoint = f"https://{urlsplit(self.url).hostname}/sql"

    def sorgu(self, query: str, params: list | None = None) -> list[dict]:
        r = self.client.post(self.endpoint, headers={"Neon-Connection-String": self.url},
                             json={"query": query, "params": params or []})
        if r.status_code != 200:
            raise RuntimeError(f"Neon {r.status_code}: {r.text[:300]}")
        return r.json().get("rows", [])


def _deger(value):
    if isinstance(value, datetime):
        return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        return value.replace("\x00", "")  # Postgres metinde NUL kabul etmez
    return value


def _sema_olustur(neon: Neon) -> None:
    dialect = postgresql.dialect()
    for table in Base.metadata.sorted_tables:
        neon.sorgu(str(CreateTable(table, if_not_exists=True).compile(dialect=dialect)))
        for index in table.indexes:
            neon.sorgu(str(CreateIndex(index, if_not_exists=True).compile(dialect=dialect)))
        # create_all gibi CREATE TABLE da mevcut tabloya sonradan eklenen sütunları getirmez
        mevcut = {r["column_name"] for r in neon.sorgu(
            "SELECT column_name FROM information_schema.columns WHERE table_name = $1", [table.name])}
        for col in table.columns:
            if col.name not in mevcut:
                neon.sorgu(f"ALTER TABLE {table.name} ADD COLUMN {col.name} {col.type.compile(dialect=dialect)}")


def _etiketleri_cek(neon: Neon) -> int:
    """Sitede verilen onayları yerel veritabanına yazar.

    Bulut yalnız kendinde bulunan satırlar için esastır; henüz gönderilmemiş satırların
    yerel onayına dokunulmaz (ilk eşitlemede bulut boşken yerel onaylar silinmesin).
    """
    uzak = {r["article_id"]: r["human_label"] for r in
            neon.sorgu("SELECT article_id, human_label FROM classifications")}
    degisen = 0
    with Session() as s:
        yerel = dict(s.execute(select(Classification.article_id, Classification.human_label)).all())
        for article_id, etiket in uzak.items():
            if article_id in yerel and yerel[article_id] != etiket:
                s.execute(update(Classification).where(Classification.article_id == article_id)
                          .values(human_label=etiket))
                degisen += 1
        s.commit()
    return degisen


def _varsayilanlar(table) -> dict:
    """Sonradan eklenen sütunlar eski SQLite satırlarında boş; Postgres'te NOT NULL oldukları için doldur."""
    sonuc = {}
    for col in table.columns:
        if not col.nullable and col.default is not None:
            arg = col.default.arg
            sonuc[col.name] = (lambda a=arg: a(None)) if col.default.is_callable else (lambda a=arg: a)
    return sonuc


def _gonder(neon: Neon, table, rows: list[dict]) -> None:
    cols = [c.name for c in table.columns]
    varsayilan = _varsayilanlar(table)
    korunan = BULUTTA_DUZENLENEN.get(table.name, set())
    guncelle = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c != "id" and c not in korunan)
    query = (f"INSERT INTO {table.name} SELECT * FROM json_populate_recordset(NULL::{table.name}, $1::json) "
             f"ON CONFLICT (id) DO UPDATE SET {guncelle}")
    parca: list[dict] = []
    boyut = 0
    for row in rows:
        satir = {c: _deger(row[c] if row[c] is not None or c not in varsayilan else varsayilan[c]()) for c in cols}
        parca.append(satir)
        boyut += len(json.dumps(satir, ensure_ascii=False))
        if boyut >= PARCA_BAYT:
            neon.sorgu(query, [json.dumps(parca, ensure_ascii=False)])
            parca, boyut = [], 0
    if parca:
        neon.sorgu(query, [json.dumps(parca, ensure_ascii=False)])


def esitle(tam: bool = False, log=print) -> dict:
    if not settings.neon_database_url:
        raise SystemExit(".env'de NEON_DATABASE_URL tanımlı değil.")
    neon = Neon(settings.neon_database_url)
    _sema_olustur(neon)
    sonuc = {"etiket_cekilen": _etiketleri_cek(neon)}
    log(f"Sitedeki onaylardan yerelde güncellenen: {sonuc['etiket_cekilen']}")

    with Session() as s:
        for table in Base.metadata.sorted_tables:
            query = select(table).order_by(table.c.id)
            if table.name in YENIDEN_KURULAN:
                neon.sorgu(f"DELETE FROM {table.name}")
            elif not tam and table.name not in TAM_GONDERILEN:
                uzak_max = neon.sorgu(f"SELECT COALESCE(MAX(id), 0) AS m FROM {table.name}")[0]["m"]
                query = query.where(table.c.id > int(uzak_max))
            rows = s.execute(query).mappings().all()
            _gonder(neon, table, rows)
            sonuc[table.name] = len(rows)
            log(f"{table.name}: {len(rows)} satır gönderildi")
        yerel = {t.name: s.scalar(select(func.count()).select_from(t)) for t in Base.metadata.sorted_tables}
    uzak = {t: int(neon.sorgu(f"SELECT COUNT(*) AS n FROM {t}")[0]["n"]) for t in yerel}
    sonuc["fark"] = {t: yerel[t] - uzak[t] for t in yerel if yerel[t] != uzak[t]}
    log("Kontrol: yerel ve bulut satır sayıları " + ("aynı." if not sonuc["fark"] else f"farklı: {sonuc['fark']}"))
    return sonuc
