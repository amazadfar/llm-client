"""Phase 2 tests: catalog v2 schema, version-aware loader, structured fields, flat
projection, alias/snapshot identity, unknown-vs-zero pricing, and override migration.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from telic.models import ModelProfile
from telic.model_catalog import (
    Lifecycle,
    Pricing,
    PricingDimension,
    clear_model_catalog_cache,
    get_default_model_catalog,
    load_model_catalog,
    metadata_from_profile,
    model_profile_from_metadata,
)


def _v2_model(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "key": "claude-sonnet-4-6",
        "provider": "anthropic",
        "family": "claude-sonnet",
        "display_name": "Claude Sonnet 4.6",
        "model_name": "claude-sonnet-4-6",
        "release_channel": "ga",
        "aliases": ["claude-4-6-sonnet"],
        "snapshots": ["claude-sonnet-4-6-20251114"],
        "category": "completions",
        "encoding": "cl100k_base",
        "streaming": True,
        "lifecycle": {"status": "active"},
        "endpoints": ["messages", "batch"],
        "modalities": {"input": ["text", "image"], "output": ["text"]},
        "limits": {"context_window": 1_000_000, "max_output": 64_000},
        "reasoning": {
            "supported": True,
            "efforts": ["low", "medium", "high"],
            "default_effort": "medium",
            "incompatible_params": ["temperature"],
        },
        "caching": {
            "supported": True,
            "min_cacheable_tokens": 2048,
            "ttls": ["5m", "1h"],
            "multipliers": {"cache_read": 0.1, "cache_write_5m": 1.25, "cache_write_1h": 2.0},
        },
        "service": {"tiers": ["standard", "priority"], "speed_modes": [], "batch_eligible": True},
        "tools": {"client_tools": True, "structured_outputs": True, "server_tools": ["web_search"]},
        "pricing": {
            "completeness": "complete",
            "dimensions": [
                {"metric": "input", "unit": "million_tokens", "rate": 3.0},
                {"metric": "output", "unit": "million_tokens", "rate": 15.0},
                {"metric": "output", "unit": "million_tokens", "speed": "fast", "rate": 30.0},
                {"metric": "input", "unit": "million_tokens", "mode": "batch", "rate": 1.5},
            ],
        },
        "rate_limits": {"tkn_per_min": 120_000},
    }
    base.update(overrides)
    return base


def _v2_doc(models: list[dict[str, Any]], defaults: dict | None = None) -> dict[str, Any]:
    return {
        "version": 2,
        "defaults": defaults or {"anthropic": {"completions": "claude-sonnet-4-6"}},
        "models": models,
    }


def _write(tmp_path: Path, name: str, doc: dict[str, Any]) -> str:
    path = tmp_path / name
    path.write_text(json.dumps(doc), encoding="utf-8")
    return str(path)


def _load(path: str, **kwargs: Any):
    clear_model_catalog_cache()
    return load_model_catalog(path, **kwargs)


# --- schema validation ---------------------------------------------------------------

def test_v2_valid_document_loads(tmp_path: Path) -> None:
    cat = _load(_write(tmp_path, "c.json", _v2_doc([_v2_model()])))
    m = cat.get("claude-sonnet-4-6")
    assert m.schema_version == 2
    assert m.family == "claude-sonnet"
    assert m.endpoints == ("messages", "batch")


def test_v2_rejects_invalid_category(tmp_path: Path) -> None:
    bad = _v2_doc([_v2_model(category="chat")])
    with pytest.raises(ValueError, match="Invalid model catalog document"):
        _load(_write(tmp_path, "bad.json", bad))


def test_v2_rejects_missing_required_lifecycle(tmp_path: Path) -> None:
    model = _v2_model()
    del model["lifecycle"]
    with pytest.raises(ValueError, match="Invalid model catalog document"):
        _load(_write(tmp_path, "bad.json", _v2_doc([model])))


def test_v2_rejects_unknown_field(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Invalid model catalog document"):
        _load(_write(tmp_path, "bad.json", _v2_doc([_v2_model(bogus_field=1)])))


# --- flat projection (backward compatibility) ----------------------------------------

def test_flat_projection_from_v2(tmp_path: Path) -> None:
    m = _load(_write(tmp_path, "c.json", _v2_doc([_v2_model()]))).get("claude-sonnet-4-6")
    assert m.vision_input is True
    assert m.audio_input is False
    assert m.reasoning is True
    assert m.reasoning_efforts == ("low", "medium", "high")
    assert m.tool_calling is True
    assert m.structured_outputs is True
    assert m.context_window == 1_000_000
    assert m.max_output == 64_000
    # per-token cost projection from million-token rates
    assert m.usage_costs["input"] == pytest.approx(3.0 / 1_000_000)
    assert m.usage_costs["output"] == pytest.approx(15.0 / 1_000_000)
    assert m.usage_costs["batch_input"] == pytest.approx(1.5 / 1_000_000)


def test_v2_structured_fields_preserved(tmp_path: Path) -> None:
    m = _load(_write(tmp_path, "c.json", _v2_doc([_v2_model()]))).get("claude-sonnet-4-6")
    assert m.reasoning_incompatible_params == ("temperature",)
    assert m.input_modalities == ("text", "image")
    assert m.caching["min_cacheable_tokens"] == 2048
    assert m.service["batch_eligible"] is True
    assert isinstance(m.lifecycle, Lifecycle) and m.lifecycle.status == "active"
    assert isinstance(m.pricing, Pricing) and len(m.pricing.dimensions) == 4
    assert m.pricing.dimensions[2].speed == "fast"


# --- alias / snapshot identity (A-CAT-003) -------------------------------------------

def test_alias_and_snapshot_resolve_but_stay_distinct(tmp_path: Path) -> None:
    cat = _load(_write(tmp_path, "c.json", _v2_doc([_v2_model()])))
    assert cat.get("claude-4-6-sonnet").key == "claude-sonnet-4-6"
    assert cat.get("claude-sonnet-4-6-20251114").key == "claude-sonnet-4-6"
    assert cat.resolve_key("claude-4-6-sonnet") == "claude-sonnet-4-6"
    # aliases/snapshots are not canonical entries
    assert "claude-4-6-sonnet" not in cat._items
    assert "claude-sonnet-4-6-20251114" not in cat._items
    assert len(cat.list()) == 1


# --- unknown vs zero vs absent pricing (Decision D2) ---------------------------------

def test_unknown_zero_and_absent_pricing_are_distinguishable(tmp_path: Path) -> None:
    unknown = _v2_model(
        key="m-unknown", model_name="m-unknown", aliases=[], snapshots=[],
        pricing={"completeness": "unknown", "dimensions": [
            {"metric": "input", "unit": "million_tokens", "rate": None},
            {"metric": "output", "unit": "million_tokens", "rate": None},
        ]},
    )
    zero = _v2_model(
        key="m-zero", model_name="m-zero", aliases=[], snapshots=[],
        pricing={"completeness": "complete", "dimensions": [
            {"metric": "input", "unit": "million_tokens", "rate": 0.0},
            {"metric": "output", "unit": "million_tokens", "rate": 0.0},
        ]},
    )
    partial = _v2_model(
        key="m-partial", model_name="m-partial", aliases=[], snapshots=[],
        pricing={"completeness": "partial", "dimensions": [
            {"metric": "output", "unit": "million_tokens", "rate": 5.0},
        ]},
    )
    cat = _load(_write(tmp_path, "c.json", _v2_doc([unknown, zero, partial],
                                                   defaults={"openai": {"completions": "m-zero"}})))

    u = cat.get("m-unknown")
    assert u.cost_status == "unknown"
    assert u.usage_costs == {}  # unknown is NOT zero

    z = cat.get("m-zero")
    assert z.cost_status == "complete"
    assert z.usage_costs["input"] == 0.0  # a genuine, known zero

    p = cat.get("m-partial")
    assert p.cost_status == "partial"
    assert "input" not in p.usage_costs  # absent dimension stays absent
    assert p.usage_costs["output"] == pytest.approx(5.0 / 1_000_000)


# --- deterministic load ---------------------------------------------------------------

def test_deterministic_load(tmp_path: Path) -> None:
    path = _write(tmp_path, "c.json", _v2_doc([_v2_model()]))
    first = _load(path).get("claude-sonnet-4-6")
    second = _load(path).get("claude-sonnet-4-6")
    assert first == second


# --- override migration ---------------------------------------------------------------

def test_v2_override_on_v2_base_merges(tmp_path: Path) -> None:
    base = _write(tmp_path, "base.json", _v2_doc([_v2_model()]))
    override = _write(tmp_path, "ov.json", _v2_doc([_v2_model(
        pricing={"completeness": "complete", "dimensions": [
            {"metric": "input", "unit": "million_tokens", "rate": 9.0},
            {"metric": "output", "unit": "million_tokens", "rate": 9.0},
        ]},
    )]))
    cat = _load(base, override_path=override)
    m = cat.get("claude-sonnet-4-6")
    assert m.usage_costs["input"] == pytest.approx(9.0 / 1_000_000)


def test_v1_override_on_v2_base_warns_and_applies(tmp_path: Path) -> None:
    base = _write(tmp_path, "base.json", _v2_doc([_v2_model()]))
    # A complete v1-shaped override entry for the same key.
    v1_override = {
        "version": 1,
        "defaults": {},
        "models": [{
            "key": "claude-sonnet-4-6",
            "provider": "anthropic",
            "model_name": "claude-sonnet-4-6",
            "category": "completions",
            "context_window": 500_000,
            "encoding": "cl100k_base",
            "reasoning": False,
            "reasoning_efforts": [],
            "tool_calling": True,
            "streaming": True,
            "structured_outputs": False,
            "vision_input": False,
            "audio_input": False,
            "file_input": False,
            "deprecated": False,
            "rate_limits": {},
            "usage_costs": {"input": 0.000001},
            "responses_api": False,
            "background_responses": False,
            "responses_native_tools": False,
            "normalized_output_items": False,
        }],
    }
    ov = _write(tmp_path, "ov_v1.json", v1_override)
    clear_model_catalog_cache()
    with pytest.warns(DeprecationWarning, match="v1 overrides are deprecated"):
        cat = load_model_catalog(base, override_path=ov)
    m = cat.get("claude-sonnet-4-6")
    # override (v1) replaced the entry for this key
    assert m.context_window == 500_000
    assert m.schema_version == 1


# --- compatibility projection ---------------------------------------------------------

def test_existing_model_profiles_still_resolve() -> None:
    assert ModelProfile.get("gpt-5-mini").key == "gpt-5-mini"
    assert ModelProfile.get("claude-sonnet-4-6").key == "claude-sonnet-4-6"


def test_model_profile_get_prefers_catalog_v2_metadata() -> None:
    profile = ModelProfile.get("o4-mini-deep-research")
    catalog_meta = get_default_model_catalog().get("o4-mini-deep-research")

    assert profile._skip_registry is True
    assert profile is not ModelProfile._registry["o4-mini-deep-research"]
    assert profile.responses_api_support is catalog_meta.responses_api is True
    assert profile.responses_native_tools_support is catalog_meta.responses_native_tools is True
    assert profile.background_responses_support is catalog_meta.background_responses is True


def test_model_profile_from_metadata_roundtrip() -> None:
    prof = ModelProfile.get("claude-sonnet-4-6")
    meta = metadata_from_profile(prof)
    derived = model_profile_from_metadata(meta)
    assert derived.key == "claude-sonnet-4-6"
    assert derived._skip_registry is True
    # catalog projections are not registered as canonical static entries
    assert ModelProfile._registry.get("claude-sonnet-4-6") is not prof
    assert derived.usage_costs["input"] == prof.usage_costs["input"]
    assert derived.reasoning_efforts == list(prof.reasoning_efforts)
