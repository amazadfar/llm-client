# telic Examples Guide

This guide explains how to use the cookbook under
[examples/README.md](../examples/README.md)
as a package adoption surface.

## What The Cookbook Is For

The cookbook is not just a smoke-test folder. It serves three purposes:

- prove real package behavior against real providers and optional infra
- show the recommended way to compose package capabilities
- provide application-shaped references without promoting all workflows into
  the core package surface

The default example runner tracks the currently validated cookbook ring. Some
newer advanced provider-specific examples may be documented here before they
are promoted into that default ring, and should be run directly by filename
until they are live-validated consistently.

## Prerequisites

Baseline:

- install the package and any needed extras
- load environment variables explicitly
- provide provider credentials for the examples you want to run

Common environment variables:

- `OPENAI_API_KEY`
- `TELIC_EXAMPLE_PROVIDER`
- `TELIC_EXAMPLE_MODEL`
- `TELIC_EXAMPLE_SECONDARY_PROVIDER`
- `TELIC_EXAMPLE_SECONDARY_MODEL`
- `TELIC_EXAMPLE_EMBEDDINGS_PROVIDER`
- `TELIC_EXAMPLE_EMBEDDINGS_MODEL`

Optional infrastructure:

- `TELIC_EXAMPLE_PG_DSN` for persistence examples
- `QDRANT_URL` and optionally `QDRANT_API_KEY` for retrieval/cache examples
- `TELIC_EXAMPLE_MCP_PREVIOUS_RESPONSE_ID` and
  `TELIC_EXAMPLE_MCP_APPROVAL_REQUEST_ID` for the MCP approval
  continuation example
- optionally `TELIC_EXAMPLE_MCP_APPROVE=0|1` to flip the approval
  continuation outcome
- `TELIC_EXAMPLE_REALTIME_MODEL` for the realtime wrapper example
- `TELIC_EXAMPLE_REALTIME_TRANSCRIPTION_MODEL` for the realtime
  transcription example
- `TELIC_EXAMPLE_VECTOR_STORE_ID`,
  `TELIC_EXAMPLE_VECTOR_STORE_FILE_IDS`, and
  `TELIC_EXAMPLE_VECTOR_STORE_UPLOAD_PATHS` for the vector-store batch
  example
- `TELIC_EXAMPLE_DEEP_RESEARCH_MODEL` and
  `TELIC_EXAMPLE_DEEP_RESEARCH_PROMPT` for the deep-research
  examples
- `TELIC_EXAMPLE_DEEP_RESEARCH_CLARIFICATIONS` and optionally
  `TELIC_EXAMPLE_DEEP_RESEARCH_WAIT=0|1` for the staged deep-research
  example
- `TELIC_EXAMPLE_OPENAI_TOOLS_MODEL`,
  `TELIC_EXAMPLE_MCP_SERVER_URL`, and/or
  `TELIC_EXAMPLE_CONNECTOR_ID` for the MCP/connector workflow example
- optionally `TELIC_EXAMPLE_MCP_AUTHORIZATION` and
  `TELIC_EXAMPLE_CONNECTOR_AUTHORIZATION` for authenticated MCP and
  connector workflows
- the MCP approval continuation example can also reuse those MCP/connector
  env vars when approval continuation must resend an auth-bearing tool
  definition
- `TELIC_EXAMPLE_UPLOAD_FILE_PATH` and optionally
  `TELIC_EXAMPLE_FILE_PURPOSE` / `TELIC_EXAMPLE_KEEP_UPLOADED_FILE`
  for the generic OpenAI Files API example
- `TELIC_EXAMPLE_ANTHROPIC_MODEL` and optionally
  `TELIC_EXAMPLE_ANTHROPIC_EFFORT` for Anthropic current-feature examples
- `TELIC_EXAMPLE_ANTHROPIC_UPLOAD_FILE_PATH` and optionally
  `TELIC_EXAMPLE_KEEP_ANTHROPIC_FILE=0|1` for the Anthropic Files API path
- `TELIC_EXAMPLE_RUN_PROVIDER_BATCH=1` to create real OpenAI Batch and
  Anthropic Message Batches jobs; example `62` is dry-run by default

## Example Categories

### Core capability examples

These demonstrate stable package capabilities directly:

- `01` one-shot completion
- `02` streaming
- `03` embeddings
- `04` content blocks and envelopes
- `05` structured extraction
- `06` provider registry and routing
- `07` engine cache/retry/idempotency
- `08` tool execution modes
- `09` tool-calling agent
- `10` context and memory planning
- `11` observability and redaction
- `12` benchmarks
- `13` local concurrent batch processing with checkpointed manager
- `14` sync wrappers
- `15` rate limiting
- `35` file block transport
- `38` OpenAI background Responses lifecycle
- `39` OpenAI conversation state workflow
- `40` OpenAI normalized output items
- `41` OpenAI background stream resume/reconnect
- `42` OpenAI prompt caching and encrypted reasoning continuity
- `43` OpenAI long-running conversation compaction
- `46` OpenAI realtime connection wrapper
- `47` OpenAI vector-store file batches
- `48` OpenAI deep-research clarify/rewrite kickoff
- `49` OpenAI realtime transcription session
- `50` OpenAI MCP and connector workflows
- `51` OpenAI staged deep research orchestration
- `52` OpenAI Files API upload/retrieve/list/content/delete flow
- `53` OpenAI realtime conversation lifecycle
- `54` OpenAI `tool_search` and namespaces
- `55` OpenAI Uploads API lifecycle
- `56` OpenAI realtime output collection
- `57` OpenAI realtime push-to-talk helper flow
- `58` OpenAI vector-store provisioning
- `59` OpenAI realtime MCP lifecycle and tool-loading wait helper
- `60` Anthropic thinking and structured outputs
- `61` Anthropic native content, cache controls, Models API, and optional Files
  API upload
