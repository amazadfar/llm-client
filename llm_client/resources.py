"""Shared typed results for provider Models and Files resources (Phase 7).

These envelopes give the package a stable, provider-neutral shape for the supporting
Anthropic/OpenAI resources (model discovery, file lifecycle) while preserving the raw
provider object for callers that need provider-specific fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ModelInfo:
    """A model entry returned by a provider's Models API."""

    id: str
    provider: str
    display_name: str | None = None
    created_at: Any = None
    type: str | None = None
    raw: Any = field(default=None, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "provider": self.provider,
            "display_name": self.display_name,
            "created_at": self.created_at,
            "type": self.type,
        }


@dataclass(frozen=True)
class FileObject:
    """A file entry returned by a provider's Files API."""

    id: str
    provider: str
    filename: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    created_at: Any = None
    purpose: str | None = None
    downloadable: bool | None = None
    raw: Any = field(default=None, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "provider": self.provider,
            "filename": self.filename,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "created_at": self.created_at,
            "purpose": self.purpose,
            "downloadable": self.downloadable,
        }


@dataclass(frozen=True)
class ResourcePage:
    """A single page of a paginated resource listing (models or files)."""

    data: tuple[Any, ...]
    has_more: bool = False
    first_id: str | None = None
    last_id: str | None = None

    def __iter__(self):
        return iter(self.data)

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, index: int) -> Any:
        return self.data[index]


__all__ = ["FileObject", "ModelInfo", "ResourcePage"]
