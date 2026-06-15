"""Phase 8: Anthropic thinking, structured outputs, native tools, and rich results.

Covers lossless rich-result parsing (signed/redacted thinking, citations, server-tool
results, refusal, stop_details), the structured-output (output_config.format) contract,
native AnthropicServerTool descriptors, thinking replay, and fast-mode eligibility.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from llm_client.content import ReasoningBlock, content_blocks_to_anthropic_content
from llm_client.providers.anthropic import AnthropicProvider
from llm_client.tools import AnthropicServerTool


def _provider(**model_attrs: Any) -> AnthropicProvider:
    provider = AnthropicProvider.__new__(AnthropicProvider)
    provider._model = SimpleNamespace(**model_attrs)
    return provider


# --- rich result parsing -------------------------------------------------------------

def test_parse_preserves_signed_and_redacted_thinking() -> None:
    response = SimpleNamespace(
        stop_reason="end_turn",
        content=[
            SimpleNamespace(type="thinking", thinking="let me think", signature="sig-abc"),
            SimpleNamespace(type="redacted_thinking", data="ENCRYPTED"),
            SimpleNamespace(type="text", text="the answer", citations=None),
        ],
    )
    parsed = AnthropicProvider._parse_anthropic_response(_provider(), response)
    assert parsed["content"] == "the answer"
    assert parsed["reasoning"] == "let me think"
    items = parsed["provider_items"]
    assert {"type": "thinking", "thinking": "let me think", "signature": "sig-abc"} in items
    assert {"type": "redacted_thinking", "data": "ENCRYPTED"} in items


def test_parse_preserves_citations_and_server_tool_blocks() -> None:
    cited = {"type": "text", "text": "per the source", "citations": [{"type": "char_location"}]}
    server = {"type": "web_search_tool_result", "tool_use_id": "tu_1", "content": [{"title": "x"}]}
    response = SimpleNamespace(stop_reason="end_turn", content=[cited, server])
    parsed = AnthropicProvider._parse_anthropic_response(_provider(), response)
    assert cited in parsed["provider_items"]
    assert server in parsed["provider_items"]


def test_parse_refusal_and_stop_details() -> None:
    response = SimpleNamespace(
        stop_reason="refusal",
        stop_details={"type": "refusal", "category": "policy"},
        content=[SimpleNamespace(type="text", text="I can't help with that", citations=None)],
    )
    parsed = AnthropicProvider._parse_anthropic_response(_provider(), response)
    assert parsed["refusal"] == "I can't help with that"
    assert parsed["stop_details"] == {"type": "refusal", "category": "policy"}


# --- thinking replay (request side) --------------------------------------------------

def test_signed_reasoning_block_replays_as_thinking_block() -> None:
    content = content_blocks_to_anthropic_content([ReasoningBlock(text="prior", signature="sig-1")])
    assert content == [{"type": "thinking", "thinking": "prior", "signature": "sig-1"}]


def test_unsigned_reasoning_block_replays_as_text() -> None:
    content = content_blocks_to_anthropic_content([ReasoningBlock(text="prior")])
    assert content == "prior"


# --- structured outputs --------------------------------------------------------------

def test_resolve_output_format_variants() -> None:
    rf = AnthropicProvider._resolve_output_format
    assert rf("json") == {"type": "json_object"}
    assert rf(None) is None
    # Bare JSON schema -> wrapped json_schema
    schema = {"type": "object", "properties": {"a": {"type": "string"}}}
    assert rf(schema) == {"type": "json_schema", "schema": schema}
    # Explicit format spec passed through
    spec = {"type": "json_schema", "schema": schema}
    assert rf(spec) == spec


def test_resolve_output_format_from_schema_provider() -> None:
    class Model:
        @staticmethod
        def model_json_schema() -> dict[str, Any]:
            return {"type": "object", "properties": {}}

    assert AnthropicProvider._resolve_output_format(Model) == {
        "type": "json_schema",
        "schema": {"type": "object", "properties": {}},
    }


def test_apply_output_format_sets_output_config_distinct_from_tools() -> None:
    provider = _provider()
    params: dict[str, Any] = {}
    provider._apply_output_format(params, {"type": "object", "properties": {"x": {"type": "number"}}})
    assert params["output_config"]["format"]["type"] == "json_schema"
    assert "tools" not in params  # output format must not leak into tool schemas


# --- native server tools -------------------------------------------------------------

def test_server_tool_descriptors_and_validation() -> None:
    assert AnthropicServerTool.web_search().to_dict() == {"type": "web_search_20250305", "name": "web_search"}
    assert AnthropicServerTool.web_fetch(version="20250910").family == "web_fetch"
    with pytest.raises(ValueError, match="Unknown Anthropic server tool family"):
        AnthropicServerTool(type="totally_made_up")


def test_convert_tools_mixes_function_and_server_tools() -> None:
    fn = SimpleNamespace(name="lookup", description="d", parameters={"type": "object"})
    converted = AnthropicProvider._convert_tools_for_anthropic([fn, AnthropicServerTool.web_search()])
    assert {"name": "lookup", "description": "d", "input_schema": {"type": "object"}} in converted
    assert {"type": "web_search_20250305", "name": "web_search"} in converted


def test_convert_tools_rejects_openai_native_descriptors() -> None:
    from llm_client.tools import ResponsesBuiltinTool

    with pytest.raises(ValueError):
        AnthropicProvider._convert_tools_for_anthropic([ResponsesBuiltinTool.web_search()])


# --- fast mode eligibility -----------------------------------------------------------

def test_fast_mode_only_on_opus_4_6() -> None:
    ok = _provider(key="claude-opus-4-6", model_name="claude-opus-4-6")
    ok._validate_anthropic_speed("fast")  # no raise
    bad = _provider(key="claude-opus-4-8", model_name="claude-opus-4-8")
    with pytest.raises(ValueError):
        bad._validate_anthropic_speed("fast")