- `62` provider Batch APIs; dry-run by default, live OpenAI Batch and
  Anthropic Message Batches only when explicitly enabled

### Application-shaped examples

These show realistic compositions of stable package primitives:

- `16` FastAPI SSE
- `17` persistence repository
- `18` memory-backed assistant
- `19` multi-provider failover gateway
- `20` RAG with citations
- `21` document review diff
- `22` human-in-the-loop approvals
- `23` async job queue + SSE
- `24` customer support copilot
- `25` incident war room assistant
- `26` research briefing agent
- `27` SQL analytics assistant
- `28` release readiness control plane
- `29` multimodal intake pipeline
- `30` eval and regression gate
- `31` partial tool failures
- `32` cache strategy showdown
- `33` compliance redaction pipeline
- `34` end-to-end mission control
- `36` direct PostgreSQL adaptor usage
- `37` tool-wrapped SQL adaptor agent
- `44` engine-orchestrated OpenAI workflow
- `45` MCP approval continuation from stored OpenAI response state

Current opt-in classification:

- realtime audio, MCP, upload, Qdrant, PostgreSQL, and provider Batch examples
  require extra local inputs or services
- provider Batch example `62` is dry-run by default because live mode creates
  durable provider jobs/files
- frontier models are not cookbook defaults; use explicit model env vars when
  you want to demonstrate GPT-5.5, Opus 4.8, Fable 5, or higher reasoning
- every generation request has an explicit output-token ceiling, enforced by
  the cookbook inventory test
- examples that create temporary provider files or vector stores delete them
  by default unless a documented `KEEP_*` option is enabled
- the suite runner ignores inherited `KEEP_*` flags unless
  `TELIC_EXAMPLE_ALLOW_PERSISTENT_RESOURCES=1` is explicitly set

## How To Interpret Success

Expected outcomes:

- core examples should demonstrate one major package capability clearly
- application-shaped examples should demonstrate composition, not just isolated
  API calls
- examples that need unavailable optional services should fail fast with clear
  setup guidance rather than silently degrade

Typical failure classes:

- missing provider credentials
- optional provider package not installed
- optional infrastructure not running
- provider quota/rate limits
- large-upload examples may also fail on provider-side file-purpose or MIME
  validation if the local file does not match the configured purpose
- realtime audio-turn examples may also skip or fail fast when no compatible
  local audio file is configured or the websocket session cannot be established

These failures should be treated differently from package regressions.

## How Examples Map To Stable APIs

Examples are intended to map back to the stable package contract:

- provider usage maps to `telic.providers`
- engine/routing/failover maps to `telic.engine`
- tool examples map to `telic.tools`
- agent examples map to `telic.agent`
- memory and context examples map to `telic.context`,
  `telic.context_assembly`, and `telic.memory`
- observability examples map to `telic.observability`
- benchmark examples map to `telic.benchmarks`
- file transport examples map to `telic.content` and provider translation
  through the engine/provider surface
- service adaptor examples map to `telic.adapters` and
  `telic.adapters.tools`

If an example demonstrates an application architecture pattern, treat the
underlying stable primitive as the real package API, not the full surrounding
workflow.

## Recommended Reading Order

For a new adopter:

1. `01`, `02`, `05`
2. `07`, `08`, `09`
3. `10`, `11`, `35`
4. `38`, `39`, `40` if you plan to use OpenAI Responses lifecycle/state APIs
5. `41`, `42`, `43` if you need reconnectable background streams, prompt
   caching controls, or context compaction
6. `44`, `45`, `46`, `47`, `48`, `49`, `50`, `51`, `53`, `54`, `55`, `56`,
   `57`, `58`, `59` if you plan to orchestrate stored OpenAI workflows,
   realtime product surfaces, hosted-tool workflows, files/uploads, or vector
   stores at the engine layer
7. `60`, `61`, `62` if you plan to use Anthropic current features or real
   provider Batch APIs
8. `36`, `37` if you plan to expose controlled service access through tools
9. application-shaped examples that match your target use case

## Per-Example Purpose Notes

The cookbook README already contains one short purpose note for every example.
Use this guide alongside that index:

- the README is the quick inventory
- this document explains how to interpret the inventory
- the package API and usage guides explain which package surface each example
  is actually demonstrating
