"""Tests for the embedding provider abstraction + factory."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.infrastructure.config import settings
from src.core.services.embeddings import (
    CohereEmbeddingProvider,
    get_embedding_provider,
)


def _client_returning(json_body: dict) -> MagicMock:
    """Build a patched httpx.AsyncClient context manager whose post() returns
    a response with ``json_body``."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = json_body
    client = AsyncMock()
    client.post = AsyncMock(return_value=resp)
    client_cm = MagicMock()
    client_cm.__aenter__ = AsyncMock(return_value=client)
    client_cm.__aexit__ = AsyncMock(return_value=None)
    return client_cm, client


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def test_factory_fake_provider_raises(monkeypatch):
    monkeypatch.setattr(settings, "embedding_provider", "fake")
    with pytest.raises(ValueError):
        get_embedding_provider()


def test_factory_cohere_without_key_raises(monkeypatch):
    monkeypatch.setattr(settings, "embedding_provider", "cohere")
    monkeypatch.setattr(settings, "embedding_api_key", None)
    with pytest.raises(ValueError):
        get_embedding_provider()


def test_factory_cohere_returns_provider(monkeypatch):
    monkeypatch.setattr(settings, "embedding_provider", "cohere")
    monkeypatch.setattr(settings, "embedding_api_key", "secret-key")
    monkeypatch.setattr(settings, "embedding_model", "embed-v4.0")
    monkeypatch.setattr(settings, "embedding_dim", 1536)
    provider = get_embedding_provider()
    assert isinstance(provider, CohereEmbeddingProvider)
    assert provider.dim == 1536


# ---------------------------------------------------------------------------
# CohereEmbeddingProvider.embed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_embed_empty_short_circuits():
    provider = CohereEmbeddingProvider("k", "m", 3)
    assert await provider.embed([]) == []


@pytest.mark.asyncio
async def test_embed_posts_payload_and_returns_vectors():
    provider = CohereEmbeddingProvider("k", "model-x", 3)
    client_cm, client = _client_returning({"embeddings": {"float": [[0.1, 0.2, 0.3]]}})
    with patch(
        "src.core.services.embeddings.httpx.AsyncClient", return_value=client_cm
    ):
        out = await provider.embed(["hello"], input_type="search_query")

    assert out == [[0.1, 0.2, 0.3]]
    _, kwargs = client.post.call_args
    assert kwargs["json"]["model"] == "model-x"
    assert kwargs["json"]["input_type"] == "search_query"
    assert kwargs["json"]["texts"] == ["hello"]


@pytest.mark.asyncio
async def test_embed_dimension_mismatch_raises():
    provider = CohereEmbeddingProvider("k", "m", 5)  # expects 5, model returns 3
    client_cm, _ = _client_returning({"embeddings": {"float": [[0.1, 0.2, 0.3]]}})
    with patch(
        "src.core.services.embeddings.httpx.AsyncClient", return_value=client_cm
    ):
        with pytest.raises(ValueError):
            await provider.embed(["hello"])
