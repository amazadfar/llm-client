# Phase 0 — Source Lock, Baseline, and Decision Freeze

- Date: 2026-06-13
- Plan: `plans/2026-06-13-openai-anthropic-provider-completeness-implementation-plan.md`
- Audit (detailed evidence): `docs/openai-anthropic-completeness-audit-2026-06-13.md`
- Package baseline version: `0.3.2` → target `0.4.0`
- Verification date (fetched/confirmed): **2026-06-13**
- Status: **Awaiting maintainer green-light** ("Phase 0 source lock and architecture decisions approved.")

This record freezes the provider facts, SDK signatures, package baseline, and architecture
decisions required before any runtime implementation begins. It contains documentation and
decision records only; no runtime behavior changes were made in Phase 0.

---

## 1. Package Baseline (pre-change)

Captured on 2026-06-13 against the repository `.venv` (Python 3.12.13).

| Gate | Command | Result |
|---|---|---|
| Unit tests | `.venv/bin/python -m pytest -q tests/llm_client` | **353 passed, 3 skipped, 6 warnings** |
| Artifact verify | `scripts/ci/verify_llm_client_artifacts.py` | Soft pass: `no wheel artifact found in dist/` (exit 0 — no build yet) |
| Examples | `run_llm_client_examples.py --subset all` | Examples 01–11 pass; **12_benchmarks fails** (classified below) |

### Baseline failure classification

- **`12_benchmarks.py`** — `FileNotFoundError` for
  `contracts/benchmarks/llm_client_deterministic_baseline.v1.json`.
  - **Pre-existing / non-blocking / environmental.** The path is gitignored
    (`.gitignore:165`) and absent because benchmark baselines were pruned when the
    public repo artifact was created (`cb10610 Prune internal artifacts from public repo`).
  - Not a regression introduced by this plan. Relevant only at the release-candidate /
    benchmark gates (Phases 10–11), where the maintainer supplies or regenerates the
    baseline. **Not blocking for Phases 1–9.**

- The 6 warnings are pre-existing `llm_client/container.py` compatibility
  `DeprecationWarning`s (compat surface), unrelated to this work.

**Baseline verdict:** green for all gates that this plan touches; the single example failure
is a documented pre-existing environmental gap.

---

## 2. SDK Signature Inventory (installed, validated)

Probed directly against installed SDKs on 2026-06-13.

- OpenAI `2.36.0`
- Anthropic `0.104.1`
- Python `3.12.13`

### 2.1 Anthropic `0.104.1`

| Surface | Status | Notes |
|---|---|---|
| `messages.create` | GA | params include `thinking`, `output_config`, `service_tier`, `container`, `tools`, `tool_choice`, `metadata`, `top_k`, `top_p`, `temperature`, `system` |
| `messages.batches` | **GA** | `create, retrieve, list, cancel, delete, results` |
| `messages.count_tokens` | GA | |
| `models` | **GA** | `list, retrieve` |
| `beta.messages.create` | beta | adds `speed`, `mcp_servers`, `betas` (also `output_config`, `container`) |
| `beta.files` | **beta only** | `upload, list, retrieve_metadata, download, delete` — no stable `client.files` |

**Scoping consequences (drives Phases 7–8):**
- **Fast mode (`speed`)**, **`mcp_servers`**, and **Files** are **beta-only**. The package
  must route these through `client.beta.messages` / `client.beta.files`.
- `output_config`/effort, `thinking`, `service_tier`, and `container` are available on the
  **stable** `messages.create` — no beta gating required for those.

### 2.2 OpenAI `2.36.0`

