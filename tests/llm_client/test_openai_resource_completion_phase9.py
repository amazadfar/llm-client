"""Phase 9 OpenAI resource-completion contracts against the SDK 2.36 surface."""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

import pytest

import llm_client
from llm_client.model_catalog import get_default_model_catalog, model_profile_from_metadata
from llm_client.models import ModelProfile
from llm_client.providers.openai import OpenAIProvider
from llm_client.providers.types import (
    ContainerFileResource,
    ContainerResource,
    SkillResource,
    SkillVersionResource,
    VideoCharacterResource,
    VideoContentResult,
    VideoResource,
)
from llm_client.resources import ModelInfo, ProviderResourceAvailability, ResourcePage
from llm_client.tools import ResponsesBuiltinTool


class _NoopLimiter:
    @asynccontextmanager
    async def limit(self, **_: Any):
        yield SimpleNamespace()


class _Page:
    def __init__(self, data: list[Any], *, has_more: bool = False) -> None:
        self.data = data
        self.first_id = getattr(data[0], "id", None) if data else None
        self.last_id = getattr(data[-1], "id", None) if data else None
        self.has_more = has_more

    async def _get_page(self) -> _Page:
        return self


def _provider(model: str = "gpt-5.5") -> OpenAIProvider:
    provider = OpenAIProvider.__new__(OpenAIProvider)
    provider._model = model_profile_from_metadata(get_default_model_catalog().get(model))
    provider.limiter = _NoopLimiter()
    return provider


def test_phase9_public_types_resolve_from_stable_namespaces() -> None:
    for name in (
        "ContainerResource",
        "ContainerFileResource",
        "SkillResource",
        "SkillVersionResource",
        "VideoResource",
        "VideoContentResult",
        "ProviderResourceAvailability",
    ):
        assert getattr(llm_client, name) is not None


@pytest.mark.asyncio
async def test_models_list_and_retrieve_use_shared_resource_types() -> None:
    provider = _provider()

    async def _list(**kwargs: Any) -> _Page:
        assert kwargs == {"extra_query": {"scope": "project"}}
        return _Page([SimpleNamespace(id="gpt-5.5", created=123, object="model", owned_by="openai")])

    async def _retrieve(model_id: str, **kwargs: Any) -> Any:
        assert model_id == "gpt-5.5" and kwargs == {}
        return SimpleNamespace(id=model_id, created=123, object="model", owned_by="openai")

    provider.client = SimpleNamespace(models=SimpleNamespace(list=_list, retrieve=_retrieve))

    page = await provider.list_models(extra_query={"scope": "project"})
    item = await provider.retrieve_model("gpt-5.5")

    assert isinstance(page, ResourcePage)
    assert isinstance(page[0], ModelInfo)
    assert page[0].provider == "openai"
    assert item.id == "gpt-5.5" and item.created_at == 123


