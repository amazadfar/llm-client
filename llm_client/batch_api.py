"""Shared provider Batch API types (Phase 6).

These model the durable, discounted provider Batch APIs (OpenAI Batch, Anthropic Message
Batches) -- distinct from :meth:`ExecutionEngine.concurrent_complete`, which is local
bounded concurrency in the standard tier (Architecture Decision 6). Provider batch jobs
carry ``execution_mode="provider_batch"`` and bill at batch rates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Normalized cross-provider job statuses. Raw provider statuses are preserved alongside.
BATCH_STATUSES = (
    "validating",
    "in_progress",
    "finalizing",
    "completed",
    "failed",
    "canceling",
    "canceled",
    "expired",
)

# OpenAI batch status -> normalized.
_OPENAI_STATUS = {
    "validating": "validating",
    "in_progress": "in_progress",
    "finalizing": "finalizing",
    "completed": "completed",
    "failed": "failed",
    "expired": "expired",
    "cancelling": "canceling",
    "cancelled": "canceled",
}

# Anthropic processing_status -> normalized.
_ANTHROPIC_STATUS = {
    "in_progress": "in_progress",
    "canceling": "canceling",
    "ended": "completed",
}


def normalize_batch_status(provider: str, raw_status: str | None) -> str:
    """Map a provider-native batch status to the normalized vocabulary (raw preserved)."""
    if raw_status is None:
        return "in_progress"
    table = _OPENAI_STATUS if provider == "openai" else _ANTHROPIC_STATUS
    return table.get(str(raw_status), str(raw_status))


@dataclass(frozen=True)
class BatchRequestItem:
    """One request in a provider batch, keyed by a caller-chosen ``custom_id``."""

    custom_id: str
    params: dict[str, Any]  # provider-native request params (model, messages, max_tokens, ...)

    def to_dict(self) -> dict[str, Any]:
        return {"custom_id": self.custom_id, "params": dict(self.params)}


@dataclass(frozen=True)
class BatchResultItem:
    """Per-item result, preserving the custom_id and per-item error."""

    custom_id: str
    status: str  # succeeded | errored | canceled | expired
    content: Any = None
    error: dict[str, Any] | None = None
    usage: dict[str, Any] | None = None
    raw: Any = field(default=None, repr=False)

    @property
    def ok(self) -> bool:
        return self.status == "succeeded"

    def to_dict(self) -> dict[str, Any]:
        return {
            "custom_id": self.custom_id,
            "status": self.status,
            "content": self.content,
            "error": dict(self.error) if self.error else None,
            "usage": dict(self.usage) if self.usage else None,
        }


@dataclass(frozen=True)
class BatchJob:
    """A durable provider batch job."""

    id: str
    provider: str
    status: str  # normalized (see BATCH_STATUSES)
    raw_status: str | None = None
    endpoint: str | None = None
    request_counts: dict[str, int] = field(default_factory=dict)
    created_at: Any = None
    expires_at: Any = None
    output_file_id: str | None = None  # OpenAI: file id holding JSONL results
    execution_mode: str = "provider_batch"
    price_mode: str = "batch"
    raw: Any = field(default=None, repr=False)

    @property
    def is_terminal(self) -> bool:
        return self.status in ("completed", "failed", "canceled", "expired")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "provider": self.provider,
            "status": self.status,
            "raw_status": self.raw_status,
            "endpoint": self.endpoint,
            "request_counts": dict(self.request_counts),
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "output_file_id": self.output_file_id,
            "execution_mode": self.execution_mode,
            "price_mode": self.price_mode,
        }


__all__ = [
    "BATCH_STATUSES",
    "BatchJob",
    "BatchRequestItem",
    "BatchResultItem",
    "normalize_batch_status",
]
