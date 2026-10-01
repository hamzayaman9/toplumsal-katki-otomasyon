"""OpenRouter üzerinden şemaya uygun JSON çıktı alan küçük istemci.

Şu an `typesafe/jev-router` kullanılıyor (isteği uygun bir LLM'e yönlendirir).
TypeSafe API anahtarı gelince bu modül Jev'in tipli çıktısıyla değiştirilecek.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Generic, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from .config import settings

T = TypeVar("T", bound=BaseModel)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class LLMError(RuntimeError):
    def __init__(self, message: str, usage: "Usage | None" = None) -> None:
        super().__init__(message)
        self.usage = usage


@dataclass
class Usage:
    """Bir çağrının (tekrar denemeler dahil) token ve maliyet dökümü."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    cached_tokens: int = 0
    cost_usd: float = 0.0
    attempts: int = 0

    def add(self, usage: dict | None) -> None:
        usage = usage or {}
        self.prompt_tokens += usage.get("prompt_tokens") or 0
        self.completion_tokens += usage.get("completion_tokens") or 0
        self.reasoning_tokens += (usage.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0
        self.cached_tokens += (usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
        self.cost_usd += usage.get("cost") or 0.0


@dataclass
class LLMResult(Generic[T]):
    value: T
    model: str
    usage: Usage = field(default_factory=Usage)


def _extract_json(text: str) -> str:
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if fenced:
        return fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise LLMError(f"JSON bulunamadı: {text[:200]!r}")
    return text[start : end + 1]


async def chat_json(system: str, user: str, output: type[T], *, retries: int = 1) -> LLMResult[T]:
    """Modelden `output` şemasına uyan bir nesne döndürür (kullanılan model ve maliyetle birlikte)."""
    if not settings.openrouter_api_key:
        raise LLMError("OPENROUTER_API_KEY tanımlı değil")

    schema = output.model_json_schema()
    body = {
        "model": settings.llm_model,
        "messages": [
            {
                "role": "system",
                "content": system
                + "\n\nYalnızca şu JSON şemasına uyan tek bir JSON nesnesi döndür, başka metin yazma:\n"
                + json.dumps(schema, ensure_ascii=False),
            },
            {"role": "user", "content": user},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": output.__name__, "strict": False, "schema": schema},
        },
        "temperature": 0,
    }
    if settings.llm_reasoning == "off":
        # sınıflandırma için "düşünme" tokenlarına gerek yok; çıktı fiyatının büyük kısmı buradan geliyordu
        body["reasoning"] = {"enabled": False}
    headers = {"Authorization": f"Bearer {settings.openrouter_api_key}"}

    usage = Usage()
    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=120) as client:
        for _ in range(retries + 1):
            usage.attempts += 1
            try:
                resp = await client.post(OPENROUTER_URL, json=body, headers=headers)
            except httpx.HTTPError as exc:
                last_error = LLMError(f"OpenRouter bağlantı hatası: {exc}")
                continue
            if resp.status_code >= 400:
                last_error = LLMError(f"OpenRouter {resp.status_code}: {resp.text[:300]}")
                continue
            data = resp.json()
            usage.add(data.get("usage"))  # başarısız denemenin maliyeti de sayılır
            content = data["choices"][0]["message"].get("content") or ""
            try:
                value = output.model_validate_json(_extract_json(content))
                return LLMResult(value, data.get("model", settings.llm_model), usage)
            except (ValidationError, LLMError) as exc:
                last_error = exc
    raise LLMError(str(last_error), usage)
