"""Tests for the resume-summary generation provider abstraction + factory."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from rs_shared.core.infrastructure.config import settings
from rs_shared.core.services.generation import (
    _RESUME_TEXT_LIMIT,
    CohereGenerationProvider,
    FakeGenerationProvider,
    get_generation_provider,
)

_ASYNC_CLIENT = "rs_shared.core.services.generation.httpx.AsyncClient"


def _client_returning(json_body: dict) -> tuple[MagicMock, AsyncMock]:
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
# Factory — a missing key is non-fatal here (unlike embeddings): fall back.
# ---------------------------------------------------------------------------


def test_factory_returns_cohere_when_configured_with_a_key(monkeypatch):
    monkeypatch.setattr(settings, "embedding_provider", "cohere")
    monkeypatch.setattr(settings, "embedding_api_key", "secret-key")

    provider = get_generation_provider()

    assert isinstance(provider, CohereGenerationProvider)
    assert provider.api_key == "secret-key"


def test_factory_falls_back_to_fake_without_a_key(monkeypatch):
    monkeypatch.setattr(settings, "embedding_provider", "cohere")
    monkeypatch.setattr(settings, "embedding_api_key", None)

    assert isinstance(get_generation_provider(), FakeGenerationProvider)


def test_factory_falls_back_to_fake_for_other_providers(monkeypatch):
    monkeypatch.setattr(settings, "embedding_provider", "fake")
    monkeypatch.setattr(settings, "embedding_api_key", "secret-key")

    assert isinstance(get_generation_provider(), FakeGenerationProvider)


@pytest.mark.asyncio
async def test_fake_provider_returns_a_fixed_summary_without_network():
    with patch(_ASYNC_CLIENT) as async_client:
        summary = await FakeGenerationProvider().summarize_resume("anything")

    assert summary
    async_client.assert_not_called()


# ---------------------------------------------------------------------------
# CohereGenerationProvider.summarize_resume
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cohere_posts_truncated_prompt_and_auth_header():
    provider = CohereGenerationProvider("k", model="model-x")
    long_text = "a" * _RESUME_TEXT_LIMIT + "TAIL_PAST_THE_LIMIT"
    client_cm, client = _client_returning(
        {"message": {"content": [{"type": "text", "text": "summary"}]}}
    )

    with patch(_ASYNC_CLIENT, return_value=client_cm):
        await provider.summarize_resume(long_text)

    _, kwargs = client.post.call_args
    payload = kwargs["json"]
    assert payload["model"] == "model-x"
    assert [m["role"] for m in payload["messages"]] == ["system", "user"]
    user_prompt = payload["messages"][1]["content"]
    assert "a" * _RESUME_TEXT_LIMIT in user_prompt
    assert "TAIL_PAST_THE_LIMIT" not in user_prompt
    assert payload["max_tokens"] > 0
    assert kwargs["headers"] == {"Authorization": "Bearer k"}


@pytest.mark.asyncio
async def test_cohere_joins_text_blocks_and_skips_other_block_types():
    provider = CohereGenerationProvider("k")
    client_cm, _ = _client_returning(
        {
            "message": {
                "content": [
                    {"type": "text", "text": " Senior backend"},
                    {"type": "tool_call", "id": "ignored"},
                    {"type": "text", "text": "engineer. "},
                ]
            }
        }
    )

    with patch(_ASYNC_CLIENT, return_value=client_cm):
        summary = await provider.summarize_resume("cv text")

    assert summary == "Senior backend engineer."


@pytest.mark.asyncio
async def test_cohere_http_error_propagates():
    """The caller decides what a failed summary means; the provider must not
    swallow it into an empty string."""
    provider = CohereGenerationProvider("k")
    client_cm, client = _client_returning({})
    error = httpx.HTTPStatusError("429", request=MagicMock(), response=MagicMock())
    client.post.return_value.raise_for_status.side_effect = error

    with patch(_ASYNC_CLIENT, return_value=client_cm):
        with pytest.raises(httpx.HTTPStatusError):
            await provider.summarize_resume("cv text")
