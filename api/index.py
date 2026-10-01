"""Vercel giriş noktası: paneli (katki.web) sunucusuz fonksiyon olarak yayınlar.

Tarama burada çalışmaz; PC'deki haftalık tur aynı DATABASE_URL'e yazar.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from katki.web import app  # noqa: E402,F401
