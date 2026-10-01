"""Eğitilmiş Laya ile yerel karar — Jev'le aynı soru ve cevap biçimi (models/laya-katki-tr-v*).

Laya, Jev'in kararlarından damıtıldı (laya_katki/). CPU'da çalışır, ücretsizdir ama yavaştır
(~3-5 sn/soru). Güveni eşiğin altında kalan soru setleri Jev'e sorulur (yedek), böylece belirsiz
kayıtlarda kalite düşmez.
"""

import asyncio
import json
import threading
from pathlib import Path

from .config import ROOT, settings
from .jev import JevResult
from .jev import decide as jev_decide
from .llm import LLMError, Usage

_agent = None
_lock = threading.Lock()  # tek model; torch zaten tüm çekirdekleri kullanır, paralel çağrı hızlandırmaz


def model_dir() -> Path:
    if settings.laya_model:
        return Path(settings.laya_model)
    adaylar = sorted((ROOT / "models").glob("laya-katki-tr-v*"), key=lambda p: p.name)
    if not adaylar:
        raise LLMError("Laya modeli yok: models/laya-katki-tr-v* (python -m laya_katki.kaggle.publish output)")
    return adaylar[-1]


def esikler() -> dict:
    """calib'de seçilen karar eşikleri (ör. {"katki": 0.45}); model klasöründeki rl_agent_config.json'da."""
    try:
        cfg = json.loads((model_dir() / "rl_agent_config.json").read_text(encoding="utf-8"))
        return cfg.get("decision_thresholds", {})
    except (OSError, LLMError):
        return {}


def _predict(state: dict, questions: dict) -> dict:
    global _agent
    with _lock:
        if _agent is None:
            import laya  # ağır (torch); yalnız Laya kullanılırken yüklenir

            _agent = laya.load(str(model_dir()), device="cpu")
        return _agent.predict(state, questions)


def _guven(cevap: dict) -> float:
    if cevap.get("type") == "noul":
        p = float(cevap.get("noul", 0.5))
        return max(p, 1 - p)
    return float(cevap.get("confidence") or max((cevap.get("probabilities") or {0: 0}).values()))


async def decide(state: dict, questions: dict) -> JevResult:
    res = await asyncio.to_thread(_predict, state, questions)
    answers = res["answers"]
    esik = settings.laya_yedek_esigi
    if esik and min(_guven(a) for a in answers.values()) < esik:
        jev = await jev_decide(state, questions)
        jev.answers = {k: {**v, "laya": answers.get(k)} for k, v in jev.answers.items()}
        jev.model = f"{model_dir().name} → {jev.model}"
        return jev
    return JevResult(answers, model_dir().name, Usage())
