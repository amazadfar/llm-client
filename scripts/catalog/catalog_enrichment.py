"""Source-backed enrichment layer for the catalog v2 build (Phase 3).

Scope: OpenAI and Anthropic only. Gemini models are carried as-is by the converter and
are intentionally NOT enriched here (deferred to the 0.5.0 Gemini plan).

- ``DEFAULTS_V2``  : the v2 default-model block (Decision D1 -- cost-balanced defaults).
- ``ENRICHMENT``  : per-key patches deep-merged onto the converted baseline (audit fixes
                    + structured lifecycle/service/caching/pricing for current models).
- ``NEW_MODELS``  : full v2 records for current flagships absent from the v1 catalog
                    (audit O-CAT-001 / A-CAT-001 / A-CAT-002b).

Pricing/spec sources: the environment ``claude-api`` reference (Anthropic) and the audit
O-CAT-001 figures re-verified against OpenAI docs (OpenAI), effective 2026-06-13.
"""

from __future__ import annotations

from typing import Any

_EFFECTIVE = "2026-06-13"
_ANTHROPIC_SRC = {"url": "claude-api reference (2026-06-13)", "fetched_at": _EFFECTIVE}
_OPENAI_SRC = {"url": "OpenAI docs (audit O-CAT-001, re-verified 2026-06-13)", "fetched_at": _EFFECTIVE}

# Anthropic-removed sampling params on current thinking models (claude-api).
_ANTHROPIC_INCOMPATIBLE = ["temperature", "top_p", "top_k"]


# --- Decision D1: cost-balanced defaults ---------------------------------------------

DEFAULTS_V2: dict[str, dict[str, str]] = {
    "openai": {"completions": "gpt-5.4-mini", "embeddings": "text-embedding-3-small"},
    "google": {"completions": "gemini-2.0-flash"},  # already a Flash; unchanged (policy-consistent)
    "anthropic": {"completions": "claude-sonnet-4-6"},
}


def _round(value: float) -> float:
    return round(value, 6)


def _anthropic_pricing(input_mtok: float, output_mtok: float) -> dict[str, Any]:
    """Standard Anthropic pricing dimensions (per-MTok) with cache + batch derivations."""
    return {
        "completeness": "complete",
        "currency": "USD",
        "effective_date": _EFFECTIVE,
        "source": _ANTHROPIC_SRC,
        "dimensions": [
            {"metric": "input", "unit": "million_tokens", "rate": input_mtok},
            {"metric": "output", "unit": "million_tokens", "rate": output_mtok},
            {"metric": "cache_read", "unit": "million_tokens", "rate": _round(input_mtok * 0.1)},
            {"metric": "cache_write_5m", "unit": "million_tokens", "rate": _round(input_mtok * 1.25)},
            {"metric": "cache_write_1h", "unit": "million_tokens", "rate": _round(input_mtok * 2.0)},
            {"metric": "input", "unit": "million_tokens", "mode": "batch", "rate": _round(input_mtok * 0.5)},
            {"metric": "output", "unit": "million_tokens", "mode": "batch", "rate": _round(output_mtok * 0.5)},
        ],
    }


def _anthropic_flagship(
    *,
    key: str,
    model_name: str,
    display_name: str,
    input_mtok: float,
    output_mtok: float,
    cache_min: int,
    max_output: int = 128_000,
    context_window: int = 1_000_000,
    efforts: list[str] | None = None,
    status: str = "active",
    aliases: list[str] | None = None,
    availability_notes: str | None = None,
    replacement: str | None = None,
    retires_on: str | None = None,
) -> dict[str, Any]:
    service: dict[str, Any] = {
        "tiers": ["standard", "priority"],
        "speed_modes": [],  # fast mode is Opus 4.6 only
        "batch_eligible": True,
        "region_modifiers": {"inference_geo_us": 1.1},
    }
    if availability_notes:
        service["availability_notes"] = availability_notes
    lifecycle: dict[str, Any] = {"status": status, "source": _ANTHROPIC_SRC}
    if replacement:
        lifecycle["replacement"] = replacement
    if retires_on:
        lifecycle["retires_on"] = retires_on
    return {
        "key": key,
        "provider": "anthropic",
        "family": "claude-" + key.split("-")[1] if "-" in key else "claude",
        "display_name": display_name,
        "model_name": model_name,
        "release_channel": "ga" if status == "active" else "preview",
        "aliases": aliases or [],
        "snapshots": [],
        "category": "completions",
        "encoding": "cl100k_base",
        "streaming": True,
        "lifecycle": lifecycle,
        "endpoints": ["messages", "batch"],
        "modalities": {"input": ["text", "image", "file"], "output": ["text"]},
        "limits": {
            "context_window": context_window,
            "max_output": max_output,
            "source": _ANTHROPIC_SRC,
        },
        "reasoning": {
            "supported": True,
            "efforts": efforts or ["low", "medium", "high", "xhigh", "max"],
            "default_effort": "high",
            "incompatible_params": list(_ANTHROPIC_INCOMPATIBLE),
        },
        "caching": {
            "supported": True,
            "min_cacheable_tokens": cache_min,
            "ttls": ["5m", "1h"],
            "multipliers": {"cache_read": 0.1, "cache_write_5m": 1.25, "cache_write_1h": 2.0},
        },
        "service": service,
        "tools": {
            "client_tools": True,
            "structured_outputs": True,
            "server_tools": [
                "web_search", "web_fetch", "code_execution", "computer_use",
                "text_editor", "bash", "memory",
            ],
        },
        "pricing": _anthropic_pricing(input_mtok, output_mtok),
        "rate_limits": {"tkn_per_min": 120_000, "req_per_min": 6_000},
    }


