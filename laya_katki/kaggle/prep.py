"""Turn typed-decisions rows into Laya training items (shared by the notebook and the local smoke test).

Same logic as `build_training_item` in the official Laya notebook, parameterised on token budgets.
"""
from __future__ import annotations

import json

from laya.common import QTYPES, build_sequence, render_options


def build_training_item(tok, state, q, gold_q, max_len, head_max_len):
    t, crit = q["type"], q.get("criteria", {})
    if t == "choice":
        target = [gold_q["probabilities"].get(k, 0.0) for k in crit.keys()]
    elif t == "noul":
        target = [gold_q["probabilities"].get("false", 0.5), gold_q["probabilities"].get("true", 0.5)]
    else:
        target = [gold_q["probabilities"].get(str(i), 0.0) for i in range(len(crit))]
    s = sum(target)
    target = [v / s for v in target] if s > 0 else [1.0 / len(target)] * len(target)
    qq = {"t": t, "ins": q["instructions"], "crit": crit}
    seq, markers = build_sequence(tok, state, qq, max_len, head_max_len)
    if len(markers) != len(render_options(qq)):
        return None
    return {"ids": seq, "markers": markers, "qtype": QTYPES[t], "target": target,
            "label": target.index(max(target))}


def build_items(tok, rows, questions, max_len, head_max_len):
    items, dropped = [], 0
    for row in rows:
        state, gold = json.loads(row["state"]), json.loads(row["gold"])
        for qid, q in questions.items():
            if qid not in gold:  # question disputed between generator and labeller for this message
                continue
            it = build_training_item(tok, state, q, gold[qid], max_len, head_max_len)
            if it:
                items.append(it)
            else:
                dropped += 1
    return items, dropped