@pytest.mark.asyncio
async def test_container_and_container_file_lifecycles() -> None:
    provider = _provider()
    captured: dict[str, Any] = {}

    async def _create_container(**kwargs: Any) -> Any:
        captured["container_create"] = kwargs
        return SimpleNamespace(
            id="ctr_1",
            name=kwargs["name"],
            status="running",
            created_at=1,
            expires_after={"anchor": "last_active_at", "minutes": 20},
            last_active_at=2,
            memory_limit="4g",
            network_policy={"type": "disabled"},
        )

    async def _retrieve_container(container_id: str, **kwargs: Any) -> Any:
        assert container_id == "ctr_1" and kwargs == {}
        return await _create_container(name="analysis")

    async def _list_containers(**kwargs: Any) -> _Page:
        captured["container_list"] = kwargs
        return _Page([await _create_container(name="analysis")], has_more=True)

    async def _delete_container(container_id: str, **kwargs: Any) -> None:
        captured["container_delete"] = (container_id, kwargs)

    async def _create_file(container_id: str, **kwargs: Any) -> Any:
        captured["file_create"] = (container_id, kwargs)
        return SimpleNamespace(
            id="cfile_1",
            container_id=container_id,
            path="/mnt/data/input.txt",
            bytes=12,
            created_at=3,
            source="user",
        )

    async def _retrieve_file(file_id: str, *, container_id: str, **kwargs: Any) -> Any:
        assert file_id == "cfile_1" and kwargs == {}
        return await _create_file(container_id, file_id=file_id)

    async def _list_files(container_id: str, **kwargs: Any) -> _Page:
        captured["file_list"] = (container_id, kwargs)
        return _Page([await _create_file(container_id, file_id="file_1")])

    async def _delete_file(file_id: str, *, container_id: str, **kwargs: Any) -> None:
        captured["file_delete"] = (container_id, file_id, kwargs)

    provider.client = SimpleNamespace(
        containers=SimpleNamespace(
            create=_create_container,
            retrieve=_retrieve_container,
            list=_list_containers,
            delete=_delete_container,
            files=SimpleNamespace(
                create=_create_file,
                retrieve=_retrieve_file,
                list=_list_files,
                delete=_delete_file,
            ),
        )
    )

    created = await provider.create_container(
        name="analysis",
        memory_limit="4g",
        file_ids=["file_1"],
        network_policy={"type": "disabled"},
    )
    listed = await provider.list_containers(limit=10, order="desc")
    attached = await provider.create_container_file("ctr_1", file_id="file_1")
    retrieved = await provider.retrieve_container_file("ctr_1", "cfile_1")
    files = await provider.list_container_files("ctr_1", limit=5)
    deleted_file = await provider.delete_container_file("ctr_1", "cfile_1")
    deleted_container = await provider.delete_container("ctr_1")

    assert isinstance(created, ContainerResource) and created.memory_limit == "4g"
    assert listed.has_more and listed.items[0].container_id == "ctr_1"
    assert isinstance(attached, ContainerFileResource)
    assert retrieved.path == "/mnt/data/input.txt" and files.items[0].bytes == 12
    assert deleted_file.ok and deleted_container.ok
    assert captured["container_list"] == {"limit": 10, "order": "desc"}

    with pytest.raises(ValueError, match="exactly one"):
        await provider.create_container_file("ctr_1")


@pytest.mark.asyncio
async def test_skills_and_versions_full_lifecycle() -> None:
    provider = _provider()
    captured: dict[str, Any] = {}

    def _skill(skill_id: str = "skill_1", default_version: str = "1") -> Any:
        return SimpleNamespace(
            id=skill_id,
            name="repo-workflow",
            description="Repository workflow",
            default_version=default_version,
            latest_version="2",
            created_at=10,
        )

    def _version(version: str = "2") -> Any:
        return SimpleNamespace(
            id=f"skill_1:{version}",
            skill_id="skill_1",
            version=version,
            name="repo-workflow",
            description="Repository workflow",
            created_at=11,
        )

    async def _create(**kwargs: Any) -> Any:
        captured["create"] = kwargs
        return _skill()

    async def _retrieve(skill_id: str, **kwargs: Any) -> Any:
        assert kwargs == {}
        return _skill(skill_id)

    async def _list(**kwargs: Any) -> _Page:
        captured["list"] = kwargs
        return _Page([_skill()])

    async def _update(skill_id: str, *, default_version: str, **kwargs: Any) -> Any:
        captured["update"] = (skill_id, default_version, kwargs)
        return _skill(skill_id, default_version)

    async def _delete(skill_id: str, **kwargs: Any) -> Any:
        return SimpleNamespace(id=skill_id, deleted=True)

    async def _create_version(skill_id: str, **kwargs: Any) -> Any:
        captured["version_create"] = (skill_id, kwargs)
        return _version()

    async def _retrieve_version(version: str, *, skill_id: str, **kwargs: Any) -> Any:
        assert skill_id == "skill_1" and kwargs == {}
        return _version(version)

    async def _list_versions(skill_id: str, **kwargs: Any) -> _Page:
        captured["version_list"] = (skill_id, kwargs)
        return _Page([_version()])

    async def _delete_version(version: str, *, skill_id: str, **kwargs: Any) -> Any:
        return SimpleNamespace(id=f"{skill_id}:{version}", deleted=True)

    provider.client = SimpleNamespace(
        skills=SimpleNamespace(
            create=_create,
            retrieve=_retrieve,
            list=_list,
            update=_update,
            delete=_delete,
            versions=SimpleNamespace(
                create=_create_version,
                retrieve=_retrieve_version,
                list=_list_versions,
                delete=_delete_version,
            ),
        )
    )

    created = await provider.create_skill(files=("skill.md", b"content"))
    retrieved = await provider.retrieve_skill("skill_1")
    listed = await provider.list_skills(limit=20)
    updated = await provider.update_skill("skill_1", default_version="2")
    version = await provider.create_skill_version("skill_1", default=True, files=["bundle.zip"])
    retrieved_version = await provider.retrieve_skill_version("skill_1", "2")
    versions = await provider.list_skill_versions("skill_1", order="desc")
    deleted_version = await provider.delete_skill_version("skill_1", "2")
    deleted = await provider.delete_skill("skill_1")

    assert isinstance(created, SkillResource) and retrieved.name == "repo-workflow"
    assert listed.items[0].latest_version == "2" and updated.default_version == "2"
    assert isinstance(version, SkillVersionResource) and retrieved_version.version == "2"
    assert versions.items[0].skill_id == "skill_1"
    assert deleted_version.ok and deleted.ok
    assert captured["version_list"] == ("skill_1", {"order": "desc"})


