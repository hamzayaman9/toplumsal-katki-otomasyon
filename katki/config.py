import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _database_url() -> str:
    url = os.getenv("DATABASE_URL") or f"sqlite:///{(ROOT / 'data' / 'katki.db').as_posix()}"
    # Neon/Vercel "postgres://" verir; SQLAlchemy psycopg 3 sürücüsünü açıkça ister
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


@dataclass(frozen=True)
class Settings:
    database_url: str = _database_url()
    # haftalık turdan sonra verinin HTTPS ile gönderildiği bulut veritabanı (bulut-esitle)
    neon_database_url: str = os.getenv("NEON_DATABASE_URL", "")
    # Vercel'de çalışırken tarama/canlı izleme kapalı (uzun iş ve Playwright yok)
    bulut: bool = bool(os.getenv("VERCEL"))
    # boş değilse panel bu şifreyi ister
    panel_sifre: str = os.getenv("PANEL_SIFRE", "")
    openrouter_api_key: str | None = os.getenv("OPENROUTER_API_KEY")
    llm_model: str = os.getenv("LLM_MODEL", "typesafe/jev-router")
    llm_reasoning: str = os.getenv("LLM_REASONING", "off")  # off: akıl yürütme kapalı | on: model varsayılanı
    # jev: kararlar Jev'den | laya: kararlar yerel Laya'dan (belirsizler Jev'e); ikisinde de özet/paydaş
    # yalnız katkılar için LLM'den | llm: her şey LLM'den (eski yöntem)
    classifier: str = os.getenv("CLASSIFIER", "jev")
    jev_model: str = os.getenv("JEV_MODEL", "typesafe/jev-1.13")
    # 1: katkılar için özet/SDG/paydaş adlarını ayrıca LLM'den al | 0 (varsayılan): her şey Jev'in
    # tek isteğindeki sorulardan (konu, SDG, hedef kitle, paydaş türü); özet üretilmez
    llm_detay: bool = os.getenv("LLM_DETAY", "0") == "1"
    # laya: kararlar yerel Laya'dan (boşsa models/ altındaki en yeni laya-katki-tr-v*);
    # güveni bu eşiğin altındaki soru setleri Jev'e sorulur (0: hiç sorma)
    laya_model: str = os.getenv("LAYA_MODEL", "")
    laya_device: str = os.getenv("LAYA_DEVICE", "cpu")  # GPU'lu bilgisayarda "cuda"
    laya_yedek_esigi: float = float(os.getenv("LAYA_YEDEK_ESIGI", "0.7"))  # v1 testinde %36 Jev'e, uyum %95
    user_agent: str = os.getenv(
        "USER_AGENT", "AU-ToplumsalKatki-Bot/0.1 (+Ankara Universitesi Toplumsal Katki Koordinatorlugu)"
    )
    robots_policy: str = os.getenv("ROBOTS_POLICY", "ignore")  # "respect" | "ignore"
    min_host_delay: float = float(os.getenv("MIN_HOST_DELAY", "2"))
    max_crawl_delay: float = float(os.getenv("MAX_CRAWL_DELAY", "10"))
    concurrency: int = int(os.getenv("CONCURRENCY", "5"))


settings = Settings()
