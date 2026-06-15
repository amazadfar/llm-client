from __future__ import annotations

import asyncio

from cookbook_support import (
    build_provider_handle,
    close_provider,
    example_env,
    fail_or_skip,
    print_heading,
    print_json,
    summarize_usage,
)

from telic.providers.types import Message


STRUCTURED_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "decision": {"type": "string"},
        "risk_level": {"type": "string", "enum": ["low", "medium", "high"]},
        "evidence": {"type": "array", "items": {"type": "string"}},
        "next_action": {"type": "string"},
    },
    "required": ["decision", "risk_level", "evidence", "next_action"],
}


async def main() -> None:
    model_name = (
        example_env("TELIC_EXAMPLE_ANTHROPIC_MODEL", "claude-sonnet-4-6")
        or "claude-sonnet-4-6"
    )
    effort = example_env("TELIC_EXAMPLE_ANTHROPIC_EFFORT", "low") or "low"
    handle = build_provider_handle("anthropic", model_name)

    try:
        result = await handle.provider.complete(
            [
                Message.user(
                    "Return a compact JSON decision packet for this release question: "
                    "should we ship after catalog drift checks pass, but before artifact "
                    "build verification has run?"
                )
            ],
            max_tokens=220,
            effort=effort,
            response_format={"type": "json_schema", "schema": STRUCTURED_SCHEMA},
        )

        print_heading("Anthropic Thinking And Structured Outputs")
        print_json(
            {
                "provider": handle.name,
                "model": handle.model,
                "effort": effort,
                "status": result.status,
                "error": result.error,
                "content": result.content,
                "reasoning_present": bool(result.reasoning),
                "provider_items": result.provider_items,
                "usage": summarize_usage(result.usage),
                "note": "Uses Anthropic output_config.effort plus output_config.format via response_format.",
            }
        )
        if result.status >= 400 or result.error:
            fail_or_skip(f"Anthropic structured-output request failed: {result.error or result.status}")
    finally:
        await close_provider(handle.provider)


if __name__ == "__main__":
    asyncio.run(main())
