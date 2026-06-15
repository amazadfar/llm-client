# llm-client Guides and Cookbook Index

This index ties the standalone package documentation to the runnable cookbook
examples under [`examples/`](../examples/README.md).

## Core Reference

- Architecture overview:
  [llm-client-architecture.md](llm-client-architecture.md)
- Public API map:
  [llm-client-public-api-v1.md](llm-client-public-api-v1.md)
- Root README and positioning:
  [README.md](../README.md)
- Package API guide:
  [llm-client-package-api-guide.md](llm-client-package-api-guide.md)
- Build and recipes guide:
  [llm-client-build-and-recipes-guide.md](llm-client-build-and-recipes-guide.md)
- Usage and capabilities guide:
  [llm-client-usage-and-capabilities-guide.md](llm-client-usage-and-capabilities-guide.md)
- OpenAI and Anthropic provider guide:
  [llm-client-openai-anthropic-provider-guide.md](llm-client-openai-anthropic-provider-guide.md)

## Guides

- Provider setup:
  [llm-client-provider-setup-guide.md](llm-client-provider-setup-guide.md)
- Routing and failover:
  [llm-client-routing-and-failover-guide.md](llm-client-routing-and-failover-guide.md)
- Tool runtime:
  [llm-client-tool-runtime-guide.md](llm-client-tool-runtime-guide.md)
- Tool creation:
  [llm-client-tool-creation-guide.md](llm-client-tool-creation-guide.md)
- Structured outputs:
  [llm-client-structured-outputs-guide.md](llm-client-structured-outputs-guide.md)
- Context and memory:
  [llm-client-context-and-memory-guide.md](llm-client-context-and-memory-guide.md)
- Observability and redaction:
  [llm-client-observability-and-redaction-guide.md](llm-client-observability-and-redaction-guide.md)
- Migration from direct SDK usage:
  [llm-client-migration-from-direct-sdk-guide.md](llm-client-migration-from-direct-sdk-guide.md)
- Migration to 0.4.0:
  [llm-client-migration-to-0.4.0.md](llm-client-migration-to-0.4.0.md)

## Packaging and Release

- Installation matrix:
  [llm-client-installation-matrix.md](llm-client-installation-matrix.md)
- Changelog process:
  [llm-client-changelog-process.md](llm-client-changelog-process.md)
- Semantic versioning policy:
  [llm-client-semver-policy.md](llm-client-semver-policy.md)
- Support policy:
  [llm-client-support-policy.md](llm-client-support-policy.md)
- 0.4.0 release notes:
  [llm-client-release-notes-0.4.0.md](llm-client-release-notes-0.4.0.md)
- 0.3.1 release notes:
  [llm-client-release-notes-0.3.1.md](llm-client-release-notes-0.3.1.md)
- 0.3.0 release notes:
  [llm-client-release-notes-0.3.0.md](llm-client-release-notes-0.3.0.md)
- 0.2.1 release notes:
  [llm-client-release-notes-0.2.1.md](llm-client-release-notes-0.2.1.md)
- 0.2.0 release notes:
  [llm-client-release-notes-0.2.0.md](llm-client-release-notes-0.2.0.md)
- 0.1.0 release notes:
  [llm-client-release-notes-0.1.0.md](llm-client-release-notes-0.1.0.md)

## Cookbook Scripts

- Cookbook entry point:
  [examples/README.md](../examples/README.md)
- Examples guide:
  [llm-client-examples-guide.md](llm-client-examples-guide.md)
- One-shot completion:
  [01_one_shot_completion.py](../examples/01_one_shot_completion.py)
- Streaming:
  [02_streaming.py](../examples/02_streaming.py)
- Embeddings:
  [03_embeddings.py](../examples/03_embeddings.py)
- Content blocks and envelopes:
  [04_content_blocks.py](../examples/04_content_blocks.py)
- Structured extraction:
  [05_structured_extraction.py](../examples/05_structured_extraction.py)
- Routing and failover:
  [06_provider_registry_and_routing.py](../examples/06_provider_registry_and_routing.py)
- Engine cache, retry, and idempotency:
  [07_engine_cache_retry_idempotency.py](../examples/07_engine_cache_retry_idempotency.py)
- Tool execution modes:
  [08_tool_execution_modes.py](../examples/08_tool_execution_modes.py)
- Tool-calling agent:
  [09_tool_calling_agent.py](../examples/09_tool_calling_agent.py)
- Context and memory planning:
  [10_context_memory_planning.py](../examples/10_context_memory_planning.py)
- Observability and redaction:
  [11_observability_and_redaction.py](../examples/11_observability_and_redaction.py)
- Benchmarks:
  [12_benchmarks.py](../examples/12_benchmarks.py)
- Batch processing:
  [13_batch_processing.py](../examples/13_batch_processing.py)
- Sync wrappers:
  [14_sync_wrappers.py](../examples/14_sync_wrappers.py)
- Rate limiting:
  [15_rate_limiting.py](../examples/15_rate_limiting.py)
- OpenAI background Responses lifecycle:
  [38_openai_background_responses.py](../examples/38_openai_background_responses.py)
- OpenAI conversation state workflow:
  [39_openai_conversation_state_workflow.py](../examples/39_openai_conversation_state_workflow.py)
- OpenAI normalized output items:
  [40_openai_normalized_output_items.py](../examples/40_openai_normalized_output_items.py)
- FastAPI SSE:
  [16_fastapi_sse.py](../examples/16_fastapi_sse.py)
- Persistence repository:
  [17_persistence_repository.py](../examples/17_persistence_repository.py)
- Memory-backed assistant:
  [18_memory_backed_assistant.py](../examples/18_memory_backed_assistant.py)
