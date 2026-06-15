import json
from decimal import Decimal

import pytest

from telic.config.provider import AnthropicConfig, GoogleConfig, OpenAIConfig
from telic.model_catalog import (
    DEFAULT_MODEL_CATALOG_PATH,
    MODEL_CATALOG_OVERRIDE_PATH_ENV,
    clear_model_catalog_cache,
    get_default_model_catalog,
    infer_provider_for_model,
    load_model_catalog,
    metadata_from_profile,
)
from telic.models import GPT5, GPT54, GPT54Mini, GPT54Nano, GPT54Pro, ModelProfile, TextEmbedding3Small
from telic.provider_registry import get_default_provider_registry


def test_model_catalog_loads_asset_backed_metadata() -> None:
    catalog = get_default_model_catalog()

    gpt5 = catalog.get("gpt-5")

    assert str(DEFAULT_MODEL_CATALOG_PATH) == catalog.source
    assert gpt5.provider == "openai"
    assert gpt5.reasoning is True
    assert gpt5.tool_calling is True
    assert gpt5.streaming is True
    assert gpt5.structured_outputs is True
    assert gpt5.responses_api is True
    assert gpt5.background_responses is True
    assert gpt5.responses_native_tools is True
    assert gpt5.normalized_output_items is True
    assert gpt5.vision_input is True
    assert gpt5.context_window >= 400_000


def test_model_catalog_includes_gpt54_family_metadata() -> None:
    catalog = get_default_model_catalog()

    gpt54 = catalog.get("gpt-5.4")
    gpt54_mini = catalog.get("gpt-5.4-mini")
    gpt54_nano = catalog.get("gpt-5.4-nano")
    gpt54_pro = catalog.get("gpt-5.4-pro")

    assert gpt54.model_name == "gpt-5.4-2026-03-05"
    assert gpt54.context_window == 1_050_000
    assert gpt54.default_reasoning_effort == "none"
    assert gpt54.usage_costs["input"] == float(Decimal("2.50") / Decimal("1000000"))

    assert gpt54_mini.model_name == "gpt-5.4-mini-2026-03-17"
    assert gpt54_mini.context_window == 400_000
    assert gpt54_mini.responses_native_tools is True
    assert gpt54_mini.audio_input is False

    assert gpt54_nano.model_name == "gpt-5.4-nano-2026-03-17"
    assert gpt54_nano.context_window == 400_000
    assert gpt54_nano.reasoning_efforts == ("none", "low", "medium", "high", "xhigh")
    assert gpt54_nano.audio_input is False

    assert gpt54_pro.model_name == "gpt-5.4-pro-2026-03-05"
    assert gpt54_pro.context_window == 1_050_000
    assert gpt54_pro.structured_outputs is False
    assert gpt54_pro.responses_api is True
    assert gpt54_pro.audio_input is False


def test_model_catalog_includes_current_anthropic_models() -> None:
    catalog = get_default_model_catalog()

    opus = catalog.get("claude-opus-4-7")
    sonnet = catalog.get("claude-sonnet-4-6")
    haiku = catalog.get("claude-haiku-4-5")

    assert opus.provider == "anthropic"
    assert opus.model_name == "claude-opus-4-7"
    assert opus.context_window == 1_000_000
    assert opus.max_output == 128_000
    assert opus.usage_costs["input"] == float(Decimal("5.00") / Decimal("1000000"))
    assert opus.usage_costs["cache_write_5m_input"] == float(Decimal("6.25") / Decimal("1000000"))
    assert opus.usage_costs["cache_write_1h_input"] == float(Decimal("10.00") / Decimal("1000000"))
    assert opus.usage_costs["batch_output"] == float(Decimal("12.50") / Decimal("1000000"))
    assert (opus.service or {}).get("speed_modes") == ["fast"]

    assert sonnet.model_name == "claude-sonnet-4-6"
    assert sonnet.context_window == 1_000_000
    assert sonnet.max_output == 64_000
    assert sonnet.reasoning is True
    assert sonnet.default_reasoning_effort == "medium"
    assert sonnet.usage_costs["batch_input"] == float(Decimal("1.50") / Decimal("1000000"))
    assert sonnet.usage_costs["cache_write_1h_input"] == float(Decimal("6.00") / Decimal("1000000"))

    assert haiku.model_name == "claude-haiku-4-5-20251001"
    assert haiku.context_window == 200_000
    assert haiku.max_output == 64_000
    assert haiku.usage_costs["input"] == float(Decimal("1.00") / Decimal("1000000"))
    assert haiku.usage_costs["cache_write_5m_input"] == float(Decimal("1.25") / Decimal("1000000"))
    assert haiku.usage_costs["batch_output"] == float(Decimal("2.50") / Decimal("1000000"))


