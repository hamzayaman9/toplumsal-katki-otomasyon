"""Sınıflandırma maliyetini ölçer ve maliyet modelinin parametrelerini tahmin eder.

Model:  C_kayıt = p_in · T_in + p_out · T_out
        T_in  = T_sabit + T_haber,   T_haber ≈ karakter_haber / ρ   (ρ: karakter/token)
        T_out = T_json + T_akıl_yürütme
"""

import sqlite3
import statistics as st
from collections import defaultdict
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
db = sqlite3.connect(ROOT / "data" / "katki.db")

rows = db.execute(
    """select k.model, k.prompt_tokens, k.completion_tokens, k.reasoning_tokens, k.cached_tokens,
              k.cost_usd, k.input_chars, k.attempts, length(a.text)
       from classifications k join articles a on a.id = k.article_id
       where k.cost_usd is not null"""
).fetchall()
print(f"Maliyeti ölçülen kayıt: {len(rows)}\n")

# OpenRouter liste fiyatları ($/token)
prices = {}
try:
    for m in httpx.get("https://openrouter.ai/api/v1/models", timeout=30).json()["data"]:
        prices[m["id"]] = (float(m["pricing"]["prompt"]), float(m["pricing"]["completion"]))
except Exception as exc:
    print("fiyat listesi alınamadı:", exc)

by_model = defaultdict(list)
for r in rows:
    by_model[r[0]].append(r)

print(f"{'model':38} {'n':>5} {'T_in ort':>9} {'T_out ort':>9} {'akıl yür.':>9} {'$/kayıt':>10} {'p_in $/M':>9} {'p_out $/M':>9}")
for model, rs in sorted(by_model.items(), key=lambda kv: -len(kv[1])):
    p_in, p_out = prices.get(model.split(":")[0], (float("nan"), float("nan")))
    print(
        f"{model:38} {len(rs):5} {st.mean(r[1] for r in rs):9.0f} {st.mean(r[2] for r in rs):9.0f} "
        f"{st.mean(r[3] or 0 for r in rs):9.0f} {st.mean(r[5] for r in rs):10.6f} {p_in*1e6:9.3f} {p_out*1e6:9.3f}"
    )

tin = [r[1] for r in rows]
tout = [r[2] for r in rows]
cost = [r[5] for r in rows]
art_chars = [min(r[8], 6000) for r in rows]

# T_in = a + b * karakter  (en küçük kareler) -> ρ = 1/b, T_sabit = a
mx, my = st.mean(art_chars), st.mean(tin)
b = sum((x - mx) * (y - my) for x, y in zip(art_chars, tin)) / sum((x - mx) ** 2 for x in art_chars)
a = my - b * mx
print(f"\nT_in ≈ {a:.0f} + {b:.3f} · karakter_haber   →  T_sabit ≈ {a:.0f} token, ρ ≈ {1/b:.2f} karakter/token")
print(f"T_in  ortalama {st.mean(tin):.0f}, medyan {st.median(tin):.0f}, maks {max(tin)}")
print(f"T_out ortalama {st.mean(tout):.0f} (akıl yürütme payı %{100*sum(r[3] or 0 for r in rows)/max(1,sum(tout)):.0f})")
print(f"Önbellekten gelen giriş tokenı: %{100*sum(r[4] or 0 for r in rows)/max(1,sum(tin)):.1f}")
print(f"Tekrar deneme oranı: {st.mean(r[7] for r in rows) - 1:.3f}")
print(f"\nKayıt başına maliyet: ortalama ${st.mean(cost):.6f}, medyan ${st.median(cost):.6f}, maks ${max(cost):.6f}")
print(f"Toplam (kayıtlı): ${sum(cost):.4f}")
