# llm-client 0.3.1 Release Notes

Last updated: 2026-05-25

`llm_client` `0.3.1` is a patch release for provider catalog correctness,
Anthropic pricing metadata, README positioning, and the one-time version-line
reset from the premature `1.x` tags to the pre-`1.0` `0.x` line.

## Fixed

- Refreshed Anthropic model IDs, aliases, token limits, knowledge cutoffs, and
  deprecated-model metadata in the model catalog.
- Added Anthropic prompt-cache, batch, data-residency, and fast-mode pricing
  metadata where the package cost model can represent it.
- Preserved Anthropic cache read and cache creation token accounting in usage
  parsing and lifecycle aggregation.
- Updated Anthropic example defaults to current Claude model aliases.

## Documentation

- Reworked the root README into a concise package positioning page.
- Updated the guide index and build/provider docs to align with the current
  README and Anthropic model naming.
- Renamed release notes from the premature `1.x` line to the corresponding
  `0.x` line:
  - `1.0.0` is now documented as `0.1.0`
  - `1.1.0` is now documented as `0.2.0`
  - `1.1.1` is now documented as `0.2.1`
  - `1.2.0` is now documented as `0.3.0`

## Versioning

- Package metadata is now `0.3.1`.
- The old `v1.1.0`, `v1.1.1`, and `v1.2.0` tags were replaced by
  `v0.2.0`, `v0.2.1`, and `v0.3.0` on the same release commits.
- The initial package release commit is documented as `0.1.0`; no previous
  remote `v1.0.0` tag existed to rename.

## Validation

Current package validation passed before the release metadata reset:

```bash
./.venv/bin/pytest -q tests/llm_client
```

Result: `354 passed, 3 skipped, 6 warnings`

```bash
.venv/bin/python -m compileall llm_client
```

Result: passed
