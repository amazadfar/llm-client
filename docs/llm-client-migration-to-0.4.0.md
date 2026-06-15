# Migrating to llm-client 0.4.0

`0.4.0` is a provider-completeness release for OpenAI and Anthropic.

## Dependency Floors

- OpenAI SDK: `openai>=2.36,<3`
- Anthropic SDK: `anthropic>=0.104,<1`
- Python: `3.10`, `3.11`, or `3.12`

## RequestSpec and Provider Options

Move stable cross-provider controls onto `RequestSpec`:

```python
from llm_client import AnthropicRequestOptions, RequestSpec

spec = RequestSpec(
    provider="anthropic",
    model="claude-opus-4-8",
    messages=[...],
    service_tier="auto",
    anthropic_options=AnthropicRequestOptions(
        thinking={"type": "adaptive"},
        effort="high",
        speed="fast",
    ),
)
```

Use `OpenAIRequestOptions` and `AnthropicRequestOptions` for provider-only
controls. `RequestSpec.extra` remains an unsafe forward-compatibility escape
hatch.

## Default Models

- OpenAI changed from `gpt-5` to `gpt-5.4-mini`.
- Anthropic changed from `claude-opus-4-7` to `claude-sonnet-4-6`.

Defaults target development and experimentation costs. Configure production
models explicitly.

## Unknown Models

Explicit provider model IDs no longer hard-fail solely because they are absent
from the static catalog. They use conservative unknown capability and pricing
metadata. Feature-gated requests may still be rejected until capability
metadata is available.

## Catalog Overrides

Catalog v2 is the canonical schema. v1 overrides remain readable through the
`0.4.x` line with a deprecation warning and are scheduled for removal in
`0.5.0`.

## Usage and Cost

Cost resolution is multidimensional. Unknown or incomplete prices now return
`None` with `cost_status="unknown"` or `"partial"` rather than a fabricated
`0.0`. Update code that assumes every request has a numeric total:

```python
cost = result.usage.total_cost
if cost is None:
    handle_unpriced_usage(result.usage.cost_status)
```

Requested and actual service tiers are separate fields. Use the actual tier for
cost reconciliation.

## Batch Semantics

Use `concurrent_complete()` for local concurrency. `batch_complete()` remains a
deprecated alias during the compatibility window.

Use OpenAI Batch or Anthropic Message Batches provider methods for asynchronous
provider jobs and batch pricing.

## Anthropic Changes

- Image and document blocks are transported natively where the model supports
  them.
- Cache controls are preserved and validated.
- Thinking, citations, refusal details, server-tool blocks, and rich usage are
  retained.
- Structured outputs use `output_config.format`.
- Fast mode uses the beta Messages API and is available only on catalog-eligible
  models.

## OpenAI Changes

- Responses request fields and reasoning objects are preserved.
- Service-tier request and actual response values are retained.
- Models, Containers, Skills, and Video have typed wrappers.
- Resource availability is distinct from completion-model capability.
- Native tools are validated by endpoint and model before network calls.
