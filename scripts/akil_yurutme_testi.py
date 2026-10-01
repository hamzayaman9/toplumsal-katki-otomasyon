"""Akıl yürütme kapalıyken birkaç kaydı (kaydetmeden) sınıflandırıp token/maliyeti karşılaştırır."""
import asyncio
import sqlite3
import sys

from katki.classify import SYSTEM, KatkiSinifi, _prompt
from katki.db import Article, Session
from katki.llm import chat_json

N = int(sys.argv[1]) if len(sys.argv) > 1 else 20


async def main():
    with Session() as s:
        ids = [r[0] for r in sqlite3.connect("data/katki.db").execute(
            "select article_id from classifications where cost_usd is not null order by random() limit ?", (N,))]
        arts = [s.get(Article, i) for i in ids]
        for a in arts:
            _ = a.source
    old = {r[0]: r[1:] for r in sqlite3.connect("data/katki.db").execute(
        f"select article_id, model, completion_tokens, reasoning_tokens, cost_usd, is_contribution from classifications where article_id in ({','.join(map(str, ids))})")}
    res = await asyncio.gather(*(chat_json(SYSTEM, _prompt(a), KatkiSinifi) for a in arts), return_exceptions=True)
    ok = [(a, r) for a, r in zip(arts, res) if not isinstance(r, Exception)]
    print(f"{len(ok)}/{N} başarılı")
    same = sum(r.value.toplumsal_katki_mi == bool(old[a.id][4]) for a, r in ok)
    for label, rows in [("ONCE (akıl yürütme açık)", [old[a.id] for a, _ in ok]),
                        ("SIMDI (kapalı)", [(r.model, r.usage.completion_tokens, r.usage.reasoning_tokens, r.usage.cost_usd, None) for _, r in ok])]:
        n = len(rows)
        print(f"{label:26} ort. çıktı {sum(x[1] for x in rows)/n:6.0f}  akıl yür. {sum((x[2] or 0) for x in rows)/n:6.0f}  $/kayıt {sum(x[3] for x in rows)/n:.6f}")
    print("modeller şimdi:", {m: sum(1 for _, r in ok if r.model == m) for m in {r.model for _, r in ok}})
    print(f"katkı kararı aynı kalan: {same}/{len(ok)}")

asyncio.run(main())