# --- new Anthropic flagships (absent from v1) ----------------------------------------

NEW_MODELS: list[dict[str, Any]] = [
    _anthropic_flagship(
        key="claude-opus-4-8", model_name="claude-opus-4-8", display_name="Claude Opus 4.8",
        input_mtok=5.0, output_mtok=25.0, cache_min=4096,
        efforts=["low", "medium", "high", "xhigh", "max"],
        aliases=["claude-4-8-opus"],
    ),
    _anthropic_flagship(
        key="claude-fable-5", model_name="claude-fable-5", display_name="Claude Fable 5",
        input_mtok=10.0, output_mtok=50.0, cache_min=2048,
        availability_notes="Requires 30-day data retention; not available under ZDR.",
    ),
    _anthropic_flagship(
        key="claude-mythos-5", model_name="claude-mythos-5", display_name="Claude Mythos 5",
        input_mtok=10.0, output_mtok=50.0, cache_min=2048,
        availability_notes="Project Glasswing participants only.",
    ),
    _anthropic_flagship(
        key="claude-mythos-preview", model_name="claude-mythos-preview",
        display_name="Claude Mythos Preview",
        input_mtok=10.0, output_mtok=50.0, cache_min=2048,
        status="preview", replacement="claude-mythos-5", retires_on="2026-06-30",
        availability_notes="Invitation-only; retiring 2026-06-30. Use claude-mythos-5.",
    ),
]


# --- new OpenAI flagships (absent from v1) -------------------------------------------

def _openai_gpt55() -> dict[str, Any]:
    # Standard / batch / flex / priority + long-context threshold (>272K) dimensions.
    dims: list[dict[str, Any]] = [
        {"metric": "input", "unit": "million_tokens", "rate": 5.0},
        {"metric": "cached_input", "unit": "million_tokens", "rate": 0.5},
        {"metric": "output", "unit": "million_tokens", "rate": 30.0},
        # batch
        {"metric": "input", "unit": "million_tokens", "mode": "batch", "rate": 2.5},
        {"metric": "cached_input", "unit": "million_tokens", "mode": "batch", "rate": 0.25},
        {"metric": "output", "unit": "million_tokens", "mode": "batch", "rate": 15.0},
        # flex (same rates as batch, but a synchronous service tier)
        {"metric": "input", "unit": "million_tokens", "tier": "flex", "rate": 2.5},
        {"metric": "cached_input", "unit": "million_tokens", "tier": "flex", "rate": 0.25},
        {"metric": "output", "unit": "million_tokens", "tier": "flex", "rate": 15.0},
        # priority
        {"metric": "input", "unit": "million_tokens", "tier": "priority", "rate": 12.5},
        {"metric": "cached_input", "unit": "million_tokens", "tier": "priority", "rate": 1.25},
        {"metric": "output", "unit": "million_tokens", "tier": "priority", "rate": 75.0},
        # long-context (> 272K tokens): 2x input, 1.5x output
        {"metric": "input", "unit": "million_tokens", "threshold": {"min_tokens": 272_001}, "rate": 10.0},
        {"metric": "output", "unit": "million_tokens", "threshold": {"min_tokens": 272_001}, "rate": 45.0},
    ]
    return {
        "key": "gpt-5.5", "provider": "openai", "family": "gpt-5.5",
        "display_name": "GPT-5.5", "model_name": "gpt-5.5", "release_channel": "ga",
        "aliases": [], "snapshots": ["gpt-5.5-2026-04-23"], "category": "completions",
        "encoding": "o200k_base", "streaming": True,
        "lifecycle": {"status": "active", "source": _OPENAI_SRC},
        "endpoints": ["chat_completions", "responses", "batch"],
        "modalities": {"input": ["text", "image", "file"], "output": ["text"]},
        "limits": {"context_window": 400_000, "max_output": 128_000, "source": _OPENAI_SRC},
        "reasoning": {
            "supported": True,
            "efforts": ["none", "low", "medium", "high", "xhigh"],
            "default_effort": "medium",
            "incompatible_params": [],
        },
        "service": {
            "tiers": ["standard", "flex", "priority", "scale"],
            "speed_modes": [],
            "batch_eligible": True,
            "region_modifiers": {"regional": 1.1},
            "availability_notes": "Prompt cache retention supports only 24h.",
        },
        "tools": {
            "client_tools": True,
            "structured_outputs": True,
            "server_tools": [
                "web_search", "file_search", "tool_search", "image_generation",
                "code_interpreter", "hosted_shell", "apply_patch", "skills",
                "computer_use", "mcp",
            ],
        },
        "pricing": {
            "completeness": "complete", "currency": "USD", "effective_date": _EFFECTIVE,
            "source": _OPENAI_SRC, "dimensions": dims,
        },
    }


