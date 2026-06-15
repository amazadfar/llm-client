# telic Public API Map

This document defines the intended public package boundary for `telic`.
It is the contract to use when modernizing imports, writing examples, and
deciding whether a symbol should be considered stable, compatibility-only,
advanced, reserved, or internal.

This is the current public package map for the pre-`1.0.0` line. The file name
is retained for link stability, but the map is not yet a frozen `1.x`
compatibility promise.

## Stability Levels

- `Stable`: Recommended for new projects. Backward-compatibility should be
  preserved deliberately.
- `Compatibility`: Retained for existing callers. New projects should avoid it.
- `Advanced`: Supported lower-level helpers for specialized use, but not part
  of the preferred standalone-package surface.
- `Reserved`: Namespace is intentionally reserved for future promotion, but is
  not yet implemented as a stable module.
- `Internal`: Not part of the public contract. Behavior and exports may change
  without notice.

## Canonical Import Rule

For new integrations:

- Prefer module namespaces over top-level `telic` imports.
- Treat `telic.__init__` as a convenience layer, not the canonical source
  of truth for long-term integrations.
- Use `telic.compat` for legacy API access.
- Use `telic.advanced` for lower-level helper and integration surfaces.

## Stable Namespaces

### `telic.providers`

Purpose:
- Provider protocol and concrete provider entry points.

Use for:
- `Provider`, `BaseProvider`
- `OpenAIProvider`, `AnthropicProvider`, `GoogleProvider`
- provider-level message/result/event types when working directly at provider
  level

Notes:
- Provider-specific translator internals remain internal.

### `telic.models`

Purpose:
- Stable model profile definitions.

Use for:
- `ModelProfile`
- named model profiles such as `GPT5`, `GPT5Mini`, `Gemini20Flash`

Notes:
- The metadata catalog is exposed separately through `telic.model_catalog`
  and the top-level stable surface.

### `telic.types`

Purpose:
- Canonical request/result/event/cancellation data types.

Use for:
- `RequestContext`, `RequestSpec`
- `Message`, `Role`
- `ToolCall`, `ToolCallDelta`
- `Usage`
- `CompletionResult`, `NormalizedOutputItem`, `BackgroundResponseResult`, `DeepResearchRunResult`, `ConversationResource`, `CompactionResult`, `DeletionResult`, `ConversationItemResource`, `ConversationItemsPage`, `EmbeddingResult`
- `BatchJob`, `BatchRequestItem`, `BatchResultItem`
- `ModelInfo`, `FileObject`, `ResourcePage`
- `ContainerResource`, `ContainersPage`, `ContainerFileResource`, `ContainerFilesPage`
- `SkillResource`, `SkillsPage`, `SkillVersionResource`, `SkillVersionsPage`
- `VideoResource`, `VideosPage`, `VideoContentResult`, `VideoCharacterResource`
- `ModerationResult`, `ImageGenerationResult`, `GeneratedImage`, `AudioTranscriptionResult`, `AudioSpeechResult`
- `FileResource`, `FilesPage`, `FileContentResult`, `UploadResource`, `UploadPartResource`
- `VectorStoreResource`, `VectorStoresPage`, `VectorStoreSearchResult`, `VectorStoreFileResource`, `VectorStoreFilesPage`, `VectorStoreFileContentResult`, `VectorStoreFileBatchResource`
- `FineTuningJobResult`, `FineTuningJobsPage`, `FineTuningJobEventsPage`
- `RealtimeClientSecretResult`, `RealtimeTranscriptionSessionResult`, `RealtimeCallResult`, `RealtimeEventResult`, `RealtimeMCPToolListingResult`, `RealtimeResponseOutput`, `RealtimeConnection`, `WebhookEventResult`
- `StreamEvent`, `StreamEventType`
- `CancellationToken`, `CancelledError`

Notes:
- New code should prefer this namespace over importing the same core types from
  provider-specific modules.

### `telic.content`

Purpose:
- Canonical structured content model and content-envelope boundary.

Use for:
- typed content blocks
- `ContentMessage`
- `ContentRequestEnvelope`
- `ContentResponseEnvelope`
- content projection and response/envelope normalization helpers

Notes:
- This is the canonical multimodal/content boundary for engine and provider
  integrations.

### `telic.context`

Purpose:
- Canonical execution-context layer above request correlation.

Use for:
- `BudgetSpec`
- `PolicyRef`
- `RunVersions`
- `ExecutionContext`

Notes:
- `RequestContext` stays canonical in `telic.types` / `telic.spec`.

### `telic.budgets`

