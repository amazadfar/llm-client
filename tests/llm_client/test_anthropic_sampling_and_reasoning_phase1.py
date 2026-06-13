"""Phase 1 hotfix tests for Anthropic model-aware sampling and explicit reasoning-control
handling.

Audit findings:
- A-API-002: generic (OpenAI-style) ``reasoning``/``reasoning_effort`` controls were
  silently dropped; they must be rejected (or translated) explicitly.
- A-API-014: the package-default temperature was injected unconditionally; under extended
  thinking, temperature must be unset/1, so the default must be omitted and an explicit
  incompatible temperature rejected.
"""

from __future__ import annotations

import pytest

from llm_client.providers.anthropic import AnthropicProvider


def _provider(default_temperature: float | None = 0.7) -> AnthropicProvider:
    provider = AnthropicProvider.__new__(AnthropicProvider)
    provider.default_temperature = default_temperature
    return provider


# --- A-API-002: explicit rejection of generic reasoning controls --------------------

def test_sanitize_rejects_reasoning_effort() -> None:
    with pytest.raises(ValueError, match="reasoning_effort"):
        AnthropicProvider._sanitize_request_kwargs({"reasoning_effort": "high"})


def test_sanitize_rejects_reasoning_object() -> None:
    with pytest.raises(ValueError, match="reasoning"):
        AnthropicProvider._sanitize_request_kwargs({"reasoning": {"effort": "high"}})


def test_sanitize_ignores_none_reasoning_controls() -> None:
    # The engine forwards reasoning=None / reasoning_effort=None unconditionally; those
    # must not raise (they are simply unset).
    out = AnthropicProvider._sanitize_request_kwargs(
        {"reasoning": None, "reasoning_effort": None, "top_p": 0.9}
    )
    assert out == {"top_p": 0.9}


# --- A-API-014: model-aware temperature --------------------------------------------

def test_default_temperature_injected_without_thinking() -> None:
    provider = _provider(0.7)
    params: dict[str, object] = {}
    provider._apply_sampling_temperature(params, None, {})
    assert params["temperature"] == 0.7


def test_default_temperature_omitted_under_thinking() -> None:
    provider = _provider(0.7)
    params: dict[str, object] = {}
    provider._apply_sampling_temperature(
        params, None, {"thinking": {"type": "enabled", "budget_tokens": 4096}}
    )
    assert "temperature" not in params


def test_explicit_incompatible_temperature_rejected_under_thinking() -> None:
    provider = _provider(0.7)
    with pytest.raises(ValueError, match="thinking requires temperature"):
        provider._apply_sampling_temperature(
            {}, 0.2, {"thinking": {"type": "enabled", "budget_tokens": 4096}}
        )


def test_temperature_one_allowed_under_thinking() -> None:
    provider = _provider(0.7)
    params: dict[str, object] = {}
    provider._apply_sampling_temperature(
        params, 1.0, {"thinking": {"type": "enabled", "budget_tokens": 4096}}
    )
    assert params["temperature"] == 1.0


def test_explicit_temperature_passed_without_thinking() -> None:
    provider = _provider(0.7)
    params: dict[str, object] = {}
    provider._apply_sampling_temperature(params, 0.2, {})
    assert params["temperature"] == 0.2


def test_no_default_temperature_means_no_injection() -> None:
    provider = _provider(None)
    params: dict[str, object] = {}
    provider._apply_sampling_temperature(params, None, {})
    assert "temperature" not in params
