"""Phase 7: native Anthropic multimodal transport, cache-control, Models and Files.

Covers native image/document translation (base64/url/file_id/text sources), lossless
cache-control placement, model-aware cache validation, capability activation, and the
Models/Files resource wrappers (mocked SDK).
"""

from __future__ import annotations

import base64
from types import SimpleNamespace
from typing import Any

import pytest

from telic.content import (
    FileBlock,
    ImageBlock,
    TextBlock,
    content_block_from_dict,
    content_blocks_to_anthropic_content,
)
from telic.models import ModelProfile
from telic.providers.anthropic import AnthropicProvider
from telic.resources import FileObject, ModelInfo, ResourcePage


# --- native image translation --------------------------------------------------------

def test_image_http_url_to_native_block() -> None:
    blocks = [ImageBlock(image_url="https://example.com/x.png")]
    content = content_blocks_to_anthropic_content(blocks, supports_images=True)
    assert content == [{"type": "image", "source": {"type": "url", "url": "https://example.com/x.png"}}]


def test_image_base64_data_url_to_native_block() -> None:
    payload = base64.b64encode(b"\x89PNG").decode()
    blocks = [ImageBlock(image_url=f"data:image/png;base64,{payload}")]
    content = content_blocks_to_anthropic_content(blocks, supports_images=True)
    assert content == [
        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": payload}}
    ]


def test_image_file_id_to_native_block() -> None:
    blocks = [ImageBlock(image_url="", file_id="file_abc")]
    content = content_blocks_to_anthropic_content(blocks, supports_images=True)
    assert content == [{"type": "image", "source": {"type": "file", "file_id": "file_abc"}}]


def test_image_degrades_to_placeholder_when_unsupported() -> None:
    blocks = [ImageBlock(image_url="https://example.com/x.png")]
    content = content_blocks_to_anthropic_content(blocks, supports_images=False)
    assert content == "[image] https://example.com/x.png"


# --- native document translation -----------------------------------------------------

def test_pdf_base64_to_document_block() -> None:
    payload = base64.b64encode(b"%PDF-1.7").decode()
    blocks = [FileBlock(data=payload, mime_type="application/pdf", name="report.pdf")]
    content = content_blocks_to_anthropic_content(blocks, supports_files=True)
    assert content == [
        {
            "type": "document",
            "source": {"type": "base64", "media_type": "application/pdf", "data": payload},
            "title": "report.pdf",
        }
    ]


def test_file_id_and_url_to_document_block() -> None:
    by_id = content_blocks_to_anthropic_content([FileBlock(file_id="file_1")], supports_files=True)
    assert by_id == [{"type": "document", "source": {"type": "file", "file_id": "file_1"}}]
    by_url = content_blocks_to_anthropic_content(
        [FileBlock(file_url="https://example.com/a.pdf")], supports_files=True
    )
    assert by_url == [{"type": "document", "source": {"type": "url", "url": "https://example.com/a.pdf"}}]


def test_text_file_to_document_text_source() -> None:
    blocks = [FileBlock(extracted_text="hello world")]
    content = content_blocks_to_anthropic_content(blocks, supports_files=True)
    assert content == [
        {"type": "document", "source": {"type": "text", "media_type": "text/plain", "data": "hello world"}}
    ]


def test_no_supported_block_degrades_to_placeholder_when_capable() -> None:
    # When capabilities are on, supported blocks must NOT degrade to placeholder text.
    payload = base64.b64encode(b"%PDF").decode()
    blocks = [
        TextBlock("see attached"),
        ImageBlock(image_url="https://example.com/x.png"),
        FileBlock(data=payload, mime_type="application/pdf"),
    ]
    content = content_blocks_to_anthropic_content(blocks, supports_images=True, supports_files=True)
    types = [b["type"] for b in content]
    assert types == ["text", "image", "document"]
    assert all("[image]" not in str(b) and "[file]" not in str(b) for b in content)


# --- cache-control preservation ------------------------------------------------------

def test_cache_control_preserved_on_text_image_file() -> None:
    cc = {"type": "ephemeral", "ttl": "1h"}
    blocks = [
        TextBlock("sys", cache_control=cc),
        ImageBlock(image_url="https://example.com/x.png", cache_control=cc),
        FileBlock(file_id="file_1", cache_control=cc),
    ]
    content = content_blocks_to_anthropic_content(blocks, supports_images=True, supports_files=True)
    assert all(b.get("cache_control") == cc for b in content)


def test_cache_control_parsed_from_dict_roundtrip() -> None:
    cc = {"type": "ephemeral"}
    block = content_block_from_dict({"type": "text", "text": "x", "cache_control": cc})
    assert isinstance(block, TextBlock) and block.cache_control == cc
    assert block.to_dict()["cache_control"] == cc


def test_single_cached_text_block_not_collapsed_to_string() -> None:
    content = content_blocks_to_anthropic_content(
        [TextBlock("x", cache_control={"type": "ephemeral"})]
    )
    assert isinstance(content, list) and content[0]["cache_control"] == {"type": "ephemeral"}