def test_model_catalog_includes_anthropic_legacy_and_compatibility_aliases() -> None:
    catalog = get_default_model_catalog()

    assert catalog.get("claude-opus-4-6").model_name == "claude-opus-4-6"
    assert catalog.get("claude-opus-4-5").model_name == "claude-opus-4-5-20251101"
    assert catalog.get("claude-opus-4-1").model_name == "claude-opus-4-1-20250805"
    assert catalog.get("claude-sonnet-4-5").model_name == "claude-sonnet-4-5-20250929"

    assert catalog.get("claude-4-5-haiku").model_name == "claude-haiku-4-5-20251001"
    assert catalog.get("claude-4-5-sonnet").model_name == "claude-sonnet-4-5-20250929"
    assert catalog.get("claude-4-5-opus").model_name == "claude-opus-4-5-20251101"

    deprecated_sonnet = catalog.get("claude-sonnet-4")
    deprecated_opus = catalog.get("claude-opus-4")
    retired_haiku = catalog.get("claude-3-5-haiku")

    assert deprecated_sonnet.deprecated is True
    assert deprecated_sonnet.replacement == "claude-sonnet-4-6"
    assert deprecated_sonnet.max_output == 64_000
    assert deprecated_opus.deprecated is True
    assert deprecated_opus.replacement == "claude-opus-4-8"
    assert deprecated_opus.usage_costs["input"] == float(Decimal("15.00") / Decimal("1000000"))
    assert retired_haiku.deprecated is True
    assert retired_haiku.replacement == "claude-haiku-4-5"
    assert retired_haiku.usage_costs["input"] == float(Decimal("0.80") / Decimal("1000000"))


def test_model_catalog_filters_by_provider_category_and_capability() -> None:
    catalog = get_default_model_catalog()

    google_models = catalog.list(provider="google", category="completions", structured_outputs=True)
    embedding_models = catalog.list(provider="openai", category="embeddings")
    openai_responses_models = catalog.list(provider="openai", category="completions", responses_api=True)
    openai_audio_models = catalog.list(provider="openai", category="audio")
    openai_image_models = catalog.list(provider="openai", category="images")
    openai_moderation_models = catalog.list(provider="openai", category="moderations")

    assert any(item.key == "gemini-2.0-flash" for item in google_models)
    assert [item.key for item in embedding_models] == [
        "text-embedding-3-large",
        "text-embedding-3-small",
        "text-embedding-ada-002",
    ]
    assert any(item.key == "gpt-5" for item in openai_responses_models)
    assert any(item.key == "gpt-4.1" for item in openai_responses_models)
    assert any(item.key == "o3" for item in openai_responses_models)
    assert any(item.key == "gpt-4o-transcribe" for item in openai_audio_models)
    assert any(item.key == "gpt-audio" for item in openai_audio_models)
    assert any(item.key == "gpt-image-1" for item in openai_image_models)
    assert any(item.key == "gpt-image-1.5" for item in openai_image_models)
    assert any(item.key == "omni-moderation-latest" for item in openai_moderation_models)


def test_model_catalog_resolves_provider_defaults() -> None:
    catalog = get_default_model_catalog()

    # Decision D1: cost-balanced defaults for dev/experimentation.
    assert catalog.default_for_provider("openai").key == "gpt-5.4-mini"
    assert catalog.default_for_provider("openai", category="embeddings").key == "text-embedding-3-small"
    assert catalog.default_for_provider("google").key == "gemini-2.0-flash"
    assert catalog.default_for_provider("anthropic").key == "claude-sonnet-4-6"


