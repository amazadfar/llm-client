#!/usr/bin/env python
"""Generate the canonical catalog v2 asset from the v1 asset plus an enrichment layer.

Phase 3 of the OpenAI/Anthropic completeness program. The converter:

1. Lifts every v1 model entry faithfully into v2 shape (baseline) -- this keeps the
   ``google`` (Gemini) models present and behaviorally unchanged; Gemini is carried
   as-is (not audited; that is the 0.5.0 Gemini plan's job).
2. Applies the uniform pricing fix: zero-priced entries become ``completeness:
   "unknown"`` with ``rate: null`` (audit O-CAT-003 -- unknown is not free).
3. Applies an enrichment layer for the in-scope OpenAI/Anthropic models (lifecycle
   dates, aliases/snapshots, service tiers, cache minimums, speed modes, and the
   specific audit corrections).

The output is checked in as ``llm_client/assets/model_catalog.json`` (v2); the prior v1
asset is preserved as ``model_catalog.v1.json`` for the dual-read compatibility window.

Run: ``.venv/bin/python scripts/catalog/build_catalog_v2.py``
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from catalog_enrichment import DEFAULTS_V2, ENRICHMENT, NEW_MODELS

ASSETS = Path(__file__).resolve().parents[2] / "llm_client" / "assets"
V1_PATH = ASSETS / "model_catalog.json"
V1_PRESERVED_PATH = ASSETS / "model_catalog.v1.json"
OUT_PATH = ASSETS / "model_catalog.json"


# --- flat (v1) -> structured (v2) reverse projection --------------------------------

_COST_KEY_TO_METRIC = {
    "input": ("input", "standard"),
    "output": ("output", "standard"),
    "cached_input": ("cached_input", "standard"),
    "cache_read_input": ("cache_read", "standard"),
    "cache_write_5m_input": ("cache_write_5m", "standard"),
    "cache_write_1h_input": ("cache_write_1h", "standard"),
    "batch_input": ("input", "batch"),
    "batch_output": ("output", "batch"),
}


def _endpoints(provider: str, category: str, responses_api: bool) -> list[str]:
    if category == "completions":
        if provider == "openai":
            eps = ["chat_completions"]
            if responses_api:
                eps.append("responses")
            eps.append("batch")
            return eps
        if provider == "anthropic":
            return ["messages", "batch"]
        return []  # google: carried as-is; endpoint semantics deferred to 0.5.0
    return [category] if category in {"embeddings", "images", "audio", "realtime", "moderations"} else []


def _output_modalities(category: str) -> list[str]:
    return {
        "completions": ["text"],
        "embeddings": ["embedding"],
        "images": ["image"],
        "audio": ["audio"],
        "realtime": ["text", "audio"],
        "moderations": ["text"],
    }.get(category, [])


# Source-confirmed Anthropic image/document input support by family (Phase 7). The v1
# source carried these as False under the temporary Phase 1 truthfulness guard; with native
# image/document transport now implemented, re-derive truthfully here so the catalog matches.
_ANTHROPIC_VISION_ONLY_KEYS = {"claude-3-opus", "claude-3-sonnet", "claude-3-haiku"}


def _input_modalities(v1: dict[str, Any]) -> list[str]:
    provider = str(v1.get("provider") or "").strip().lower()
    category = str(v1.get("category") or "").strip().lower()
    key = str(v1.get("key") or "")
    vision = bool(v1.get("vision_input"))
    audio = bool(v1.get("audio_input"))
    file = bool(v1.get("file_input"))
    if provider == "anthropic" and category == "completions":
        if key.startswith("claude-3-5-haiku"):
            vision, file = False, False
        elif key in _ANTHROPIC_VISION_ONLY_KEYS:
            vision, file = True, False
        else:
            vision, file = True, True
    mods = ["text"]
    if vision:
        mods.append("image")
    if audio:
        mods.append("audio")
    if file:
        mods.append("file")
    return mods


def _pricing_from_v1(v1: dict[str, Any]) -> dict[str, Any]:
    costs = v1.get("usage_costs") or {}
    all_zero = bool(costs) and all(float(value) == 0.0 for value in costs.values())
    if not costs or all_zero:
        # Unknown is never zero (audit O-CAT-003). Represent the principal dimensions
        # as explicitly unknown so callers can detect missing pricing.
        return {
            "completeness": "unknown",
            "dimensions": [
                {"metric": "input", "unit": "million_tokens", "rate": None},
                {"metric": "output", "unit": "million_tokens", "rate": None},
            ],
        }
    dimensions: list[dict[str, Any]] = []
    for key, value in costs.items():
        mapped = _COST_KEY_TO_METRIC.get(key)
        if mapped is None:
            continue  # e.g. fast_mode_* -- captured via service.speed_modes
        metric, mode = mapped
        dim: dict[str, Any] = {"metric": metric, "unit": "million_tokens", "rate": round(float(value) * 1_000_000, 6)}
        if mode == "batch":
            dim["mode"] = "batch"
        dimensions.append(dim)
    return {"completeness": "complete", "dimensions": dimensions}


def _caching_service_from_v1(v1: dict[str, Any]) -> tuple[dict | None, dict | None]:
    features = v1.get("pricing_features") or {}
    caching: dict[str, Any] | None = None
    service: dict[str, Any] = {}
    prompt_caching = features.get("prompt_caching")
    if isinstance(prompt_caching, dict):
        caching = {
            "supported": True,
            "ttls": ["5m", "1h"],
            "multipliers": {
                "cache_read": prompt_caching.get("cache_read_multiplier"),
                "cache_write_5m": prompt_caching.get("cache_write_5m_multiplier"),
                "cache_write_1h": prompt_caching.get("cache_write_1h_multiplier"),
            },
        }
    if features.get("batch"):
        service["batch_eligible"] = True
    fast = features.get("fast_mode")
    if isinstance(fast, dict):
        service["speed_modes"] = ["fast"]
    residency = features.get("data_residency")
    if isinstance(residency, dict):
        service["region_modifiers"] = {
            k: v for k, v in residency.items() if isinstance(v, (int, float))
        }
    return caching, (service or None)


def _v1_to_v2(v1: dict[str, Any]) -> dict[str, Any]:
    provider = str(v1["provider"]).strip().lower()
    category = str(v1["category"]).strip().lower()
    responses_api = bool(v1.get("responses_api"))

    lifecycle: dict[str, Any] = {"status": "deprecated" if v1.get("deprecated") else "active"}
    if v1.get("replacement"):
        lifecycle["replacement"] = v1["replacement"]

    model: dict[str, Any] = {
        "key": v1["key"],
        "provider": provider,
        "model_name": v1["model_name"],
        "category": category,
        "encoding": v1.get("encoding") or "cl100k_base",
        "streaming": bool(v1.get("streaming")),
        "lifecycle": lifecycle,
        "endpoints": _endpoints(provider, category, responses_api),
        "modalities": {"input": _input_modalities(v1), "output": _output_modalities(category)},
        "limits": {
            "context_window": v1.get("context_window"),
            "max_output": v1.get("max_output"),
            "output_dimensions": v1.get("output_dimensions"),
        },
        "reasoning": {
            "supported": bool(v1.get("reasoning")),
            "efforts": list(v1.get("reasoning_efforts") or []),
            "default_effort": v1.get("default_reasoning_effort"),
            "incompatible_params": [],
        },
        "tools": {
            "client_tools": bool(v1.get("tool_calling")),
            "structured_outputs": bool(v1.get("structured_outputs")),
            "responses_native_tools": bool(v1.get("responses_native_tools")),
        },
        "pricing": _pricing_from_v1(v1),
    }
    caching, service = _caching_service_from_v1(v1)
    if caching is not None:
        model["caching"] = caching
    if service is not None:
        model["service"] = service
    if v1.get("rate_limits"):
        model["rate_limits"] = dict(v1["rate_limits"])
    return model


# --- enrichment merge ----------------------------------------------------------------

def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def build() -> dict[str, Any]:
    # Source from the preserved v1 asset if it exists (idempotent re-runs), else the
    # current asset (first run, before it is flipped to v2).
    source_path = V1_PRESERVED_PATH if V1_PRESERVED_PATH.exists() else V1_PATH
    v1_doc = json.loads(source_path.read_text(encoding="utf-8"))
    if int(v1_doc.get("version", 1)) != 1:
        raise SystemExit(
            f"Expected a v1 source asset at {source_path}, found version {v1_doc.get('version')!r}"
        )

    models: list[dict[str, Any]] = []
    for v1 in v1_doc["models"]:
        v2 = _v1_to_v2(v1)
        patch = ENRICHMENT.get(v2["key"])
        if patch is not None:
            v2 = _deep_merge(v2, patch)
        models.append(v2)

    # Append current flagships that are absent from the v1 catalog (audit O-CAT-001 /
    # A-CAT-001 / A-CAT-002b).
    existing_keys = {m["key"] for m in models}
    for new_model in NEW_MODELS:
        if new_model["key"] in existing_keys:
            raise SystemExit(f"NEW_MODELS key {new_model['key']!r} already present in v1 catalog")
        models.append(new_model)

    models.sort(key=lambda m: (m["provider"], m["key"]))
    return {"version": 2, "defaults": DEFAULTS_V2, "models": models}


def main() -> None:
    doc = build()
    # Preserve the v1 asset for the dual-read compatibility window (if not already saved).
    if not V1_PRESERVED_PATH.exists():
        V1_PRESERVED_PATH.write_text(V1_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    OUT_PATH.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    counts: dict[str, int] = {}
    for m in doc["models"]:
        counts[m["provider"]] = counts.get(m["provider"], 0) + 1
    print(f"Wrote {OUT_PATH} (v2): {len(doc['models'])} models {counts}")


if __name__ == "__main__":
    main()