Purpose:
- Canonical budget enforcement and usage-ledger primitives.

Use for:
- `Ledger`, `LedgerWriter`, `InMemoryLedgerWriter`
- `LedgerEvent`, `LedgerEventType`
- `UsageRecord`
- `Budget`, `BudgetDecision`, `BudgetExceededError`

Notes:
- This namespace owns generic execution-usage and budget concepts.
- Product billing policy, tenant ledgers, and application-owned quota
  persistence stay outside `telic`.

### `telic.context_assembly`

Purpose:
- Generic multi-source context assembly contracts above the planner and memory
  subsystems.

Use for:
- `ContextSourceLoader`
- `ContextSourceRequest`
- `ContextSourcePayload`
- `ContextAssemblyRequest`
- `ContextAssemblyResult`
- `MultiSourceContextAssembler`

Notes:
- This namespace is intentionally generic.
- Domain-specific entity loaders and product context loaders must stay outside
  `telic`.

### `telic.engine`

Purpose:
- Canonical engine runtime for retries, failover, hooks, cache, and
  idempotency-aware orchestration.

Use for:
- `ExecutionEngine`
- `RetryConfig`
- `FailoverPolicy`

### `telic.agent`

Purpose:
- Canonical multi-turn agent layer.

Use for:
- `Agent`
- `AgentConfig`
- `AgentResult`
- `TurnResult`
- `quick_agent`

### `telic.benchmarks`

Purpose:
- Canonical benchmark harness, report format, and trend-comparison helpers.

Use for:
- `BenchmarkCase`, `BenchmarkReport`, `BenchmarkRunMode`
- deterministic local benchmark runs
- explicitly labeled live benchmark runs
- committed baseline report storage and comparison

Notes:
- benchmark cases should default to deterministic providers and local
  primitives
- live benchmark runs should stay opt-in and explicitly labeled

### `telic.tools`

Purpose:
- Canonical tool definition and middleware surface.

Use for:
- `Tool`, `ToolRegistry`, `ToolResult`
- `ResponsesBuiltinTool`, `ResponsesAttributeFilter`, `ResponsesChunkingStrategy`, `ResponsesExpirationPolicy`, `ResponsesFileSearchHybridWeights`, `ResponsesFileSearchRankingOptions`, `ResponsesToolSearch`, `ResponsesFunctionTool`, `ResponsesToolNamespace`, `ResponsesVectorStoreFileSpec`, `ResponsesConnectorId`, `ResponsesDropboxTool`, `ResponsesGmailTool`, `ResponsesGoogleCalendarTool`, `ResponsesGoogleDriveTool`, `ResponsesMicrosoftTeamsTool`, `ResponsesOutlookCalendarTool`, `ResponsesOutlookEmailTool`, `ResponsesSharePointTool`, `ResponsesMCPTool`, `ResponsesMCPApprovalPolicy`, `ResponsesMCPToolFilter`, `ResponsesCustomTool`, `ResponsesGrammar`, `ResponsesShellCallChunk`, `ResponsesShellCallOutcome`, `ResponsesShellCallOutput`, `ResponsesApplyPatchCallOutput`
- `tool`, `sync_tool`, `tool_from_function`
- tool middleware stack for advanced use

Notes:
- `ToolRegistry` remains the execution/runtime surface for local function tools.
- `ResponsesBuiltinTool`, `ResponsesAttributeFilter`,
  `ResponsesChunkingStrategy`, `ResponsesExpirationPolicy`,
  `ResponsesFileSearchHybridWeights`, `ResponsesFileSearchRankingOptions`,
  `ResponsesToolSearch`, `ResponsesFunctionTool`, `ResponsesToolNamespace`,
  `ResponsesVectorStoreFileSpec`, `ResponsesMCPTool`, the connector-tool enums,
  `ResponsesShellCallChunk`, `ResponsesShellCallOutcome`,
  `ResponsesShellCallOutput`, `ResponsesApplyPatchCallOutput`, and
  `ResponsesCustomTool` are provider-native request/continuation descriptors
  for OpenAI Responses workflows, not locally executable tools.

### `telic.cache`

Purpose:
- Cache abstractions and supported backends.

Use for:
- `CacheCore`
- `CachePolicy`, `CacheInvalidationMode`
- `MetadataCacheStore`, `SummaryCacheStore`
- cache backend types/settings
- supported cache backend implementations

Notes:
- Persistence-specific SQL helpers are not part of the preferred stable
  surface.
- Cache-backed metadata and summary stores remain storage-agnostic and sit
  above `CacheCore`, not above repo-specific ledgers or billing models.

