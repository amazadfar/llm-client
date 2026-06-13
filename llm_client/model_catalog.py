"""
Canonical model metadata catalog.

This module provides an asset-backed metadata API so model capabilities,
pricing, defaults, and lifecycle metadata can be shared across projects
without hard-coding everything into Python classes.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
import json
import os
import re
import warnings
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft202012Validator
except Exception:  # pragma: no cover - optional runtime dependency
    Draft202012Validator = None

from .models import ModelProfile


MODEL_CATALOG_PATH_ENV = "LLM_CLIENT_MODEL_CATALOG_PATH"
MODEL_CATALOG_OVERRIDE_PATH_ENV = "LLM_CLIENT_MODEL_CATALOG_OVERRIDE_PATH"
ASSETS_DIR = Path(__file__).with_name("assets")
DEFAULT_MODEL_CATALOG_PATH = ASSETS_DIR / "model_catalog.json"
DEFAULT_MODEL_CATALOG_SCHEMA_PATH = ASSETS_DIR / "model_catalog.schema.json"
DEFAULT_MODEL_CATALOG_SCHEMA_V2_PATH = ASSETS_DIR / "model_catalog.schema.v2.json"
CURRENT_CATALOG_SCHEMA_VERSION = 2


@dataclass(frozen=True)
class Lifecycle:
    """Structured lifecycle state (catalog v2). Replaces the v1 ``deprecated`` boolean."""

    status: str = "active"  # active | preview | deprecated | retired
    announced_on: str | None = None
    deprecated_on: str | None = None
    retires_on: str | None = None
    replacement: str | None = None
    source: dict[str, Any] | None = None

    @property
    def is_deprecated(self) -> bool:
        return self.status in ("deprecated", "retired")

    @property
    def is_retired(self) -> bool:
        return self.status == "retired"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "announced_on": self.announced_on,
            "deprecated_on": self.deprecated_on,
            "retires_on": self.retires_on,
            "replacement": self.replacement,
            "source": dict(self.source) if self.source else None,
        }


@dataclass(frozen=True)
class PricingDimension:
    """A single priced dimension (catalog v2).

    ``rate is None`` means the price is UNKNOWN and must never be treated as zero.
    """

    metric: str
    unit: str
    mode: str = "standard"
    tier: str | None = None
    region: str | None = None
    threshold: dict[str, Any] | None = None
    rate: float | None = None
    effective_date: str | None = None
    source: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"metric": self.metric, "unit": self.unit, "mode": self.mode}
        if self.tier is not None:
            data["tier"] = self.tier
        if self.region is not None:
            data["region"] = self.region
        if self.threshold is not None:
            data["threshold"] = dict(self.threshold)
        data["rate"] = self.rate
        if self.effective_date is not None:
            data["effective_date"] = self.effective_date
        if self.source is not None:
            data["source"] = dict(self.source)
        return data


@dataclass(frozen=True)
class Pricing:
    """Structured, multidimensional pricing (catalog v2)."""

    completeness: str = "unknown"  # complete | partial | unknown
    currency: str = "USD"
    effective_date: str | None = None
    source: dict[str, Any] | None = None
    dimensions: tuple[PricingDimension, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "completeness": self.completeness,
            "currency": self.currency,
            "effective_date": self.effective_date,
            "source": dict(self.source) if self.source else None,
            "dimensions": [dim.to_dict() for dim in self.dimensions],
        }


@dataclass(frozen=True)
class ModelMetadata:
    key: str
    provider: str
    model_name: str
    category: str
    context_window: int
    max_output: int | None
    output_dimensions: int | None
    encoding: str
    reasoning: bool
    reasoning_efforts: tuple[str, ...]
    default_reasoning_effort: str | None
    tool_calling: bool
    streaming: bool
    structured_outputs: bool
    responses_api: bool
    background_responses: bool
    responses_native_tools: bool
    normalized_output_items: bool
    vision_input: bool
    audio_input: bool
    file_input: bool
    deprecated: bool
    replacement: str | None
    rate_limits: dict[str, int]
    usage_costs: dict[str, float]
    pricing_features: dict[str, Any]

    # --- Catalog v2 structured fields (additive; default to empty/None so the v1 loader
    #     constructs ModelMetadata unchanged). The flat fields above remain the
    #     backward-compatible projection of these structures. ---
    schema_version: int = 1
    aliases: tuple[str, ...] = ()
    snapshots: tuple[str, ...] = ()
    family: str | None = None
    display_name: str | None = None
    release_channel: str | None = None
    endpoints: tuple[str, ...] = ()
    input_modalities: tuple[str, ...] = ()
    output_modalities: tuple[str, ...] = ()
    reasoning_incompatible_params: tuple[str, ...] = ()
    lifecycle: Lifecycle | None = None
    caching: dict[str, Any] | None = None
    service: dict[str, Any] | None = None
    tools: dict[str, Any] | None = None
    pricing: Pricing | None = None

    @property
    def cost_status(self) -> str:
        """Pricing completeness: ``complete`` | ``partial`` | ``unknown``.

        v1 records (flat ``usage_costs``) report ``complete`` when costs are present and
        ``unknown`` when empty, so callers can distinguish unknown from a real zero.
        """
        if self.pricing is not None:
            return self.pricing.completeness
        return "complete" if self.usage_costs else "unknown"

    def to_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "provider": self.provider,
            "model_name": self.model_name,
            "category": self.category,
            "context_window": self.context_window,
            "max_output": self.max_output,
            "output_dimensions": self.output_dimensions,
            "encoding": self.encoding,
            "reasoning": self.reasoning,
            "reasoning_efforts": list(self.reasoning_efforts),
            "default_reasoning_effort": self.default_reasoning_effort,
            "tool_calling": self.tool_calling,
            "streaming": self.streaming,
            "structured_outputs": self.structured_outputs,
            "responses_api": self.responses_api,
            "background_responses": self.background_responses,
            "responses_native_tools": self.responses_native_tools,
            "normalized_output_items": self.normalized_output_items,
            "vision_input": self.vision_input,
            "audio_input": self.audio_input,
            "file_input": self.file_input,
            "deprecated": self.deprecated,
            "replacement": self.replacement,
            "rate_limits": dict(self.rate_limits),
            "usage_costs": dict(self.usage_costs),
            "pricing_features": dict(self.pricing_features),
        }


class ModelCatalog:
    def __init__(
        self,
        items: list[ModelMetadata],
        *,
        defaults: dict[str, dict[str, str]] | None = None,
        source: str | None = None,
    ) -> None:
        self._items = {item.key: item for item in items}
        # Alias / snapshot index → canonical key. Canonical keys remain distinct
        # identities; aliases and snapshots resolve to them without overwriting the
        # canonical entry (catalog v2, audit A-CAT-003).
        self._aliases: dict[str, str] = {}
        for item in items:
            for alt in (*item.aliases, *item.snapshots):
                alt_key = str(alt).strip()
                if alt_key and alt_key not in self._items:
                    self._aliases.setdefault(alt_key, item.key)
        self._defaults = {
            str(provider).strip().lower(): {
                str(category).strip().lower(): str(model).strip()
                for category, model in categories.items()
                if str(model).strip()
            }
            for provider, categories in (defaults or {}).items()
        }
        self.source = source

    def get(self, key: str) -> ModelMetadata:
        if key in self._items:
            return self._items[key]
        canonical = self._aliases.get(key)
        if canonical is not None:
            return self._items[canonical]
        raise ValueError(f"Unknown model key {key!r}") from None

    def resolve_key(self, key: str) -> str | None:
        """Return the canonical key for ``key`` (which may be an alias/snapshot), or None."""
        if key in self._items:
            return key
        return self._aliases.get(key)

    def list(
        self,
        *,
        provider: str | None = None,
        category: str | None = None,
        reasoning: bool | None = None,
        tool_calling: bool | None = None,
        streaming: bool | None = None,
        structured_outputs: bool | None = None,
        responses_api: bool | None = None,
        background_responses: bool | None = None,
        responses_native_tools: bool | None = None,
        normalized_output_items: bool | None = None,
    ) -> list[ModelMetadata]:
        provider_norm = str(provider or "").strip().lower() or None
        category_norm = str(category or "").strip().lower() or None
        results: list[ModelMetadata] = []
        for item in sorted(self._items.values(), key=lambda current: (current.provider, current.key)):
            if provider_norm is not None and item.provider != provider_norm:
                continue
            if category_norm is not None and item.category != category_norm:
                continue
            if reasoning is not None and item.reasoning != reasoning:
                continue
            if tool_calling is not None and item.tool_calling != tool_calling:
                continue
            if streaming is not None and item.streaming != streaming:
                continue
            if structured_outputs is not None and item.structured_outputs != structured_outputs:
                continue
            if responses_api is not None and item.responses_api != responses_api:
                continue
            if background_responses is not None and item.background_responses != background_responses:
                continue
            if responses_native_tools is not None and item.responses_native_tools != responses_native_tools:
                continue
            if normalized_output_items is not None and item.normalized_output_items != normalized_output_items:
                continue
            results.append(item)
        return results

    def default_key_for_provider(self, provider: str, *, category: str = "completions") -> str | None:
        provider_name = str(provider or "").strip().lower()
        category_name = str(category or "").strip().lower() or "completions"
        if not provider_name:
            return None
        configured = self._defaults.get(provider_name, {}).get(category_name)
        if configured:
            return configured
        matches = self.list(provider=provider_name, category=category_name)
        return matches[0].key if matches else None

    def default_for_provider(self, provider: str, *, category: str = "completions") -> ModelMetadata | None:
        key = self.default_key_for_provider(provider, category=category)
        if not key:
            return None
        try:
            return self.get(key)
        except ValueError:
            return None

    def to_document(self) -> dict[str, object]:
        return {
            "version": 1,
            "defaults": {
                provider: dict(categories)
                for provider, categories in sorted(self._defaults.items())
            },
            "models": [item.to_dict() for item in self.list()],
        }


def infer_provider_for_model(model_key: str) -> str:
    key = str(model_key or "").strip().lower()
    if key in {"o1", "o3", "o4-mini"}:
        return "openai"
    if key.startswith(
        (
            "gpt-",
            "chatgpt-",
            "text-embedding-",
            "omni-moderation-",
            "text-moderation-",
            "whisper-",
            "tts-",
            "o1-",
            "o3-",
            "o4-",
            "dall-e-",
            "davinci-",
            "babbage-",
            "computer-use-",
            "codex-",
            "ft:",
            "ft-",
        )
    ):
        return "openai"
    if key.startswith("gemini-"):
        return "google"
    if key.startswith("claude-"):
        return "anthropic"
    return "unknown"


def _default_capability_flags(profile: type[ModelProfile]) -> dict[str, bool]:
    provider = infer_provider_for_model(profile.key)
    is_completion = profile.category == "completions"
    if provider == "openai":
        is_image = profile.category == "images"
        is_audio = profile.category == "audio"
        is_moderation = profile.category == "moderations"
        is_realtime = profile.category == "realtime"
        is_completion_like = is_completion or is_realtime
        supports_image_input = is_completion or is_image or profile.key == "omni-moderation-latest"
        supports_audio_input = is_completion_like or is_audio
        supports_file_input = is_completion_like or is_audio or is_image
        if is_moderation and profile.key.startswith("text-moderation-"):
            supports_image_input = False
            supports_audio_input = False
            supports_file_input = False
        structured_outputs = is_completion
        responses_api = is_completion
        background_responses = is_completion
        responses_native_tools = is_completion
        normalized_output_items = is_completion
        vision_input = supports_image_input
        audio_input = supports_audio_input
        file_input = supports_file_input
        for attribute_name, current_key in (
            ("structured_outputs_support", "structured_outputs"),
            ("responses_api_support", "responses_api"),
            ("background_responses_support", "background_responses"),
            ("responses_native_tools_support", "responses_native_tools"),
            ("normalized_output_items_support", "normalized_output_items"),
            ("vision_input_support", "vision_input"),
            ("audio_input_support", "audio_input"),
            ("file_input_support", "file_input"),
        ):
            override = getattr(profile, attribute_name, None)
            if override is None:
                continue
            if current_key == "structured_outputs":
                structured_outputs = bool(override)
            elif current_key == "responses_api":
                responses_api = bool(override)
            elif current_key == "background_responses":
                background_responses = bool(override)
            elif current_key == "responses_native_tools":
                responses_native_tools = bool(override)
            elif current_key == "normalized_output_items":
                normalized_output_items = bool(override)
            elif current_key == "vision_input":
                vision_input = bool(override)
            elif current_key == "audio_input":
                audio_input = bool(override)
            elif current_key == "file_input":
                file_input = bool(override)
        return {
            "structured_outputs": structured_outputs,
            "responses_api": responses_api,
            "background_responses": background_responses,
            "responses_native_tools": responses_native_tools,
            "normalized_output_items": normalized_output_items,
            "vision_input": vision_input,
            "audio_input": audio_input,
            "file_input": file_input,
        }
    if provider == "google":
        return {
            "structured_outputs": is_completion,
            "responses_api": False,
            "background_responses": False,
            "responses_native_tools": False,
            "normalized_output_items": False,
            "vision_input": is_completion,
            "audio_input": is_completion,
            "file_input": is_completion,
        }
    if provider == "anthropic":
        return {
            "structured_outputs": False,
            "responses_api": False,
            "background_responses": False,
            "responses_native_tools": False,
            "normalized_output_items": False,
            "vision_input": is_completion,
            "audio_input": False,
            "file_input": is_completion,
        }
    return {
        "structured_outputs": False,
        "responses_api": False,
        "background_responses": False,
        "responses_native_tools": False,
        "normalized_output_items": False,
        "vision_input": False,
        "audio_input": False,
        "file_input": False,
    }


def metadata_from_profile(profile: type[ModelProfile]) -> ModelMetadata:
    usage_costs = {
        str(name): float(value if isinstance(value, Decimal) else Decimal(str(value)))
        for name, value in dict(getattr(profile, "usage_costs", {})).items()
    }
    rate_limits = {str(name): int(value) for name, value in dict(getattr(profile, "rate_limits", {})).items()}
    defaults = _default_capability_flags(profile)
    return ModelMetadata(
        key=profile.key,
        provider=infer_provider_for_model(profile.key),
        model_name=profile.model_name,
        category=profile.category,
        context_window=profile.context_window,
        max_output=getattr(profile, "max_output", None),
        output_dimensions=getattr(profile, "output_dimensions", None),
        encoding=getattr(profile, "encoding", "cl100k_base"),
        reasoning=bool(getattr(profile, "reasoning_model", False)),
        reasoning_efforts=tuple(getattr(profile, "reasoning_efforts", []) or []),
        default_reasoning_effort=getattr(profile, "default_reasoning_effort", None),
        tool_calling=bool(getattr(profile, "function_calling_support", False)),
        streaming=bool(getattr(profile, "token_streaming_support", False)),
        structured_outputs=defaults["structured_outputs"],
        responses_api=defaults["responses_api"],
        background_responses=defaults["background_responses"],
        responses_native_tools=defaults["responses_native_tools"],
        normalized_output_items=defaults["normalized_output_items"],
        vision_input=defaults["vision_input"],
        audio_input=defaults["audio_input"],
        file_input=defaults["file_input"],
        deprecated=bool(getattr(profile, "deprecated", False)),
        replacement=getattr(profile, "replacement", None),
        rate_limits=rate_limits,
        usage_costs=usage_costs,
        pricing_features=dict(getattr(profile, "pricing_features", {}) or {}),
    )


def model_profile_from_metadata(meta: ModelMetadata) -> type[ModelProfile]:
    """Derive a ``ModelProfile``-compatible class from catalog metadata.

    Inverse of :func:`metadata_from_profile`; the bridge that lets catalog v2 JSON serve
    as the canonical source while existing ``ModelProfile``-based callers keep working.
    The generated class is **not** registered in the global profile registry. Costs are
    reconstructed as ``Decimal`` per-token values; unknown costs remain absent (never
    fabricated as zero).
    """
    usage_costs = {str(name): Decimal(str(value)) for name, value in meta.usage_costs.items()}
    dynamic_name = "CatalogModel_" + re.sub(r"[^0-9A-Za-z_]", "_", meta.key)
    namespace: dict[str, Any] = {
        "key": meta.key,
        "model_name": meta.model_name,
        "category": meta.category,
        "context_window": meta.context_window,
        "max_output": meta.max_output,
        "output_dimensions": meta.output_dimensions,
        "encoding": meta.encoding,
        "reasoning_model": meta.reasoning,
        "reasoning_efforts": list(meta.reasoning_efforts),
        "default_reasoning_effort": meta.default_reasoning_effort,
        "function_calling_support": meta.tool_calling,
        "token_streaming_support": meta.streaming,
        "structured_outputs_support": meta.structured_outputs,
        "responses_api_support": meta.responses_api,
        "background_responses_support": meta.background_responses,
        "responses_native_tools_support": meta.responses_native_tools,
        "normalized_output_items_support": meta.normalized_output_items,
        "vision_input_support": meta.vision_input,
        "audio_input_support": meta.audio_input,
        "file_input_support": meta.file_input,
        "deprecated": meta.deprecated,
        "replacement": meta.replacement,
        "rate_limits": dict(meta.rate_limits),
        "usage_costs": usage_costs,
        "pricing_features": dict(meta.pricing_features),
        "resolved": True,
        "_skip_registry": True,
    }
    return type(dynamic_name, (ModelProfile,), namespace)


def _fallback_catalog_document_from_profiles() -> dict[str, object]:
    items = [metadata_from_profile(profile).to_dict() for _, profile in sorted(ModelProfile._registry.items())]
    return {
        "version": 1,
        "defaults": {
            "openai": {
                "completions": "gpt-5",
                "embeddings": "text-embedding-3-small",
            },
            "google": {
                "completions": "gemini-2.0-flash",
            },
            "anthropic": {
                "completions": "claude-opus-4-7",
            },
        },
        "models": items,
    }


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _validate_catalog_document(document: dict[str, Any], schema_path: Path) -> None:
    if Draft202012Validator is None:
        return
    schema = _load_json(schema_path)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(document), key=lambda error: list(error.path))
    if not errors:
        return
    error = errors[0]
    location = ".".join(str(part) for part in error.path) or "<root>"
    raise ValueError(f"Invalid model catalog document at {location}: {error.message}")


def _normalize_defaults(defaults: dict[str, Any] | None) -> dict[str, dict[str, str]]:
    normalized: dict[str, dict[str, str]] = {}
    for provider, categories in (defaults or {}).items():
        provider_name = str(provider).strip().lower()
        if not provider_name or not isinstance(categories, dict):
            continue
        normalized[provider_name] = {}
        for category, model_key in categories.items():
            category_name = str(category).strip().lower()
            model_name = str(model_key or "").strip()
            if category_name and model_name:
                normalized[provider_name][category_name] = model_name
    return normalized


def _merge_catalog_documents(base: dict[str, Any], override: dict[str, Any] | None) -> dict[str, Any]:
    if not override:
        return base
    merged_models: dict[str, dict[str, Any]] = {
        str(item["key"]): dict(item)
        for item in base.get("models", [])
        if isinstance(item, dict) and str(item.get("key") or "").strip()
    }
    for item in override.get("models", []) if isinstance(override.get("models"), list) else []:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        if not key:
            continue
        merged = dict(merged_models.get(key, {}))
        merged.update(item)
        merged_models[key] = merged
    merged_defaults = _normalize_defaults(base.get("defaults"))
    for provider, categories in _normalize_defaults(override.get("defaults")).items():
        merged_defaults.setdefault(provider, {}).update(categories)
    return {
        "version": int(override.get("version") or base.get("version") or 1),
        "defaults": merged_defaults,
        "models": [merged_models[key] for key in sorted(merged_models)],
    }


def _document_version(document: dict[str, Any]) -> int:
    try:
        return int(document.get("version", 1))
    except (TypeError, ValueError):
        return 1


def _schema_path_for_version(version: int) -> Path:
    return DEFAULT_MODEL_CATALOG_SCHEMA_V2_PATH if version >= 2 else DEFAULT_MODEL_CATALOG_SCHEMA_PATH


def _catalog_from_document(document: dict[str, Any], *, source: str | None = None) -> ModelCatalog:
    if _document_version(document) >= 2:
        return _catalog_from_v2_document(document, source=source)
    return _catalog_from_v1_document(document, source=source)


def _catalog_from_v1_document(document: dict[str, Any], *, source: str | None = None) -> ModelCatalog:
    items: list[ModelMetadata] = []
    for raw in document.get("models", []):
        item = ModelMetadata(
            key=str(raw["key"]),
            provider=str(raw["provider"]).strip().lower(),
            model_name=str(raw["model_name"]),
            category=str(raw["category"]).strip().lower(),
            context_window=int(raw["context_window"]),
            max_output=None if raw.get("max_output") is None else int(raw["max_output"]),
            output_dimensions=None if raw.get("output_dimensions") is None else int(raw["output_dimensions"]),
            encoding=str(raw.get("encoding") or "cl100k_base"),
            reasoning=bool(raw.get("reasoning", False)),
            reasoning_efforts=tuple(str(item) for item in (raw.get("reasoning_efforts") or [])),
            default_reasoning_effort=(
                None if raw.get("default_reasoning_effort") is None else str(raw["default_reasoning_effort"])
            ),
            tool_calling=bool(raw.get("tool_calling", False)),
            streaming=bool(raw.get("streaming", False)),
            structured_outputs=bool(raw.get("structured_outputs", False)),
            responses_api=bool(raw.get("responses_api", False)),
            background_responses=bool(raw.get("background_responses", False)),
            responses_native_tools=bool(raw.get("responses_native_tools", False)),
            normalized_output_items=bool(raw.get("normalized_output_items", False)),
            vision_input=bool(raw.get("vision_input", False)),
            audio_input=bool(raw.get("audio_input", False)),
            file_input=bool(raw.get("file_input", False)),
            deprecated=bool(raw.get("deprecated", False)),
            replacement=None if raw.get("replacement") is None else str(raw["replacement"]),
            rate_limits={str(name): int(value) for name, value in dict(raw.get("rate_limits") or {}).items()},
            usage_costs={str(name): float(value) for name, value in dict(raw.get("usage_costs") or {}).items()},
            pricing_features=dict(raw.get("pricing_features") or {}),
        )
        items.append(item)
    return ModelCatalog(items, defaults=_normalize_defaults(document.get("defaults")), source=source)


# Maps v2 pricing metrics to the flat v1 ``usage_costs`` keys used by existing callers.
_V2_METRIC_TO_FLAT_COST = {
    "input": "input",
    "output": "output",
    "cached_input": "cached_input",
    "cache_read": "cache_read_input",
    "cache_write_5m": "cache_write_5m_input",
    "cache_write_1h": "cache_write_1h_input",
}


def _projected_flat_costs_from_pricing(pricing: Pricing) -> dict[str, float]:
    """Project v2 pricing dimensions to a flat v1 ``usage_costs`` map (per-token floats).

    Only KNOWN rates from the default region and un-thresholded bands are included; an
    unknown rate (``rate is None``) is omitted so it is never misread as a real zero.
    """
    flat: dict[str, float] = {}
    for dim in pricing.dimensions:
        if dim.rate is None or dim.region not in (None, "default") or dim.threshold is not None:
            continue
        # Reconstruct per-token cost via Decimal so the float matches the v1
        # ``float(Decimal(rate)/Decimal(1_000_000))`` representation bit-for-bit.
        if dim.unit == "million_tokens":
            per_unit = float(Decimal(str(dim.rate)) / Decimal(1_000_000))
        else:
            per_unit = float(dim.rate)
        if dim.mode == "batch":
            if dim.metric in ("input", "output"):
                flat.setdefault(f"batch_{dim.metric}", per_unit)
            continue
        flat_key = _V2_METRIC_TO_FLAT_COST.get(dim.metric)
        if flat_key is not None:
            flat.setdefault(flat_key, per_unit)
    return flat


def _projected_pricing_features(raw: dict[str, Any]) -> dict[str, Any]:
    """Best-effort v1 ``pricing_features`` projection from v2 caching/service blocks."""
    features: dict[str, Any] = {}
    caching = raw.get("caching") or {}
    multipliers = caching.get("multipliers") or {}
    if multipliers:
        features["prompt_caching"] = {
            "cache_read_multiplier": multipliers.get("cache_read"),
            "cache_write_5m_multiplier": multipliers.get("cache_write_5m"),
            "cache_write_1h_multiplier": multipliers.get("cache_write_1h"),
        }
    service = raw.get("service") or {}
    if service.get("batch_eligible"):
        features["batch"] = {"input_output_discount_multiplier": 0.5}
    if "fast" in (service.get("speed_modes") or []):
        features["fast_mode"] = {"available_on": ["messages"]}
    region_modifiers = service.get("region_modifiers") or {}
    if region_modifiers:
        features["data_residency"] = dict(region_modifiers)
    return features


def _metadata_from_v2_model(raw: dict[str, Any]) -> ModelMetadata:
    lifecycle_raw = raw.get("lifecycle") or {}
    lifecycle = Lifecycle(
        status=str(lifecycle_raw.get("status", "active")),
        announced_on=lifecycle_raw.get("announced_on"),
        deprecated_on=lifecycle_raw.get("deprecated_on"),
        retires_on=lifecycle_raw.get("retires_on"),
        replacement=lifecycle_raw.get("replacement"),
        source=lifecycle_raw.get("source"),
    )
    pricing_raw = raw.get("pricing") or {}
    dimensions = tuple(
        PricingDimension(
            metric=str(d["metric"]),
            unit=str(d["unit"]),
            mode=str(d.get("mode", "standard")),
            tier=d.get("tier"),
            region=d.get("region"),
            threshold=d.get("threshold"),
            rate=None if d.get("rate") is None else float(d["rate"]),
            effective_date=d.get("effective_date"),
            source=d.get("source"),
        )
        for d in pricing_raw.get("dimensions", [])
    )
    pricing = Pricing(
        completeness=str(pricing_raw.get("completeness", "unknown")),
        currency=str(pricing_raw.get("currency", "USD")),
        effective_date=pricing_raw.get("effective_date"),
        source=pricing_raw.get("source"),
        dimensions=dimensions,
    )
    modalities = raw.get("modalities") or {}
    input_mods = tuple(str(m) for m in modalities.get("input", []))
    output_mods = tuple(str(m) for m in modalities.get("output", []))
    reasoning_raw = raw.get("reasoning") or {}
    tools_raw = raw.get("tools") or {}
    endpoints = tuple(str(e) for e in raw.get("endpoints", []))
    limits = raw.get("limits") or {}
    has_responses = "responses" in endpoints

    return ModelMetadata(
        key=str(raw["key"]),
        provider=str(raw["provider"]).strip().lower(),
        model_name=str(raw["model_name"]),
        category=str(raw["category"]).strip().lower(),
        context_window=int(limits.get("context_window") or 0),
        max_output=None if limits.get("max_output") is None else int(limits["max_output"]),
        output_dimensions=None if limits.get("output_dimensions") is None else int(limits["output_dimensions"]),
        encoding=str(raw.get("encoding") or "cl100k_base"),
        # --- flat projections (backward compatible) ---
        reasoning=bool(reasoning_raw.get("supported", False)),
        reasoning_efforts=tuple(str(e) for e in (reasoning_raw.get("efforts") or [])),
        default_reasoning_effort=reasoning_raw.get("default_effort"),
        tool_calling=bool(tools_raw.get("client_tools", False)),
        streaming=bool(raw.get("streaming", False)),
        structured_outputs=bool(tools_raw.get("structured_outputs", False)),
        responses_api=has_responses,
        background_responses=has_responses,
        responses_native_tools=bool(tools_raw.get("responses_native_tools", has_responses)),
        normalized_output_items=has_responses,
        vision_input="image" in input_mods,
        audio_input="audio" in input_mods,
        file_input="file" in input_mods,
        deprecated=lifecycle.is_deprecated,
        replacement=lifecycle.replacement,
        rate_limits={str(name): int(value) for name, value in dict(raw.get("rate_limits") or {}).items()},
        usage_costs=_projected_flat_costs_from_pricing(pricing),
        pricing_features=_projected_pricing_features(raw),
        # --- v2 structured fields (the source of truth) ---
        schema_version=2,
        aliases=tuple(str(a) for a in (raw.get("aliases") or [])),
        snapshots=tuple(str(s) for s in (raw.get("snapshots") or [])),
        family=raw.get("family"),
        display_name=raw.get("display_name"),
        release_channel=raw.get("release_channel"),
        endpoints=endpoints,
        input_modalities=input_mods,
        output_modalities=output_mods,
        reasoning_incompatible_params=tuple(str(p) for p in (reasoning_raw.get("incompatible_params") or [])),
        lifecycle=lifecycle,
        caching=dict(raw["caching"]) if raw.get("caching") else None,
        service=dict(raw["service"]) if raw.get("service") else None,
        tools=dict(tools_raw) if tools_raw else None,
        pricing=pricing,
    )


def _catalog_from_v2_document(document: dict[str, Any], *, source: str | None = None) -> ModelCatalog:
    items = [_metadata_from_v2_model(raw) for raw in document.get("models", [])]
    return ModelCatalog(items, defaults=_normalize_defaults(document.get("defaults")), source=source)


def _merge_catalogs(base: ModelCatalog, override: ModelCatalog) -> ModelCatalog:
    """Merge two already-parsed catalogs (override entries replace/add by key).

    Used for cross-schema-version overrides where a raw document merge would mix
    incompatible field shapes.
    """
    merged_items = dict(base._items)
    merged_items.update(override._items)
    merged_defaults = {provider: dict(categories) for provider, categories in base._defaults.items()}
    for provider, categories in override._defaults.items():
        merged_defaults.setdefault(provider, {}).update(categories)
    return ModelCatalog(list(merged_items.values()), defaults=merged_defaults, source=base.source)


def _resolved_catalog_paths(
    catalog_path: str | Path | None = None,
    override_path: str | Path | None = None,
) -> tuple[Path | None, Path | None]:
    base = catalog_path or os.getenv(MODEL_CATALOG_PATH_ENV)
    override = override_path or os.getenv(MODEL_CATALOG_OVERRIDE_PATH_ENV)
    return (
        Path(base).expanduser().resolve() if base else DEFAULT_MODEL_CATALOG_PATH,
        Path(override).expanduser().resolve() if override else None,
    )


@lru_cache(maxsize=8)
def load_model_catalog(
    catalog_path: str | Path | None = None,
    *,
    override_path: str | Path | None = None,
) -> ModelCatalog:
    base_path, resolved_override_path = _resolved_catalog_paths(catalog_path, override_path)
    if base_path is not None and base_path.exists():
        base_document = _load_json(base_path)
    else:
        base_document = _fallback_catalog_document_from_profiles()
    base_version = _document_version(base_document)
    source = str(base_path) if base_path is not None else "<embedded>"

    if resolved_override_path is None or not resolved_override_path.exists():
        _validate_catalog_document(base_document, _schema_path_for_version(base_version))
        return _catalog_from_document(base_document, source=source)

    override_document = _load_json(resolved_override_path)
    override_version = _document_version(override_document)
    if override_version < CURRENT_CATALOG_SCHEMA_VERSION:
        warnings.warn(
            f"Catalog override uses schema v{override_version}; v{CURRENT_CATALOG_SCHEMA_VERSION} "
            "is canonical. v1 overrides are deprecated and support will be removed in 0.5.0. "
            "Migrate the override to schema v2.",
            DeprecationWarning,
            stacklevel=2,
        )

    if override_version == base_version:
        merged = _merge_catalog_documents(base_document, override_document)
        _validate_catalog_document(merged, _schema_path_for_version(base_version))
        return _catalog_from_document(merged, source=source)

    # Cross-version override: validate and parse each against its own schema, then merge
    # at the catalog level (a raw document merge would mix incompatible field shapes).
    _validate_catalog_document(base_document, _schema_path_for_version(base_version))
    _validate_catalog_document(override_document, _schema_path_for_version(override_version))
    base_catalog = _catalog_from_document(base_document, source=source)
    override_catalog = _catalog_from_document(override_document, source=source)
    return _merge_catalogs(base_catalog, override_catalog)


def get_default_model_catalog() -> ModelCatalog:
    return load_model_catalog()


def clear_model_catalog_cache() -> None:
    load_model_catalog.cache_clear()


def get_provider_default_model(provider: str, *, category: str = "completions") -> str | None:
    catalog = get_default_model_catalog()
    return catalog.default_key_for_provider(provider, category=category)


__all__ = [
    "ASSETS_DIR",
    "CURRENT_CATALOG_SCHEMA_VERSION",
    "DEFAULT_MODEL_CATALOG_PATH",
    "DEFAULT_MODEL_CATALOG_SCHEMA_PATH",
    "DEFAULT_MODEL_CATALOG_SCHEMA_V2_PATH",
    "MODEL_CATALOG_OVERRIDE_PATH_ENV",
    "MODEL_CATALOG_PATH_ENV",
    "Lifecycle",
    "ModelMetadata",
    "ModelCatalog",
    "Pricing",
    "PricingDimension",
    "clear_model_catalog_cache",
    "get_default_model_catalog",
    "get_provider_default_model",
    "infer_provider_for_model",
    "load_model_catalog",
    "metadata_from_profile",
    "model_profile_from_metadata",
]
