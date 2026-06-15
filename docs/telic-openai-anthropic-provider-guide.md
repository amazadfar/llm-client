# OpenAI and Anthropic Provider Guide

This guide describes the provider behavior shipped in `telic 0.4.0`.
Provider documentation changes faster than package releases, so treat the
checked-in catalog as a reviewed snapshot rather than a live billing oracle.

## Catalog and Model Discovery

Use `get_default_model_catalog()` for package metadata and provider `list_models()`
for the models visible to the configured account:

```python
from telic.model_catalog import get_default_model_catalog

catalog = get_default_model_catalog()
metadata = catalog.get("gpt-5.5")
print(metadata.endpoints, metadata.reasoning_efforts, metadata.cost_status)
```

The catalog records canonical keys, provider wire IDs, aliases, snapshots,
lifecycle, endpoints, modalities, reasoning controls, caching, service modes,
tools, limits, and multidimensional pricing. Explicit unknown provider model IDs
remain callable through a conservative profile; their capabilities and prices are
unknown until supplied by a catalog override or a package update.

Package defaults are cost-balanced development defaults:

- OpenAI completions: `gpt-5.4-mini`
- Anthropic completions: `claude-sonnet-4-6`
- OpenAI embeddings: `text-embedding-3-small`

Production deployments should configure model IDs explicitly.

## Lifecycle

`metadata.lifecycle.status` is one of `active`, `preview`, `deprecated`, or
`retired`. Deprecated selections emit warnings with their replacement when one
is known. Retired models are not suitable for new requests.

The offline catalog validator checks date ordering and rejects records whose
retirement date has passed without a `retired` status:

```bash
.venv/bin/python scripts/catalog/validate_provider_catalog.py
```

## Endpoints and Native Tools

OpenAI model capability and OpenAI platform-resource availability are separate:

- model capabilities describe completion endpoints and tools;
- resource availability describes SDK/account surfaces such as Models,
  Containers, Skills, Video, Files, Vector Stores, and Realtime.

Responses-native tools are validated against the selected endpoint and model
catalog before a request. Anthropic server tools use `AnthropicServerTool` and
remain separate from OpenAI `Responses*` descriptors.

## Reasoning and Thinking

OpenAI accepts a full reasoning object on Responses requests. GPT-5.5 supports
`none`, `low`, `medium`, `high`, and `xhigh`; its default is `medium`.

Anthropic maps `reasoning_effort` or `AnthropicRequestOptions.effort` to
`output_config.effort`. Current effort-capable models expose their accepted
levels through the catalog. Opus 4.8 and Opus 4.7 require adaptive thinking when
thinking is enabled; manual token-budget thinking is not supported on those
models.

## Prompt Caching

OpenAI:

- eligible prompts are cached automatically;
- `prompt_cache_key` improves routing for repeated prefixes;
- `prompt_cache_retention="24h"` requests extended retention where supported;
- cached tokens are preserved in normalized usage.

Anthropic:

- cache breakpoints are preserved on supported content blocks;
- 5-minute and 1-hour TTLs are represented;
- cache reads and writes remain distinct usage dimensions;
- Opus 4.8 has a 1,024-token minimum cacheable prefix in the June 15, 2026
  provider snapshot.

## Service Tiers, Speed, and Batch

OpenAI synchronous `service_tier` values are provider request modes such as
`auto`, `default`, `flex`, and `priority`. The normalized result keeps both the
requested and actual tier. Provider Batch is a separate API and is never encoded
as `service_tier="batch"`.

Anthropic request values are `auto` and `standard_only`. `auto` can consume
Priority Tier capacity when the account and model are eligible; the actual
assignment is returned in usage. Message Batches are separate from synchronous
service tiers.

Anthropic fast mode is a beta Messages surface. `speed="fast"` routes through
`client.beta.messages`, adds the required beta identifier, and is catalog-gated.
The June 15 snapshot supports Opus 4.8, 4.7, and 4.6; 4.6 fast mode is deprecated.
Fast mode and provider Batch cannot be combined.

## Local Concurrency Versus Provider Batch

`ExecutionEngine.concurrent_complete()` executes ordinary synchronous requests
with bounded local concurrency. It receives standard synchronous pricing.

`batch_complete()` is a deprecated compatibility alias for local concurrency.
It is not OpenAI Batch or Anthropic Message Batches.

Use provider batch methods for discounted asynchronous provider jobs. Their
results carry `execution_mode="provider_batch"` so cost resolution can select
batch dimensions.

## Pricing and Uncertainty

`resolve_cost()` selects dimensions by execution mode, actual tier, speed,
region, cache TTL, and token threshold. Unknown rates are `None`, never zero.
The result reports `complete`, `partial`, or `unknown` through `cost_status`.

Prices can vary by contract, region, platform, and provider changes. The source
manifest records review dates and URLs in
`telic/assets/provider_source_manifest.json`. Applications making billing
decisions should reconcile package estimates with provider invoices.

## Source Refresh

Offline validation is the default CI gate:

```bash
.venv/bin/python scripts/catalog/build_catalog_v2.py
.venv/bin/python scripts/catalog/validate_provider_catalog.py
```

Maintainers can opt into source reachability checks:

```bash
.venv/bin/python scripts/catalog/validate_provider_catalog.py \
  --online --strict-staleness
```

Online checks do not update review dates automatically. A maintainer must review
provider changes, update the enrichment layer and source manifest, regenerate
the asset, and run the full test suite.
