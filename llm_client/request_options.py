"""Typed, namespaced provider-specific request options (Phase 4).

Stable cross-provider controls (``service_tier``, ``top_p``, ``metadata``, cache controls)
live directly on :class:`~llm_client.spec.RequestSpec`. Provider-only controls live in
these typed namespaced objects, so neither provider's surface is forced through the
other's parameter names. ``RequestSpec.extra`` remains an explicitly-unsafe
forward-compatibility escape hatch.

Architecture Decision 5: stable shared fields on RequestSpec; provider-only fields in
typed namespaced option objects; ``extra`` as the escape hatch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class OpenAIRequestOptions:
    """Typed OpenAI-specific request controls.

    ``endpoint`` is a routing hint (``"chat_completions"`` | ``"responses"`` | ``None``
    for model-aware auto-routing); it is consumed by routing, not forwarded as a kwarg.
    The remaining fields are forwarded to the provider call.
    """

    endpoint: str | None = None
    verbosity: str | None = None
    safety_identifier: str | None = None
    store: bool | None = None
    background: bool | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key in ("endpoint", "verbosity", "safety_identifier", "store", "background"):
            value = getattr(self, key)
            if value is not None:
                out[key] = value
        if self.extra:
            out["extra"] = dict(self.extra)
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "OpenAIRequestOptions | None":
        if not data:
            return None
        return cls(
            endpoint=data.get("endpoint"),
            verbosity=data.get("verbosity"),
            safety_identifier=data.get("safety_identifier"),
            store=data.get("store"),
            background=data.get("background"),
            extra=dict(data.get("extra") or {}),
        )

    def provider_kwargs(self) -> dict[str, Any]:
        """Kwargs to forward to the OpenAI provider call (excludes the routing-only
        ``endpoint`` hint)."""
        kwargs: dict[str, Any] = {}
        for key in ("verbosity", "safety_identifier", "store", "background"):
            value = getattr(self, key)
            if value is not None:
                kwargs[key] = value
        kwargs.update(self.extra)
        return kwargs


@dataclass(frozen=True)
class AnthropicRequestOptions:
    """Typed Anthropic-specific request controls.

    ``thinking`` is the native extended-thinking config (e.g. ``{"type": "adaptive"}``).
    ``effort`` maps to ``output_config.effort``. ``speed`` is the fast-mode selector
    (Opus 4.6 only). All are forwarded to the provider call.
    """

    thinking: dict[str, Any] | None = None
    effort: str | None = None
    speed: str | None = None
    container: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.thinking is not None:
            out["thinking"] = dict(self.thinking)
        for key in ("effort", "speed", "container"):
            value = getattr(self, key)
            if value is not None:
                out[key] = value
        if self.extra:
            out["extra"] = dict(self.extra)
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "AnthropicRequestOptions | None":
        if not data:
            return None
        return cls(
            thinking=dict(data["thinking"]) if data.get("thinking") else None,
            effort=data.get("effort"),
            speed=data.get("speed"),
            container=data.get("container"),
            extra=dict(data.get("extra") or {}),
        )

    def provider_kwargs(self) -> dict[str, Any]:
        """Kwargs to forward to the Anthropic provider call."""
        kwargs: dict[str, Any] = {}
        if self.thinking is not None:
            kwargs["thinking"] = dict(self.thinking)
        for key in ("effort", "speed", "container"):
            value = getattr(self, key)
            if value is not None:
                kwargs[key] = value
        kwargs.update(self.extra)
        return kwargs


__all__ = ["OpenAIRequestOptions", "AnthropicRequestOptions"]
