"""Yerel SQLite veritabanını (data/katki.db) bulut Postgres'e kopyalar.

Hedef, .env'deki DATABASE_URL'dir (Postgres olmalı). Hedef boş olmalı; --sil ile önce boşaltılır:
    <uv python> scripts/buluta_aktar.py [--sil]
"""
import site
import sys
from datetime import timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
site.addsitedir(str(ROOT / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine, func, insert, select, text  # noqa: E402

from katki.config import settings  # noqa: E402
from katki.db import Base  # noqa: E402

PARCA = 500


def _temizle(value):
    # SQLite saat dilimsiz saklar, yazdığımız her şey UTC; Postgres metinde NUL kabul etmez
    if hasattr(value, "tzinfo") and hasattr(value, "hour") and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        return value.replace("\x00", "")
    return value


def main() -> None:
    if not settings.database_url.startswith("postgresql"):
        sys.exit(".env'deki DATABASE_URL bir Postgres adresi değil.\n" + __doc__)
    kaynak = create_engine(f"sqlite:///{(ROOT / 'data' / 'katki.db').as_posix()}")
    hedef = create_engine(settings.database_url)

    Base.metadata.create_all(hedef)
    tablolar = Base.metadata.sorted_tables
    with hedef.begin() as h:
        dolu = {t.name: h.scalar(select(func.count()).select_from(t)) for t in tablolar}
        if any(dolu.values()):
            if "--sil" not in sys.argv:
                sys.exit(f"Hedef boş değil: {dolu}. Üzerine yazmak için --sil ekleyin.")
            for t in reversed(tablolar):
                h.execute(t.delete())

    with kaynak.connect() as k, hedef.begin() as h:
        for t in tablolar:
            satirlar = k.execute(select(t)).mappings().all()
            for i in range(0, len(satirlar), PARCA):
                parca = [{c: _temizle(v) for c, v in r.items()} for r in satirlar[i:i + PARCA]]
                h.execute(insert(t), parca)
            # id dizisini kopyalanan en büyük id'nin ardına al
            h.execute(text(f"SELECT setval(pg_get_serial_sequence('{t.name}', 'id'), "
                           f"COALESCE((SELECT MAX(id) FROM {t.name}), 0) + 1, false)"))
            print(f"{t.name}: {len(satirlar)} satır")
    print("Bitti.")


if __name__ == "__main__":
    main()
