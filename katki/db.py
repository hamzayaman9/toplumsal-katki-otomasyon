from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from .config import ROOT, settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Source(Base):
    """Taranan bir site (ör. dtcf.ankara.edu.tr)."""

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    host: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str | None] = mapped_column(String(500))
    org: Mapped[str] = mapped_column(String(255), default="Ankara Üniversitesi")
    org_type: Mapped[str | None] = mapped_column(String(100))
    city: Mapped[str | None] = mapped_column(String(100))
    focus: Mapped[bool] = mapped_column(Boolean, default=False)
    js_render_required: Mapped[bool] = mapped_column(Boolean, default=False)
    kind: Mapped[str | None] = mapped_column(String(100))  # fakülte, enstitü, MYO...
    cms: Mapped[str | None] = mapped_column(String(100))
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    # discover ile doldurulur
    base_url: Mapped[str | None] = mapped_column(String(500))
    adapter: Mapped[str | None] = mapped_column(String(50))  # wp_rest | rss | list | none
    feed_url: Mapped[str | None] = mapped_column(String(1000))
    list_urls: Mapped[dict] = mapped_column(JSON, default=dict)  # {"haber": url, "duyuru": url, ...}
    list_rules: Mapped[dict] = mapped_column(JSON, default=dict)  # {liste_url: {link_regex, css, ornek, ...}}
    wp_categories: Mapped[dict] = mapped_column(JSON, default=dict)  # {"12": "Haberler"}
    robots_disallow_all: Mapped[bool] = mapped_column(Boolean, default=False)
    crawl_delay: Mapped[float | None] = mapped_column(Float)
    discovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    last_crawled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[list] = mapped_column(JSON, default=list)

    articles: Mapped[list["Article"]] = relationship(back_populates="source")


class Article(Base):
    """Bir haber / duyuru / etkinlik kaydı."""

    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    url: Mapped[str] = mapped_column(String(1000), unique=True)
    external_id: Mapped[str | None] = mapped_column(String(500))  # RSS guid bazen uzun URL
    title: Mapped[str] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    text: Mapped[str] = mapped_column(Text, default="")
    categories: Mapped[list] = mapped_column(JSON, default=list)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    via: Mapped[str] = mapped_column(String(50))  # wp_rest | rss | list
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    source: Mapped[Source] = relationship(back_populates="articles")
    classification: Mapped["Classification | None"] = relationship(back_populates="article", uselist=False)


class Classification(Base):
    __tablename__ = "classifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"), unique=True)
    model: Mapped[str] = mapped_column(String(200))
    is_contribution: Mapped[bool] = mapped_column(Boolean)
    confidence: Mapped[float | None] = mapped_column(Float)
    category: Mapped[str | None] = mapped_column(String(200))
    activity_type: Mapped[str | None] = mapped_column(String(200))
    sdgs: Mapped[list] = mapped_column(JSON, default=list)
    beneficiaries: Mapped[list] = mapped_column(JSON, default=list)
    partners: Mapped[list] = mapped_column(JSON, default=list)
    summary: Mapped[str | None] = mapped_column(Text)
    # faaliyetin yeri: bolge = 7 bölgeden biri ya da Türkiye geneli / Yurt dışı / Çevrimiçi; il yalnız tek bölgede
    bolge: Mapped[str | None] = mapped_column(String(50))
    il: Mapped[str | None] = mapped_column(String(50))
    konum_guven: Mapped[float | None] = mapped_column(Float)
    raw: Mapped[dict] = mapped_column(JSON, default=dict)
    # koordinatörlük onayı: None = bakılmadı, True/False = insan kararı
    human_label: Mapped[bool | None] = mapped_column(Boolean)
    # maliyet ölçümü (tekrar denemeler dahil)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    reasoning_tokens: Mapped[int | None] = mapped_column(Integer)
    cached_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Float)
    input_chars: Mapped[int | None] = mapped_column(Integer)
    attempts: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    article: Mapped[Article] = relationship(back_populates="classification")


class CrawlRun(Base):
    __tablename__ = "crawl_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sources_ok: Mapped[int] = mapped_column(Integer, default=0)
    sources_failed: Mapped[int] = mapped_column(Integer, default=0)
    new_articles: Mapped[int] = mapped_column(Integer, default=0)


if settings.database_url.startswith("sqlite"):
    (ROOT / "data").mkdir(exist_ok=True)

if settings.database_url.startswith("sqlite"):
    engine = create_engine(settings.database_url, connect_args={"timeout": 30})
else:
    # Neon boşta bağlantıyı kapatabiliyor; sunucusuz ortamda havuzu küçük tut
    engine = create_engine(settings.database_url, pool_pre_ping=True, pool_size=2, max_overflow=3, pool_recycle=300)
Session = sessionmaker(engine, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)
    _add_missing_columns()
    from sqlalchemy import text

    with engine.begin() as conn:
        conn.execute(text("UPDATE sources SET org_type = 'devlet_universitesi', city = 'Ankara' "
                          "WHERE (host = 'ankara.edu.tr' OR host LIKE '%.ankara.edu.tr') "
                          "AND (org_type IS NULL OR city IS NULL)"))
        conn.execute(text("UPDATE sources SET focus = FALSE WHERE focus IS NULL"))
        conn.execute(text("UPDATE sources SET js_render_required = FALSE WHERE js_render_required IS NULL"))


def backup_db(keep: int = 5) -> str | None:
    """SQLite veritabanının tutarlı bir kopyasını data/yedek/ altına alır; en yeni `keep` yedeği tutar."""
    if not settings.database_url.startswith("sqlite"):
        return None
    import sqlite3
    from datetime import datetime

    src_path = settings.database_url.split("///", 1)[1]
    backup_dir = ROOT / "data" / "yedek"
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"katki_{datetime.now():%Y%m%d_%H%M%S}.db"
    with sqlite3.connect(src_path, timeout=30) as src, sqlite3.connect(target) as dst:
        src.backup(dst)  # çalışan başka bir süreç yazarken de tutarlı kopya alır
    for old in sorted(backup_dir.glob("katki_*.db"))[:-keep]:
        old.unlink()
    return str(target)


def _add_missing_columns() -> None:
    """create_all mevcut tablolara yeni sütun eklemez; basit ALTER TABLE ile tamamla."""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            existing = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name not in existing:
                    conn.execute(text(f"ALTER TABLE {table.name} ADD COLUMN {col.name} {col.type.compile(engine.dialect)}"))
