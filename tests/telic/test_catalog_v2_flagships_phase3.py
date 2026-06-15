"""Phase 3 golden tests: current-flagship catalog data and the specific audit
corrections applied during the v1->v2 migration.

Locks the source-backed values for the models added in Phase 3 (audit O-CAT-001 /
A-CAT-001 / A-CAT-002b) plus the targeted fixes (fast-mode scope, cache minimums,
Claude 3 Haiku retirement, gpt-oss unknown pricing, default-model migration).
"""

from __future__ import annotations

import pytest

from telic.model_catalog import clear_model_catalog_cache, get_default_model_catalog


@pytest.fixture(scope="module")
def catalog():
    clear_model_catalog_cache()
    cat = get_default_model_catalog()
    yield cat
    clear_model_catalog_cache()


def _rate(model, *, metric, mode="standard", tier=None, speed=None, threshold=False):
    for dim in model.pricing.dimensions:
        if dim.metric != metric or dim.mode != mode or dim.tier != tier or dim.speed != speed:
            continue
        if threshold != (dim.threshold is not None):
            continue
        return dim.rate
    return "MISSING"


# --- new Anthropic flagships ---------------------------------------------------------

def test_claude_opus_4_8_present_and_priced(catalog) -> None:
    m = catalog.get("claude-opus-4-8")
    assert m.lifecycle.status == "active"
    assert m.context_window == 1_000_000 and m.max_output == 128_000
    assert m.caching["min_cacheable_tokens"] == 1024
    assert _rate(m, metric="input") == 5.0
    assert _rate(m, metric="output") == 25.0
    assert _rate(m, metric="cache_read") == 0.5
    assert _rate(m, metric="input", mode="batch") == 2.5
    assert (m.service or {}).get("speed_modes") == ["fast"]
    assert _rate(m, metric="input", speed="fast") == 10.0
    assert _rate(m, metric="output", speed="fast") == 50.0
    assert m.reasoning_incompatible_params == ("temperature", "top_p", "top_k")


def test_claude_fable_5_present_and_priced(catalog) -> None:
    m = catalog.get("claude-fable-5")
    assert m.lifecycle.status == "active"
    assert m.caching["min_cacheable_tokens"] == 2048  # Fable 5 / Sonnet 4.6 tier
    assert _rate(m, metric="input") == 10.0
    assert _rate(m, metric="output") == 50.0
    assert "30-day data retention" in (m.service or {}).get("availability_notes", "")


def test_mythos_models_present(catalog) -> None:
    m5 = catalog.get("claude-mythos-5")
    assert _rate(m5, metric="input") == 10.0 and _rate(m5, metric="output") == 50.0
    preview = catalog.get("claude-mythos-preview")
    assert preview.lifecycle.status == "preview"
    assert preview.lifecycle.retires_on == "2026-06-30"
    assert preview.lifecycle.replacement == "claude-mythos-5"


# --- new OpenAI flagships ------------------------------------------------------------

def test_gpt_5_5_full_tiered_pricing(catalog) -> None:
    m = catalog.get("gpt-5.5")
    assert m.pricing.completeness == "complete"
    assert m.context_window == 400_000
    assert "gpt-5.5-2026-04-23" in m.snapshots
    # standard
    assert _rate(m, metric="input") == 5.0
    assert _rate(m, metric="cached_input") == 0.5
    assert _rate(m, metric="output") == 30.0
    # batch / flex
    assert _rate(m, metric="input", mode="batch") == 2.5
    assert _rate(m, metric="input", tier="flex") == 2.5
    # priority
    assert _rate(m, metric="input", tier="priority") == 12.5
    assert _rate(m, metric="output", tier="priority") == 75.0
    # long-context (> 272K): 2x input, 1.5x output
    assert _rate(m, metric="input", threshold=True) == 10.0
    assert _rate(m, metric="output", threshold=True) == 45.0
    assert m.service["tiers"] == ["standard", "flex", "priority", "scale"]
    assert m.reasoning_efforts == ("none", "low", "medium", "high", "xhigh")


def test_gpt_5_5_pro_partial_pricing(catalog) -> None:
    m = catalog.get("gpt-5.5-pro")
    # priority tier rates are not published -> partial, those rows null (Phase 0 D2)
    assert m.pricing.completeness == "partial"
    assert _rate(m, metric="input") == 30.0
    assert _rate(m, metric="output") == 180.0
    assert _rate(m, metric="input", tier="priority") is None
    assert m.endpoints == ("responses", "batch")


# --- targeted audit corrections ------------------------------------------------------

def test_fast_mode_scope_corrected(catalog) -> None:
    assert (catalog.get("claude-opus-4-6").service or {}).get("speed_modes") == ["fast"]
    assert (catalog.get("claude-opus-4-7").service or {}).get("speed_modes") == ["fast"]
    assert (catalog.get("claude-opus-4-8").service or {}).get("speed_modes") == ["fast"]
    assert "pending removal" in catalog.get("claude-opus-4-6").service["availability_notes"]


def test_cache_minimums_corrected(catalog) -> None:
    assert catalog.get("claude-opus-4-7").caching["min_cacheable_tokens"] == 4096
    assert catalog.get("claude-opus-4-8").caching["min_cacheable_tokens"] == 1024
    assert catalog.get("claude-haiku-4-5").caching["min_cacheable_tokens"] == 4096
    assert catalog.get("claude-sonnet-4-6").caching["min_cacheable_tokens"] == 2048


def test_claude_3_haiku_retired(catalog) -> None:
    m = catalog.get("claude-3-haiku")
    assert m.lifecycle.status == "retired"
    assert m.lifecycle.retires_on == "2026-04-20"
    assert m.lifecycle.replacement == "claude-haiku-4-5"
    assert m.deprecated is True  # flat projection


def test_gpt_oss_completions_unknown_not_zero(catalog) -> None:
    for key in ("gpt-oss-120b", "gpt-oss-20b"):
        m = catalog.get(key)
        assert m.cost_status == "unknown"
        assert m.usage_costs == {}  # never a fabricated zero


def test_default_models_migrated(catalog) -> None:
    assert catalog.default_key_for_provider("openai") == "gpt-5.4-mini"
    assert catalog.default_key_for_provider("anthropic") == "claude-sonnet-4-6"
    assert catalog.default_key_for_provider("google") == "gemini-2.0-flash"


def test_gemini_carried_as_is(catalog) -> None:
    # Gemini is migrated mechanically (not audited); models stay present and priced.
    for key in ("gemini-2.0-flash", "gemini-3-flash", "gemini-3-pro", "gemini-1.5-pro"):
        m = catalog.get(key)
        assert m.provider == "google"
        assert m.usage_costs.get("input") is not None
