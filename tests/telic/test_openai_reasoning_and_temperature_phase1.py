"""Phase 1 hotfix tests for OpenAI reasoning-object preservation and stream/non-stream
temperature parity.

Audit findings:
- O-API-003: the Responses ``reasoning`` object was collapsed to ``{"effort": ...}``,
  discarding valid fields such as ``summary``.
- O-API-005: streaming requests inserted ``temperature`` directly, bypassing the
  GPT-5-family omission applied to non-streaming requests.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from telic.providers.openai import OpenAIProvider
from telic.providers.types import Message
from tests.telic.fakes import FakeModel


class _LimitContext:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc) -> bool:
        return False


class _NoopLimiter:
    def limit(self, **kwargs):
        return _LimitContext()


class _AsyncResponseStreamManager:
    def __init__(self, events: list[object]) -> None:
        self._events = list(events)
        self._index = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._index >= len(self._events):
            raise StopAsyncIteration
        item = self._events[self._index]
        self._index += 1
        return item


def _reasoning_provider(model_name: str = "gpt-5") -> OpenAIProvider:
    provider = OpenAIProvider.__new__(OpenAIProvider)
    provider._model = SimpleNamespace(
        key=model_name,
        model_name=model_name,
        reasoning_model=True,
        reasoning_efforts=["low", "medium", "high"],
    )
    provider.limiter = _NoopLimiter()
    return provider


def _temp_provider(model_name: str) -> OpenAIProvider:
    provider = OpenAIProvider.__new__(OpenAIProvider)
    provider._model = FakeModel(key=model_name, model_name=model_name)
    provider.use_responses_api = True
    provider.limiter = _NoopLimiter()
    return provider


# --- O-API-003: reasoning object preservation ---------------------------------------

def test_responses_reasoning_object_preserves_extra_fields() -> None:
    provider = _reasoning_provider("gpt-5")
    params = {"reasoning": {"effort": "high", "summary": "auto"}}

    out = provider._check_reasoning_params(params, "responses")

    assert out["reasoning"] == {"effort": "high", "summary": "auto"}


def test_responses_reasoning_object_normalizes_effort_but_keeps_summary() -> None:
    provider = _reasoning_provider("gpt-5")
    # reasoning_effort and a reasoning object carrying summary; effort must agree/merge.
    params = {"reasoning": {"effort": "medium", "summary": "detailed"}}

    out = provider._check_reasoning_params(params, "responses")

    assert out["reasoning"]["effort"] == "medium"
    assert out["reasoning"]["summary"] == "detailed"


def test_completions_reasoning_object_collapses_to_effort() -> None:
    provider = _reasoning_provider("gpt-5")
    params = {"reasoning": {"effort": "high", "summary": "auto"}}

    out = provider._check_reasoning_params(params, "completions")

    assert out["reasoning_effort"] == "high"
    assert "reasoning" not in out


# --- O-API-005: stream/non-stream temperature parity --------------------------------

@pytest.mark.asyncio
async def test_stream_responses_omits_non_default_temperature_for_gpt5() -> None:
    provider = _temp_provider("gpt-5")
    captured: dict[str, object] = {}

    def _responses_stream(**kwargs):
        captured.update(kwargs)
        return _AsyncResponseStreamManager([])

    provider.client = SimpleNamespace(responses=SimpleNamespace(stream=_responses_stream))

    _ = [event async for event in provider.stream([Message.user("hi")], temperature=0.2)]

    assert "temperature" not in captured


@pytest.mark.asyncio
async def test_stream_responses_keeps_temperature_for_non_gpt5() -> None:
    provider = _temp_provider("gpt-4o-mini")
    captured: dict[str, object] = {}

    def _responses_stream(**kwargs):
        captured.update(kwargs)
        return _AsyncResponseStreamManager([])

    provider.client = SimpleNamespace(responses=SimpleNamespace(stream=_responses_stream))

    _ = [event async for event in provider.stream([Message.user("hi")], temperature=0.2)]

    assert captured.get("temperature") == 0.2
