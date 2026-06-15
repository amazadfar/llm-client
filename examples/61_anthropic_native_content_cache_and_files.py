from __future__ import annotations

import asyncio
from pathlib import Path

from cookbook_support import (
    build_provider_handle,
    close_provider,
    example_env,
    fail_or_skip,
    print_heading,
    print_json,
    summarize_usage,
)

from llm_client.content import FileBlock, TextBlock, content_blocks_to_anthropic_content
from llm_client.providers.types import Message


def _page_to_dict(page) -> dict[str, object]:
    return {
        "data": [item.to_dict() if hasattr(item, "to_dict") else dict(item) for item in page],
        "has_more": page.has_more,
        "first_id": page.first_id,
        "last_id": page.last_id,
    }


async def main() -> None:
    model_name = (
        example_env("LLM_CLIENT_EXAMPLE_ANTHROPIC_MODEL", "claude-sonnet-4-6")
        or "claude-sonnet-4-6"
    )
    upload_path = example_env("LLM_CLIENT_EXAMPLE_ANTHROPIC_UPLOAD_FILE_PATH")
    keep_uploaded_file = example_env("LLM_CLIENT_EXAMPLE_KEEP_ANTHROPIC_FILE", "0") == "1"
    handle = build_provider_handle("anthropic", model_name)
    uploaded_file = None
    deleted_file = None

    cache_control = {"type": "ephemeral", "ttl": "5m"}
    blocks = [
        TextBlock(
            "Package release note: provider catalog drift checks passed, but artifact "
            "build verification remains a release gate.",
            cache_control=cache_control,
        ),
        FileBlock(
            name="release-gate-note.txt",
            mime_type="text/plain",
            extracted_text="Artifact verification must pass after building wheel and sdist.",
            cache_control=cache_control,
        ),
    ]
    native_content = content_blocks_to_anthropic_content(
        blocks,
        supports_images=True,
        supports_files=True,
    )

    try:
        models_page = await handle.provider.list_models(limit=5)

        if upload_path:
            path = Path(upload_path)
            if path.exists():
                with path.open("rb") as fh:
                    uploaded_file = await handle.provider.upload_file(fh)

        result = await handle.provider.complete(
            [Message.user(native_content)],
            max_tokens=180,
            effort="low",
        )

        if uploaded_file is not None and not keep_uploaded_file:
            deleted_file = await handle.provider.delete_file(uploaded_file.id)

        print_heading("Anthropic Native Content Cache And Files")
        print_json(
            {
                "provider": handle.name,
                "model": handle.model,
                "native_content": native_content,
                "models_page": _page_to_dict(models_page),
                "uploaded_file": uploaded_file.to_dict() if uploaded_file else None,
                "deleted_file": deleted_file.to_dict() if deleted_file else None,
                "content": result.content,
                "usage": summarize_usage(result.usage),
                "note": "File upload is opt-in via LLM_CLIENT_EXAMPLE_ANTHROPIC_UPLOAD_FILE_PATH.",
            }
        )
        if result.status >= 400 or result.error:
            fail_or_skip(f"Anthropic native-content request failed: {result.error or result.status}")
    finally:
        if uploaded_file is not None and not keep_uploaded_file and deleted_file is None:
            try:
                await handle.provider.delete_file(uploaded_file.id)
            except Exception as exc:
                print(f"warning: failed to clean up Anthropic file {uploaded_file.id}: {exc}")
        await close_provider(handle.provider)


if __name__ == "__main__":
    asyncio.run(main())