@pytest.mark.asyncio
async def test_video_lifecycle_operations_and_failed_payload_preservation() -> None:
    provider = _provider()
    captured: dict[str, Any] = {}

    def _video(video_id: str = "video_1", *, status: str = "completed") -> Any:
        return SimpleNamespace(
            id=video_id,
            status=status,
            model="sora-2",
            prompt="A tracking shot",
            progress=100 if status == "completed" else 25,
            seconds="8",
            size="1280x720",
            created_at=20,
            completed_at=21 if status == "completed" else None,
            expires_at=22,
            remixed_from_video_id=None,
            error=(
                SimpleNamespace(code="render_failed", message="bad render")
                if status == "failed"
                else None
            ),
        )

    async def _create(**kwargs: Any) -> Any:
        captured["create"] = kwargs
        return _video(status="queued")

    async def _create_and_poll(**kwargs: Any) -> Any:
        captured["create_and_poll"] = kwargs
        return _video()

    async def _retrieve(video_id: str, **kwargs: Any) -> Any:
        assert kwargs == {}
        return _video(video_id)

    async def _poll(video_id: str, **kwargs: Any) -> Any:
        captured["poll"] = (video_id, kwargs)
        return _video(video_id)

    async def _list(**kwargs: Any) -> _Page:
        captured["list"] = kwargs
        return _Page([_video()], has_more=True)

    async def _delete(video_id: str, **kwargs: Any) -> Any:
        return SimpleNamespace(id=video_id, deleted=True, object="video.deleted")

    async def _download(video_id: str, **kwargs: Any) -> Any:
        captured["download"] = (video_id, kwargs)
        return SimpleNamespace(content=b"VIDEO", headers={"content-type": "video/mp4"})

    async def _edit(**kwargs: Any) -> Any:
        captured["edit"] = kwargs
        return _video("video_edit")

    async def _extend(**kwargs: Any) -> Any:
        captured["extend"] = kwargs
        return _video("video_extend")

    async def _remix(video_id: str, **kwargs: Any) -> Any:
        captured["remix"] = (video_id, kwargs)
        return _video("video_remix")

    async def _create_character(**kwargs: Any) -> Any:
        captured["create_character"] = kwargs
        return SimpleNamespace(id="char_1", name="Mossy", created_at=30)

    async def _get_character(character_id: str, **kwargs: Any) -> Any:
        assert kwargs == {}
        return SimpleNamespace(id=character_id, name="Mossy", created_at=30)

    provider.client = SimpleNamespace(
        videos=SimpleNamespace(
            create=_create,
            create_and_poll=_create_and_poll,
            retrieve=_retrieve,
            poll=_poll,
            list=_list,
            delete=_delete,
            download_content=_download,
            edit=_edit,
            extend=_extend,
            remix=_remix,
            create_character=_create_character,
            get_character=_get_character,
        )
    )

    queued = await provider.create_video(prompt="A tracking shot", model="sora-2")
    completed = await provider.create_video_and_poll(
        prompt="A tracking shot",
        poll_interval_ms=100,
    )
    polled = await provider.poll_video("video_1", poll_interval_ms=50)
    listed = await provider.list_videos(limit=5)
    content = await provider.download_video("video_1", variant="thumbnail")
    edited = await provider.edit_video(video={"id": "video_1"}, prompt="Make it teal")
    extended = await provider.extend_video(
        video={"id": "video_1"},
        prompt="Continue upward",
        seconds="8",
    )
    remixed = await provider.remix_video("video_1", prompt="Legacy remix")
    character = await provider.create_video_character(name="Mossy", video=b"MP4")
    fetched_character = await provider.retrieve_video_character("char_1")
    deleted = await provider.delete_video("video_1")
    failed = provider._video_resource_from_response(_video("video_bad", status="failed"))

    assert isinstance(queued, VideoResource) and queued.status == "queued"
    assert completed.is_terminal and polled.progress == 100
    assert listed.has_more and listed.items[0].experimental is True
    assert isinstance(content, VideoContentResult) and content.content == b"VIDEO"
    assert {edited.video_id, extended.video_id, remixed.video_id} == {
        "video_edit",
        "video_extend",
        "video_remix",
    }
    assert isinstance(character, VideoCharacterResource)
    assert fetched_character.character_id == "char_1" and deleted.ok
    assert failed.error == {"code": "render_failed", "message": "bad render"}


