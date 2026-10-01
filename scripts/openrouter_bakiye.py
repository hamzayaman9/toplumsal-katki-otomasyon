"""OpenRouter hesabının toplam harcamasını yazdırır (anahtarı yazdırmaz)."""
import os

import httpx

r = httpx.get("https://openrouter.ai/api/v1/credits", headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"}, timeout=30)
r.raise_for_status()
d = r.json()["data"]
print(f"total_usage={d['total_usage']:.6f} total_credits={d['total_credits']:.2f}")