| Surface | Status | Notes |
|---|---|---|
| `responses.create` | GA | params include `include`, `prompt_cache_key`, `prompt_cache_retention`, `reasoning`, `service_tier`, `store`, `safety_identifier`, `background`, `conversation`, `text`, `tools`, `truncation`, `max_output_tokens` |
| `chat.completions.create` | GA | params include `service_tier`, `prompt_cache_key`, `prompt_cache_retention`, `reasoning_effort`, `verbosity`, `web_search_options`, `safety_identifier`, `store`, `metadata` |
| `batches` | GA | `create, retrieve, list, cancel`; create params: `completion_window, endpoint, input_file_id, metadata, output_expires_after` |
| `models` | GA | `list, retrieve, delete` |
| `files` | GA | `create, retrieve, list, delete, content, wait_for_processing` |
| `containers` (+ `containers.files`) | GA | container + container-file lifecycle present |
| `vector_stores` | GA | `create, retrieve, list, update, delete, search` |
| `fine_tuning` | GA | `jobs, checkpoints, alpha` |
| `images` | GA | `generate, edit, create_variation` |
| `audio` | GA | `speech, transcriptions, translations` |
| `realtime` | GA | `connect` |
| `embeddings` | GA | `create` |
| `videos` | GA | full lifecycle (`create, create_and_poll, remix, extend, character ops, …`) |
| `skills` | **GA** | present on the client (resolves Phase 0 open question — Skills IS in scope) |
| `uploads`, `moderations` | GA | |

**Key consequence:** every audited OpenAI request field (`include`, `prompt_cache_key`,
`prompt_cache_retention`, `reasoning`, `service_tier`) is supported at the SDK level. The
field-dropping the audit flagged is a **package-side gap only** (Phase 1 fix), not an SDK
limitation. All Phase 9 resource targets (Models, Containers+files, Skills, realtime/voice,
video) are confirmed available in `2.36.0`.

---

## 3. Locked Provider Facts (model / lifecycle / pricing snapshot)

Effective and verified **2026-06-13**. Detailed evidence and per-finding citations live in
`docs/openai-anthropic-completeness-audit-2026-06-13.md`. Authoritative sources: the
environment `claude-api` reference for Anthropic facts; Context7 + official OpenAI docs for
OpenAI. **Unknown values are recorded as unknown and must never be encoded as zero.**

### 3.1 Anthropic (locked)

- **GA flagship families:** `claude-fable-5` (GA flagship; base **$10 / $50** per MTok
  input/output), `claude-opus-4-8`, `claude-sonnet-4-6`, `claude-haiku-4-5`.
- **Additional:** `claude-mythos-5`; `claude-mythos-preview` — **invitation-only, retiring
  2026-06-30**.
- **Fast mode (`speed:"fast"`):** **Opus 4.6 ONLY.** Not 4.7, not 4.8. SDK surface is
  **beta-only** (§2.1). The current catalog falsely flags `fast_mode=True` on
  `claude-opus-4-7`, and `tests/llm_client/test_model_catalog.py:84` locks that false price
  ($150/1M) in — both corrected in Phases 1/3.
- **Prompt-cache minimum cacheable tokens:** Opus 4.x / Haiku 4.5 = **4,096**;
  Fable 5 / Sonnet 4.6 = **2,048**.
- **Cache TTL:** 5-minute default, 1-hour extended.
- **Service tiers:** `standard`, `priority`; provider batch via Message Batches API at a
  **50% discount** (distinct from local concurrency — see Decision D6).
- **Thinking:** adaptive; `output_config.effort`.
- **Claude 3 Haiku retirement:** **2026-04-19**.

### 3.2 OpenAI (locked + unknowns)

- **Verified:** GPT-5.5 standard pricing (Context7). `gpt-5.4` family present
  (`gpt-5.4`, `-mini`, `-nano`, `-pro`) with dated snapshots.
- **Responses API:** `include`, `prompt_cache_key`, `prompt_cache_retention` (24h retention),
  reasoning-effort objects, `service_tier` ∈ {standard, flex, priority, scale}.
- **Pricing dimensions:** long-context (> 272K tokens) = **2× input / 1.5× output**;
  **10% regional uplift**.
- **Zero-priced catalog entries:** 22 total, **including `gpt-oss-120b` and `gpt-oss-20b`
  completions** (a text request currently accounts to $0) — these are *unknown*, not free,
  and are corrected in Phase 3/5.
- **UNKNOWN (stay unknown; resolve before encoding):**
  - Exact **GPT-5.5-Pro** standard/batch/flex/priority rates.
  - OpenAI **priority** and **flex** pricing multipliers.
  - These are explicitly carried as unknown into the catalog (Decision D2 representation).

---

## 4. Architecture Decisions (maintainer-ratified 2026-06-13)

