# llm-client 0.1.0 Release Notes

Release date: 2026-03-26

`llm_client` `0.1.0` is the first public package release of the project as a
standalone, typed, reusable LLM and agentic runtime framework.

This release establishes the initial public package map defined in:

- [llm-client-public-api-v1.md](llm-client-public-api-v1.md)

## What 0.1.0 Means

`0.1.0` means:

- the standalone namespace map is usable and documented
- new integrations should be built against the stable module namespaces
- compatibility layers remain available for migration, but they are not the
  preferred package surface
- future `0.x` releases may still evolve the API before the real `1.0.0`
  stability promise

## Stable Namespace Contract

The initial public surface is:

- `llm_client.providers`
- `llm_client.models`
- `llm_client.types`
- `llm_client.content`
- `llm_client.context`
- `llm_client.budgets`
- `llm_client.context_assembly`
- `llm_client.engine`
- `llm_client.agent`
- `llm_client.benchmarks`
- `llm_client.tools`
- `llm_client.adapters`
- `llm_client.cache`
- `llm_client.memory`
- `llm_client.observability`
- `llm_client.validation`
- `llm_client.errors`
- `llm_client.config`

Compatibility-only or advanced surfaces remain available, but they are outside
the preferred package surface.

## What Shipped In The Initial Package Program

- provider, engine, agent, tool, cache, context, observability, and structured
  output layers were tightened into a standalone package boundary
- engine-first execution became the canonical higher-level runtime path
- generic runtime substrate extracted from higher layers now lives in the
  package:
  - context
  - budget and ledger primitives
  - runtime events
  - replay
  - structured runtime helpers
  - generic context-planning and assembly primitives
- `FileBlock` became a real transport feature
- stable service adaptors were added under `llm_client.adapters`:
  - SQL
  - Redis
  - vector/Qdrant
- standalone package guides, examples guide, and cookbook alignment work were
  completed
- OSS/package hygiene and packaging verification were completed

## Validation Completed For 0.1.0

- focused package suites passed
- guide, packaging, and public API inventory suites passed
- cookbook contract validation passed
- deterministic benchmark artifacts were generated and compared
- live provider smoke tests passed for OpenAI and Anthropic
- wheel and sdist verification passed
- `twine check` passed for the final `0.1.0` distributions

## Final Adjustments Between RC1 And GA

- Anthropic defaults were aligned to current Claude 4 naming while preserving
  legacy `claude-4-5-*` compatibility keys
- the GPT-5 Mini live smoke path was corrected to avoid false failures caused
  by a too-small completion budget
- a practical build guide was added:
  [llm-client-build-and-recipes-guide.md](llm-client-build-and-recipes-guide.md)
- the public API map was promoted into the documented package boundary
- support and semver docs were updated to describe the package boundary
  explicitly

## Documentation Starting Points

If you are adopting the package in another project, start with:

1. [llm-client-package-api-guide.md](llm-client-package-api-guide.md)
2. [llm-client-build-and-recipes-guide.md](llm-client-build-and-recipes-guide.md)
3. [llm-client-usage-and-capabilities-guide.md](llm-client-usage-and-capabilities-guide.md)
4. [llm-client-examples-guide.md](llm-client-examples-guide.md)
5. [examples/README.md](../examples/README.md)

## Compatibility Note

The package still contains compatibility layers for migration, including
`llm_client.compat` and some top-level convenience aliases. Those remain valid
for migration, but new code should target the stable module namespaces above.
