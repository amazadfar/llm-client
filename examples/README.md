# telic Cookbook

These examples are the runnable cookbook for the standalone `telic`
package.

Design goals:

- real provider calls for all LLM-facing examples
- fail fast when required credentials or services are missing
- one script per major capability
- a few combined flows that look like real application designs
- optional dependency or infrastructure examples fail with clear setup guidance

Run examples from the repository root:

```bash
python examples/01_one_shot_completion.py
```

Or run the full live cookbook ring:

```bash
python scripts/ci/run_telic_examples.py --subset all
```

Run only the core capability ring:

```bash
python scripts/ci/run_telic_examples.py --subset core
```

Run only the application-shaped examples:

```bash
python scripts/ci/run_telic_examples.py --subset application
```

The default runner tracks the currently validated cookbook ring. Newly added
advanced provider-specific examples may appear in this index before they are
promoted into that default ring, and can be run directly by filename.

## Core Capability Examples

- `01_one_shot_completion.py`: direct provider completion
- `02_streaming.py`: token streaming and final stream result handling
- `03_embeddings.py`: embedding generation through the engine
- `04_content_blocks.py`: content blocks, envelopes, and content projection
- `05_structured_extraction.py`: schema validation, repair loop, diagnostics
- `06_provider_registry_and_routing.py`: provider registry, capability lookup,
  routing, and failover
- `07_engine_cache_retry_idempotency.py`: retries, cache hits, idempotency, and
  engine diagnostics
- `08_tool_execution_modes.py`: single, sequential, and parallel tool execution
- `09_tool_calling_agent.py`: multi-turn agent with tool calling
- `10_context_memory_planning.py`: memory retrieval, summaries, and context
  planning
- `11_observability_and_redaction.py`: diagnostics, lifecycle reports, metrics,
  and redaction
- `12_benchmarks.py`: deterministic benchmark harness and saved report
- `13_batch_processing.py`: engine local concurrency with
  `concurrent_complete()` plus checkpointed batch manager
- `14_sync_wrappers.py`: sync access to conversation and summarization helpers
- `15_rate_limiting.py`: token/request limiter usage
- `35_file_block_transport.py`: canonical file preparation, native OpenAI
  responses transport, and explicit fallback behavior for non-native providers
- `38_openai_background_responses.py`: engine-managed OpenAI background
  response lifecycle with polling and deletion
- `39_openai_conversation_state_workflow.py`: engine-managed OpenAI
  conversation creation, item listing, and context compaction
- `40_openai_normalized_output_items.py`: normalized `output_items` versus
  low-level provider replay items across a Responses tool loop
- `41_openai_background_resume_stream.py`: background stream attach/reconnect
  with `sequence_number` resume support
- `42_openai_prompt_cache_and_encrypted_reasoning.py`: first-class prompt
  caching controls and encrypted reasoning continuity inspection
- `43_openai_long_running_compaction.py`: longer conversation threads,
  compaction, and item retrieval against stored OpenAI state
- `46_openai_realtime_connection_wrapper.py`: realtime client-secret creation
  and websocket connection wrapper usage
- `47_openai_vector_store_file_batches.py`: vector-store file batches, polling,
  and batch file listing
- `48_openai_deep_research_clarify_rewrite.py`: deep-research clarification,
  prompt rewrite, and kickoff flow
- `49_openai_realtime_transcription_session.py`: realtime transcription
  session creation and transcription websocket connection wrapper usage
- `50_openai_mcp_and_connector_workflows.py`: hosted web-search plus typed
  remote MCP / connector workflow helpers
- `51_openai_run_deep_research_staged.py`: staged deep-research orchestration
  with clarification, rewrite, kickoff, and optional wait-for-completion
- `52_openai_files_api.py`: generic OpenAI Files API upload, retrieval,
  listing, content fetch, and optional cleanup
- `53_openai_realtime_conversation_lifecycle.py`: realtime text-turn
  lifecycle with `create_text_message(...)`, `create_response(...)`, and typed
  event waiting
- `54_openai_tool_search_and_namespaces.py`: advanced OpenAI `tool_search`
  plus namespaced deferred tools and optional `submit_tool_search_output(...)`
  continuation
- `55_openai_uploads_api.py`: OpenAI Uploads API lifecycle with create, part
  upload, completion, cancellation, and chunked-upload helper coverage
- `56_openai_realtime_output_collection.py`: realtime text-turn output
  collection via `collect_response_output(...)`
- `57_openai_realtime_push_to_talk.py`: optional realtime push-to-talk helper
  flow with `disable_vad(...)` and `send_audio_turn(...)`
- `58_openai_vector_store_provisioning.py`: create a vector store, attach typed
  file specs, wait for ingestion, and run a hosted search
- `59_openai_realtime_mcp_lifecycle.py`: realtime MCP session-tool injection
  and `mcp_list_tools` lifecycle waiting
