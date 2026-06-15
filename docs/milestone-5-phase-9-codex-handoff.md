# Milestone 5 (Phase 9) — Codex Execution Handoff

**Audience:** the agent executing Phase 9 (OpenAI Current Platform Resource Completion).
**Authoritative sources you must follow:**
- Plan: `plans/2026-06-13-openai-anthropic-provider-completeness-implementation-plan.md` → **Phase 9**.
- Audit: `docs/openai-anthropic-completeness-audit-2026-06-13.md`.
- Locked decisions: `docs/phase-0-source-lock-and-decisions-2026-06-13.md` (esp. **D1–D6**, **D5 = OpenAI resource scope**).

**Branch:** `phase-4-typed-requests` (the whole 0.4.0 effort is stacked here — do **not** branch off or rename).
**Test runner:** `.venv/bin/python -m pytest tests/ -q` (project venv; system python has no pytest).
**Baseline before you start:** **470 passed, 3 skipped**. Do not regress this number.

---

## Part A — What is already done (Milestones 1–4 / Phases 0–8)

You are inheriting a stable foundation. **Do not re-derive, re-litigate, or contradict any of this.**

### Phase 0 — Source lock & decisions (`docs/phase-0-source-lock-and-decisions-2026-06-13.md`)
Baseline, SDK inventory (`openai>=2.36,<3`, `anthropic>=0.104,<1`), and ratified decisions **D1–D6**. The ones that bind your work:
- **D2 — Unknown cost = `None`, never `0.0`**, plus an additive `cost_status`/`cost_complete` diagnostic. *Never fabricate a missing price/limit as zero.*
- **D5 — OpenAI resource scope (your scope contract):**
  - **IN scope (SDK-confirmed GA in openai 2.36):** Models, Batches, **Containers (+ container files)**, **Skills**, current realtime/transcription/voice, **Video**.
  - **OUT of scope (do not implement):** organization administration, billing admin, RBAC, audit-log, project-management APIs.
- **D6 — Local concurrency ≠ provider batch.** `concurrent_complete()` is local async concurrency in standard tier (no discount). Provider Batch is a separate method, batch-priced. Don't blur them.

### Phase 1 — Correctness hotfixes
- Signature-aware forwarding: the engine only forwards a named param to a provider if that provider **declares** it. Reasoning-object preservation; unified temperature handling; unknown-model conservative fallback profile; lifecycle deprecation warnings.

### Phase 2–3 — Catalog v2 (`llm_client/model_catalog.py`, `llm_client/assets/model_catalog.json`, schema `…schema.v2.json`)
- Versioned catalog: structured `lifecycle`/`endpoints`/`modalities`/`reasoning`/`caching`/`service`/`tools` + **dimensional pricing** (`completeness` + nullable `rate`; **unknown ≠ zero**).
- Dual-read loader projects v2 → flat v1 fields for back-compat. **The shipped catalog is v2 and is generated** by `scripts/catalog/build_catalog_v2.py` (+ `catalog_enrichment.py`). **If you change catalog data, edit the generator and regenerate — never hand-edit `model_catalog.json`.** v1 override path is deprecated (D4, removed in 0.5.0).

### Phase 4 — Typed requests, service tiers, routing
- `llm_client/request_options.py`: `OpenAIRequestOptions` / `AnthropicRequestOptions` (typed, namespaced). Shared `RequestSpec` fields `service_tier`/`top_p`/`metadata`.
- `requested_service_tier` vs actual `service_tier` tracked separately on results.

### Phase 5 — Multidimensional pricing (`llm_client/pricing.py`)
- `resolve_cost(...)` selects a rate by mode/tier/region/long-context-threshold and reports `cost_status` ∈ {complete, partial, unknown}. **unknown is never 0.** Provider-batch discount applies **only** to `mode="provider_batch"`.

### Phase 6 — Provider Batch APIs (`llm_client/batch_api.py`, both providers)
- Shared `BatchJob`/`BatchRequestItem`/`BatchResultItem` + `normalize_batch_status`. OpenAI file-backed JSONL batch + Anthropic Message Batches; per-item `custom_id`/error preservation; `execution_mode="provider_batch"`.

### Phase 7 — Anthropic native content, cache, Models, Files (template for your Models/Containers/Skills work)
- Native image/document transport in `llm_client/content.py`; lossless `cache_control`; capability activation by model family.
- **`llm_client/resources.py` — shared typed results `ModelInfo` / `FileObject` / `ResourcePage`.** The Anthropic provider's `list_models`/`retrieve_model` and `upload_file`/`list_files`/`retrieve_file_metadata`/`download_file`/`delete_file` return these. **Reuse these exact types for the OpenAI Models resource** — do not invent a parallel `OpenAIModelInfo`.

