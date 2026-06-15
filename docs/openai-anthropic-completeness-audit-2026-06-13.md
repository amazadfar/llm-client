# OpenAI and Anthropic Completeness Audit

Date: 2026-06-13  
Package version inspected: `0.3.2`  
Scope: OpenAI and Anthropic only. Gemini is intentionally excluded.

## Review verification and corrections (independent pass, 2026-06-13)

This audit was independently reviewed against the repository source and the
authoritative Anthropic model / pricing / caching reference. The code-level
findings were spot-checked and hold: the cited file/line evidence is accurate
(`base.py` `ModelProfile.get` → `ValueError`; `RequestSpec` cache fields at
`spec.py:367-369` that `engine.py` never forwards; Anthropic vision/files
stripped via `supports_images=False` / `supports_files=False` in `content.py`;
server tools rejected by `ensure_function_tools_only` in `anthropic.py`; stale
`gpt-5` / `claude-opus-4-7` defaults; catalog counts of 66 OpenAI / 17 Anthropic
/ 4 Google). The following provider-fact corrections were applied to this
document:

1. Opus 4.8 prompt-cache minimum is 4,096 tokens, not 1,024 (A-CAT-002).
2. Fast mode (`speed: "fast"`) is Opus 4.6-only — not Opus 4.7 or 4.8. The
   catalog advertises `fast_mode` on `claude-opus-4-7`, a false positive the
   original audit both missed and endorsed; the "$10/$50 Opus 4.8 fast price"
   was wrong (that is Fable 5's base price). See A-API-010.
3. Added Fable 5 / Mythos 5 catalog requirements (A-CAT-002b) — the GA flagship
   was under-specified relative to Opus 4.8.
4. Corrected the Claude 3 Haiku retirement date to 2026-04-19 (C-004).

OpenAI follow-up audit (second pass): the OpenAI code-level findings were also
spot-checked and hold (`use_responses_api=False` default; `_check_reasoning_params`
collapses the reasoning object to `{"effort": effort}` at `openai.py:311`; the
streaming Responses path inserts `temperature` directly at `openai.py:2798`,
bypassing the GPT-5 default guard; `service_tier`/`tier` appears nowhere in
`providers/types.py`; 22 OpenAI catalog entries — image, audio, moderation, and
`gpt-oss-120b`/`gpt-oss-20b` completions — carry zero input/output costs). The
GPT-5.5 provider figures in O-CAT-001 were re-verified against the OpenAI docs
via Context7: $5.00 input / $0.50 cached / $30.00 output per 1M, the >272K → 2x
input / 1.5x output rule, the 10% regional uplift, and `prompt_cache_retention:
"24h"` all match; `gpt-realtime-2` and GPT Image 2 (released 2026-04-21, token
pricing, Batch 50% discount) are confirmed. Still **not** independently
re-derived: the exact `gpt-5.5-pro` rates and the priority/flex sub-tier
multipliers in O-CAT-001 — re-confirm those two before implementation.

## Executive summary

The package has a broad OpenAI implementation and a usable basic Anthropic
Messages implementation, but it is not currently a reliable, complete source of
truth for either provider.

The most important conclusions are:

1. The model catalogs are stale. The OpenAI catalog has 66 entries and the
   Anthropic catalog has 17, but count is misleading because current models are
   missing and retired models remain callable-looking entries.
2. Current flagship models are absent. OpenAI lacks `gpt-5.5` and
   `gpt-5.5-pro`. Anthropic lacks `claude-fable-5`, `claude-mythos-5`,
   `claude-opus-4-8`, and `claude-mythos-preview`.
3. Unknown current model IDs fail before reaching the provider API because
   `BaseProvider` requires every model string to resolve through
   `ModelProfile.get`.
4. Cached-input accounting is partially implemented, but the orchestration
   layer silently drops OpenAI's first-class prompt-cache controls.
5. OpenAI `service_tier` and Anthropic `service_tier` can only be supplied as
   untyped pass-through parameters. The actual tier used is discarded from
   normalized results and never affects cost calculation.
6. The package does not implement either provider's actual Batch API.
   `ExecutionEngine.batch_complete()` is concurrent synchronous traffic, not
   discounted asynchronous batch processing.
7. Anthropic support is materially incomplete: vision and file support are
   advertised but stripped during content translation; structured outputs,
   current thinking controls, server tools, citations, Files, Models, and
   Message Batches are not represented properly.
8. Cost calculation is not robust enough for billing decisions. It lacks
   OpenAI tier pricing, long-context pricing, regional multipliers, multimodal
   prices, and tool charges. Anthropic fast-mode pricing is also mis-scoped: the
   catalog advertises `fast_mode` on Opus 4.7, which does not have fast mode
   (it is Opus 4.6-only).
9. Capability flags are inferred too broadly. They produce false positives,
   especially for OpenAI Responses features and Anthropic vision/files.
10. The catalog needs a schema and lifecycle redesign before merely adding more
    model classes. Otherwise each provider release will continue to create
    silent inaccuracies.

Overall assessment:

| Area | OpenAI | Anthropic |
|---|---|---|
| Basic text completion and streaming | Strong | Usable |
| Current model catalog | Incomplete and stale | Severely incomplete and stale |
| Model-specific parameter validation | Weak | Weak |
| Cached input request support | Partial | Partial |
| Cached input usage accounting | Partial | Partial |
| Service/request tiers | Pass-through only | Pass-through only |
| Actual provider Batch API | Absent | Absent |
| Native/server tools | Broad but incomplete | Essentially absent |
| Multimodal input | Partial | Advertised but not implemented |
| Structured outputs | Broad OpenAI support | Incorrectly marked unsupported and not normalized |
| Pricing and cost accounting | Base text rates only | Better base/cache metadata, incomplete runtime selection |
| Lifecycle/deprecation accuracy | Incorrect | Incorrect |
| Live model discovery | Absent | Absent |

## Method and evidence

This audit used:

- the repository source, catalog asset, schema, examples, and tests;
- the existing repository `.venv`;
- installed OpenAI SDK `2.36.0`;
- installed Anthropic SDK `0.104.1`;
- Context7's current Anthropic Python SDK index;
- the official OpenAI developer documentation and OpenAPI endpoint index;
- the official Anthropic model, pricing, caching, service-tier, tool, and
  deprecation documentation.

No credentials were used and no live paid model requests were made.

Support is classified as:

- **First-class**: typed package API, normalized result, validation, tests, and
  documented behavior.
- **Pass-through**: can be sent through `**kwargs` or `RequestSpec.extra`, but
  the package does not understand or validate it.
- **Partial**: some request or response behavior exists, but important paths or
  accounting are missing.
- **Incorrect**: package metadata or behavior conflicts with current official
  documentation.
- **Absent**: no usable package surface exists.

## Environment findings

- Python executable:
  `.venv/bin/python`
- `llm_client` imports from the current checkout.
- No dependencies were installed or changed during this audit.
- The worktree already had a modified `.gitignore`; it was not touched.
- Source and `pyproject.toml` identify this checkout as version `0.3.2`.

## Catalog architecture findings

### C-001: Current model IDs hard-fail when absent from the static registry

Severity: Critical  
Status: Incorrect

`BaseProvider` resolves every string model through `ModelProfile.get`.
Non-fine-tuned unknown IDs raise `ValueError`. Therefore newly released models
cannot be used by passing their API model ID until the package ships a catalog
update.

Evidence:

- `llm_client/providers/base.py:830-837`
- `llm_client/models.py:358-365`

Impact:

- `OpenAIProvider(model="gpt-5.5")` fails locally.
- `AnthropicProvider(model="claude-opus-4-8")` fails locally.
- Provider APIs cannot be used as the final authority.

Required change:

- Separate model identity from optional metadata.
- Allow explicit provider model IDs even when metadata is unknown.
- Use a conservative unknown-model profile with no inferred capabilities and
  no estimated cost, or require an explicit custom profile.

### C-002: The JSON catalog is not an independent source of truth

Severity: High  
Status: Incorrect architecture

The JSON asset is required by tests to exactly match Python `ModelProfile`
classes. This duplicates the same information rather than creating a
maintainable data catalog.

Evidence:

- `tests/llm_client/test_model_catalog.py:227-237`
- `llm_client/model_catalog.py:321-355`

Impact:

- Every catalog correction requires synchronized Python and JSON edits.
- Provider updates cannot be generated or reviewed as data-only changes.
- Tests preserve stale values instead of detecting drift from provider docs.

Required change:

- Make one canonical, source-attributed catalog artifact.
- Generate Python conveniences from the artifact, not the reverse.
- Add freshness and provider-document conformance tests.

### C-003: Catalog schema cannot represent the data needed for correctness

Severity: Critical  
Status: Absent

The schema contains only broad capability booleans, flat usage costs, a
`deprecated` boolean, and generic rate limits.

Evidence:

- `llm_client/model_catalog.py:34-61`
- `llm_client/assets/model_catalog.schema.json:25-170`

Missing fields include:

- canonical ID, alias, and snapshot relationships;
- release date, deprecation date, retirement date, and replacement;
- lifecycle state such as active, preview, limited availability, deprecated,
  retired, or removed;
- supported endpoints per model;
- provider/platform availability;
- input and output modalities separately;
- native/server tool compatibility by tool version;
- per-model request parameter constraints and defaults;
- reasoning/thinking mode compatibility;
- service-tier eligibility;
- Batch API eligibility and batch-specific output limits;
- prompt-cache support, minimum prefix, retention modes, and platform limits;
- short-context and long-context pricing thresholds;
- standard, batch, flex, priority, fast, and regional pricing;
- modality-specific prices;
- provider tool charges;
- structured-output constraints;
- beta headers and feature versions;
- source URL, effective date, and catalog `fetched_at`.

### C-004: Lifecycle is reduced to an inadequate boolean

Severity: Critical  
Status: Incorrect

`deprecated: bool` cannot distinguish active, preview, deprecated, retired,
removed, or limited-availability models. Removed models remain selectable.

Examples:

- OpenAI `dall-e-2` and `dall-e-3` were removed on 2026-05-12.
- OpenAI `text-moderation-latest` and `text-moderation-stable` were removed on
  2025-10-27, but the package marks them active.
- OpenAI `chatgpt-4o-latest` was removed on 2026-02-17, but the package marks it
  active.
- Anthropic Claude 3 Haiku was retired on 2026-04-19.
- Anthropic Claude 3 Opus was retired on 2026-01-05.
- Anthropic Claude Sonnet 4 and Opus 4 retire on 2026-06-15.
- Anthropic Claude Opus 4.1 was deprecated on 2026-06-05 and retires on
  2026-08-05.

Required change:

- Introduce a lifecycle object with status and exact dates.
- Prevent removed/retired models from being selected by default.
- Emit actionable warnings for deprecated models.

### C-005: Capability inference creates false positives

Severity: Critical  
Status: Incorrect

For OpenAI, nearly every completion model is assumed to support structured
outputs, Responses, background responses, native tools, image input, audio
input, and file input unless manually overridden.

For Anthropic, every completion model is advertised as supporting image and
file input.

Evidence:

- `llm_client/model_catalog.py:224-308`

This is incompatible with model-specific endpoint and tool matrices. It also
directly conflicts with Anthropic content translation, which currently strips
images and files.

Required change:

- Default all optional capabilities to unknown/false.
- Populate capabilities from explicit model records.
- Represent endpoint and tool support as matrices rather than one boolean.

### C-006: Static rate limits are not trustworthy

Severity: High  
Status: Incorrect

The catalog stores one request/token rate per model even though both providers
use account, organization, project, model-family, and usage-tier-dependent
limits.

Impact:

- Local throttling can be unnecessarily restrictive or dangerously permissive.
- Values cannot represent shared family limits, cached-token treatment, batch
  queues, or fast-mode capacity.

Required change:

- Treat provider response headers and account configuration as authoritative.
- Label static limits as optional conservative hints with source and tier.

## OpenAI model catalog gaps

### O-CAT-001: GPT-5.5 family is missing

Severity: Critical  
Status: Absent

Missing:

- `gpt-5.5`
- `gpt-5.5-2026-04-23`
- `gpt-5.5-pro`
- `gpt-5.5-pro-2026-04-23`

Required GPT-5.5 metadata:

- reasoning efforts: `none`, `low`, `medium`, `high`, `xhigh`;
- default reasoning effort: `medium`;
- supported native tools: function calling, web search, file search, tool
  search, image generation, code interpreter, hosted shell, apply patch,
  skills, computer use, and MCP;
- standard price under the long-context threshold:
  `$5.00` input, `$0.50` cached input, `$30.00` output per million tokens;
- Batch/Flex price:
  `$2.50`, `$0.25`, `$15.00`;
- Priority price:
  `$12.50`, `$1.25`, `$75.00`;
- inputs above 272K are charged at 2x input and 1.5x output for the full
  standard, batch, or flex session;
- eligible regional processing has a 10% uplift;
- prompt cache retention supports only `24h`.

Required GPT-5.5 Pro metadata:

- Responses API, including Batch API;
- no cached-input discount;
- standard `$30.00` input and `$180.00` output;
- Batch/Flex `$15.00` input and `$90.00` output;
- regional processing 10% uplift;
- long-running requests should support background mode.

### O-CAT-002: Current multimodal models are missing

Severity: Critical  
Status: Absent

Missing at minimum:

- `gpt-image-2` and snapshot `gpt-image-2-2026-04-21`;
- `gpt-realtime-2`;
- `gpt-realtime-translate`;
- `gpt-realtime-whisper`;
- `gpt-audio-1.5`.
- `chat-latest`;
- `gpt-5.3-chat-latest`;
- `gpt-5.3-codex`.

The catalog still centers older or deprecated image, audio, and realtime
families.

### O-CAT-003: Image and audio prices are represented as zero

Severity: Critical  
Status: Incorrect

Many image and audio profiles use zero for all costs. Confirmed: 22 OpenAI
catalog entries carry `input == output == 0`, spanning images
(`dall-e-2`/`dall-e-3`, `gpt-image-1`/`gpt-image-1-mini`/`gpt-image-1.5`,
`chatgpt-image-latest`), audio/transcription/TTS (`whisper-1`, `tts-1`/`tts-1-hd`,
`gpt-4o-transcribe`, `gpt-audio`), and moderation. Note this is not limited to
multimodal: the `gpt-oss-120b` and `gpt-oss-20b` **completions** profiles are
also zero-priced, so a text request against them silently costs nothing in the
package's accounting — fold these into the same fix.

Evidence:

- `llm_client/models.py:914-1125`

Examples of currently missing pricing dimensions:

- GPT Image 2 text-input, image-input, cached-input, and image-output token
  prices;
- Batch image pricing;
- GPT Realtime 2 text, audio, and image token prices;
- realtime translation and transcription per-minute prices;
- transcription per-token and estimated per-minute prices;
- speech generation pricing.

Cost totals from these profiles are not suitable for billing or budget
enforcement.

### O-CAT-004: OpenAI lifecycle flags and replacements are stale

Severity: Critical  
Status: Incorrect

The 2026 deprecation schedule is not reflected comprehensively. Examples:

- `gpt-5-chat-latest`, `gpt-5-codex`, GPT-5.1 Codex variants, deep-research
  models, and `computer-use-preview` have 2026-07-23 shutdown dates.
- `gpt-image-1`, `o1`, `o1-pro`, `o3-mini`, `o4-mini`, GPT-4, GPT-4 Turbo,
  GPT-3.5 Turbo, and GPT-4.1 Nano have 2026-10-23 shutdown dates.
- `gpt-5.2-chat-latest` and `gpt-5.3-chat-latest` are being replaced by
  GPT-5.5.
- removed DALL-E, moderation, ChatGPT-4o, audio preview, and realtime preview
  entries need a retired/removed status rather than a generic deprecated flag.

### O-CAT-005: Default OpenAI model is stale

Severity: High  
Status: Incorrect

The default remains `gpt-5`.

Evidence:

- `llm_client/assets/model_catalog.json:3-6`
- `llm_client/model_catalog.py:358-372`
- `llm_client/provider_registry.py:203-221`
- `llm_client/config/provider.py:49-57`

The default policy should be explicit and stable. A package should not silently
change all users to the most expensive newest model, but it also should not call
an older model the current default without documenting that policy.

Recommended design:

- named policies such as `stable`, `latest`, `cost_optimized`, and
  `provider_recommended`;
- explicit pinned model IDs in production;
- catalog metadata identifying the provider-recommended current model.

## OpenAI request and response gaps

### O-API-001: Responses API is opt-in even for current reasoning models

Severity: High  
Status: Partial

`OpenAIProvider` defaults to `use_responses_api=False`.

Evidence:

- `llm_client/providers/openai.py:181-227`
- `llm_client/config/provider.py:49-58`

This routes new models through Chat Completions unless callers know to opt in,
despite the package's strongest features and current OpenAI guidance centering
the Responses API.

Required change:

- select endpoint from explicit per-model endpoint support;
- use Responses by default for new reasoning/agentic models;
- retain a compatibility override.

### O-API-002: `RequestSpec` prompt-cache fields are silently dropped

Severity: Critical  
Status: Incorrect

`RequestSpec` defines:

- `include`;
- `prompt_cache_key`;
- `prompt_cache_retention`.

The engine forwards none of them to `provider.complete()` or
`provider.stream()`.

Evidence:

- fields: `llm_client/spec.py:355-370`
- non-stream dispatch: `llm_client/engine.py:3011-3032`
- stream dispatch: `llm_client/engine.py:702-713`

Direct provider calls work and are tested, but engine calls silently ignore the
same first-class settings.

Required change:

- forward all first-class fields in both complete and stream paths;
- add engine-level regression tests.

### O-API-003: Reasoning normalization destroys valid Responses configuration

Severity: Critical  
Status: Incorrect

When a Responses `reasoning` object contains `effort` plus other fields such as
`summary`, `_check_reasoning_params()` replaces it with only
`{"effort": effort}`.

Evidence:

- `llm_client/providers/openai.py:277-316`

Required change:

- preserve the original reasoning object;
- normalize only the effort key;
- validate model-specific fields without deleting them.

### O-API-004: Model-specific parameter constraints are not enforced

Severity: High  
Status: Partial

Examples:

- GPT-5.5 accepts only `24h` prompt cache retention, but the package also
  accepts `in_memory` until the API rejects it.
- GPT-5.5 Pro has no cached-input discount.
- service-tier support differs by model.
- long-context pricing and regional processing depend on request details.
- temperature support differs by model and reasoning mode.

The current validation is mostly based on broad profile flags and effort lists.

### O-API-005: Streaming and non-streaming temperature handling is inconsistent

Severity: High  
Status: Incorrect

The non-streaming Responses path calls `_set_temperature()`. The streaming
Responses path inserts `temperature` directly.

Evidence:

- non-stream: `llm_client/providers/openai.py:2185-2195`
- stream: `llm_client/providers/openai.py:2796-2807`

The same request can therefore be accepted, omitted, or rejected differently
depending on streaming mode.

### O-API-006: Request surface is mostly untyped pass-through

Severity: Medium  
Status: Pass-through

Current OpenAI SDK request fields not represented first-class in `RequestSpec`
include:

- `background`;
- `context_management`;
- `conversation`;
- `instructions`;
- `max_tool_calls`;
- `metadata`;
- `parallel_tool_calls`;
- `previous_response_id`;
- reusable `prompt`;
- `safety_identifier`;
- `service_tier`;
- `store`;
- `stream_options`;
- `text.verbosity`;
- `top_logprobs`;
- `top_p`;
- `truncation`.

They can generally be supplied through `extra`, but receive no provider-aware
typing, validation, serialization guarantee, or cache-key policy.

### O-API-007: Actual service tier is discarded

Severity: High  
Status: Incorrect

OpenAI responses report the processing tier actually used. The normalized
`Usage` and `CompletionResult` do not preserve it.

Evidence:

- `llm_client/providers/types.py:155-207`

Impact:

- callers cannot verify whether `auto` resolved to standard, flex, scale, or
  priority;
- cost calculation cannot select the correct rate;
- observability cannot correlate latency and cost with the actual tier.

### O-API-008: OpenAI Batch API is absent

Severity: Critical  
Status: Absent

There are no wrappers for:

- create batch;
- retrieve batch;
- list batches;
- cancel batch;
- batch output/error file handling.

`ExecutionEngine.batch_complete()` only runs normal requests concurrently.

Evidence:

- `llm_client/engine.py:3346-3384`

This method should not be described as OpenAI Batch API support and cannot
receive Batch API discounts.

### O-API-009: Pricing ignores request mode and conditional modifiers

Severity: Critical  
Status: Incorrect

Runtime cost accounting always uses one flat model rate. It does not apply:

- standard versus batch versus flex versus priority pricing;
- long-context thresholds;
- data residency uplift;
- modality-specific rates;
- web search, file search, container, or other tool charges;
- per-minute media pricing.

### O-API-010: Important current platform resources are missing

Severity: Medium  
Status: Absent or partial

Within a model-client scope, the highest-value missing OpenAI resources are:

- Models list/retrieve;
- Batches;
- Containers and container files as standalone resources;
- hosted Skills resource lifecycle;
- video generation/edit/extensions/characters;
- current voice consent and custom voice resources;
- complete realtime translation resources;
- newer fine-tuning pause/resume/checkpoint permission and grader surfaces.

Organization administration, RBAC, audit logs, and billing APIs are valid
OpenAI platform APIs but should be treated as a separate administration module,
not silently folded into the model provider.

## Anthropic model catalog gaps

### A-CAT-001: The current Anthropic flagship families are missing

Severity: Critical  
Status: Absent

Official Anthropic documentation current on 2026-06-13 includes:

- `claude-fable-5`, generally available since 2026-06-09;
- `claude-mythos-5`, limited availability since 2026-06-09;
- `claude-opus-4-8`;
- `claude-mythos-preview`, invitation-only and retiring 2026-06-30.

The package contains none of them.

This also shows why SDK literals cannot be the only catalog source: Context7's
indexed Anthropic SDK included Opus 4.8 and Mythos Preview but had not yet
incorporated the June 9 Fable 5 and Mythos 5 release.

### A-CAT-002: Opus 4.8 specifications cannot be represented accurately

Severity: Critical  
Status: Absent

Required metadata includes:

- 1M default context on Claude API, Bedrock, and Vertex AI;
- 200K context on Microsoft Foundry;
- 128K synchronous max output;
- up to 300K batch output with a beta header;
- text and image input, text output;
- adaptive thinking only;
- effort default `high`;
- `xhigh` recommendation for some coding/autonomy workloads;
- non-default `temperature`, `top_p`, and `top_k` rejected;
- manual thinking budgets rejected;
- prompt-cache minimum 4,096 tokens (Opus 4.x / Haiku 4.5 tier; Fable 5 and
  Sonnet 4.6 use 2,048);
- no fast mode (`speed: "fast"` is supported only on Opus 4.6, not 4.7 or 4.8);
- Priority Tier support;
- mid-conversation system messages;
- refusal `stop_details`;
- current server/client tool matrix.

The existing schema cannot express most of these conditions.

### A-CAT-002b: Fable 5 and Mythos 5 specifications cannot be represented accurately

Severity: Critical  
Status: Absent

Fable 5 is the current generally available flagship (with Mythos 5 as its
Project Glasswing twin), yet this audit otherwise details only Opus 4.8 metadata.
Fable 5 / Mythos 5 carry distinct constraints the schema must capture:

- 1M context (default and maximum), 128K synchronous max output;
- text and image input, text output;
- always-on thinking: the `thinking` parameter must be omitted (or `adaptive`);
  both `thinking: {type: "disabled"}` and `{type: "enabled", budget_tokens: N}`
  return 400;
- `output_config.effort` with `low` through `xhigh` and `max`; no manual budget;
- a distinct tokenizer that produces roughly 30% more tokens than Opus-tier for
  the same content, so token counts, context budgets, and cost baselines do not
  transfer from other models;
- `stop_reason: "refusal"` from input safety classifiers (HTTP 200) with a
  `stop_details.category`; pre-output refusals are unbilled, mid-stream refusals
  bill the streamed output;
- protected thinking: the raw chain of thought is never returned; thinking blocks
  must be replayed unchanged on the same model and are dropped (unbilled) on
  other models;
- 30-day data-retention requirement: requests from zero-data-retention (or
  sub-30-day) organizations return 400;
- no assistant prefill;
- no fast mode;
- prompt-cache minimum 2,048 tokens (distinct from the Opus 4.x 4,096 minimum);
- base pricing `$10` input / `$50` output per million tokens (above Opus-tier),
  with the standard 0.5x batch and prompt-cache multipliers.

The existing schema and the Opus-centric remediation above cannot express most
of these. Mythos 5 shares all of the above and differs only by model ID and its
limited (Project Glasswing) availability.

### A-CAT-003: Anthropic aliases and snapshots are incomplete or conflated

Severity: High  
Status: Incorrect

Current API names include aliases such as:

- `claude-opus-4-0`;
- `claude-sonnet-4-0`;
- dated and dateless forms for several models.

The package instead uses internal compatibility keys such as
`claude-opus-4` and `claude-sonnet-4`. Internal convenience keys are useful,
but they must be distinguished from provider-valid API IDs.

### A-CAT-004: Anthropic default is stale

Severity: High  
Status: Incorrect

The package default is `claude-opus-4-7`, and its class documentation calls it
the most capable current model.

Evidence:

- `llm_client/models.py:1486-1500`
- `llm_client/assets/model_catalog.json:11-13`
- `llm_client/config/provider.py:60-68`

That claim is no longer current.

### A-CAT-005: Anthropic lifecycle data is inaccurate

Severity: Critical  
Status: Incorrect

Examples:

- Opus 4.1 is active-looking in the catalog but officially deprecated.
- Opus 4 and Sonnet 4 replacements point to Opus 4.7 in places where current
  official guidance points to Opus 4.8.
- retired Claude 3 models remain normal registry entries.
- Mythos Preview's 2026-06-30 retirement cannot be represented.

## Anthropic request and response gaps

### A-API-001: Vision and file support are advertised but stripped

Severity: Critical  
Status: Incorrect

The catalog and provider registry advertise Anthropic vision and file input.
However, Anthropic content projection declares both unsupported and degrades
them to text in lossy mode.

Evidence:

- advertised: `llm_client/model_catalog.py:298-308`
- advertised: `llm_client/provider_registry.py:243-261`
- stripped: `llm_client/content.py:868-908`

Required change:

- implement Anthropic image source blocks;
- implement PDF/document and Files API references;
- preserve provider-native content blocks and citations;
- make strict mode fail rather than silently degrade unsupported content.

### A-API-002: Generic reasoning parameters are silently removed

Severity: Critical  
Status: Incorrect

The provider removes both `reasoning_effort` and `reasoning` from request
kwargs.

Evidence:

- `llm_client/providers/anthropic.py:459-464`

Callers must know the raw Anthropic fields:

- `thinking`;
- `output_config.effort`.

The package's generic reasoning abstraction therefore claims support while the
Anthropic provider discards it.

### A-API-003: Current thinking modes and effort levels are not modeled

Severity: Critical  
Status: Incorrect

Current Anthropic APIs distinguish:

- adaptive thinking;
- enabled thinking with budget on compatible older models;
- disabled thinking;
- always-on adaptive thinking for Fable 5/Mythos 5;
- `output_config.effort`;
- model-dependent effort levels and defaults;
- thinking display behavior.

The catalog contains only broad `low`, `medium`, and `high` lists. Opus 4.7 is
marked as a reasoning model but has no effort list. Opus 4.8 and Fable 5 are
absent.

`AnthropicConfig.max_thinking_tokens` exists but is unused.

Evidence:

- `llm_client/config/provider.py:60-68`
- no runtime references outside config/schema.

### A-API-004: Thinking content is lost from final normalized results

Severity: Critical  
Status: Incorrect

Non-streaming response parsing only extracts text and `tool_use` blocks.
Thinking and redacted-thinking blocks are ignored.

Streaming emits reasoning deltas but does not accumulate them into the final
`CompletionResult`.

Evidence:

- non-stream extraction: `llm_client/providers/anthropic.py:334-372`
- streaming delta: `llm_client/providers/anthropic.py:752-765`
- final stream result: `llm_client/providers/anthropic.py:830-845`

This also prevents correct multi-turn preservation of signed thinking blocks.

### A-API-005: Structured outputs are incorrectly represented

Severity: High  
Status: Incorrect

The current standard Anthropic Messages API accepts `output_config`, including
structured output format and effort. The catalog and provider registry mark
Anthropic structured outputs false, and the generic `response_format` path
does not translate to `output_config.format`.

Raw `output_config` pass-through may work, but it is not normalized,
capability-checked, or documented as first-class package behavior.

### A-API-006: Provider-native and server-side tools are rejected

Severity: Critical  
Status: Absent

Anthropic tool conversion calls `ensure_function_tools_only`, rejecting raw or
provider-native descriptors.

Evidence:

- `llm_client/providers/anthropic.py:316-332`
- `llm_client/tools/base.py:1005-1029`

Missing support includes:

- web search;
- web fetch;
- code execution;
- computer use;
- text editor;
- bash;
- memory;
- tool search;
- MCP connector/server definitions;
- Agent Skills and managed execution tools;
- tool-version compatibility;
- server-tool result block parsing;
- server-tool usage and charges;
- fine-grained tool input streaming.

### A-API-007: Citations and richer content blocks are discarded

Severity: High  
Status: Absent

Response extraction understands only `text` and `tool_use`. It does not
normalize:

- citations;
- web search results;
- web fetch results;
- code execution results;
- document/file results;
- refusal details;
- stop details;
- container artifacts;
- thinking signatures.

### A-API-008: Prompt caching is only partially implemented

Severity: High  
Status: Partial

What works:

- top-level `cache_control` can pass through `**kwargs`;
- cache-read and cache-creation tokens are included in normalized usage;
- 5-minute and 1-hour rates exist in the model profiles;
- data-residency multiplier support exists.

What is missing or incorrect:

- no first-class `RequestSpec.cache_control`;
- explicit cache controls on normalized content blocks are not preserved by
  Anthropic content translation;
- no validation of model-specific minimum cacheable prompt lengths;
- no validation of maximum breakpoints or automatic-cache platform support;
- nested `usage.cache_creation` TTL breakdown is not parsed directly;
- mixed 5-minute and 1-hour cache writes can be mispriced because the fallback
  infers one TTL for the whole request;
- cache behavior with thinking blocks is not modeled;
- cache invalidation from speed, tools, thinking, and tool choice is not
  represented in request caching policy;
- prewarming with `max_tokens=0` is not exposed intentionally.

Evidence:

- TTL inference: `llm_client/providers/anthropic.py:402-457`
- usage parser: `llm_client/models.py:283-356`

### A-API-009: Anthropic service tier is pass-through only

Severity: High  
Status: Pass-through

The standard request accepts:

- `auto`;
- `standard_only`.

The response can report:

- `standard`;
- `priority`;
- `batch`.

Important semantic distinction:

- a normal Messages request does not directly select `"priority"`; `auto`
  permits Anthropic to assign Priority Tier when capacity and account
  configuration allow it;
- Batch is a separate Message Batches API.

The package has no typed field, validation, normalized actual tier, or
tier-aware metrics.

### A-API-010: Fast mode is not implemented (and is mis-scoped in the catalog)

Severity: High  
Status: Absent / Incorrect

There is no `speed` request support or runtime pricing selection. Fast-mode
prices exist only as unused catalog fields.

Fast mode (`speed: "fast"`) is supported on **Opus 4.6 only** among the current
Opus line. Per current Anthropic guidance it is **not** available on Opus 4.7 or
Opus 4.8. The catalog's 6x multiplier on Opus 4.6 yields `$30` input / `$150`
output over its `$5` / `$25` base.

Catalog defect (identified during review, not in the original audit): the
catalog advertises `fast_mode` on `claude-opus-4-7`
(`pricing_features.fast_mode`, plus `usage_costs.fast_mode_input` /
`fast_mode_output`), which is a false positive — Opus 4.7 has no fast mode. Opus
4.8 likewise has no fast mode, so there is no separate Opus 4.8 fast price to
model. (The earlier "`$10` / `$50` Opus 4.8 fast price" was incorrect — that is
Fable 5's *base* price, not an Opus 4.8 fast rate.)

Any future fast-mode support must be gated to the specific models that actually
expose `speed: "fast"`, with the exact multiplier verified against official
pricing rather than assumed to be 6x for every model.

Evidence:

- generic multiplier: `llm_client/models.py:53-69`
- catalog false positive: `llm_client/assets/model_catalog.json`
  (`claude-opus-4-7` `pricing_features.fast_mode` / `usage_costs.fast_mode_*`)

### A-API-011: Anthropic Message Batches API is absent

Severity: Critical  
Status: Absent

The installed SDK exposes create, retrieve, list, cancel, delete, and results
operations. The package wraps none of them.

Consequences:

- batch pricing fields are never selected;
- the package cannot use the 50% Batch API discount;
- 300K batch output beta behavior cannot be represented;
- batch result/error lifecycle is unavailable.

### A-API-012: Models and Files APIs are absent

Severity: High  
Status: Absent

Missing:

- Models list and retrieve;
- capability, release date, max-input, and max-output discovery;
- Files upload, list, retrieve metadata, download, and delete;
- file/container upload integration used by code execution.

The Models API is particularly important because it provides a provider-owned
runtime source for capabilities and token limits.

### A-API-013: Usage metadata is discarded

Severity: High  
Status: Incorrect

Anthropic usage can report:

- cache creation TTL breakdown;
- inference geography;
- actual service tier;
- server tool usage counts.

The normalized `Usage` type preserves none of the latter three and does not
retain the raw cache breakdown.

Evidence:

- `llm_client/providers/types.py:155-207`
- `llm_client/providers/anthropic.py:374-393`

### A-API-014: Anthropic sampling parameters are not model-validated

Severity: High  
Status: Partial

`AnthropicProvider` accepts a `default_temperature` and inserts it into every
request when set. The constructor default is `None`
(`anthropic.py:120`), so the provider does not inject a temperature on its own;
the implicit value comes from `AnthropicConfig.default_temperature = 0.7`
(`config/provider.py:36`) when a provider is built from config. The provider
also accepts per-request `temperature`, `top_p`, and `top_k` through its normal
or pass-through surfaces. Opus 4.7 and later reject non-default sampling
parameters, but the package does not validate that model constraint before
dispatch.

Evidence:

- insertion: `llm_client/providers/anthropic.py:514-517`
- config default: `llm_client/config/provider.py:36`

Required change:

- keep sampling parameters omitted by default for incompatible models;
- enforce per-model parameter constraints before dispatch.

## Request tiers and batch semantics

### OpenAI

| User concept | Provider mechanism | Package state |
|---|---|---|
| Standard | `service_tier="default"` or project `auto` resolving to default | Raw pass-through only |
| Flex | `service_tier="flex"` | Raw pass-through only |
| Priority | `service_tier="priority"` | Raw pass-through only |
| Scale | `service_tier="scale"` where eligible | Raw pass-through only |
| Batch | `/v1/batches`, not a `service_tier` value | Absent |

### Anthropic

| User concept | Provider mechanism | Package state |
|---|---|---|
| Standard | default tier or `service_tier="standard_only"` | Raw pass-through only |
| Priority | organization capacity plus `service_tier="auto"` assignment | Not modeled |
| Batch | Message Batches API | Absent |
| Fast | `speed="fast"` on Opus 4.6 only | Absent |
| Flex | No Anthropic equivalent documented | Not applicable |

Required cross-provider design:

- do not force unlike provider concepts into one string enum;
- define normalized intent such as `latency_policy` and `execution_mode`;
- retain provider-specific request values;
- always record the actual tier/mode reported by the provider;
- make Batch an explicit asynchronous job API, not a request tier;
- calculate cost from actual mode, model, context band, region, and modality.

### Execution model vs. service tier: keep the two axes separate

This is a correctness requirement, not a stylistic one. The package overloads
the word "batch" across two orthogonal concepts, and any remediation must keep
them apart.

**Axis 1 — execution model (how/when requests run):**

- *Synchronous*: one request, one blocking call.
- *Concurrent async (package-level batching)*: many synchronous requests fired
  together over non-blocking async I/O, bounded by a semaphore. This is what
  `ExecutionEngine.batch_complete()` (`llm_client/engine.py:3346-3384`) and
  `BatchManager` / `RequestManager` (`llm_client/batch_req.py`) already do. Each
  call is an ordinary standard-mode request to the synchronous Messages /
  Responses / Chat Completions endpoint; there is no provider discount and no
  job lifecycle. It never sets `service_tier` and runs at the request's chosen
  synchronous tier (standard by default). **This behavior must be preserved.**
- *Provider Batch job API (absent)*: a single submission of many requests to a
  dedicated asynchronous endpoint — OpenAI `/v1/batches`, Anthropic Message
  Batches — that returns a job ID, runs out-of-band (minutes to 24h), and bills
  at the 50% Batch discount. A different code path with its own
  create / poll / cancel / results lifecycle. It does not exist yet (see
  O-API-008, A-API-011).

**Axis 2 — service tier (priced latency class of a synchronous request):**
`standard` / `flex` / `priority` / `scale` (OpenAI) and `standard` / `priority`
(Anthropic, assigned by `auto`). A service tier modifies a *synchronous*
request; it composes with either execution model above.

**Rules the implementation must follow:**

1. Provider Batch is an execution model (an async job API with its own pricing
   mode), **not** a `service_tier` value. Never map "batch" onto `service_tier`,
   and never apply the 50% Batch discount to concurrent-async
   (`batch_complete`) results — those bill at whatever synchronous tier the
   request selected.
2. Keep `batch_complete` (concurrent standard-mode async) unchanged in behavior,
   but rename or document it so it cannot be mistaken for the provider Batch API
   — e.g. `concurrent_complete` / `gather_complete`, with `batch_complete`
   retained as a deprecated alias for compatibility.
3. Introduce the provider Batch API under a separate, unambiguous surface
   (e.g. a `Batches` resource / `submit_batch_job`) that returns a job handle
   and applies batch pricing only to results that actually came back from that
   job.
4. The service-tier axis stays independent: a `latency_policy` / tier control
   selects standard/flex/priority/scale for synchronous requests (fired one at a
   time or concurrently); it has no meaning for a Batch job submission.
5. Cost accounting selects the rate from the *actual* execution model and tier
   the provider reports — concurrent-async results use the synchronous tier
   rate, Batch-job results use the batch rate — so the two never cross-
   contaminate billing.

Net effect: package-level batching remains non-blocking concurrent standard-mode
I/O, and real provider Batch support is added beside it without overloading the
same name or the `service_tier` field, while the overall package stays healthy
(the existing `batch_complete` / `BatchManager` paths and their tests are kept).

## Native tool coverage

### OpenAI

Current strengths:

- typed descriptors and workflows exist for web search, file search, tool
  search, code interpreter, hosted shell, apply patch, computer use, image
  generation, remote MCP, and connectors;
- background Responses, conversations, compaction, MCP approval, and several
  continuation flows are implemented.

Important gaps:

- model-specific tool compatibility is not enforced accurately;
- GPT-5.5 Skills support is not represented in the catalog;
- standalone Skills and Containers resource lifecycle is absent;
- tool charges are not included in usage costs;
- newer tool parameters can depend on raw pass-through;
- provider endpoint defaults can leave these features disabled.

### Anthropic

Current strength:

- normal client-executed function tools work.

Everything beyond ordinary function tools is missing or rejected, including the
server/client tool families listed in A-API-006.

## Tests and validation gaps

### T-001: Tests certify stale snapshots rather than current provider truth

Tests explicitly assert:

- GPT-5.4 as the newest OpenAI family;
- Opus 4.7 as the current Anthropic flagship;
- Opus 4.7 fast pricing;
- stale provider defaults.

Evidence:

- `tests/llm_client/test_model_catalog.py:39-127`
- `tests/llm_client/test_model_catalog.py:267-272`

### T-002: No provider-document drift test exists

Missing automated checks:

- required current model IDs;
- active/deprecated/retired states;
- exact snapshots and aliases;
- pricing effective dates;
- endpoint compatibility;
- reasoning and thinking constraints;
- native tool compatibility;
- service-tier support;
- prompt-cache retention and thresholds.

### T-003: No engine regression covers dropped cache controls

Direct OpenAI provider tests confirm cache parameters are passed, but no test
uses `ExecutionEngine` with the same `RequestSpec` fields.

Evidence:

- direct test: `tests/llm_client/test_provider_response_parsing.py:800-831`

### T-004: No real Batch API contract tests

There are no mocked contract tests for either provider's batch resource
lifecycle, request files, result streams, cancellation, or discounted cost
mode.

### T-005: Anthropic current-feature tests are absent

Missing tests include:

- Opus 4.8 constraints;
- Fable 5 and Mythos 5 behavior;
- adaptive thinking and `output_config.effort`;
- thinking/redacted-thinking round trips;
- structured outputs;
- image/PDF/file input;
- automatic and explicit prompt caching;
- mixed-TTL cache usage;
- service tier and fast mode;
- server tools and citations;
- Message Batches, Files, and Models.

## Documentation-source assessment

### OpenAI

The OpenAI Docs MCP is the more reliable and easier primary source for OpenAI
model and API work.

Reasons:

- it searches and fetches official OpenAI documentation only;
- it exposes the current OpenAPI endpoint list;
- dedicated model pages return structured model IDs, snapshots, reasoning, tool,
  and pricing notes;
- current deprecation and request parameter references are directly available.

Context7 remains useful for checking an installed OpenAI SDK's code-level
surface, but it should not outrank OpenAI's own model, pricing, lifecycle, and
API documentation.

### Anthropic

Context7 is useful for current Anthropic SDK type signatures and examples, but
it is not sufficient as the catalog authority.

Observed limitations:

- it exposed Opus 4.8 and Mythos Preview in the SDK model literal;
- it did not yet include the 2026-06-09 Fable 5 and Mythos 5 release;
- it does not provide authoritative numeric pricing and lifecycle dates as
  reliably as Anthropic's official pages.

For Anthropic:

1. official model, pricing, deprecation, and feature docs should be primary;
2. the Models API should be used for runtime capability/token-limit discovery;
3. Context7 and installed SDK introspection should validate request/response
   type availability;
4. discrepancies should be recorded rather than silently selecting one source.

## Recommended remediation sequence

### Phase 0: Correctness blockers

1. Allow explicit unknown provider model IDs.
2. Forward all `RequestSpec` cache/include fields through engine complete and
   stream paths.
3. Preserve full OpenAI reasoning objects.
4. stop advertising Anthropic image/file support until implemented.
5. add model-aware validation and omission of caller-configured Anthropic
   sampling parameters (`temperature`, `top_p`, `top_k`) for models that reject
   non-default sampling (Opus 4.7+). Note the `AnthropicProvider` constructor
   already defaults `default_temperature` to `None`, so there is no implicit
   *provider* default to remove; the only implicit source is
   `AnthropicConfig.default_temperature = 0.7` (`config/provider.py:36`), which
   must not be injected for incompatible models. (See A-API-014.)
6. add a *narrow, temporary* lifecycle guard — a small denylist of known
   removed/retired model IDs that blocks selection by default, plus a warning on
   the existing `deprecated` flag. This does not require the Phase 1 schema and
   is explicitly superseded by it; see the note below. (See C-004.)
7. label engine concurrent batching distinctly from provider Batch APIs.

The full lifecycle model — a status enum (`active` / `preview` /
`limited_availability` / `deprecated` / `retired` / `removed`) with exact
release/deprecation/retirement dates and replacement pointers — depends on the
Catalog v2 schema and lands in Phase 1 (item 3). Phase 0 item 6 is deliberately
scoped to a minimal stopgap so the safety win (not silently selecting removed
models) ships without blocking on the schema redesign; Phase 1 replaces the
stopgap denylist with the schema-driven lifecycle object.

### Phase 1: Catalog v2

1. Replace duplicated class/JSON truth with a canonical catalog.
2. Add source attribution, effective dates, and freshness metadata.
3. Add aliases/snapshots, lifecycle, endpoint, modality, parameter, tool,
   caching, tier, and pricing structures.
4. Add current OpenAI and Anthropic models and exact deprecations.
5. add a generated compatibility layer for existing model classes.

### Phase 2: Request and usage normalization

1. Add typed operational controls without erasing provider-specific values.
2. Preserve actual service tier, region, speed, batch mode, server-tool usage,
   and cache TTL breakdown.
3. implement a pricing resolver based on model, date, mode, context band,
   region, modality, and tools.
4. treat unknown costs as unknown, never zero.

### Phase 3: Provider Batch APIs

1. Implement OpenAI Batches lifecycle and result files.
2. Implement Anthropic Message Batches lifecycle and result streaming.
3. Add normalized batch job/result types.
4. Apply actual batch pricing only to batch results.

### Phase 4: Anthropic feature completion

1. Implement vision, PDF/document, and Files API transport.
2. Implement adaptive thinking, effort, structured outputs, and signed thinking
   block round trips.
3. Add provider-native/server tool descriptors and result parsing.
4. Add citations, refusal details, server-tool usage, Models API, fast mode, and
   service-tier observability.

### Phase 5: OpenAI platform completion

1. Make endpoint choice model-aware and Responses-first where appropriate.
2. Add Models, Containers, Skills, Batches, current Realtime translation, voice,
   and video resources according to package scope.
3. Add current multimodal model profiles and pricing.
4. Add tool-charge and media-price accounting.

### Phase 6: Drift prevention

1. Add provider-doc snapshot update tooling.
2. Compare official model/lifecycle tables in CI or a scheduled audit job.
3. require source URLs and effective dates for pricing changes.
4. test installed minimum and maximum supported SDK versions.
5. publish a generated coverage report for each release.

## Proposed acceptance criteria

The package should not claim provider completeness until:

- every active generally available model in scope is usable by ID;
- limited-access and preview models are clearly marked;
- retired/removed models cannot be mistaken for active models;
- endpoint, modality, reasoning, cache, tier, and tool support is explicit per
  model;
- direct provider calls and engine calls preserve the same first-class fields;
- actual tier/mode/region/cache/tool usage survives normalization;
- costs are correct for standard, batch, flex/priority or fast, long-context,
  regional, multimodal, and tool usage, or explicitly reported as unknown;
- both actual provider Batch APIs are implemented;
- Anthropic vision/files/thinking/structured outputs/server tools work end to
  end;
- automated drift checks catch provider releases and deprecations.

## Facts, inferences, and unknowns

### Facts

- The installed SDK and package surfaces described above were inspected
  directly.
- Catalog counts are 66 OpenAI entries and 17 Anthropic entries.
- All specifically listed missing model IDs fail catalog lookup.
- Engine dispatch omits three defined OpenAI first-class fields.
- Both provider SDKs expose Batch resources, but this package does not wrap
  them.
- Official provider docs conflict with multiple catalog lifecycle and pricing
  entries.

### Inferences

- Raw pass-through fields will generally work when the installed SDK accepts
  them, but this is not robust package support because validation,
  normalization, cache keys, and result metadata are incomplete.
- The current catalog's broad capability inference will continue producing new
  false positives as provider surfaces diverge.
- A catalog-only patch would improve model availability but would not solve the
  larger correctness problems.

### Unknowns

- Live account-specific model access, priority capacity, and rate limits were
  not tested.
- Paid API request behavior was not tested.
- Limited-availability Anthropic models may require account contracts not
  visible to this package.
- Provider documentation may change after the audit date; the proposed catalog
  must therefore preserve source and effective-date metadata.

Confidence:

- High for repository implementation findings.
- High for official model, pricing, lifecycle, and request-surface findings as
  of 2026-06-13.
- Medium for behavior available only through limited-access accounts or preview
  features.

## Official sources

OpenAI:

- https://developers.openai.com/api/docs/models/gpt-5.5
- https://developers.openai.com/api/docs/models/gpt-5.5-pro
- https://developers.openai.com/api/docs/models/gpt-realtime-2
- https://developers.openai.com/api/docs/models/gpt-image-2
- https://developers.openai.com/api/docs/pricing
- https://developers.openai.com/api/docs/guides/prompt-caching
- https://developers.openai.com/api/docs/deprecations
- https://developers.openai.com/api/reference/resources/responses/methods/create
- https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create

Anthropic:

- https://docs.anthropic.com/en/docs/about-claude/models
- https://docs.anthropic.com/en/docs/about-claude/models/whats-new-claude-4-8
- https://docs.anthropic.com/en/docs/about-claude/pricing
- https://docs.anthropic.com/en/docs/about-claude/model-deprecations
- https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching
- https://docs.anthropic.com/en/api/service-tiers
- https://docs.anthropic.com/en/api/messages
- https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/code-execution-tool
- https://github.com/anthropics/anthropic-sdk-python