- `60_anthropic_thinking_and_structured_outputs.py`: Anthropic
  `output_config.effort` plus structured output-format handling
- `61_anthropic_native_content_cache_and_files.py`: Anthropic native content
  blocks, cache-control placement, Models API, and optional Files API upload
- `62_provider_batch_apis.py`: dry-run provider Batch payloads by default,
  with opt-in live OpenAI Batch and Anthropic Message Batches job creation

## Combined / Application-Shaped Examples

- `16_fastapi_sse.py`: FastAPI streaming endpoint built on `telic`
- `17_persistence_repository.py`: persistence repository dry run and safety
  checks
- `18_memory_backed_assistant.py`: context planning + memory + engine response
- `19_multi_provider_failover_gateway.py`: injected failure + router fallback
  + gateway diagnostics
- `20_rag_with_citations.py`: Qdrant-backed retrieval + citations + grounded
  answer generation
- `21_document_review_diff.py`: draft diffing + structured review + approval
  framing
- `22_human_in_the_loop_approvals.py`: approval checkpoint + memory-backed
  revision loop
- `23_async_job_queue_sse.py`: FastAPI job queue with polling + SSE progress
- `24_customer_support_copilot.py`: Qdrant-backed support copilot with
  retrieval + structured routing
- `25_incident_war_room_assistant.py`: agentic war-room workflow with tools and
  live synthesis
- `26_research_briefing_agent.py`: Qdrant-backed research briefing workflow
- `27_sql_analytics_assistant.py`: NL-to-SQL drafting with safety checks
- `28_release_readiness_control_plane.py`: structured go/no-go control-plane
  decision
- `29_multimodal_intake_pipeline.py`: multimodal content projection +
  intake-brief generation
- `30_eval_and_regression_gate.py`: live evaluation suite with ship/hold gate
- `31_tool_calling_with_partial_failures.py`: graceful degradation around
  partial and failed tool calls
- `32_cache_strategy_showdown.py`: no-cache vs FS vs Qdrant vs idempotency
  comparison
- `33_compliance_redaction_pipeline.py`: safe payload handling + audit artifact
  generation
- `34_end_to_end_mission_control.py`: full-stack incident/release mission
  control showcase across routing, context, tools, redaction, replay, cache,
  and evaluation-minded decisioning
- `36_sql_adaptor_direct.py`: direct PostgreSQL adaptor usage with read-only
  querying, safety enforcement, and explicit write enablement on a temporary
  table
- `37_sql_adaptor_tools.py`: live tool-calling agent using a read-only SQL
  adaptor tool against temporary incident data in PostgreSQL
- `44_engine_orchestrated_openai_workflow.py`: engine-level orchestration
  across conversation state, background responses, follow-up turns, and
  compaction
- `45_openai_mcp_approval_continuation.py`: continue a stored MCP approval
  loop with a first-class approval-response helper

## Notes

- The examples now use real provider calls.
- By default, the cookbook expects `OPENAI_API_KEY` and uses OpenAI models.
- Defaults are cost-controlled. The standard cookbook uses models such as
  `gpt-5-nano`, `gpt-5-mini`, `o4-mini-deep-research`, and
  `claude-sonnet-4-6`; it does not default to Opus 4.8, Fable 5, GPT-5.5,
  high reasoning, or long-running deep-research waits.
- Every completion request declares a bounded `max_tokens` value. The cookbook
  inventory test rejects new unbounded generation calls.
- Examples that create provider files or vector stores clean them up by
  default. Provider Batch remains dry-run unless explicitly enabled.
- The suite runner forces cleanup even if a local `.env` contains legacy
  `KEEP_*` flags. Set `TELIC_EXAMPLE_ALLOW_PERSISTENT_RESOURCES=1` only
  when intentionally preserving remote cookbook resources.
- The OpenAI Responses lifecycle/state examples (`38`-`45`) expect
  `TELIC_EXAMPLE_PROVIDER=openai`.