### Phase 8 — Anthropic thinking / structured outputs / native tools / rich results
- `CompletionResult.stop_details` added; lossless rich-result parsing (signed/redacted thinking, citations, server-tool blocks, refusal).
- **`AnthropicServerTool`** descriptor lives in `llm_client/tools/base.py`, registered in `is_provider_native_tool`, kept **separate** from OpenAI's `Responses*` descriptors. The OpenAI side already has `ResponsesBuiltinTool` / `ResponsesMCPTool` / `ResponsesToolSearch` / `ResponsesCustomTool` etc. **Keep provider-native tool descriptors provider-separated.**

---

## Part B — What Phase 9 requires (your task)

### B.1 Current OpenAI provider surface (already implemented — do NOT rebuild)
`llm_client/providers/openai.py` already has: **Files** (create/retrieve/list/delete/content), **Uploads** (create/add_part/complete/cancel/chunked), **Vector Stores** (full lifecycle + files + batches + poll + search), **Fine-tuning** (create/retrieve/list/cancel/events), **Conversations** (+ items), **Moderation**, **Images** (generate/edit), **Audio** (transcribe/translate/speech), **Realtime** (calls, client secrets, transcription sessions, connect), **Background responses**, **Deep research**, **Webhooks**, **Batches** (Phase 6), and the Responses native tools (`respond_with_*`). Typed result classes live in `llm_client/providers/types.py`.

### B.2 Confirmed GAPS to fill (the actual work)
Implement each additively. Mirror the existing method/converter/typed-result pattern already in `openai.py`.

