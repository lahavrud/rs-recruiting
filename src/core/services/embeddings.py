"""Embedding service abstraction layer for the resume-matching engine.

Mirrors ``src/core/services/email.py``: an ABC, a concrete hosted provider,
and a ``get_embedding_provider()`` factory selected by ``settings``.

Language contract — IMPORTANT
-----------------------------
CVs and job postings are Hebrew, English, or a mix of both. The whole point of
using a *hosted multilingual* model is that it aligns all of these in one
cross-lingual vector space, so an English CV can match a Hebrew job by meaning.

Callers MUST pass raw, un-preprocessed text:
- no stemming, stopword removal, or language-specific tokenization
- no translation of either side

Any "optimization" that special-cases one language breaks cross-lingual
matching. Keep the text whole.
"""

import logging
from abc import ABC, abstractmethod

import httpx

from src.core.infrastructure.config import settings

logger = logging.getLogger(__name__)

# Cohere's multilingual embed endpoint. ``input_type`` distinguishes the corpus
# side ("search_document") from the query side ("search_query") — both land in
# the same space; the asymmetry just improves retrieval quality.
_COHERE_EMBED_URL = "https://api.cohere.com/v2/embed"
_HTTP_TIMEOUT_SECONDS = 30.0


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @abstractmethod
    async def embed(
        self, texts: list[str], *, input_type: str = "search_document"
    ) -> list[list[float]]:
        """Embed a batch of texts into vectors.

        ``input_type`` is "search_document" for the indexed corpus (jobs) and
        "search_query" for the thing being matched (a CV). Providers that don't
        distinguish may ignore it. Returns one vector per input text, in order.
        """
        raise NotImplementedError


class CohereEmbeddingProvider(EmbeddingProvider):
    """Cohere multilingual embedding provider (strong Hebrew + English)."""

    def __init__(self, api_key: str, model: str, dim: int):
        self.api_key = api_key
        self.model = model
        self.dim = dim

    async def embed(
        self, texts: list[str], *, input_type: str = "search_document"
    ) -> list[list[float]]:
        if not texts:
            return []
        payload = {
            "model": self.model,
            "texts": texts,
            "input_type": input_type,
            "embedding_types": ["float"],
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
            resp = await client.post(_COHERE_EMBED_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        vectors = data["embeddings"]["float"]
        if any(len(v) != self.dim for v in vectors):
            raise ValueError(
                f"Embedding dimension mismatch: model returned "
                f"{len(vectors[0]) if vectors else 0}, expected {self.dim}. "
                "Update settings.embedding_dim and the Vector column migration."
            )
        return vectors


def get_embedding_provider() -> EmbeddingProvider:
    """Factory: select the embedding provider from configuration.

    ``fake`` is the dev/test default — the real test fake lives in
    ``tests/conftest.py`` and is injected by overriding this function, mirroring
    how the email/storage fakes are wired. A bare call with ``fake`` configured
    still raises, so production never silently ships zero vectors.
    """
    if settings.embedding_provider == "cohere":
        if not settings.embedding_api_key:
            raise ValueError("EMBEDDING_API_KEY must be set when using Cohere")
        return CohereEmbeddingProvider(
            api_key=settings.embedding_api_key,
            model=settings.embedding_model,
            dim=settings.embedding_dim,
        )
    raise ValueError(
        "No real embedding provider configured "
        f"(embedding_provider={settings.embedding_provider!r}). "
        "Set EMBEDDING_PROVIDER=cohere, or inject a fake in tests."
    )
