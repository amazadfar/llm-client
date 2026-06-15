"""Anthropic model-aware sampling and reasoning-control handling.

Audit findings A-API-002 / A-API-003 / A-API-014. Phase 1 introduced model-aware
temperature handling and explicit (non-silent) reasoning-control handling; Phase 4
upgraded the reasoning handling from outright rejection to model-aware translation of the
generic ``reasoning_effort`` into Anthropic's ``output_config.effort``.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from llm_client.providers.anthropic import AnthropicProvider


def _provider(default_temperature: float | None = 0.7, *, efforts=("low", "medium", "high")) -> AnthropicProvider:
    provider = AnthropicProvider.__new__(AnthropicProvider)
    provider.default_temperature = default_temperature
    provider._model = SimpleNamespace(
        key="claude-sonnet-4-6", model_name="claude-sonnet-4-6", reasoning_efforts=list(efforts)
    )
    return provider


# --- A-API-002 / A-API-003: model-aware reasoning_effort -> output_config.effort -----

def test_reasoning_effort_translated_to_output_config() -> None:
    provider = _provider()
    params: dict[str, object] = {}
    provider._apply_anthropic_request_controls(
        params, temperature=None, thinking=None, effort=None, reasoning_effort="high",
        reasoning=None, speed=None, service_tier=None, top_p=None, metadata=None, container=None,
    )
    assert params["output_config"] == {"effort": "high"}


def test_generic_reasoning_object_effort_translated() -> None:
    provider = _provider()
    assert provider._resolve_anthropic_effort(None, None, {"effort": "medium"}) == "medium"


def test_explicit_anthropic_effort_wins() -> None:
    provider = _provider()
    assert provider._resolve_anthropic_effort("low", "high", None) == "low"


def test_unsupported_effort_rejected() -> None:
    provider = _provider(efforts=("low", "medium", "high"))
    with pytest.raises(ValueError, match="not supported"):
        provider._resolve_anthropic_effort("xhigh", None, None)


def test_effort_on_non_reasoning_model_rejected() -> None:
    provider = _provider(efforts=())
    with pytest.raises(ValueError, match="does not support a reasoning effort"):
        provider._resolve_anthropic_effort("high", None, None)


def test_no_effort_means_no_output_config() -> None:
    provider = _provider()
    assert provider._resolve_anthropic_effort(None, None, None) is None


def test_sanitize_keeps_non_none_kwargs() -> None:
    out = AnthropicProvider._sanitize_request_kwargs({"top_p": 0.9, "dropme": None})
    assert out == {"top_p": 0.9}


# --- A-API-010: fast-mode (speed) scope ---------------------------------------------

def test_speed_fast_rejected_when_catalog_does_not_advertise_it() -> None:
    provider = _provider()
    provider._model.service = {"speed_modes": []}
    with pytest.raises(ValueError, match="speed='fast'"):
        provider._validate_anthropic_speed("fast")


def test_speed_fast_allowed_when_catalog_advertises_it() -> None:
    provider = _provider()
    provider._model = SimpleNamespace(
        key="claude-opus-4-8",
        model_name="claude-opus-4-8",
        reasoning_efforts=["low"],
        service={"speed_modes": ["fast"]},
    )
    provider._validate_anthropic_speed("fast")  # must not raise


# --- A-API-014: model-aware temperature ---------------------------------------------

def test_default_temperature_injected_without_thinking() -> None:
    provider = _provider(0.7)
    params: dict[str, object] = {}
    provider._apply_sampling_temperature(params, None, None)
    assert params["temperature"] == 0.7


def test_default_temperature_omitted_under_thinking() -> None:
    provider = _provider(0.7)
    params: dict[str, object] = {}
    provider._apply_sampling_temperature(params, None, {"type": "enabled", "budget_tokens": 4096})
    assert "temperature" not in params


def test_explicit_incompatible_temperature_rejected_under_thinking() -> None:
    provider = _provider(0.7)
    with pytest.raises(ValueError, match="thinking requires temperature"):
        provider._apply_sampling_temperature({}, 0.2, {"type": "enabled", "budget_tokens": 4096})


def test_temperature_one_allowed_under_thinking() -> None:
    provider = _provider(0.7)
    params: dict[str, object] = {}
    provider._apply_sampling_temperature(params, 1.0, {"type": "enabled", "budget_tokens": 4096})
    assert params["temperature"] == 1.0


def test_explicit_temperature_passed_without_thinking() -> None:
    provider = _provider(0.7)
    params: dict[str, object] = {}
    provider._apply_sampling_temperature(params, 0.2, None)
    assert params["temperature"] == 0.2


def test_no_default_temperature_means_no_injection() -> None:
    provider = _provider(None)
    params: dict[str, object] = {}
    provider._apply_sampling_temperature(params, None, None)
    assert "temperature" not in params