1. **Models resource** — `list_models(...)` + `retrieve_model(model_id)` via `self.client.models.list()/retrieve()`. **Return `ResourcePage`/`ModelInfo` from `llm_client/resources.py`** (same as Anthropic Phase 7; set `provider="openai"`). This is the clearest missing piece.
2. **Containers (+ container files)** — lifecycle (create/retrieve/list/delete) and container-file ops via `self.client.containers...` / `self.client.containers.files...`. New typed results in `types.py` (`ContainerResource`, `ContainerFileResource`, pages) following the `VectorStore*`/`FileResource` shape.
3. **Skills** — lifecycle methods via `self.client.skills...` (D5/Phase 0 confirmed **in scope**). Typed results in `types.py`.
4. **Video** — generation + operation methods via `self.client.videos...` (`create`, `create_and_poll`, `remix`, `extend`, character ops, retrieve/list/download as the SDK exposes). Treat preview/experimental pieces as explicitly experimental (Rollback/Containment note). Typed results in `types.py`.
5. **Reconcile** realtime/transcription/voice **and** existing files/vector-stores/fine-tuning/images/audio wrappers with **current 2.36 SDK signatures** (fix any signature drift; don't gratuitously rewrite working code).
6. **Model-aware native-tool validation** — validate OpenAI native tools by **model and endpoint** before the network call (e.g., a tool only valid on the Responses endpoint / certain models is rejected early with a clear error). Reuse existing capability data; don't hardcode sprawling matrices.
7. **Capability discovery** — distinguish **resource availability** (does the SDK/account expose this resource) from **completion-model support** (does a given model support a feature). Do not conflate them.

### B.3 Exit criteria (from the plan — you must hit all)
- Every D5-approved OpenAI resource has a **typed package wrapper** or an **explicit, documented exclusion**.
- Existing OpenAI resource wrappers **remain compatible** (regression suite stays green).
- Resource availability and model capability are **not conflated**.
- **Green-light cue:** "Approved OpenAI resource inventory passes contract and compatibility suites."

---

## Part C — Anti-drift invariants (READ TWICE — these are how you avoid drifting)

1. **Scope is D5. Nothing else.** No org-admin / billing / RBAC / audit-log / project-management. If you find another resource, add it to a "documented exclusions" note — do **not** implement it.
2. **Unknown ≠ zero (D2).** Never write `0.0`/`0` for an unknown price, limit, or token field. Use `None` + the existing `cost_status` machinery. If you don't have an authoritative source for a number, represent it as unknown — don't guess.
3. **Source-faithfulness.** Every SDK method name, signature, namespace, and field must come from the **actual installed `openai` 2.36 SDK / official OpenAI docs** — not from memory or analogy to another provider. This is *why this milestone went to you*: verify against real OpenAI sources. If a method/field isn't confirmed, stop and surface it rather than inventing it.
4. **Reuse, don't fork.** Models resource → reuse `llm_client/resources.py` (`ModelInfo`/`ResourcePage`). New resources → add typed results in `llm_client/providers/types.py` following the existing `VectorStoreResource`/`FilesPage`/`DeletionResult` patterns (with `to_dict`, `provider="openai"`, and a `raw` field preserving the SDK object). Do not invent a new results module.
5. **Provider-native tools stay provider-separated.** OpenAI native tools use the existing `Responses*` descriptors in `llm_client/tools/base.py`. **Do not** route them through `AnthropicServerTool`, and don't merge the two families.
6. **Preserve the envelope.** Every wrapper must preserve operation **status, errors, usage, and the raw response** (see how existing OpenAI wrappers keep `raw`/status). Don't drop provider data.
7. **Additive & independently disableable.** Ship each resource family additively. Don't refactor the completion/stream hot paths (`complete`, `_complete_responses`, `stream`, `_stream_responses`) for this work.
8. **Catalog edits go through the generator.** If model data changes, edit `scripts/catalog/build_catalog_v2.py` / `catalog_enrichment.py` and regenerate; never hand-edit `model_catalog.json`. The catalog is **v2** — don't reintroduce v1 shapes.
9. **Engine forwarding is signature-aware.** If you add request params a provider must receive, the provider method must **declare them as named params** (a bare `**kwargs` will not receive engine-forwarded controls). Match the Phase 4 pattern.
10. **Tests + scoped commits, no remote.** Add **mocked-SDK contract tests per resource** (lifecycle, pagination, polling, cancellation, error fixtures — see `tests/llm_client/test_provider_batch_api_phase6.py` and the Phase 7 `test_anthropic_native_content_phase7.py` for the mock style: construct the provider via `Provider.__new__(Provider)` and attach a `SimpleNamespace` `client`). Commit locally in **small scoped commits**; end each message with the `Co-Authored-By:` trailer. **Do not push, open a PR, or merge** to any remote. Run `graphify update .` after code changes.
11. **Don't touch Anthropic, pricing, batch, or catalog semantics** except where Phase 9 explicitly requires (e.g., reusing `resources.py`). Those are locked from Milestones 1–4.
12. **Keep `__init__.py` exports tidy.** New public types get added to both the import block and `__all__`, next to the existing `ModelInfo`/`FileObject`/`ResourcePage`/`BatchJob` exports.

---

## Part D — Pattern templates to copy

- **Models resource (reuse shared types):** copy the Anthropic Phase 7 implementation shape — `llm_client/providers/anthropic.py` → `list_models` / `retrieve_model` / `_model_info_from_anthropic`. Do the OpenAI equivalent with `self.client.models.*` and `provider="openai"`.
- **A new lifecycle resource with its own typed results:** copy the vector-store pattern in `openai.py` (`create_vector_store`, `_vector_store_resource_from_response`, `_vector_stores_page_from_response`) + the `VectorStoreResource`/`VectorStoresPage` dataclasses in `types.py`.
- **File-backed download/content:** copy `get_file_content` / `_read_file_content` in `openai.py`.
- **Mocked contract test harness:** copy `tests/llm_client/test_provider_batch_api_phase6.py` (OpenAI half) — `OpenAIProvider.__new__`, attach `SimpleNamespace` client with async stubs, assert lifecycle + error preservation.

---

## Part E — Verification & hand-back

Before declaring Phase 9 done:
1. `.venv/bin/python -m pytest tests/ -q` → must be **≥ 470 passed** (your new tests add to it), 0 failed.
2. `.venv/bin/python -c "import llm_client"` imports clean; new public types resolve.
3. If catalog touched: re-run the generator and confirm the catalog tests pass.
4. Produce a short completion report listing: each resource added (with the SDK calls used), each **documented exclusion**, new typed results, new test files + counts, and the scoped commit list (`git log --oneline main..HEAD`).

**When finished, hand back to the maintainer.** The Claude side (me) will then verify Phase 9 against this contract and the plan's exit criteria, and proceed to Milestone 6 (Phase 10: drift prevention/docs/RC) and Milestone 7 (Phase 11: release → 0.4.0). **Do not start Phase 10/11 — those are out of your handoff.**

### Most likely drift points to self-check
- Inventing SDK method names/fields not in installed `openai` 2.36 → **verify against real docs/SDK**.
- Writing `0` for an unknown value → use `None` (D2).
- Re-implementing Files/Vector Stores/Audio that already exist → only **reconcile signatures**.
- Creating a parallel results module instead of reusing `resources.py` / extending `types.py`.
- Implementing an out-of-scope resource (org/billing/RBAC/audit/project) → exclude + document.
- Pushing to a remote / opening a PR → **local commits only**.
