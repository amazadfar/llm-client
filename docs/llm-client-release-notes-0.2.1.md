# llm-client 0.2.1 Release Notes

Last updated: 2026-04-02

`llm_client` `0.2.1` is a patch release focused on packaging and metadata
cleanup after the `0.2.0` OpenAI/provider expansion release.

## Fixed

- Corrected the canonical repository and documentation URLs in
  [pyproject.toml](../pyproject.toml)
  so package metadata now points at the actual `llm-client` repository rather
  than the older `intelligence-layer-bif` location.

## Changed

- `asyncpg` and `redis` are no longer installed as base dependencies.
- PostgreSQL-backed cache and persistence paths now lazy-load their optional
  runtime dependencies instead of requiring them during base-package import.
- The `pg_redis` backend now behaves more explicitly:
  - `llm-client[postgres]` is required for PostgreSQL-backed durable storage
  - `llm-client[redis]` is optional and enables the Redis hot-cache layer
  - without the Redis extra, the backend can still operate in durable
    PostgreSQL-only mode

## Documentation

- Updated installation guidance in
  [docs/llm-client-installation-matrix.md](llm-client-installation-matrix.md).
- Updated package installation guidance for the optional cache dependencies.
- Updated cache backend notes in
  [README.md](../README.md)
  and
  [docs/llm-client-build-and-recipes-guide.md](llm-client-build-and-recipes-guide.md).

## Validation

Focused validation passed for the optional-dependency refactor:

```bash
./.venv/bin/pytest -q \
  tests/llm_client/test_optional_cache_dependencies.py \
  tests/llm_client/test_public_api_namespaces.py \
  tests/llm_client/test_request_builders.py \
  tests/llm_client/test_provider_registry.py
```

Result: `28 passed`
