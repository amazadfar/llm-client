from __future__ import annotations

import asyncio

from cookbook_support import (
    build_provider_handle,
    close_provider,
    example_env,
    fail_or_skip,
    print_heading,
    print_json,
)

from telic.batch_api import BatchRequestItem


def _openai_items(model: str) -> list[BatchRequestItem]:
    return [
        BatchRequestItem(
            custom_id="cookbook-openai-1",
            params={
                "model": model,
                "input": "Write one sentence explaining why provider Batch is not local concurrency.",
                "max_output_tokens": 64,
                "reasoning": {"effort": "low"},
            },
        )
    ]


def _anthropic_items(model: str) -> list[BatchRequestItem]:
    return [
        BatchRequestItem(
            custom_id="cookbook-anthropic-1",
            params={
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": "Write one sentence explaining why Message Batches are durable provider jobs.",
                    }
                ],
                "max_tokens": 64,
            },
        )
    ]


async def main() -> None:
    run_live = example_env("TELIC_EXAMPLE_RUN_PROVIDER_BATCH", "0") == "1"
    openai_model = example_env("TELIC_EXAMPLE_OPENAI_BATCH_MODEL", "gpt-5-nano") or "gpt-5-nano"
    anthropic_model = (
        example_env("TELIC_EXAMPLE_ANTHROPIC_BATCH_MODEL", "claude-sonnet-4-6")
        or "claude-sonnet-4-6"
    )
    openai_items = _openai_items(openai_model)
    anthropic_items = _anthropic_items(anthropic_model)

    payload: dict[str, object] = {
        "live_batch_creation": run_live,
        "openai_requests": [item.to_dict() for item in openai_items],
        "anthropic_requests": [item.to_dict() for item in anthropic_items],
        "note": (
            "Set TELIC_EXAMPLE_RUN_PROVIDER_BATCH=1 to create real provider batch "
            "jobs. Dry-run mode is the default so the cookbook suite does not create "
            "durable remote jobs during routine validation."
        ),
    }

    openai_handle = None
    anthropic_handle = None
    try:
        if run_live:
            openai_handle = build_provider_handle("openai", openai_model, use_responses_api=True)
            anthropic_handle = build_provider_handle("anthropic", anthropic_model)
            openai_job = await openai_handle.provider.create_batch(
                openai_items,
                endpoint="responses",
                metadata={"workflow": "telic-cookbook-provider-batch"},
            )
            anthropic_job = await anthropic_handle.provider.create_message_batch(anthropic_items)
            payload["openai_job"] = openai_job.to_dict()
            payload["anthropic_job"] = anthropic_job.to_dict()
        elif example_env("TELIC_EXAMPLE_REQUIRE_LIVE_BATCH", "0") == "1":
            fail_or_skip("Set TELIC_EXAMPLE_RUN_PROVIDER_BATCH=1 to run live provider Batch APIs.")

        print_heading("Provider Batch APIs")
        print_json(payload)
    finally:
        if openai_handle is not None:
            await close_provider(openai_handle.provider)
        if anthropic_handle is not None:
            await close_provider(anthropic_handle.provider)


if __name__ == "__main__":
    asyncio.run(main())
