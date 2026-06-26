"""LLM generation service for resume summarisation.

Mirrors ``embeddings.py``: an ABC, a concrete Cohere provider, a fake for
dev/test, and a ``get_generation_provider()`` factory selected by ``settings``.
Reuses ``embedding_api_key`` — the same Cohere API key covers both embed and
generate endpoints.
"""

import logging
from abc import ABC, abstractmethod

import httpx

from src.core.infrastructure.config import settings

logger = logging.getLogger(__name__)

_COHERE_CHAT_URL = "https://api.cohere.com/v2/chat"
_HTTP_TIMEOUT_SECONDS = 30.0

_SYSTEM_PROMPT = "אתה עוזר גיוס מקצועי. ענה בעברית בלבד. ספק תשובות תמציתיות."
_USER_PROMPT_TEMPLATE = (
    "סכם את קורות החיים הבאים במשפט אחד קצר, "
    "תוך הדגשת התחום המקצועי, רמת הניסיון ותפקידים בולטים:\n\n{text}"
)
_RESUME_TEXT_LIMIT = 3000
_MAX_TOKENS = 80


class GenerationProvider(ABC):
    """Abstract base class for LLM generation providers."""

    @abstractmethod
    async def summarize_resume(self, text: str) -> str:
        """Generate a one-line Hebrew summary of a resume's text."""
        raise NotImplementedError


class FakeGenerationProvider(GenerationProvider):
    """No-op provider for local dev and tests."""

    async def summarize_resume(self, text: str) -> str:
        return "סיכום לדוגמה"


class CohereGenerationProvider(GenerationProvider):
    """Cohere Command R generation provider (Hebrew/English multilingual)."""

    def __init__(self, api_key: str, model: str = "command-r-plus-08-2024"):
        self.api_key = api_key
        self.model = model

    async def summarize_resume(self, text: str) -> str:
        truncated = text[:_RESUME_TEXT_LIMIT]
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _USER_PROMPT_TEMPLATE.format(text=truncated),
                },
            ],
            "max_tokens": _MAX_TOKENS,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
            resp = await client.post(_COHERE_CHAT_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        content_blocks = data["message"]["content"]
        text_blocks = [b["text"] for b in content_blocks if b.get("type") == "text"]
        return " ".join(text_blocks).strip()


def get_generation_provider() -> GenerationProvider:
    """Factory: select the generation provider from configuration.

    Falls back to ``FakeGenerationProvider`` when no real provider is configured
    so that tests and local dev work without an API key. Unlike the embedding
    provider, a missing key here is non-fatal — a NULL ``resume_summary`` is
    acceptable; a missing embedding would break matching entirely.
    """
    if settings.embedding_provider == "cohere" and settings.embedding_api_key:
        return CohereGenerationProvider(api_key=settings.embedding_api_key)
    return FakeGenerationProvider()
