"""Tests for local-concurrency naming: ``concurrent_complete`` and the deprecated
``batch_complete`` alias (Phase 1, Decision D6).

``batch_complete`` implied provider Batch API semantics but only ever performed local
bounded concurrency in the standard tier. It is renamed to ``concurrent_complete`` and
retained as a behaviorally-identical, deprecated alias.
"""

from __future__ import annotations

import warnings

import pytest

from llm_client.engine import ExecutionEngine, RetryConfig
from llm_client.providers.types import Message
from llm_client.spec import RequestSpec
from tests.llm_client.fakes import ScriptedProvider, ok_result


def _spec(text: str) -> RequestSpec:
    return RequestSpec(provider="openai", model="gpt-5-mini", messages=[Message.user(text)])


@pytest.mark.asyncio
async def test_concurrent_complete_returns_results_in_order() -> None:
    provider = ScriptedProvider(
        complete_script=[ok_result("a"), ok_result("b"), ok_result("c")]
    )
    engine = ExecutionEngine(provider=provider, retry=RetryConfig(attempts=1, backoff=0.0))

    results = await engine.concurrent_complete([_spec("1"), _spec("2"), _spec("3")])

    assert [r.content for r in results] == ["a", "b", "c"]
    assert all(r.ok for r in results)


@pytest.mark.asyncio
async def test_batch_complete_is_deprecated_alias() -> None:
    provider = ScriptedProvider(complete_script=[ok_result("a"), ok_result("b")])
    engine = ExecutionEngine(provider=provider, retry=RetryConfig(attempts=1, backoff=0.0))

    with pytest.warns(DeprecationWarning, match="concurrent_complete"):
        results = await engine.batch_complete([_spec("1"), _spec("2")])

    assert [r.content for r in results] == ["a", "b"]


@pytest.mark.asyncio
async def test_concurrent_complete_emits_no_deprecation_warning() -> None:
    provider = ScriptedProvider(complete_script=[ok_result("a")])
    engine = ExecutionEngine(provider=provider, retry=RetryConfig(attempts=1, backoff=0.0))

    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        results = await engine.concurrent_complete([_spec("1")])

    assert results[0].content == "a"


@pytest.mark.asyncio
async def test_max_concurrency_override_is_respected() -> None:
    provider = ScriptedProvider(complete_script=[ok_result("a"), ok_result("b")])
    engine = ExecutionEngine(provider=provider, retry=RetryConfig(attempts=1, backoff=0.0))

    results = await engine.concurrent_complete(
        [_spec("1"), _spec("2")], max_concurrency=1
    )

    assert [r.content for r in results] == ["a", "b"]
