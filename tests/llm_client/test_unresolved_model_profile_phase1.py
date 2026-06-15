"""Phase 1 tests for the conservative unresolved-model fallback (audit C-001 / C-005).

An explicit but unrecognized model ID must be attemptable: ``ModelProfile.get`` returns a
conservative profile that fabricates no capabilities, modalities, lifecycle, limits, or
prices (cost is reported unknown, never zero). A strict switch restores the old raising
behavior.
"""

from __future__ import annotations

import pytest

from llm_client.models import ModelProfile

_UNKNOWN = "totally-made-up-model-zzz-2099"


def test_unknown_model_returns_conservative_profile() -> None:
    profile = ModelProfile.get(_UNKNOWN)
    assert profile.key == _UNKNOWN
    assert profile.model_name == _UNKNOWN
    assert profile.resolved is False
    assert profile.category == "completions"


def test_unresolved_profile_infers_no_capabilities_or_prices() -> None:
    profile = ModelProfile.get(_UNKNOWN)
    assert profile.usage_costs == {}
    assert profile.rate_limits == {}
    assert profile.pricing_features == {}
    assert profile.reasoning_model is False
    assert profile.reasoning_efforts == []
    assert profile.function_calling_support is False
    assert profile.vision_input_support is None
    assert profile.audio_input_support is None
    assert profile.file_input_support is None
    assert profile.deprecated is False
    assert profile.replacement is None


def test_unresolved_profile_reports_unknown_cost_not_zero() -> None:
    profile = ModelProfile.get(_UNKNOWN)
    parsed = profile.parse_usage({"input_tokens": 10, "output_tokens": 5, "total_tokens": 15})
    assert parsed["input_tokens"] == 10
    assert parsed["output_tokens"] == 5
    assert parsed["total_tokens"] == 15
    assert parsed["input_cost"] is None
    assert parsed["output_cost"] is None
    assert parsed["total_cost"] is None
    assert parsed["cost_status"] == "unknown"


def test_unresolved_profile_can_still_count_tokens() -> None:
    profile = ModelProfile.get(_UNKNOWN)
    assert profile.count_tokens("hello world") > 0


def test_unresolved_profiles_are_not_registered() -> None:
    assert _UNKNOWN not in ModelProfile._registry
    # Two lookups must not collide on the duplicate-key guard.
    first = ModelProfile.get(_UNKNOWN)
    second = ModelProfile.get(_UNKNOWN)
    assert first.key == second.key == _UNKNOWN
    assert _UNKNOWN not in ModelProfile._registry


def test_known_model_remains_resolved() -> None:
    profile = ModelProfile.get("gpt-5-mini")
    assert profile.resolved is True
    assert profile.usage_costs  # real prices present


def test_strict_mode_restores_raising() -> None:
    ModelProfile.strict_unknown_models = True
    try:
        with pytest.raises(ValueError, match="Unknown model key"):
            ModelProfile.get(_UNKNOWN)
    finally:
        ModelProfile.strict_unknown_models = False