| ID | Decision | Detail |
|---|---|---|
| **D1** | **Default-model policy = cost-balanced pinned stable aliases** | Defaults are package-pinned **stable aliases** (not snapshots, not provider-"latest"), deliberately chosen at a **cost-balanced** tier because defaults are used predominantly for dev/experimentation/testing. Frontier models (gpt-5.5, Opus 4.8) are **not** defaults due to high cost. **Docs must state: defaults are dev/experimentation-tier; production deployments should configure models explicitly.** |
| **D2** | **Unknown cost = `None` + additive `cost_status`** | Unknown/incomplete cost is `None` (**never `0.0`**), accompanied by an additive `cost_status`/`cost_complete` diagnostic. Legacy flat cost accessors remain as compatibility projections for fully-known token-only cases. The `None`-vs-float behavior change is disclosed prominently in the 0.4.0 changelog. Accuracy/production-readiness prioritized. |
| **D3** | **SDK floors raised to validated installed** | `openai>=2.36,<3`, `anthropic>=0.104,<1`. Rationale: leverage current SDK features; keeping floors artificially low is unjustified for fast-moving provider SDKs. Disclosed in the 0.4.0 changelog. |
| **D4** | **Catalog v1 override compat window = one minor** | Dual-read v1 overrides through 0.4.x with a deprecation warning; **remove in 0.5.0** (aligns with the queued Gemini 0.5.0 boundary). |
| **D5** | **OpenAI resource scope confirmed** | In scope (SDK-confirmed GA): Models, Batches, Containers (+files), Skills, current realtime/transcription/voice, Video. **Out of scope:** organization administration, billing admin, RBAC, audit-log, project-management APIs. |
| **D6** | **Local concurrency ≠ provider batch** (carried from plan) | `concurrent_complete()` names local async concurrency, fired in **standard tier** with no batch discount. OpenAI Batch / Anthropic Message Batches are separate provider methods; batch discounts apply **only** to real provider-batch results. `batch_complete()` retained as a deprecated alias for one window. |

### 4.1 Concrete default-model values (Decision D1)

Current catalog `defaults` block (`llm_client/assets/model_catalog.json:3–14`):

```json
"defaults": {
  "openai":    { "completions": "gpt-5",            "embeddings": "text-embedding-3-small" },
  "google":    { "completions": "gemini-2.0-flash" },
  "anthropic": { "completions": "claude-opus-4-7" }
}
```

Phase 3 changes (each is a default change → requires migration note + release note + test):

| Provider | Field | From | To | Status |
|---|---|---|---|---|
| openai | `completions` | `gpt-5` | **`gpt-5.4-mini`** | confirmed present (key@2392, snapshot `gpt-5.4-mini-2026-03-17`) |
| anthropic | `completions` | `claude-opus-4-7` | **`claude-sonnet-4-6`** | confirmed present (key@952) |
| openai | `embeddings` | `text-embedding-3-small` | *(unchanged — already cost-balanced)* | — |
| google | `completions` | `gemini-2.0-flash` | *(unchanged now)* | Already a Flash/cost-balanced default. **Policy recorded for the 0.5.0 Gemini plan: upgrade to `gemini-3-flash`.** Not changed in 0.4.0 (Gemini is a non-goal here). |

---

## 5. Phase 0 Exit Criteria — status

- [x] Every time-sensitive fact needed by Phases 1–10 has an official source and a
      verification date (2026-06-13), **or** is explicitly recorded as unknown
      (GPT-5.5-Pro rates; OpenAI priority/flex multipliers).
- [x] All critical unknowns resolved or explicitly scoped: default-model policy (D1),
      unknown-cost representation (D2), SDK floors (D3), v1 compat window (D4),
      OpenAI resource scope (D5). Skills confirmed in scope via SDK probe.
- [x] Baseline failures classified (benchmarks example = pre-existing/environmental).
- [ ] **Maintainer approves the architecture decisions** ← green-light gate.

### Remaining unknowns carried forward (by design, not blocking)

These do not block Phase 1 (correctness hotfixes) and are resolved before the values are
encoded in Phase 3/5:

1. Exact GPT-5.5-Pro pricing (all tiers).
2. OpenAI priority/flex multipliers.

Both are represented via Decision D2 (`None` + `cost_status`) until officially sourced.

---

## 6. Rollback / Containment

Documentation and decision records only. No runtime behavior changed in Phase 0. This file
and the audit doc are the entire Phase 0 footprint.
