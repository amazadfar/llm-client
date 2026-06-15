# llm-client 0.4.0 Release Notes

Status: released

## Added

- Catalog v2 with lifecycle, endpoint, modality, reasoning, caching, service,
  tool, limit, and multidimensional pricing metadata.
- Current OpenAI and Anthropic flagship catalog entries.
- Typed OpenAI and Anthropic request options and service-tier tracking.
- OpenAI Batch and Anthropic Message Batches lifecycle APIs.
- Anthropic Models, Files, native image/document transport, structured outputs,
  rich thinking/citation/refusal results, and server tools.
- OpenAI Models, Containers, Skills, Video, and resource-capability discovery.
- Offline provider catalog validation, reviewed source manifest, and opt-in
  online drift workflow.

## Changed

- Package defaults are now `gpt-5.4-mini` and `claude-sonnet-4-6`.
- OpenAI SDK floor is `2.36`; Anthropic SDK floor is `0.104`.
- Unknown explicit model IDs use conservative metadata instead of failing
  before the provider request.
- Cost resolution selects rates by provider batch mode, tier, speed, region,
  cache TTL, and long-context threshold.
- Anthropic fast mode is routed through the beta Messages resource.

## Deprecated

- Catalog v1 overrides remain supported through `0.4.x` and are scheduled for
  removal in `0.5.0`.
- `ExecutionEngine.batch_complete()` remains a compatibility alias for local
  concurrency; use `concurrent_complete()`.

## Fixed

- Unknown prices are no longer represented as zero.
- OpenAI prompt-cache controls and full reasoning objects are no longer dropped.
- Requested and actual service tiers are no longer conflated.
- Anthropic image/file blocks, cache controls, thinking, citations, native
  tools, usage metadata, and stop details are no longer discarded.
- Anthropic fast-mode eligibility, pricing, and Opus 4.8 cache minimum are
  aligned with the June 15, 2026 provider documentation snapshot.

## Security

- No security boundary changes.
- Existing redaction and credential-loading behavior remains unchanged.

## Compatibility

- Python `3.10` through `3.12` remain supported.
- OpenAI `>=2.36,<3` and Anthropic `>=0.104,<1` are required for their current
  provider surfaces.
- Existing flat catalog and usage projections remain available where their
  values are complete.

## Migration

See [llm-client-migration-to-0.4.0.md](llm-client-migration-to-0.4.0.md).

## Validation

Validated before release:

- `489 passed, 3 skipped, 6 warnings` for `tests/llm_client`.
- Offline and online provider-catalog validation passed for the
  `2026-06-15` reviewed snapshot.
- Deterministic release-candidate benchmarks passed all 8 semantic cases.
- Cookbook examples were validated in segmented live rings with credential-less
  skip support for optional Qdrant, PostgreSQL, realtime audio, and MCP
  continuation prerequisites.
- Wheel/sdist build, artifact verification, and clean-install smoke were run
  during final release packaging.

## Known Limitations

- Catalog data is a reviewed snapshot, not live provider billing data.
- Account-specific rate limits, entitlements, preview access, and negotiated
  prices cannot be inferred from public documentation.
- Gemini catalog and provider expansion remain intentionally out of scope and
  are planned for the `0.5.0` development cycle.
