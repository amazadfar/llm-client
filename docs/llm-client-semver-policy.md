# llm-client Semantic Versioning Policy

`llm-client` uses semantic versioning for the standalone package contract.

The project is currently in the `0.x` line. The public API map defines the
intended integration boundary, but it is not yet a `1.0.0` stability promise.
Minor `0.x` releases may still make documented API adjustments while the
runtime kernel scope settles.

## Version Meaning

- `MAJOR`: incompatible changes to the stable public API or stable behavior
- `MINOR`: backward-compatible feature additions and meaningful capability
  expansions
- `PATCH`: backward-compatible fixes, reliability improvements, documentation
  updates, and benchmark/test improvements

## Public API Scope

The intended public API scope is defined in:

- [llm-client-public-api-v1.md](llm-client-public-api-v1.md)

Breaking changes are evaluated against that public API map, not against
internal helper modules or compatibility surfaces.

For the `0.x` line, public surface should still be added deliberately and
sparingly. Compatibility layers may remain, but they should not expand in a way
that obscures the canonical module map. A future `1.0.0` release will mark the
point where the public API map becomes a long-term compatibility promise.

## Deprecation Policy

- Deprecations must be documented in release notes.
- Compatibility surfaces may emit `DeprecationWarning`.
- Removal of a deprecated stable API requires a major version bump.

## Experimental and Advanced Surfaces

Modules explicitly labeled `advanced`, `compat`, or internal are not held to
the same stability guarantees as the stable namespace set, but significant
behavioral changes should still be documented in release notes.
