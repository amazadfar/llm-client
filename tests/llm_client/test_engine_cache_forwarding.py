"""Regression tests for engine forwarding of first-class cache/include controls.

Audit findings O-API-002 / O-API-005 / T-003 (and A-API-008 in part): ``RequestSpec``
exposes ``include``, ``prompt_cache_key`` and ``prompt_cache_retention`` as stable fields,
but ``ExecutionEngine`` never passed them to the provider call. Providers that support them
(OpenAI) therefore silently never received them. Forwarding must be signature-aware so that
providers which do not declare the parameters (Anthropic) are unaffected.
"""

from __future__ import annotations

from typing import Any

import pytest

from llm_client.engine import ExecutionEngine, RetryConfig
from llm_client.providers.types import (
    CompletionResult,
    Message,
    StreamEvent,
    StreamEventType,
    Usage,
)
from llm_client.spec import RequestSpec
from tests.llm_client.fakes import FakeModel, ScriptedProvider, ok_result


class CacheAwareProvider:
    """Provider that explicitly declares the cache/include parameters (like OpenAI)."""

    def __init__(self, *, model_name: str = "gpt-5-mini") -> None:
        self.model = FakeModel(key=model_name, model_name=model_name)
        self.model_name = model_name
        self.complete_calls: list[dict[str, Any]] = []
        self.stream_calls: list[dict[str, Any]] = []

    async def complete(
        self,
        messages,
        *,
        include: list[str] | None = None,
        prompt_cache_key: str | None = None,
        prompt_cache_retention: str | None = None,
        **kwargs: Any,
    ) -> CompletionResult:
        self.complete_calls.append(
            {
                "include": include,
                "prompt_cache_key": prompt_cache_key,
                "prompt_cache_retention": prompt_cache_retention,
                "extra": kwargs,
            }
        )
        return ok_result("ok", model=self.model_name)

    async def stream(
        self,
        messages,
        *,
        include: list[str] | None = None,
        prompt_cache_key: str | None = None,
        prompt_cache_retention: str | None = None,
        **kwargs: Any,
    ):
        self.stream_calls.append(
            {
                "include": include,
                "prompt_cache_key": prompt_cache_key,
                "prompt_cache_retention": prompt_cache_retention,
                "extra": kwargs,
            }
        )
        yield StreamEvent(type=StreamEventType.TOKEN, data="hi")
        yield StreamEvent(type=StreamEventType.DONE, data=ok_result("hi", model=self.model_name))

    def count_tokens(self, content: Any) -> int:
        return self.model.count_tokens(content)

    def parse_usage(self, raw_usage: dict[str, Any]) -> Usage:
        return Usage()

    async def close(self) -> None:
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        return None


def _spec(**overrides: Any) -> RequestSpec:
    base: dict[str, Any] = {
        "provider": "openai",
        "model": "gpt-5-mini",
        "messages": [Message.user("hello")],
    }
    base.update(overrides)
    return RequestSpec(**base)


@pytest.mark.asyncio
async def test_complete_forwards_cache_controls_to_supporting_provider() -> None:
    provider = CacheAwareProvider()
    engine = ExecutionEngine(provider=provider, retry=RetryConfig(attempts=1, backoff=0.0))

    spec = _spec(
        include=["reasoning.encrypted_content"],
        prompt_cache_key="route-key-1",
        prompt_cache_retention="24h",
    )
    result = await engine.complete(spec)

    assert result.ok is True
    assert provider.complete_calls[0]["include"] == ["reasoning.encrypted_content"]
    assert provider.complete_calls[0]["prompt_cache_key"] == "route-key-1"
    assert provider.complete_calls[0]["prompt_cache_retention"] == "24h"


@pytest.mark.asyncio
async def test_stream_forwards_cache_controls_to_supporting_provider() -> None:
    provider = CacheAwareProvider()
    engine = ExecutionEngine(provider=provider, retry=RetryConfig(attempts=1, backoff=0.0))

    spec = _spec(
        include=["reasoning.encrypted_content"],
        prompt_cache_key="route-key-2",
        prompt_cache_retention="in_memory",
    )
    events = [event async for event in engine.stream(spec)]

    assert events  # stream produced events
    assert provider.stream_calls[0]["include"] == ["reasoning.encrypted_content"]
    assert provider.stream_calls[0]["prompt_cache_key"] == "route-key-2"
    assert provider.stream_calls[0]["prompt_cache_retention"] == "in_memory"


@pytest.mark.asyncio
async def test_cache_controls_not_forwarded_to_provider_without_params() -> None:
    """A provider that uses ``**kwargs`` (no declared params, like Anthropic) must not
    receive these fields, and must not error."""
    provider = ScriptedProvider(complete_script=[ok_result("ok")])
    engine = ExecutionEngine(provider=provider, retry=RetryConfig(attempts=1, backoff=0.0))

    spec = _spec(prompt_cache_key="key", include=["x"], prompt_cache_retention="24h")
    result = await engine.complete(spec)

    assert result.ok is True
    forwarded = provider.complete_calls[0]["kwargs"]
    assert "prompt_cache_key" not in forwarded
    assert "include" not in forwarded
    assert "prompt_cache_retention" not in forwarded


@pytest.mark.asyncio
async def test_extra_value_takes_precedence_over_spec_field() -> None:
    provider = CacheAwareProvider()
    engine = ExecutionEngine(provider=provider, retry=RetryConfig(attempts=1, backoff=0.0))

    # Same key supplied via both the first-class field and the extra escape hatch.
    spec = _spec(
        prompt_cache_key="from-field",
        extra={"prompt_cache_key": "from-extra"},
    )
    result = await engine.complete(spec)

    assert result.ok is True
    assert provider.complete_calls[0]["prompt_cache_key"] == "from-extra"
