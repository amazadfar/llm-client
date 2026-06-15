"""Phase 4 tests: typed request contracts, shared-field + typed-option forwarding, and
requested/actual service-tier tracking.

Audit O-API-006/007, A-API-009, plus the shared/namespaced options architecture
(Decision 5).
"""

from __future__ import annotations

from typing import Any

import pytest

from telic.engine import ExecutionEngine, RetryConfig
from telic.providers.types import CompletionResult, Message, StreamEvent, StreamEventType, Usage
from telic.request_options import AnthropicRequestOptions, OpenAIRequestOptions
from telic.spec import RequestSpec
from tests.telic.fakes import FakeModel, ScriptedProvider, ok_result


class ControlAwareProvider:
    """Provider that declares the Phase 4 controls (shared + a mix of provider-specific)."""

    def __init__(self, *, actual_tier: str | None = None) -> None:
        self.model = FakeModel()
        self.model_name = "gpt-5-mini"
        self._actual_tier = actual_tier
        self.calls: list[dict[str, Any]] = []

    async def complete(
        self,
        messages,
        *,
        service_tier: str | None = None,
        top_p: float | None = None,
        metadata: dict[str, Any] | None = None,
        effort: str | None = None,
        thinking: dict[str, Any] | None = None,
        verbosity: str | None = None,
        **kwargs: Any,
    ) -> CompletionResult:
        self.calls.append({
            "service_tier": service_tier, "top_p": top_p, "metadata": metadata,
            "effort": effort, "thinking": thinking, "verbosity": verbosity, "extra": kwargs,
        })
        raw = {"service_tier": self._actual_tier} if self._actual_tier else None
        return CompletionResult(content="ok", usage=Usage(), model=self.model_name, status=200, raw_response=raw)

    async def stream(self, messages, **kwargs):
        yield StreamEvent(type=StreamEventType.DONE, data=ok_result("ok"))

    def count_tokens(self, content: Any) -> int:
        return 1

    def parse_usage(self, raw_usage: dict[str, Any]) -> Usage:
        return Usage()

    async def close(self) -> None:
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc) -> None:
        return None


def _spec(**overrides: Any) -> RequestSpec:
    base: dict[str, Any] = {"provider": "openai", "model": "gpt-5-mini", "messages": [Message.user("hi")]}
    base.update(overrides)
    return RequestSpec(**base)


def _engine(provider) -> ExecutionEngine:
    return ExecutionEngine(provider=provider, retry=RetryConfig(attempts=1, backoff=0.0))


# --- typed contracts -----------------------------------------------------------------

def test_requestspec_roundtrip_and_v2_decode() -> None:
    spec = _spec(
        service_tier="priority", top_p=0.9, metadata={"k": "v"},
        openai_options=OpenAIRequestOptions(endpoint="responses", verbosity="low"),
        anthropic_options=AnthropicRequestOptions(effort="high", thinking={"type": "adaptive"}),
    )
    back = RequestSpec.from_dict(spec.to_dict())
    assert back.schema_version == 3
    assert back.service_tier == "priority" and back.top_p == 0.9 and back.metadata == {"k": "v"}
    assert back.openai_options.verbosity == "low"
    assert back.anthropic_options.effort == "high"
    # A v2 document (without the new fields) still decodes.
    v2 = {"schema_version": 2, "provider": "openai", "model": "gpt-5-mini",
          "messages": [{"role": "user", "content": "hi"}]}
    old = RequestSpec.from_dict(v2)
    assert old.service_tier is None and old.openai_options is None


# --- shared-field + typed-option forwarding -----------------------------------------

@pytest.mark.asyncio
async def test_shared_fields_forwarded() -> None:
    provider = ControlAwareProvider()
    await _engine(provider).complete(_spec(service_tier="flex", top_p=0.8, metadata={"a": 1}))
    call = provider.calls[0]
    assert call["service_tier"] == "flex" and call["top_p"] == 0.8 and call["metadata"] == {"a": 1}


@pytest.mark.asyncio
async def test_typed_options_routed_to_declaring_params() -> None:
    provider = ControlAwareProvider()
    spec = _spec(
        anthropic_options=AnthropicRequestOptions(effort="high", thinking={"type": "adaptive"}),
        openai_options=OpenAIRequestOptions(verbosity="low", endpoint="responses"),
    )
    await _engine(provider).complete(spec)
    call = provider.calls[0]
    assert call["effort"] == "high"
    assert call["thinking"] == {"type": "adaptive"}
    assert call["verbosity"] == "low"
    # routing-only hint is not forwarded as a kwarg
    assert "endpoint" not in call["extra"]


@pytest.mark.asyncio
async def test_controls_not_forwarded_to_undeclaring_provider() -> None:
    provider = ScriptedProvider(complete_script=[ok_result("ok")])
    spec = _spec(service_tier="priority", top_p=0.9,
                 anthropic_options=AnthropicRequestOptions(effort="high"))
    result = await _engine(provider).complete(spec)
    assert result.ok
    forwarded = provider.complete_calls[0]["kwargs"]
    for key in ("service_tier", "top_p", "effort"):
        assert key not in forwarded


# --- requested vs actual service tier ------------------------------------------------

@pytest.mark.asyncio
async def test_requested_and_actual_service_tier_tracked() -> None:
    provider = ControlAwareProvider(actual_tier="priority")
    result = await _engine(provider).complete(_spec(service_tier="auto"))
    assert result.requested_service_tier == "auto"
    assert result.service_tier == "priority"


@pytest.mark.asyncio
async def test_requested_tier_recorded_without_actual() -> None:
    provider = ControlAwareProvider(actual_tier=None)
    result = await _engine(provider).complete(_spec(service_tier="flex"))
    assert result.requested_service_tier == "flex"
    assert result.service_tier is None