### `telic.memory`

Purpose:
- Generic memory and persistent-summary abstractions.

Use for:
- `MemoryRecord`, `MemoryQuery`, `MemoryWrite`
- `MemoryReader`, `MemoryWriter`, `MemoryStore`
- `SummaryRecord`, `SummaryStore`
- `ShortTermMemoryStore`, `InMemorySummaryStore`

Notes:
- This namespace holds generic in-process abstractions only.
- Domain-backed entity loaders, tenant-specific retrieval services, and
  product-owned memory policies stay outside `telic`.

### `telic.observability`

Purpose:
- Canonical hooks, diagnostics, runtime eventing, replay, and telemetry entry
  point.

Use for:
- hooks and metrics hooks
- `EngineDiagnosticsRecorder`
- runtime events/event bus
- replay primitives
- telemetry registry/usage tracking

Notes:
- `RuntimeEvent` / replay types are canonical here, even though their concrete
  implementations live in dedicated modules.

### `telic.validation`

Purpose:
- Canonical validation entry point for requests, tools, and schemas.

Use for:
- `ValidationError`
- request/tool/schema validation functions

### `telic.errors`

Purpose:
- Canonical error taxonomy.

Use for:
- `TelicError`
- provider/tool/cache/agent/config error types
- retryability-aware error mapping helpers

### `telic.config`

Purpose:
- Supported configuration and `.env` loading surface.

Use for:
- settings models
- `get_settings`
- `configure`
- `load_env`

## Compatibility Namespace

### `telic.compat`

Status:
- `Compatibility`

Use for:
- `OpenAIClient`
- `ResponseTimeoutError`

Policy:
- Retained for existing users.
- New code should prefer `telic.providers`, `telic.engine`, and
  `telic.agent`.
- Top-level `telic.OpenAIClient` should be treated as compatibility-only.

## Advanced Namespace

### `telic.advanced`

Status:
- `Advanced`

Purpose:
- Explicit home for lower-level helpers and integration surfaces that are still
  useful but are not the preferred standalone-package API.

Contains:
- container/factory helpers
- idempotency helpers
- hashing/performance/serialization utilities
- streaming adapters/utilities

Policy:
- Supported for specialized use.
- Not the primary package entry point for typical integrations.

## Stable And Reserved Namespaces

### `telic.adapters`

Status:
- `Stable`

Purpose:
- Canonical namespace for generic service adaptors such as SQL, Redis, and
  vector backends.

Use for:
- normalized adaptor contracts
- typed request/result shapes
- concrete backend adaptors behind optional extras
- generic tool-construction helpers over adaptors

Current concrete backend surface:
- `PostgresSQLAdaptor`
- `MySQLSQLAdaptor`
- `RedisKVAdaptor`
- `QdrantVectorAdaptor`

Policy:
- The public concern is normalized adaptors, not raw backend drivers.
- Lower-level drivers may exist as internal or advanced implementation detail.
- Business queries and domain workflows stay outside the package.

### `telic.plugins`

Status:
- `Reserved`
- `Deferred For 1.0`

Intent:
- Future canonical namespace for pluggable runtime/plugin interfaces if that
  layer is promoted from repo-specific runtime integrations.

Policy:
- The current `0.x` line does not introduce a stable plugin registry in
  `telic`.
- Plugin lifecycle and host-runtime extension concerns remain external to the
  core package for now.
- Revisit only after the standalone package API is frozen and real extension
  requirements are proven across projects.

## Internal / Non-Contract Modules

These modules may exist and be useful internally, but they are not part of the intended standalone-package contract:

- provider-specific translator internals
- request-builder internals
- resilience implementation details
- retry-policy implementation details
- low-level runtime extraction helpers not promoted into stable namespaces
- repo-specific orchestration glue in other packages

## Canonical Type Placement

The intended canonical placement is:

- request/result/usage/event/cancellation core types: `telic.types`
- structured content and envelopes: `telic.content`
- execution context / budgets / policy refs: `telic.context`
- budget enforcement and usage-ledger primitives: `telic.budgets`
- runtime events and replay access: `telic.observability`
- error taxonomy: `telic.errors`

This means new API work should avoid introducing duplicate type entry points
unless there is a strong compatibility reason.

## Top-Level `telic` Policy

Top-level `telic` exports should stay intentionally small:

- stable high-value convenience exports may remain
- compatibility aliases may remain with warnings
- hidden accidental exports should not leak into the module namespace

Long-term callers should still import from the canonical module namespaces
above rather than relying on top-level convenience imports.
