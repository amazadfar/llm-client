"""Phase 6 contract tests for the real provider Batch APIs (mocked SDKs).

OpenAI Batch (file-backed JSONL) and Anthropic Message Batches: create/retrieve/list/
cancel/results lifecycle, per-item custom_id + error preservation, status normalization,
and provider-batch execution/price mode. Distinct from local concurrency.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from telic.batch_api import BatchRequestItem, normalize_batch_status
from telic.providers.anthropic import AnthropicProvider
from telic.providers.openai import OpenAIProvider


# --- status normalization ------------------------------------------------------------

def test_status_normalization() -> None:
    assert normalize_batch_status("openai", "cancelling") == "canceling"
    assert normalize_batch_status("openai", "completed") == "completed"
    assert normalize_batch_status("anthropic", "ended") == "completed"
    assert normalize_batch_status("anthropic", "in_progress") == "in_progress"


# --- Anthropic Message Batches -------------------------------------------------------

class _AsyncResults:
    def __init__(self, entries: list[Any]) -> None:
        self._entries = entries

    def __aiter__(self):
        self._it = iter(self._entries)
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration


def _anthropic_provider() -> AnthropicProvider:
    provider = AnthropicProvider.__new__(AnthropicProvider)
    captured: dict[str, Any] = {}

    async def _create(*, requests):
        captured["requests"] = requests
        return SimpleNamespace(id="msgbatch_1", processing_status="in_progress",
                               request_counts=SimpleNamespace(processing=2, succeeded=0, errored=0, canceled=0, expired=0),
                               created_at="t0", expires_at="t1")

    async def _retrieve(bid):
        return SimpleNamespace(id=bid, processing_status="ended",
                               request_counts=SimpleNamespace(processing=0, succeeded=1, errored=1, canceled=0, expired=0),
                               created_at="t0", expires_at="t1")

    async def _cancel(bid):
        return SimpleNamespace(id=bid, processing_status="canceling", request_counts=None, created_at="t0", expires_at="t1")

    async def _list(*, limit):
        return SimpleNamespace(data=[SimpleNamespace(id="msgbatch_1", processing_status="ended",
                               request_counts=None, created_at="t0", expires_at="t1")])

    async def _results(bid):
        ok = SimpleNamespace(custom_id="r1", result=SimpleNamespace(
            type="succeeded",
            message=SimpleNamespace(content=[{"type": "text", "text": "hi"}],
                                    usage=SimpleNamespace(to_dict=lambda: {"input_tokens": 5, "output_tokens": 2}))))
        err = SimpleNamespace(custom_id="r2", result=SimpleNamespace(
            type="errored", error=SimpleNamespace(to_dict=lambda: {"type": "invalid_request"})))
        return _AsyncResults([ok, err])

    provider.client = SimpleNamespace(messages=SimpleNamespace(batches=SimpleNamespace(
        create=_create, retrieve=_retrieve, cancel=_cancel, list=_list, results=_results)))
    provider._captured = captured
    return provider


@pytest.mark.asyncio
async def test_anthropic_create_and_lifecycle() -> None:
    provider = _anthropic_provider()
    job = await provider.create_message_batch([
        BatchRequestItem("r1", {"model": "claude-opus-4-8", "max_tokens": 16, "messages": []}),
        BatchRequestItem("r2", {"model": "claude-opus-4-8", "max_tokens": 16, "messages": []}),
    ])
    assert job.id == "msgbatch_1" and job.provider == "anthropic"
    assert job.status == "in_progress" and job.raw_status == "in_progress"
    assert job.execution_mode == "provider_batch" and job.price_mode == "batch"
    assert provider._captured["requests"][0]["custom_id"] == "r1"

    retrieved = await provider.retrieve_batch("msgbatch_1")
    assert retrieved.status == "completed" and retrieved.is_terminal
    assert retrieved.request_counts["succeeded"] == 1

    canceled = await provider.cancel_batch("msgbatch_1")
    assert canceled.status == "canceling"
    listed = await provider.list_batches()
    assert listed[0].id == "msgbatch_1"


@pytest.mark.asyncio
async def test_anthropic_results_preserve_custom_ids_and_errors() -> None:
    provider = _anthropic_provider()
    results = await provider.batch_results("msgbatch_1")
    by_id = {r.custom_id: r for r in results}
    assert by_id["r1"].ok and by_id["r1"].usage == {"input_tokens": 5, "output_tokens": 2}
    assert by_id["r2"].status == "errored" and by_id["r2"].error == {"type": "invalid_request"}


# --- OpenAI Batch (file-backed) ------------------------------------------------------

def _openai_provider(output_lines: list[dict] | None = None) -> OpenAIProvider:
    provider = OpenAIProvider.__new__(OpenAIProvider)
    captured: dict[str, Any] = {}

    async def _files_create(*, file, purpose):
        captured["upload"] = {"filename": file[0], "jsonl": file[1].decode("utf-8"), "purpose": purpose}
        return SimpleNamespace(id="file_in_1")

    async def _batches_create(*, input_file_id, endpoint, completion_window, metadata=None):
        captured["create"] = {"input_file_id": input_file_id, "endpoint": endpoint}
        return SimpleNamespace(id="batch_1", status="validating", endpoint=endpoint,
                               request_counts=SimpleNamespace(total=2, completed=0, failed=0),
                               created_at="t0", expires_at="t1", output_file_id=None)

    async def _batches_retrieve(bid):
        return SimpleNamespace(id=bid, status="completed", endpoint="/v1/responses",
                               request_counts=SimpleNamespace(total=2, completed=2, failed=0),
                               created_at="t0", expires_at="t1", output_file_id="file_out_1")

    async def _batches_cancel(bid):
        return SimpleNamespace(id=bid, status="cancelling", endpoint="/v1/responses",
                               request_counts=None, created_at="t0", expires_at="t1", output_file_id=None)

    async def _batches_list(*, limit):
        return SimpleNamespace(data=[SimpleNamespace(id="batch_1", status="completed", endpoint="/v1/responses",
                               request_counts=None, created_at="t0", expires_at="t1", output_file_id="file_out_1")])

    lines = output_lines or [
        {"custom_id": "r1", "response": {"status_code": 200, "body": {"output_text": "hi", "usage": {"input_tokens": 5}}}},
        {"custom_id": "r2", "error": {"code": "invalid_request", "message": "bad"}},
    ]
    jsonl = "\n".join(json.dumps(line) for line in lines)

    async def _files_content(file_id):
        return SimpleNamespace(text=jsonl)

    provider.client = SimpleNamespace(
        files=SimpleNamespace(create=_files_create, content=_files_content),
        batches=SimpleNamespace(create=_batches_create, retrieve=_batches_retrieve,
                                cancel=_batches_cancel, list=_batches_list),
    )
    provider._captured = captured
    return provider


@pytest.mark.asyncio
async def test_openai_create_uploads_jsonl_and_starts_job() -> None:
    provider = _openai_provider()
    job = await provider.create_batch([
        BatchRequestItem("r1", {"model": "gpt-5.5", "input": "hi"}),
        BatchRequestItem("r2", {"model": "gpt-5.5", "input": "yo"}),
    ], endpoint="responses")
    assert job.id == "batch_1" and job.provider == "openai"
    assert job.status == "validating" and job.execution_mode == "provider_batch" and job.price_mode == "batch"
    # JSONL upload carries one line per request with custom_id + url + body
    upload = provider._captured["upload"]
    first = json.loads(upload["jsonl"].splitlines()[0])
    assert first["custom_id"] == "r1" and first["url"] == "/v1/responses" and first["method"] == "POST"
    assert provider._captured["create"]["input_file_id"] == "file_in_1"


@pytest.mark.asyncio
async def test_openai_lifecycle_and_results() -> None:
    provider = _openai_provider()
    retrieved = await provider.retrieve_batch("batch_1")
    assert retrieved.status == "completed" and retrieved.output_file_id == "file_out_1"
    canceled = await provider.cancel_batch("batch_1")
    assert canceled.status == "canceling"

    results = await provider.batch_results("batch_1")
    by_id = {r.custom_id: r for r in results}
    assert by_id["r1"].ok and by_id["r1"].usage == {"input_tokens": 5}
    assert by_id["r2"].status == "errored" and by_id["r2"].error["code"] == "invalid_request"
