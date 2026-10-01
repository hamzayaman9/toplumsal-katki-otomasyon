"""Decision metrics shared by the local eval scripts and the Kaggle notebook (copied in verbatim).

Only numpy is required so the file can be `%%writefile`d into a notebook.
Uyarlama: chatbot/laya_ft/eval/metrics.py; kabul ölçütleri toplumsal katkı damıtması için (öğretmen: Jev),
il soruları bölgeye göre ayrı (il_marmara, ...) olduğundan "il" toplu doğruluğu ayrıca hesaplanır.
"""
from __future__ import annotations

import numpy as np

# Recall targets need precision floors: a model that answers "true" to everything
# (as zero-shot laya-multilingual does on Turkish) would otherwise pass them.
ACCEPTANCE = {
    "katki.accuracy": (">=", 0.92),
    "kategori.accuracy": (">=", 0.80),
    "bolge.accuracy": (">=", 0.85),
    "il.accuracy": (">=", 0.85),
    "overall.ece": ("<=", 0.08),
}


def ece(conf: np.ndarray, correct: np.ndarray, bins: int = 15) -> float:
    edges = np.linspace(0, 1, bins + 1)
    total, err = len(conf), 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            err += m.sum() / total * abs(conf[m].mean() - correct[m].mean())
    return float(err)


def _prf(pred: np.ndarray, gold: np.ndarray) -> dict:
    tp = int((pred & gold).sum()); fp = int((pred & ~gold).sum()); fn = int((~pred & gold).sum())
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"precision": p, "recall": r, "f1": 2 * p * r / (p + r) if p + r else 0.0,
            "support_pos": int(gold.sum()), "predicted_pos": int(pred.sum())}


# F-beta used when choosing decision thresholds on calib: recall-weighted where a miss is costly
THRESHOLD_BETA = {"katki": 1.0}
MIN_PRECISION = 0.80


def choose_thresholds(preds: list[dict], golds: list[dict], questions: dict) -> dict:
    """Per noul question, the threshold maximising F-beta with precision >= MIN_PRECISION (if reachable)."""
    out = {}
    for qid, q in questions.items():
        if q["type"] != "noul":
            continue
        keep = [i for i, g in enumerate(golds) if qid in g]
        if not keep:
            continue
        p = np.array([preds[i][qid]["noul"] for i in keep], dtype=float)
        gold = np.array([golds[i][qid]["label"] == "true" for i in keep])
        beta = THRESHOLD_BETA.get(qid, 1.0)
        best, best_ok = (0.5, -1.0), (None, -1.0)
        for t in np.round(np.arange(0.05, 0.96, 0.05), 2):
            m = _prf(p >= t, gold)
            fb = ((1 + beta**2) * m["precision"] * m["recall"] / (beta**2 * m["precision"] + m["recall"])
                  if m["precision"] + m["recall"] else 0.0)
            if fb > best[1]:
                best = (float(t), fb)
            if m["precision"] >= MIN_PRECISION and fb > best_ok[1]:
                best_ok = (float(t), fb)
        out[qid] = best_ok[0] if best_ok[0] is not None else best[0]
    return out


