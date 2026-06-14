"""
Anthropic (Claude) provider implementation.

This module implements the Provider protocol for Anthropic's Claude API,
supporting chat completions with tool calling and streaming.
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    cast,
)

from ..cache import CacheSettings, build_cache_core
from ..cache.serializers import cache_dict_to_result, result_to_cache_dict
from ..content import (
    AudioBlock,
    FileBlock,
    ImageBlock,
    MetadataBlock,
    ReasoningBlock,
    TextBlock,
    ToolCallBlock,
    ToolResultBlock,
    content_blocks_to_anthropic_content,
    content_blocks_to_text,
    message_to_content_blocks,
)
from ..errors import (
    failure_to_completion_result,
    failure_to_stream_error_data,
    normalize_exception,
    normalize_provider_failure,
)
from ..batch_api import BatchJob, BatchRequestItem, BatchResultItem, normalize_batch_status
from ..hashing import cache_key as compute_cache_key
from ..rate_limit import Limiter
from ..tools.base import ToolDefinition, ensure_function_tools_only
from .base import BaseProvider
from .types import (
    CompletionResult,
    EmbeddingResult,
    Message,
    MessageInput,
    Role,
    StreamEvent,
    StreamEventType,
    ToolCall,
    ToolCallDelta,
    Usage,
)

if TYPE_CHECKING:
    from ..models import ModelProfile

try:
    import anthropic
    from anthropic import AsyncAnthropic

    ANTHROPIC_AVAILABLE = True
except Exception:  # pragma: no cover - import guard
    anthropic = None  # type: ignore[assignment]
    AsyncAnthropic = None  # type: ignore[assignment, misc]
    ANTHROPIC_AVAILABLE = False


class AnthropicProvider(BaseProvider):
    """
    Anthropic Claude API provider implementation.

    Supports:
    - Chat completions (with and without streaming)
    - Tool/function calling
    - Extended thinking (for supported models)
    - Rate limiting

    Note: Anthropic does not support embeddings natively.

    Example:
        ```python
        provider = AnthropicProvider(model="claude-sonnet-4-6")
        result = await provider.complete("Hello, world!")
        print(result.content)
        ```

    Requires:
        - anthropic package: `pip install anthropic`
        - ANTHROPIC_API_KEY environment variable or api_key parameter
    """

    def _failure(self, error: Exception, *, operation: str):
        return normalize_exception(
            error,
            provider="anthropic",
            model=self.model_name,
            operation=operation,
        )

    # Map our Role enum to Anthropic's role strings
    ROLE_MAP = {
        Role.USER: "user",
        Role.ASSISTANT: "assistant",
        # SYSTEM is handled separately in Anthropic API
        # TOOL results use "user" role with tool_result content
    }

    def __init__(
        self,
        model: type[ModelProfile] | str,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        max_tokens: int = 4096,
        default_temperature: float | None = None,
        max_retries: int = 2,
        timeout: float | None = None,
        # Cache settings
        cache_dir: str | Path | None = None,
        cache_backend: Literal["qdrant", "pg_redis", "fs"] | None = None,
        cache_collection: str | None = None,
        pg_dsn: str | None = None,
        redis_url: str | None = None,
        qdrant_url: str | None = None,
        qdrant_api_key: str | None = None,
        redis_ttl_seconds: int = 60 * 60 * 24,
        compress_pg: bool = True,
    ) -> None:
        """
        Initialize the Anthropic provider.

        Args:
            model: ModelProfile class or model key string (e.g., "claude-sonnet-4-6")
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            base_url: Custom API base URL
            max_tokens: Default max tokens for completions (Anthropic requires this)
            default_temperature: Default temperature for completions
            max_retries: Number of retries for transient failures (SDK built-in, default: 2)
            timeout: Request timeout in seconds (SDK default: 600s)
            cache_dir: Directory for file-based caching
            cache_backend: Cache backend type ("fs", "qdrant", "pg_redis", or None)
            cache_collection: Collection/table name for caching
            pg_dsn: PostgreSQL connection string
            redis_url: Redis connection URL
            qdrant_url: Qdrant server URL
            qdrant_api_key: Qdrant API key
            redis_ttl_seconds: Redis TTL for cached items
            compress_pg: Whether to compress PostgreSQL cache entries
        """
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("anthropic package is not installed. Install it with: pip install anthropic")

        super().__init__(model)

        self.max_tokens = max_tokens
        self.default_temperature = default_temperature

        # Cache setup
        if isinstance(cache_dir, str):
            cache_dir = Path(cache_dir)
        self.cache_dir = cache_dir
        self.default_cache_collection = cache_collection

        if self.cache_dir and cache_backend == "fs":
            self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Initialize Anthropic client with retry and timeout config
        client_kwargs: dict[str, Any] = {
            "max_retries": max_retries,
        }

        if timeout is not None:
            client_kwargs["timeout"] = timeout

        if api_key:
            client_kwargs["api_key"] = api_key
        elif os.environ.get("ANTHROPIC_API_KEY"):
            client_kwargs["api_key"] = os.environ["ANTHROPIC_API_KEY"]

        if base_url:
            client_kwargs["base_url"] = base_url

        self.client = AsyncAnthropic(**client_kwargs)

        # Initialize rate limiter (uses model's rate_limits if available)
        self.limiter = Limiter(self._model)

        # Initialize cache
        backend_name = cache_backend or "none"
        self.cache = build_cache_core(
            CacheSettings(
                backend=backend_name,
                client_type=self._model.category if hasattr(self._model, "category") else "chat",
                default_collection=cache_collection,
                cache_dir=self.cache_dir,
                pg_dsn=pg_dsn,
                redis_url=redis_url,
                qdrant_url=qdrant_url,
                qdrant_api_key=qdrant_api_key,
                redis_ttl_seconds=redis_ttl_seconds,
                compress=compress_pg,
            )
        )

    async def warm_cache(self) -> None:
        """Pre-warm the cache (for backends that support it)."""
        await self.cache.warm()

    @staticmethod
    def _cache_key(api: str, params: dict[str, Any]) -> str:
        """Generate a cache key from API endpoint and parameters."""
        return compute_cache_key(api, params)

    # Cache serialization methods imported from cache.serializers
    _cached_to_result = staticmethod(cache_dict_to_result)
    _result_to_cache = staticmethod(result_to_cache_dict)

    def _convert_messages_for_anthropic(
        self,
        messages: list[Message],
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """
        Convert our Message format to Anthropic's format.

        Returns:
            Tuple of (system_message, messages_list)

        Note: Anthropic handles system message separately from messages.
        """
        system_message = None
        anthropic_messages = []

        for msg in messages:
            blocks = message_to_content_blocks(msg)
            if msg.role == Role.SYSTEM:
                # Anthropic requires system as a separate parameter
                system_text = content_blocks_to_text(blocks)
                if system_message and system_text:
                    system_message += "\n" + system_text
                elif system_text:
                    system_message = system_text
                continue

            if msg.role == Role.TOOL:
                # Tool results in Anthropic use a special format
                tool_result_blocks = [block for block in blocks if isinstance(block, ToolResultBlock)]
                tool_result = tool_result_blocks[0] if tool_result_blocks else None
                anthropic_messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": (tool_result.tool_call_id if tool_result else msg.tool_call_id),
                                "content": (tool_result.content if tool_result else content_blocks_to_text(blocks)),
                            }
                        ],
                    }
                )
                continue

            if msg.role == Role.ASSISTANT and msg.tool_calls:
                # Assistant message with tool calls
                content_blocks = self._content_blocks_to_anthropic_content(blocks, allow_tool_use=False)

                for tc in msg.tool_calls:
                    # Parse arguments from JSON string
                    try:
                        parsed_args = json.loads(tc.arguments) if tc.arguments else {}
                    except json.JSONDecodeError:
                        parsed_args = {}
                    input_data: dict[str, Any] = parsed_args if isinstance(parsed_args, dict) else {}

                    content_blocks.append(
                        {
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.name,
                            "input": input_data,
                        }
                    )

                anthropic_messages.append(
                    {
                        "role": "assistant",
                        "content": content_blocks,
                    }
                )
                continue

            # Regular user/assistant message
            role = self.ROLE_MAP.get(msg.role, "user")
            content = self._content_blocks_to_anthropic_content(blocks, allow_tool_use=False)
            anthropic_messages.append(
                {
                    "role": role,
                    "content": content if isinstance(content, list) else (content or ""),
                }
            )

        return system_message, anthropic_messages

    @staticmethod
    def _content_blocks_to_anthropic_content(
        blocks: list[Any],
        *,
        allow_tool_use: bool = False,
    ) -> str | list[dict[str, Any]]:
        return content_blocks_to_anthropic_content(blocks, allow_tool_use=allow_tool_use)

    @staticmethod
    def _convert_tools_for_anthropic(
        tools: list[ToolDefinition] | None,
    ) -> list[dict[str, Any]] | None:
        """Convert our Tool format to Anthropic's format."""
        function_tools = ensure_function_tools_only(tools, provider="anthropic")
        if not function_tools:
            return None

        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.parameters,
            }
            for tool in function_tools
        ]

    @staticmethod
    def _extract_tool_calls_from_response(
        content_blocks: list[Any],
    ) -> tuple[str | None, list[ToolCall] | None]:
        """
        Extract text content and tool calls from Anthropic response.

        Returns:
            Tuple of (text_content, tool_calls)
        """
        text_parts = []
        tool_calls = []

        for block in content_blocks:
            if hasattr(block, "type"):
                block_type = block.type
            elif isinstance(block, dict):
                block_type = block.get("type")
            else:
                continue

            if block_type == "text":
                text = block.text if hasattr(block, "text") else block.get("text", "")
                text_parts.append(text)
            elif block_type == "tool_use":
                tool_id = block.id if hasattr(block, "id") else block.get("id", "")
                tool_name = block.name if hasattr(block, "name") else block.get("name", "")
                tool_input = block.input if hasattr(block, "input") else block.get("input", {})

                tool_calls.append(
                    ToolCall(
                        id=tool_id,
                        name=tool_name,
                        arguments=json.dumps(tool_input) if tool_input else "{}",
                    )
                )

        text_content = "\n".join(text_parts) if text_parts else None
        return text_content, tool_calls if tool_calls else None

    @staticmethod
    def _anthropic_usage_to_dict(usage: Any) -> dict[str, Any]:
        if usage is None:
            return {}
        if isinstance(usage, dict):
            return dict(usage)
        if hasattr(usage, "to_dict"):
            return dict(usage.to_dict())
        if hasattr(usage, "model_dump"):
            return dict(usage.model_dump())
        fields = (
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "cache_read_input_tokens",
            "cache_creation_input_tokens",
            "cache_creation_5m_input_tokens",
            "cache_creation_1h_input_tokens",
        )
        return {field: getattr(usage, field) for field in fields if hasattr(usage, field)}

    def _anthropic_pricing_multiplier(self, params: dict[str, Any]) -> float:
        features = getattr(self._model, "pricing_features", {}) or {}
        residency = features.get("data_residency") if isinstance(features, dict) else None
        if params.get("inference_geo") == "us" and isinstance(residency, dict):
            return float(residency.get("inference_geo_us_multiplier") or 1.0)
        return 1.0

    @staticmethod
    def _cache_creation_ttl_from_params(params: dict[str, Any]) -> str:
        ttls: set[str] = set()

        def walk(value: Any) -> None:
            if isinstance(value, dict):
                cache_control = value.get("cache_control")
                if isinstance(cache_control, dict):
                    ttl = cache_control.get("ttl")
                    if ttl in {"5m", "1h"}:
                        ttls.add(str(ttl))
                for nested in value.values():
                    walk(nested)
            elif isinstance(value, list):
                for nested in value:
                    walk(nested)

        walk(params)
        return "1h" if ttls == {"1h"} else "5m"

    @staticmethod
    def _apply_usage_pricing_multiplier(usage: Usage, multiplier: float) -> Usage:
        if multiplier == 1.0:
            return usage
        usage.input_cost *= multiplier
        usage.output_cost *= multiplier
        usage.cache_read_input_cost *= multiplier
        usage.cache_creation_input_cost *= multiplier
        usage.total_cost *= multiplier
        return usage

    def _parse_anthropic_usage(
        self,
        usage: Any,
        *,
        pricing_multiplier: float = 1.0,
        cache_creation_ttl: str = "5m",
    ) -> Usage:
        """Parse Anthropic usage into our Usage format."""
        raw_usage = self._anthropic_usage_to_dict(usage)
        if (
            cache_creation_ttl == "1h"
            and "cache_creation_input_tokens" in raw_usage
            and "cache_creation_1h_input_tokens" not in raw_usage
            and "cache_creation_5m_input_tokens" not in raw_usage
        ):
            raw_usage["cache_creation_1h_input_tokens"] = raw_usage["cache_creation_input_tokens"]
        parsed = self.parse_usage(raw_usage)
        if parsed.total_tokens == 0:
            parsed.total_tokens = (
                parsed.input_tokens
                + parsed.output_tokens
                + parsed.cache_read_input_tokens
                + parsed.cache_creation_input_tokens
            )
        return self._apply_usage_pricing_multiplier(parsed, pricing_multiplier)

    @staticmethod
    def _sanitize_request_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
        # Generic reasoning controls are now consumed as named parameters and translated
        # (see _resolve_anthropic_effort); only None-filtering of leftover kwargs remains.
        return {key: value for key, value in kwargs.items() if value is not None}

    def _resolve_anthropic_effort(
        self,
        effort: str | None,
        reasoning_effort: str | None,
        reasoning: dict[str, Any] | None,
    ) -> str | None:
        """Resolve Anthropic ``output_config.effort``, model-aware.

        An explicit Anthropic ``effort`` wins. Otherwise the generic (OpenAI-style)
        ``reasoning_effort`` -- or the ``effort`` inside a generic ``reasoning`` object --
        is translated to Anthropic's effort. The candidate is validated against the
        model's supported efforts, so an unsupported value (or an effort on a model that
        has none) raises a clear error instead of being silently dropped (audit A-API-002
        / A-API-003).
        """
        candidate = effort
        if candidate is None and reasoning_effort is not None:
            candidate = reasoning_effort
        if candidate is None and isinstance(reasoning, dict) and reasoning.get("effort"):
            candidate = reasoning.get("effort")
        if candidate is None:
            return None
        supported = list(getattr(self._model, "reasoning_efforts", []) or [])
        if not supported:
            raise ValueError(
                f"Model {self.model_name!r} does not support a reasoning effort control."
            )
        if candidate not in supported:
            raise ValueError(
                f"Effort {candidate!r} is not supported by {self.model_name!r}; "
                f"choose from {supported}."
            )
        return candidate

    def _validate_anthropic_speed(self, speed: str) -> None:
        """Fast mode (``speed='fast'``) is only valid on Opus 4.6 (audit A-API-010)."""
        if speed == "fast" and "opus-4-6" not in str(getattr(self._model, "key", "")):
            raise ValueError(
                f"speed='fast' is only supported on Claude Opus 4.6, not {self.model_name!r}."
            )

    def _apply_sampling_temperature(
        self,
        params: dict[str, Any],
        temperature: float | None,
        thinking: dict[str, Any] | None = None,
    ) -> None:
        """Apply temperature in a model-aware way.

        Anthropic extended thinking requires temperature to be unset (or exactly ``1``).
        When thinking is enabled, an explicit incompatible temperature is rejected and the
        package-level default temperature is omitted rather than injecting a value the
        model would reject.
        """
        thinking_enabled = isinstance(thinking, dict) and thinking.get("type") == "enabled"
        if temperature is not None:
            if thinking_enabled and float(temperature) != 1.0:
                raise ValueError(
                    "Anthropic extended thinking requires temperature to be unset or 1; "
                    f"got temperature={temperature}."
                )
            params["temperature"] = temperature
        elif self.default_temperature is not None and not thinking_enabled:
            params["temperature"] = self.default_temperature

    def _apply_anthropic_request_controls(
        self,
        params: dict[str, Any],
        *,
        temperature: float | None,
        thinking: dict[str, Any] | None,
        effort: str | None,
        reasoning_effort: str | None,
        reasoning: dict[str, Any] | None,
        speed: str | None,
        service_tier: str | None,
        top_p: float | None,
        metadata: dict[str, Any] | None,
        container: str | None,
    ) -> None:
        """Apply Phase 4 request controls (shared and Anthropic-specific) to ``params``.

        Shared by complete() and stream() so both paths validate and translate identically.
        """
        resolved_effort = self._resolve_anthropic_effort(effort, reasoning_effort, reasoning)
        self._apply_sampling_temperature(params, temperature, thinking)
        if thinking is not None:
            params["thinking"] = thinking
        if resolved_effort is not None:
            output_config = dict(params.get("output_config") or {})
            output_config["effort"] = resolved_effort
            params["output_config"] = output_config
        if speed is not None:
            self._validate_anthropic_speed(speed)
            params["speed"] = speed
        if service_tier is not None:
            params["service_tier"] = service_tier
        if top_p is not None:
            params["top_p"] = top_p
        if metadata is not None:
            params["metadata"] = metadata
        if container is not None:
            params["container"] = container

    async def complete(
        self,
        messages: MessageInput,
        *,
        tools: list[ToolDefinition] | None = None,
        tool_choice: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: str | dict[str, Any] | type | None = None,
        service_tier: str | None = None,
        top_p: float | None = None,
        metadata: dict[str, Any] | None = None,
        thinking: dict[str, Any] | None = None,
        effort: str | None = None,
        speed: str | None = None,
        container: str | None = None,
        reasoning_effort: str | None = None,
        reasoning: dict[str, Any] | None = None,
        cache_response: bool = False,
        cache_collection: str | None = None,
        rewrite_cache: bool = False,
        regen_cache: bool = False,
        **kwargs: Any,
    ) -> CompletionResult:
        """
        Generate a completion using Claude.

        Args:
            messages: Input messages
            tools: Available tools for the model
            tool_choice: Tool selection mode ("auto", "any", "tool" or specific tool name)
            temperature: Sampling temperature
            max_tokens: Maximum output tokens
            response_format: Not fully supported by Anthropic (JSON mode via prompting)
            cache_response: Whether to cache the response
            cache_collection: Cache collection name
            rewrite_cache: Create new cache entry even if one exists
            regen_cache: Regenerate cache (ignore existing)
            **kwargs: Additional API parameters

        Returns:
            CompletionResult with the model's response
        """
        # Normalize and convert messages
        msg_objects = self._normalize_messages(messages)
        system_message, anthropic_messages = self._convert_messages_for_anthropic(msg_objects)

        # Build params
        params: dict[str, Any] = {
            "model": self.model_name,
            "messages": anthropic_messages,
            "max_tokens": max_tokens or self.max_tokens,
        }

        if system_message:
            params["system"] = system_message

        self._apply_anthropic_request_controls(
            params,
            temperature=temperature,
            thinking=thinking,
            effort=effort,
            reasoning_effort=reasoning_effort,
            reasoning=reasoning,
            speed=speed,
            service_tier=service_tier,
            top_p=top_p,
            metadata=metadata,
            container=container,
        )

        # Add tools
        anthropic_tools = self._convert_tools_for_anthropic(tools)
        if anthropic_tools:
            params["tools"] = anthropic_tools

            # Handle tool_choice
            if tool_choice:
                if tool_choice == "auto":
                    params["tool_choice"] = {"type": "auto"}
                elif tool_choice == "none":
                    # Remove tools to prevent tool use
                    params.pop("tools", None)
                elif tool_choice == "required" or tool_choice == "any":
                    params["tool_choice"] = {"type": "any"}
                else:
                    # Specific tool name
                    params["tool_choice"] = {"type": "tool", "name": tool_choice}

        # Add extra kwargs
        params.update(self._sanitize_request_kwargs(kwargs))
        pricing_multiplier = self._anthropic_pricing_multiplier(params)
        cache_creation_ttl = self._cache_creation_ttl_from_params(params)

        # Build cache params dict for cache key
        cache_params = {
            "model": self.model_name,
            "messages": [str(m) for m in msg_objects],
            "temperature": temperature or self.default_temperature,
            "max_tokens": max_tokens or self.max_tokens,
            "response_format": response_format,
        }
        if tools:
            cache_params["tools"] = [t.name for t in tools]
        if system_message:
            cache_params["system"] = system_message

        # Check cache before making request
        if cache_response:
            identifier = self._cache_key("anthropic.messages.create", cache_params)

            effective_collection = cache_collection or self.default_cache_collection
            cached, _ = await self.cache.get_cached(
                identifier,
                rewrite_cache=rewrite_cache,
                regen_cache=regen_cache,
                only_ok=True,
                collection=effective_collection,
            )
            if cached:
                return self._cached_to_result(cached)
        else:
            identifier = None

        # Count input tokens for rate limiting
        input_tokens = self.count_tokens(anthropic_messages)

        async with self.limiter.limit(tokens=input_tokens, requests=1) as limit_ctx:
            try:
                response = await self.client.messages.create(**params)

                # Extract content and tool calls
                text_content, tool_calls = self._extract_tool_calls_from_response(response.content)

                # Parse usage
                usage = self._parse_anthropic_usage(
                    response.usage,
                    pricing_multiplier=pricing_multiplier,
                    cache_creation_ttl=cache_creation_ttl,
                )

                # Track output tokens for rate limiting
                limit_ctx.output_tokens = usage.output_tokens

                result = CompletionResult(
                    content=text_content,
                    tool_calls=tool_calls,
                    usage=usage,
                    model=self.model_name,
                    finish_reason=response.stop_reason,
                    status=200,
                    raw_response=response,
                )

            except anthropic.APIConnectionError as e:
                result = failure_to_completion_result(
                    normalize_provider_failure(
                        status=503,
                        message=f"Connection error: {e}",
                        provider="anthropic",
                        model=self.model_name,
                        operation="complete",
                    ),
                    model=self.model_name,
                )
            except anthropic.RateLimitError as e:
                result = failure_to_completion_result(self._failure(e, operation="complete"), model=self.model_name)
            except anthropic.APIStatusError as e:
                result = failure_to_completion_result(self._failure(e, operation="complete"), model=self.model_name)
            except Exception as e:
                result = failure_to_completion_result(self._failure(e, operation="complete"), model=self.model_name)

        # Cache successful responses
        if cache_response and identifier and result.ok:
            effective_collection = cache_collection or self.default_cache_collection
            await self.cache.put_cached(
                identifier,
                rewrite_cache=rewrite_cache,
                regen_cache=regen_cache,
                response=self._result_to_cache(result, cache_params),
                model_name=self.model_name,
                log_errors=True,
                collection=effective_collection,
            )

        return result

    async def stream(
        self,
        messages: MessageInput,
        *,
        tools: list[ToolDefinition] | None = None,
        tool_choice: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: str | dict[str, Any] | type | None = None,
        service_tier: str | None = None,
        top_p: float | None = None,
        metadata: dict[str, Any] | None = None,
        thinking: dict[str, Any] | None = None,
        effort: str | None = None,
        speed: str | None = None,
        container: str | None = None,
        reasoning_effort: str | None = None,
        reasoning: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamEvent]:
        """
        Stream a completion as events.

        Anthropic uses Server-Sent Events with different event types:
        - message_start: Initial message metadata
        - content_block_start: Start of a content block (text or tool_use)
        - content_block_delta: Content chunk
        - content_block_stop: End of content block
        - message_delta: Final message updates (stop reason, usage)
        - message_stop: Stream complete

        Args:
            messages: Input messages
            tools: Available tools
            tool_choice: Tool selection mode
            temperature: Sampling temperature
            max_tokens: Maximum output tokens
            **kwargs: Additional API parameters

        Yields:
            StreamEvent objects for each chunk
        """
        # Normalize and convert messages
        msg_objects = self._normalize_messages(messages)
        system_message, anthropic_messages = self._convert_messages_for_anthropic(msg_objects)

        # Build params
        params: dict[str, Any] = {
            "model": self.model_name,
            "messages": anthropic_messages,
            "max_tokens": max_tokens or self.max_tokens,
        }

        if system_message:
            params["system"] = system_message

        self._apply_anthropic_request_controls(
            params,
            temperature=temperature,
            thinking=thinking,
            effort=effort,
            reasoning_effort=reasoning_effort,
            reasoning=reasoning,
            speed=speed,
            service_tier=service_tier,
            top_p=top_p,
            metadata=metadata,
            container=container,
        )

        # Add tools
        anthropic_tools = self._convert_tools_for_anthropic(tools)
        if anthropic_tools:
            params["tools"] = anthropic_tools

            if tool_choice:
                if tool_choice == "auto":
                    params["tool_choice"] = {"type": "auto"}
                elif tool_choice == "none":
                    params.pop("tools", None)
                elif tool_choice == "required" or tool_choice == "any":
                    params["tool_choice"] = {"type": "any"}
                else:
                    params["tool_choice"] = {"type": "tool", "name": tool_choice}

        params.update(self._sanitize_request_kwargs(kwargs))
        pricing_multiplier = self._anthropic_pricing_multiplier(params)
        cache_creation_ttl = self._cache_creation_ttl_from_params(params)

        # Emit metadata event
        yield StreamEvent(
            type=StreamEventType.META, data={"model": self.model_name, "stream": True, "provider": "anthropic"}
        )

        # Track state
        content_buffer = ""
        tool_calls_buffer: dict[int, dict[str, Any]] = {}
        current_block_index = 0
        usage = None
        raw_usage: dict[str, Any] = {}
        finish_reason = None

        # Count input tokens for rate limiting
        input_tokens = self.count_tokens(anthropic_messages)

        async with self.limiter.limit(tokens=input_tokens, requests=1) as limit_ctx:
            try:
                async with self.client.messages.stream(**params) as stream:
                    async for raw_event in stream:
                        event = cast(Any, raw_event)
                        event_type = event.type

                        if event_type == "content_block_start":
                            block = event.content_block
                            block_type = block.type if hasattr(block, "type") else None

                            if block_type == "tool_use":
                                # Tool use block starting
                                tool_calls_buffer[current_block_index] = {
                                    "id": block.id,
                                    "name": block.name,
                                    "arguments": "",
                                }

                                yield StreamEvent(
                                    type=StreamEventType.TOOL_CALL_START,
                                    data=ToolCallDelta(
                                        id=block.id,
                                        index=current_block_index,
                                        name=block.name,
                                    ),
                                )

                            current_block_index = event.index

                        elif event_type == "content_block_delta":
                            delta = event.delta
                            delta_type = delta.type if hasattr(delta, "type") else None

                            if delta_type == "text_delta":
                                text = delta.text
                                content_buffer += text
                                yield StreamEvent(type=StreamEventType.TOKEN, data=text)

                            elif delta_type == "thinking_delta":
                                # Extended thinking content (for models that support it)
                                thinking = delta.thinking
                                yield StreamEvent(type=StreamEventType.REASONING, data=thinking)

                            elif delta_type == "input_json_delta":
                                # Tool input being streamed
                                partial_json = delta.partial_json
                                if event.index in tool_calls_buffer:
                                    tool_calls_buffer[event.index]["arguments"] += partial_json

                                    yield StreamEvent(
                                        type=StreamEventType.TOOL_CALL_DELTA,
                                        data=ToolCallDelta(
                                            id=tool_calls_buffer[event.index]["id"],
                                            index=event.index,
                                            arguments_delta=partial_json,
                                        ),
                                    )

                        elif event_type == "content_block_stop":
                            # Check if this was a tool use block
                            if event.index in tool_calls_buffer:
                                tc_data = tool_calls_buffer[event.index]
                                yield StreamEvent(
                                    type=StreamEventType.TOOL_CALL_END,
                                    data=ToolCall(
                                        id=tc_data["id"],
                                        name=tc_data["name"],
                                        arguments=tc_data["arguments"],
                                    ),
                                )

                        elif event_type == "message_delta":
                            # Final message updates
                            if hasattr(event, "usage") and event.usage:
                                raw_usage.update(self._anthropic_usage_to_dict(event.usage))
                                usage = self._parse_anthropic_usage(
                                    raw_usage,
                                    pricing_multiplier=pricing_multiplier,
                                    cache_creation_ttl=cache_creation_ttl,
                                )
                                # Track output tokens for rate limiting
                                limit_ctx.output_tokens = usage.output_tokens

                            if hasattr(event.delta, "stop_reason"):
                                finish_reason = event.delta.stop_reason

                        elif event_type == "message_start":
                            # Initial message with input token count
                            if hasattr(event.message, "usage") and event.message.usage:
                                raw_usage.update(self._anthropic_usage_to_dict(event.message.usage))
                                usage = self._parse_anthropic_usage(
                                    raw_usage,
                                    pricing_multiplier=pricing_multiplier,
                                    cache_creation_ttl=cache_creation_ttl,
                                )

                # Build final tool calls list
                tool_calls = None
                if tool_calls_buffer:
                    tool_calls = [
                        ToolCall(
                            id=tc["id"],
                            name=tc["name"],
                            arguments=tc["arguments"],
                        )
                        for tc in tool_calls_buffer.values()
                    ]

                # Emit usage event
                if usage:
                    yield StreamEvent(type=StreamEventType.USAGE, data=usage)

                # Emit final result
                final_result = CompletionResult(
                    content=content_buffer if content_buffer else None,
                    tool_calls=tool_calls,
                    usage=usage,
                    model=self.model_name,
                    finish_reason=finish_reason,
                    status=200,
                )

                yield StreamEvent(type=StreamEventType.DONE, data=final_result)

            except anthropic.APIConnectionError as e:
                yield StreamEvent(
                    type=StreamEventType.ERROR,
                    data=failure_to_stream_error_data(
                        normalize_provider_failure(
                            status=503,
                            message=f"Connection error: {e}",
                            provider="anthropic",
                            model=self.model_name,
                            operation="stream",
                        )
                    ),
                )
            except anthropic.RateLimitError as e:
                yield StreamEvent(type=StreamEventType.ERROR, data=failure_to_stream_error_data(self._failure(e, operation="stream")))
            except anthropic.APIStatusError as e:
                yield StreamEvent(type=StreamEventType.ERROR, data=failure_to_stream_error_data(self._failure(e, operation="stream")))
            except Exception as e:
                yield StreamEvent(type=StreamEventType.ERROR, data=failure_to_stream_error_data(self._failure(e, operation="stream")))

    async def embed(
        self,
        inputs: str | list[str],
        **kwargs: Any,
    ) -> EmbeddingResult:
        """
        Anthropic does not support embeddings natively.

        Raises:
            NotImplementedError: Always, as Anthropic doesn't have an embeddings API
        """
        raise NotImplementedError(
            "Anthropic does not provide an embeddings API. "
            "Consider using OpenAI's text-embedding models or a dedicated embedding service."
        )

    # --- Provider Batch API: Anthropic Message Batches (Phase 6) ---------------------
    # Durable, discounted batch jobs. Distinct from local concurrency
    # (ExecutionEngine.concurrent_complete), which bills at standard rates.

    def _batch_job_from_anthropic(self, batch: Any) -> BatchJob:
        raw_status = getattr(batch, "processing_status", None)
        counts_obj = getattr(batch, "request_counts", None)
        counts: dict[str, int] = {}
        if counts_obj is not None:
            for name in ("processing", "succeeded", "errored", "canceled", "expired"):
                value = getattr(counts_obj, name, None)
                if value is not None:
                    counts[name] = int(value)
        return BatchJob(
            id=getattr(batch, "id", ""),
            provider="anthropic",
            status=normalize_batch_status("anthropic", raw_status),
            raw_status=raw_status,
            endpoint="messages",
            request_counts=counts,
            created_at=getattr(batch, "created_at", None),
            expires_at=getattr(batch, "expires_at", None),
            raw=batch,
        )

    async def create_message_batch(self, requests: list[BatchRequestItem]) -> BatchJob:
        """Create an Anthropic Message Batch from request items."""
        payload = [{"custom_id": item.custom_id, "params": dict(item.params)} for item in requests]
        batch = await self.client.messages.batches.create(requests=payload)
        return self._batch_job_from_anthropic(batch)

    async def retrieve_batch(self, batch_id: str) -> BatchJob:
        batch = await self.client.messages.batches.retrieve(batch_id)
        return self._batch_job_from_anthropic(batch)

    async def list_batches(self, *, limit: int = 20) -> list[BatchJob]:
        page = await self.client.messages.batches.list(limit=limit)
        items = getattr(page, "data", None) or []
        return [self._batch_job_from_anthropic(batch) for batch in items]

    async def cancel_batch(self, batch_id: str) -> BatchJob:
        batch = await self.client.messages.batches.cancel(batch_id)
        return self._batch_job_from_anthropic(batch)

    async def delete_batch(self, batch_id: str) -> None:
        await self.client.messages.batches.delete(batch_id)

    async def batch_results(self, batch_id: str) -> list[BatchResultItem]:
        """Retrieve per-item results, preserving custom_ids and per-item errors."""
        results = await self.client.messages.batches.results(batch_id)
        items: list[BatchResultItem] = []
        if hasattr(results, "__aiter__"):
            async for entry in results:
                items.append(self._batch_result_item_from_anthropic(entry))
        else:
            for entry in results:
                items.append(self._batch_result_item_from_anthropic(entry))
        return items

    @staticmethod
    def _batch_result_item_from_anthropic(entry: Any) -> BatchResultItem:
        custom_id = getattr(entry, "custom_id", "")
        result = getattr(entry, "result", None)
        result_type = getattr(result, "type", None)
        if result_type == "succeeded":
            message = getattr(result, "message", None)
            content = getattr(message, "content", None)
            usage_obj = getattr(message, "usage", None)
            usage = usage_obj.to_dict() if hasattr(usage_obj, "to_dict") else None
            return BatchResultItem(custom_id=custom_id, status="succeeded", content=content, usage=usage, raw=entry)
        if result_type == "errored":
            error = getattr(result, "error", None)
            error_dict = error.to_dict() if hasattr(error, "to_dict") else {"raw": str(error)}
            return BatchResultItem(custom_id=custom_id, status="errored", error=error_dict, raw=entry)
        return BatchResultItem(custom_id=custom_id, status=str(result_type or "unknown"), raw=entry)

    async def close(self) -> None:
        """
        Clean up provider resources.

        Closes the underlying AsyncAnthropic client connection and cache.
        """
        # Close cache first
        await self.cache.close()

        if hasattr(self, "client") and self.client:
            await self.client.close()

    async def count_tokens_api(
        self,
        messages: MessageInput,
        *,
        tools: list[ToolDefinition] | None = None,
    ) -> int:
        """
        Count tokens using Anthropic's token counting API.

        This is more accurate than local estimation as it uses the same
        tokenizer that would be used for the actual API call.

        Args:
            messages: Input messages to count tokens for
            tools: Optional tools to include in token count

        Returns:
            Number of input tokens

        Note:
            Token counting is free but subject to rate limits.
        """
        msg_objects = self._normalize_messages(messages)
        system_message, anthropic_messages = self._convert_messages_for_anthropic(msg_objects)

        params: dict[str, Any] = {
            "model": self.model_name,
            "messages": anthropic_messages,
        }

        if system_message:
            params["system"] = system_message

        if tools:
            anthropic_tools = self._convert_tools_for_anthropic(tools)
            if anthropic_tools:
                params["tools"] = anthropic_tools

        response = await self.client.messages.count_tokens(**params)
        return response.input_tokens


__all__ = ["AnthropicProvider", "ANTHROPIC_AVAILABLE"]
