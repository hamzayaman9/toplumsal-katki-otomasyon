"""TypeSafe Jev (System One karar modeli) istemcisi — OpenRouter Decisions API üzerinden.

Jev metin üretmez; tanımladığımız tipli sorulara kalibre olasılıklarla cevap verir:
  noul   -> "evet" olasılığı (0-1)
  choice -> seçilen seçenek + her seçeneğin olasılığı
  score  -> sıralı ölçekte konum
"""

from dataclasses import dataclass

import httpx

from .config import settings
from .llm import LLMError, Usage

DECISIONS_URL = "https://openrouter.ai/api/alpha/decisions"


@dataclass
class JevResult:
    answers: dict
    model: str
    usage: Usage


async def decide(state: dict | str, questions: dict, *, retries: int = 1) -> JevResult:
    if not settings.openrouter_api_key:
        raise LLMError("OPENROUTER_API_KEY tanımlı değil")
    usage = Usage()
    last_error = "bilinmeyen hata"
    async with httpx.AsyncClient(timeout=60) as client:
        for _ in range(retries + 1):
            usage.attempts += 1
            try:
                resp = await client.post(
                    DECISIONS_URL,
                    headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
                    json={"model": settings.jev_model, "state": state, "questions": questions},
                )
            except httpx.HTTPError as exc:
                last_error = f"Jev bağlantı hatası: {exc}"
                continue
            data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            if resp.status_code >= 400 or "answers" not in data:
                last_error = f"Jev {resp.status_code}: {resp.text[:300]}"
                continue
            u = data.get("usage") or {}
            usage.prompt_tokens += u.get("input_tokens") or 0
            usage.completion_tokens += u.get("output_tokens") or 0
            usage.cost_usd += u.get("cost") or 0.0
            return JevResult(data["answers"], data.get("model", settings.jev_model), usage)
    raise LLMError(last_error, usage)