def evaluate(preds: list[dict], golds: list[dict], questions: dict, thresholds: dict | None = None) -> dict:
    """preds[i][qid] is a Laya answer dict, golds[i][qid] a typed-decisions gold dict (may be absent)."""
    out, all_conf, all_corr = {}, [], []
    for qid, q in questions.items():
        t = q["type"]
        keep = [i for i, g in enumerate(golds) if qid in g]  # gold may omit disputed questions
        qp, qg = [preds[i] for i in keep], [golds[i] for i in keep]
        if not keep:
            continue
        if t == "choice":
            keys = list(q["criteria"].keys())
            P = np.array([[p[qid]["probabilities"].get(k, 0.0) for k in keys] for p in qp])
            P = P / np.clip(P.sum(1, keepdims=True), 1e-9, None)
            G = np.array([[g[qid]["probabilities"].get(k, 0.0) for k in keys] for g in qg])
            pi, gi = P.argmax(1), np.array([keys.index(g[qid]["label"]) for g in qg])
            corr = (pi == gi).astype(float)
            conf = P.max(1)
            conf_m = np.zeros((len(keys), len(keys)), dtype=int)
            for a, b in zip(gi, pi):
                conf_m[a, b] += 1
            per_class = {k: float(conf_m[i, i] / conf_m[i].sum()) if conf_m[i].sum() else None
                         for i, k in enumerate(keys)}
            out[qid] = {"accuracy": float(corr.mean()), "brier": float(((P - G) ** 2).sum(1).mean()),
                        "ece": ece(conf, corr), "per_class_recall": per_class,
                        "confusion": {"labels": keys, "matrix": conf_m.tolist()}}
        elif t == "noul":
            p = np.array([x[qid]["noul"] for x in qp], dtype=float)
            gp = np.array([g[qid]["noul"] for g in qg], dtype=float)
            thr = (thresholds or {}).get(qid, 0.5)
            pred, gold = p >= thr, np.array([g[qid]["label"] == "true" for g in qg])
            conf = np.maximum(p, 1 - p)
            # calibration is about the probability itself, so ECE uses the 0.5 decision regardless of thr
            cal_corr = ((p >= 0.5) == gold).astype(float)
            out[qid] = {"accuracy": float((pred == gold).mean()), "brier": float((2 * (p - gp) ** 2).mean()),
                        "ece": ece(conf, cal_corr), "threshold": thr, **_prf(pred, gold)}
            corr = cal_corr
        else:  # score
            n = len(q["criteria"])
            P = np.array([[x[qid]["probabilities"].get(str(i), 0.0) for i in range(n)] for x in qp])
            P = P / np.clip(P.sum(1, keepdims=True), 1e-9, None)
            gi = np.array([int(g[qid]["label"]) for g in qg])
            pi = P.argmax(1)
            corr = (pi == gi).astype(float)
            conf = P.max(1)
            exp_p = (P * np.arange(n)).sum(1)
            exp_g = np.array([g[qid]["score"] for g in qg], dtype=float)
            out[qid] = {"accuracy": float(corr.mean()), "within_1": float((abs(pi - gi) <= 1).mean()),
                        "mae_expected": float(abs(exp_p - exp_g).mean()), "ece": ece(conf, corr)}
        out[qid]["n"] = len(keep)
        all_conf.append(conf); all_corr.append(corr)
    # il soruları bölgeye göre ayrı: toplu "il" doğruluğu karar sayısıyla ağırlıklı
    il_q = [q for q in out if q.startswith("il_")]
    if il_q:
        n_il = sum(out[q]["n"] for q in il_q)
        out["il"] = {"accuracy": sum(out[q]["accuracy"] * out[q]["n"] for q in il_q) / n_il, "n": n_il,
                     "ece": sum(out[q]["ece"] * out[q]["n"] for q in il_q) / n_il}
    c, k = np.concatenate(all_conf), np.concatenate(all_corr)
    # overall accuracy/ECE are threshold-free (argmax / 0.5), so they compare models, not operating points
    out["overall"] = {"accuracy": float(k.mean()), "ece": ece(c, k), "n_states": len(preds),
                      "n_decisions": int(len(k))}
    out["acceptance"] = acceptance(out)
    return out


def acceptance(m: dict) -> dict:
    res = {}
    for key, (op, thr) in ACCEPTANCE.items():
        q, metric = key.split(".")
        v = m.get(q, {}).get(metric)
        ok = v is not None and (v >= thr if op == ">=" else v <= thr)
        res[key] = {"value": v, "target": f"{op} {thr}", "pass": bool(ok)}
    return res


def summary_rows(m: dict) -> list[tuple[str, str]]:
    rows = []
    for qid, v in m.items():
        # per-question entries only; skip overall/acceptance and extras such as "meta"
        if qid == "overall" or not isinstance(v, dict) or "accuracy" not in v:
            continue
        extra = f" recall={v['recall']:.3f} prec={v['precision']:.3f}" if "recall" in v else ""
        rows.append((qid, f"acc={v['accuracy']:.3f} ece={v['ece']:.3f}{extra}"))
    rows.append(("overall", f"acc={m['overall']['accuracy']:.3f} ece={m['overall']['ece']:.3f}"))
    return rows