def test_resource_availability_is_separate_from_model_capability() -> None:
    provider = _provider()
    provider.client = SimpleNamespace(
        models=object(),
        batches=object(),
        containers=SimpleNamespace(files=object()),
        skills=SimpleNamespace(versions=object()),
        videos=object(),
        audio=SimpleNamespace(transcriptions=object(), translations=object(), speech=object()),
        realtime=SimpleNamespace(client_secrets=object(), calls=object(), connect=lambda: None),
        files=object(),
        uploads=object(),
        vector_stores=object(),
        fine_tuning=SimpleNamespace(jobs=object()),
        images=object(),
    )

    availability = provider.get_resource_availability()

    assert isinstance(availability, ProviderResourceAvailability)
    assert availability.supports("containers")
    assert availability.supports("videos")
    assert "voices" in availability.unavailable
    assert availability.account_access == "unknown"
    assert "videos" in availability.experimental
    assert provider._model.responses_native_tools_support is True


def test_native_tool_validation_uses_exact_catalog_support() -> None:
    provider = _provider("gpt-5.5")

    provider._validate_tool_configuration(
        tools=[ResponsesBuiltinTool.shell()],
        use_responses_api=True,
    )

    with pytest.raises(ValueError, match="does not support"):
        provider._validate_tool_configuration(
            tools=[ResponsesBuiltinTool.of("audio_generation")],
            use_responses_api=True,
        )


def test_native_tool_validation_rejects_unresolved_models() -> None:
    provider = _provider()
    provider._model = ModelProfile._make_unresolved_profile("future-openai-model")

    with pytest.raises(ValueError, match="unresolved"):
        provider._validate_tool_configuration(
            tools=[ResponsesBuiltinTool.web_search()],
            use_responses_api=True,
        )


@pytest.mark.asyncio
async def test_sdk_236_image_variation_and_fine_tuning_pause_resume() -> None:
    provider = _provider()
    captured: dict[str, Any] = {}

    async def _variation(**kwargs: Any) -> Any:
        captured["variation"] = kwargs
        return SimpleNamespace(
            created=40,
            data=[SimpleNamespace(url="https://example.test/image.png")],
        )

    def _job(status: str) -> Any:
        return SimpleNamespace(
            id="ftjob_1",
            status=status,
            model="gpt-4.1",
            fine_tuned_model=None,
            created_at=41,
            finished_at=None,
            trained_tokens=None,
            training_file="file_train",
            validation_file=None,
            result_files=[],
            metadata={},
        )

    async def _pause(job_id: str, **kwargs: Any) -> Any:
        assert job_id == "ftjob_1" and kwargs == {}
        return _job("paused")

    async def _resume(job_id: str, **kwargs: Any) -> Any:
        assert job_id == "ftjob_1" and kwargs == {}
        return _job("running")

    provider.client = SimpleNamespace(
        images=SimpleNamespace(create_variation=_variation),
        fine_tuning=SimpleNamespace(jobs=SimpleNamespace(pause=_pause, resume=_resume)),
    )

    variation = await provider.create_image_variation(b"PNG", n=1)
    paused = await provider.pause_fine_tuning_job("ftjob_1")
    resumed = await provider.resume_fine_tuning_job("ftjob_1")

    assert variation.images[0].url == "https://example.test/image.png"
    assert captured["variation"]["image"] == b"PNG"
    assert paused.status == "paused" and resumed.status == "running"