def _openai_gpt55_pro() -> dict[str, Any]:
    # Priority-tier rates are not published (Phase 0 unknown) -> partial, those rows null.
    dims: list[dict[str, Any]] = [
        {"metric": "input", "unit": "million_tokens", "rate": 30.0},
        {"metric": "output", "unit": "million_tokens", "rate": 180.0},
        {"metric": "input", "unit": "million_tokens", "mode": "batch", "rate": 15.0},
        {"metric": "output", "unit": "million_tokens", "mode": "batch", "rate": 90.0},
        {"metric": "input", "unit": "million_tokens", "tier": "flex", "rate": 15.0},
        {"metric": "output", "unit": "million_tokens", "tier": "flex", "rate": 90.0},
        {"metric": "input", "unit": "million_tokens", "tier": "priority", "rate": None},
        {"metric": "output", "unit": "million_tokens", "tier": "priority", "rate": None},
    ]
    return {
        "key": "gpt-5.5-pro", "provider": "openai", "family": "gpt-5.5",
        "display_name": "GPT-5.5 Pro", "model_name": "gpt-5.5-pro", "release_channel": "ga",
        "aliases": [], "snapshots": ["gpt-5.5-pro-2026-04-23"], "category": "completions",
        "encoding": "o200k_base", "streaming": True,
        "lifecycle": {"status": "active", "source": _OPENAI_SRC},
        "endpoints": ["responses", "batch"],
        "modalities": {"input": ["text", "image", "file"], "output": ["text"]},
        "limits": {"context_window": 400_000, "max_output": 128_000, "source": _OPENAI_SRC},
        "reasoning": {
            "supported": True,
            "efforts": ["none", "low", "medium", "high", "xhigh"],
            "default_effort": "medium",
            "incompatible_params": [],
        },
        "service": {
            "tiers": ["standard", "flex", "priority"],
            "speed_modes": [],
            "batch_eligible": True,
            "region_modifiers": {"regional": 1.1},
            "availability_notes": "No cached-input discount. Background mode for long-running requests.",
        },
        "tools": {"client_tools": True, "structured_outputs": True},
        "pricing": {
            "completeness": "partial", "currency": "USD", "effective_date": _EFFECTIVE,
            "source": _OPENAI_SRC, "dimensions": dims,
        },
    }


NEW_MODELS.extend([_openai_gpt55(), _openai_gpt55_pro()])


# --- patches onto converted baselines ------------------------------------------------

ENRICHMENT: dict[str, dict[str, Any]] = {
    # Fast mode is Opus 4.6 ONLY. The v1 catalog falsely flags it on Opus 4.7.
    "claude-opus-4-7": {
        "service": {"speed_modes": [], "tiers": ["standard", "priority"]},
        "caching": {"min_cacheable_tokens": 4096},
        "reasoning": {"incompatible_params": list(_ANTHROPIC_INCOMPATIBLE)},
        "lifecycle": {"status": "active", "source": _ANTHROPIC_SRC},
    },
    # Opus 4.6 retains fast mode (genuinely supported).
    "claude-opus-4-6": {
        "service": {"speed_modes": ["fast"], "tiers": ["standard", "priority"]},
        "caching": {"min_cacheable_tokens": 4096},
        "reasoning": {"incompatible_params": list(_ANTHROPIC_INCOMPATIBLE)},
    },
    "claude-sonnet-4-6": {
        "caching": {"min_cacheable_tokens": 2048},
        "service": {"tiers": ["standard", "priority"], "batch_eligible": True},
        "reasoning": {"incompatible_params": list(_ANTHROPIC_INCOMPATIBLE)},
        "display_name": "Claude Sonnet 4.6",
    },
    "claude-haiku-4-5": {
        "caching": {"min_cacheable_tokens": 4096},
        "service": {"tiers": ["standard", "priority"], "batch_eligible": True},
    },
    # Claude 3 Haiku retired on 2026-04-19 (past today's 2026-06-13).
    "claude-3-haiku": {
        "lifecycle": {
            "status": "retired",
            "retires_on": "2026-04-19",
            "replacement": "claude-haiku-4-5",
            "source": _ANTHROPIC_SRC,
        },
    },
}