- Additional OpenAI capability examples use:
  - `TELIC_EXAMPLE_REALTIME_MODEL` for example `46`
  - `TELIC_EXAMPLE_REALTIME_TRANSCRIPTION_MODEL` for example `49`
  - `TELIC_EXAMPLE_VECTOR_STORE_ID`,
    `TELIC_EXAMPLE_VECTOR_STORE_FILE_IDS`, and/or
    `TELIC_EXAMPLE_VECTOR_STORE_UPLOAD_PATHS` for example `47`
  - `TELIC_EXAMPLE_DEEP_RESEARCH_MODEL` and
    `TELIC_EXAMPLE_DEEP_RESEARCH_PROMPT` for examples `48` and `51`
  - `TELIC_EXAMPLE_DEEP_RESEARCH_CLARIFICATIONS` and optionally
    `TELIC_EXAMPLE_DEEP_RESEARCH_WAIT=0|1` for example `51`
  - `TELIC_EXAMPLE_OPENAI_TOOLS_MODEL` for example `50`
  - `TELIC_EXAMPLE_MCP_SERVER_URL`,
    `TELIC_EXAMPLE_MCP_SERVER_LABEL`,
    `TELIC_EXAMPLE_MCP_AUTHORIZATION`,
    `TELIC_EXAMPLE_MCP_REQUIRE_APPROVAL`,
    `TELIC_EXAMPLE_CONNECTOR_ID`,
    `TELIC_EXAMPLE_CONNECTOR_LABEL`,
    `TELIC_EXAMPLE_CONNECTOR_AUTHORIZATION`, and
    `TELIC_EXAMPLE_CONNECTOR_REQUIRE_APPROVAL` for example `50`
  - `TELIC_EXAMPLE_UPLOAD_FILE_PATH` for example `52`
  - optionally `TELIC_EXAMPLE_FILE_PURPOSE` and
    `TELIC_EXAMPLE_KEEP_UPLOADED_FILE=0|1` for example `52`
- The MCP approval continuation example also expects:
  - `TELIC_EXAMPLE_MCP_PREVIOUS_RESPONSE_ID`
  - `TELIC_EXAMPLE_MCP_APPROVAL_REQUEST_ID`
  - optionally `TELIC_EXAMPLE_MCP_APPROVE=0|1`
  - and optionally the same connector / remote-MCP env vars used by example
    `50` when approval continuation needs to resend an auth-bearing tool
    definition
- Example `53` reuses `TELIC_EXAMPLE_REALTIME_MODEL`.
- Example `54` reuses `TELIC_EXAMPLE_OPENAI_TOOLS_MODEL`.
- Example `55` reuses `TELIC_EXAMPLE_UPLOAD_FILE_PATH`.
- Example `56` reuses `TELIC_EXAMPLE_REALTIME_MODEL`.
- Example `57` reuses `TELIC_EXAMPLE_REALTIME_MODEL` and expects
  `TELIC_EXAMPLE_REALTIME_AUDIO_PATH`.
- Example `58` reuses `TELIC_EXAMPLE_UPLOAD_FILE_PATH` and optionally
  `TELIC_EXAMPLE_KEEP_VECTOR_STORE=0|1`.
- Example `59` reuses `TELIC_EXAMPLE_REALTIME_MODEL`,
  `TELIC_EXAMPLE_MCP_SERVER_URL`,
  `TELIC_EXAMPLE_MCP_SERVER_LABEL`,
  `TELIC_EXAMPLE_MCP_AUTHORIZATION`, and optionally
  `TELIC_EXAMPLE_MCP_REQUIRE_APPROVAL`.
- Example `60` uses `TELIC_EXAMPLE_ANTHROPIC_MODEL` and optionally
  `TELIC_EXAMPLE_ANTHROPIC_EFFORT`.
- Example `61` uses `TELIC_EXAMPLE_ANTHROPIC_MODEL`, optionally
  `TELIC_EXAMPLE_ANTHROPIC_UPLOAD_FILE_PATH`, and optionally
  `TELIC_EXAMPLE_KEEP_ANTHROPIC_FILE=0|1`.
- Example `62` is dry-run by default. Set
  `TELIC_EXAMPLE_RUN_PROVIDER_BATCH=1` to create live provider Batch jobs,
  and optionally set `TELIC_EXAMPLE_OPENAI_BATCH_MODEL` /
  `TELIC_EXAMPLE_ANTHROPIC_BATCH_MODEL`.
- Example `42` uses `TELIC_EXAMPLE_OPENAI_REASONING_MODEL` and defaults
  to `gpt-5-mini` so encrypted reasoning and visible output both fit within a
  bounded request.
- You can switch providers with:
  - `TELIC_EXAMPLE_PROVIDER=openai|anthropic|google`
  - `TELIC_EXAMPLE_MODEL=...`
  - `TELIC_EXAMPLE_SECONDARY_PROVIDER=...`
  - `TELIC_EXAMPLE_SECONDARY_MODEL=...`
  - `TELIC_EXAMPLE_EMBEDDINGS_PROVIDER=...`
  - `TELIC_EXAMPLE_EMBEDDINGS_MODEL=...`
- The persistence example also requires `TELIC_EXAMPLE_PG_DSN`.
- The SQL adaptor examples also require `TELIC_EXAMPLE_PG_DSN`.
- SQL adaptor examples require the optional PostgreSQL extra:
  - `pip install telic[postgres]`
- The retrieval/cache examples that use Qdrant require:
  - `QDRANT_URL=http://127.0.0.1:6333`
  - optionally `QDRANT_API_KEY=...`
- The FastAPI app examples also require the optional FastAPI/uvicorn
  dependencies to be installed.
