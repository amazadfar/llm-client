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

from llm_client.engine import ExecutionEngine
from llm_client.providers.types import Message
from llm_client.spec import RequestSpec


def _count_reasoning_items_with_encryption(provider_items: list[dict[str, object]] | None) -> int:
    if not provider_items:
        return 0
    return sum(
        1
        for item in provider_items
        if item.get("type") in {"reasoning", "reasoning_summary"}
        and isinstance(item.get("encrypted_content"), str)
        and str(item.get("encrypted_content")).strip()
    )


async def main() -> None:
    model_name = (
        example_env("LLM_CLIENT_EXAMPLE_OPENAI_REASONING_MODEL", "gpt-5-mini")
        or "gpt-5-mini"
    )
    handle = build_provider_handle("openai", model_name, use_responses_api=True)

    try:
        engine = ExecutionEngine(provider=handle.provider)
        stable_operating_context = "\n".join(
            [
                (
                    "Operational policy: preserve tenant boundaries, version prompts and schemas, "
                    "record cache provenance, encrypt resumable reasoning state, invalidate stale "
                    "entries after model or tool changes, and retain auditable request metadata."
                )
            ]
            * 48
        )
        prompt = (
            f"{stable_operating_context}\n\n"
            "Think carefully about prompt caching tradeoffs, then explain in four short bullets "
            "how cache keys and encrypted reasoning continuity can help repeated operational prompts."
        )
        spec = RequestSpec(
            provider="openai",
            model=handle.model,
            max_tokens=768,
            messages=[Message.user(prompt)],
            reasoning={"effort": "low"},
            include=["reasoning.encrypted_content"],
            prompt_cache_key="cookbook-openai-cache-demo",
            prompt_cache_retention="24h",
        )

        first = await engine.complete(spec)
        second = await engine.complete(spec)
        second_cached_tokens = (
            getattr(second.usage, "input_tokens_cached", 0) if second.usage else 0
        )
        if second_cached_tokens <= 0:
            fail_or_skip(
                "OpenAI did not report a prompt-cache hit for the repeated long-prefix request."
            )

        print_heading("OpenAI Prompt Cache And Encrypted Reasoning")
        print_json(
            {
                "provider": handle.name,
                "model": handle.model,
                "first_content": first.content,
                "second_content": second.content,
                "first_usage": summarize_usage(first.usage),
                "second_usage": summarize_usage(second.usage),
                "second_input_tokens_cached": second_cached_tokens,
                "first_reasoning_encrypted_items": _count_reasoning_items_with_encryption(first.provider_items),
                "second_reasoning_encrypted_items": _count_reasoning_items_with_encryption(second.provider_items),
            }
        )
    finally:
        await close_provider(handle.provider)


if __name__ == "__main__":
    asyncio.run(main())
