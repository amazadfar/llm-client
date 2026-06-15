from __future__ import annotations

import asyncio
from contextlib import suppress
import hashlib
import mimetypes
from pathlib import Path

from cookbook_support import (
    build_provider_handle,
    close_provider,
    example_env,
    fail_or_skip,
    print_heading,
    print_json,
)

from llm_client.engine import ExecutionEngine


async def main() -> None:
    model_name = example_env("LLM_CLIENT_EXAMPLE_OPENAI_UPLOADS_MODEL", "gpt-5-mini") or "gpt-5-mini"
    upload_path = example_env("LLM_CLIENT_EXAMPLE_UPLOAD_FILE_PATH")
    if not upload_path:
        fail_or_skip("Set LLM_CLIENT_EXAMPLE_UPLOAD_FILE_PATH to run the OpenAI Uploads API example.")

    source_path = Path(upload_path)
    if not source_path.exists():
        fail_or_skip(f"Upload path does not exist: {source_path}")

    purpose = example_env("LLM_CLIENT_EXAMPLE_FILE_PURPOSE", "assistants") or "assistants"
    keep_uploaded_file = example_env("LLM_CLIENT_EXAMPLE_KEEP_UPLOADED_FILE", "0") == "1"
    mime_type = mimetypes.guess_type(source_path.name)[0] or "application/octet-stream"
    file_bytes = source_path.read_bytes()
    handle = build_provider_handle("openai", model_name)
    engine = ExecutionEngine(provider=handle.provider)
    active_upload_ids: set[str] = set()
    created_file_ids: set[str] = set()

    try:
        created = await engine.create_upload(
            provider_name="openai",
            model=handle.model,
            bytes=len(file_bytes),
            filename=source_path.name,
            mime_type=mime_type,
            purpose=purpose,
        )
        active_upload_ids.add(created.upload_id)
        part = await engine.add_upload_part(
            created.upload_id,
            provider_name="openai",
            model=handle.model,
            data=file_bytes,
        )
        completed = await engine.complete_upload(
            created.upload_id,
            provider_name="openai",
            model=handle.model,
            part_ids=[part.part_id],
            md5=hashlib.md5(file_bytes).hexdigest(),
        )
        active_upload_ids.discard(created.upload_id)
        if completed.file is not None:
            created_file_ids.add(completed.file.file_id)

        cancel_candidate = await engine.create_upload(
            provider_name="openai",
            model=handle.model,
            bytes=len(file_bytes),
            filename=f"cancel-{source_path.name}",
            mime_type=mime_type,
            purpose=purpose,
        )
        active_upload_ids.add(cancel_candidate.upload_id)
        cancelled = await engine.cancel_upload(
            cancel_candidate.upload_id,
            provider_name="openai",
            model=handle.model,
        )
        active_upload_ids.discard(cancel_candidate.upload_id)
        chunked = await engine.upload_file_chunked(
            provider_name="openai",
            model=handle.model,
            file=source_path,
            mime_type=mime_type,
            purpose=purpose,
        )
        if chunked.file is not None:
            created_file_ids.add(chunked.file.file_id)

        deleted_file_ids: list[str] = []
        if not keep_uploaded_file:
            for file_id in sorted(created_file_ids):
                await engine.delete_file(
                    file_id,
                    provider_name="openai",
                    model=handle.model,
                )
                deleted_file_ids.append(file_id)
            created_file_ids.clear()

        print_heading("OpenAI Uploads API")
        print_json(
            {
                "provider": handle.name,
                "model": handle.model,
                "purpose": purpose,
                "source_path": str(source_path),
                "mime_type": mime_type,
                "created": created.to_dict(),
                "part": part.to_dict(),
                "completed": completed.to_dict(),
                "cancelled": cancelled.to_dict(),
                "chunked": chunked.to_dict(),
                "deleted_file_ids": deleted_file_ids,
                "kept_uploaded_file": keep_uploaded_file,
            }
        )
    except Exception as exc:
        for upload_id in sorted(active_upload_ids):
            with suppress(Exception):
                await engine.cancel_upload(
                    upload_id,
                    provider_name="openai",
                    model=handle.model,
                )
        for file_id in sorted(created_file_ids):
            with suppress(Exception):
                await engine.delete_file(
                    file_id,
                    provider_name="openai",
                    model=handle.model,
                )
        fail_or_skip(f"OpenAI Uploads API workflow failed: {type(exc).__name__}: {exc}")
    finally:
        await close_provider(handle.provider)


if __name__ == "__main__":
    asyncio.run(main())