def test_model_catalog_override_support_changes_defaults(tmp_path, monkeypatch) -> None:
    override_path = tmp_path / "model_catalog.override.json"
    # Canonical overrides are now v2; a partial model entry deep-merges onto the base.
    override_path.write_text(
        json.dumps(
            {
                "version": 2,
                "defaults": {
                    "openai": {"completions": "gpt-5-mini"},
                },
                "models": [
                    {
                        "key": "gpt-5",
                        "lifecycle": {"status": "deprecated", "replacement": "gpt-5-mini"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv(MODEL_CATALOG_OVERRIDE_PATH_ENV, str(override_path))
    clear_model_catalog_cache()
    get_default_provider_registry.cache_clear()
    try:
        catalog = get_default_model_catalog()

        assert catalog.default_for_provider("openai").key == "gpt-5-mini"
        assert catalog.get("gpt-5").deprecated is True
        assert catalog.get("gpt-5").replacement == "gpt-5-mini"
        assert OpenAIConfig().default_model == "gpt-5-mini"
        assert get_default_provider_registry().get("openai").default_model == "gpt-5-mini"
    finally:
        monkeypatch.delenv(MODEL_CATALOG_OVERRIDE_PATH_ENV, raising=False)
        clear_model_catalog_cache()
        get_default_provider_registry.cache_clear()


def test_model_catalog_schema_validation_rejects_bad_documents(tmp_path) -> None:
    bad_path = tmp_path / "invalid_model_catalog.json"
    bad_path.write_text(
        json.dumps(
            {
                "version": 1,
                "defaults": {},
                "models": [
                    {
                        "key": "broken-model",
                        "model_name": "broken-model",
                        "category": "completions",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    clear_model_catalog_cache()
    with pytest.raises(ValueError, match="Invalid model catalog document"):
        load_model_catalog(catalog_path=bad_path)


def test_model_catalog_is_canonical_and_covers_legacy_profiles() -> None:
    # Catalog v2 is the canonical source (audit T-001 -- the prior test certified a
    # stale Python<->JSON snapshot, which is exactly the drift coupling being removed).
    # It must still cover every legacy ModelProfile key (compat) and additionally carry
    # current flagships that are not defined as Python profiles.
    catalog = get_default_model_catalog()
    catalog_keys = {item.key for item in catalog.list()}
    missing = set(ModelProfile._registry) - catalog_keys
    assert not missing, f"catalog missing legacy profile keys: {sorted(missing)}"
    for key in ("claude-opus-4-8", "claude-fable-5", "gpt-5.5", "gpt-5.5-pro"):
        assert key in catalog_keys


def test_model_metadata_helpers_infer_provider_and_serialize() -> None:
    embedding = metadata_from_profile(TextEmbedding3Small)

    assert infer_provider_for_model("gpt-5-mini") == "openai"
    assert infer_provider_for_model("gpt-5.4") == "openai"
    assert infer_provider_for_model("gpt-5.4-mini") == "openai"
    assert infer_provider_for_model("gpt-5.4-nano") == "openai"
    assert infer_provider_for_model("gpt-5.4-pro") == "openai"
    assert infer_provider_for_model("chatgpt-image-latest") == "openai"
    assert infer_provider_for_model("computer-use-preview") == "openai"
    assert infer_provider_for_model("whisper-1") == "openai"
    assert infer_provider_for_model("tts-1") == "openai"
    assert infer_provider_for_model("omni-moderation-latest") == "openai"
    assert infer_provider_for_model("gemini-3-pro") == "google"
    assert infer_provider_for_model("claude-opus-4-7") == "anthropic"
    assert infer_provider_for_model("claude-sonnet-4-6") == "anthropic"
    assert infer_provider_for_model("claude-haiku-4-5") == "anthropic"
    assert infer_provider_for_model("claude-4-5-sonnet") == "anthropic"
    assert embedding.to_dict()["provider"] == "openai"
    assert embedding.responses_api is False
    assert metadata_from_profile(GPT5).key == "gpt-5"
    assert metadata_from_profile(GPT54).key == "gpt-5.4"
    assert metadata_from_profile(GPT54Mini).key == "gpt-5.4-mini"
    assert metadata_from_profile(GPT54Nano).key == "gpt-5.4-nano"
    assert metadata_from_profile(GPT54Pro).key == "gpt-5.4-pro"


def test_provider_configs_use_catalog_defaults() -> None:
    clear_model_catalog_cache()
    get_default_provider_registry.cache_clear()
    assert OpenAIConfig().default_model == "gpt-5.4-mini"
    assert AnthropicConfig().default_model == "claude-sonnet-4-6"
    assert GoogleConfig().default_model == "gemini-2.0-flash"


def test_model_profile_supports_dynamic_fine_tuned_model_ids() -> None:
    profile = ModelProfile.get("ft:gpt-4o-mini:org:demo")

    assert profile.key == "ft:gpt-4o-mini:org:demo"
    assert profile.model_name == "ft:gpt-4o-mini:org:demo"
    assert profile.category == "completions"
    assert profile.function_calling_support is True


def test_model_catalog_tracks_deprecated_openai_models_and_replacements() -> None:
    catalog = get_default_model_catalog()

    gpt4o_realtime_preview = catalog.get("gpt-4o-realtime-preview")
    o1_preview = catalog.get("o1-preview")
    embedding_ada = catalog.get("text-embedding-ada-002")

    assert gpt4o_realtime_preview.deprecated is True
    assert gpt4o_realtime_preview.replacement == "gpt-realtime"
    assert o1_preview.deprecated is True
    assert o1_preview.replacement == "gpt-5"
    assert embedding_ada.deprecated is True
    assert embedding_ada.replacement == "text-embedding-3-small"