# --- cache validation + minimums -----------------------------------------------------

def _provider_with_model(**model_attrs: Any) -> AnthropicProvider:
    provider = AnthropicProvider.__new__(AnthropicProvider)
    provider._model = SimpleNamespace(**model_attrs)
    return provider


def test_validate_cache_controls_rejects_unsupported_ttl() -> None:
    provider = AnthropicProvider.__new__(AnthropicProvider)
    params = {"messages": [{"content": [{"type": "text", "cache_control": {"ttl": "2h"}}]}]}
    with pytest.raises(ValueError, match="cache-control ttl"):
        provider._validate_cache_controls(params)


def test_validate_cache_controls_accepts_supported_ttls() -> None:
    provider = AnthropicProvider.__new__(AnthropicProvider)
    for ttl in ("5m", "1h"):
        provider._validate_cache_controls({"x": {"cache_control": {"ttl": ttl}}})


def test_cache_minimum_tokens_by_family() -> None:
    op = _provider_with_model(model_name="claude-opus-4-8")
    assert op.cache_minimum_tokens == 4096
    haiku = _provider_with_model(model_name="claude-haiku-4-5-20251001")
    assert haiku.cache_minimum_tokens == 4096
    so = _provider_with_model(model_name="claude-sonnet-4-6")
    assert so.cache_minimum_tokens == 2048
    fable = _provider_with_model(model_name="claude-fable-5")
    assert fable.cache_minimum_tokens == 2048


# --- capability activation -----------------------------------------------------------

@pytest.mark.parametrize(
    "key, vision, file",
    [
        ("claude-sonnet-4-6", True, True),
        ("claude-3-7-sonnet", True, True),
        ("claude-3-haiku", True, False),
        ("claude-3-5-haiku", False, False),
    ],
)
def test_capability_activation(key: str, vision: bool, file: bool) -> None:
    profile = ModelProfile.get(key)
    assert profile.vision_input_support is vision
    assert profile.file_input_support is file


# --- Models + Files resources (mocked SDK) -------------------------------------------

def _resource_provider() -> AnthropicProvider:
    provider = AnthropicProvider.__new__(AnthropicProvider)

    async def _models_list(*, limit, **kw):
        return SimpleNamespace(
            data=[SimpleNamespace(id="claude-opus-4-8", display_name="Opus", created_at="t", type="model")],
            has_more=False, first_id="claude-opus-4-8", last_id="claude-opus-4-8",
        )

    async def _models_retrieve(mid):
        return SimpleNamespace(id=mid, display_name="Opus", created_at="t", type="model")

    async def _files_upload(*, file):
        return SimpleNamespace(id="file_1", filename=file, mime_type="application/pdf",
                               size_bytes=10, created_at="t", downloadable=True)

    async def _files_list(*, limit, **kw):
        return SimpleNamespace(data=[SimpleNamespace(id="file_1", filename="a.pdf", mime_type="application/pdf",
                               size_bytes=10, created_at="t", downloadable=True)], has_more=False,
                               first_id="file_1", last_id="file_1")

    async def _files_meta(fid):
        return SimpleNamespace(id=fid, filename="a.pdf", mime_type="application/pdf", size_bytes=10,
                               created_at="t", downloadable=True)

    async def _files_download(fid):
        return SimpleNamespace(read=lambda: b"PDFBYTES")

    async def _files_delete(fid):
        return SimpleNamespace(id=fid, filename=None, mime_type=None, size_bytes=None,
                               created_at=None, downloadable=None)

    provider.client = SimpleNamespace(
        models=SimpleNamespace(list=_models_list, retrieve=_models_retrieve),
        beta=SimpleNamespace(files=SimpleNamespace(
            upload=_files_upload, list=_files_list, retrieve_metadata=_files_meta,
            download=_files_download, delete=_files_delete)),
    )
    return provider


@pytest.mark.asyncio
async def test_models_list_and_retrieve() -> None:
    provider = _resource_provider()
    page = await provider.list_models(limit=5)
    assert isinstance(page, ResourcePage) and isinstance(page[0], ModelInfo)
    assert page[0].id == "claude-opus-4-8" and page[0].provider == "anthropic"
    one = await provider.retrieve_model("claude-opus-4-8")
    assert one.display_name == "Opus"


@pytest.mark.asyncio
async def test_files_lifecycle() -> None:
    provider = _resource_provider()
    uploaded = await provider.upload_file("a.pdf")
    assert isinstance(uploaded, FileObject) and uploaded.id == "file_1"
    listed = await provider.list_files()
    assert listed[0].mime_type == "application/pdf"
    meta = await provider.retrieve_file_metadata("file_1")
    assert meta.downloadable is True
    data = await provider.download_file("file_1")
    assert data == b"PDFBYTES"
    deleted = await provider.delete_file("file_1")
    assert deleted.id == "file_1"
