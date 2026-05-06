# Implementation Plan: Retrieval Backend Evolution — BM25 → Dense Embeddings (+ Hybrid Fusion)

**Branch**: `feat/585-retrieval-dense` | **Date**: 2026-04-17 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/026-retrieval-dense-embeddings/spec.md`

## Summary

Introduce a pluggable retrieval layer behind a minimal `Retriever` protocol that mirrors the current `BM25Index` surface, so `ToolRegistry` and `kosmos.tools.search.search()` remain byte-identical to callers. Three interchangeable backends — `bm25` (default, wraps today's implementation verbatim), `dense` (CPU-only multilingual sentence encoder + in-memory numpy cosine index), and `hybrid` (Reciprocal Rank Fusion over BM25 + Dense at k=60) — are selected at registry construction via `KOSMOS_RETRIEVAL_BACKEND`. Dense/hybrid initialisation failures degrade fail-open to pure BM25 with a single structured WARN log; auth/invocation gates stay fail-closed. Model weights are resolved from the Hugging Face hub cache at first boot (never committed, never CI-downloaded); a weight SHA-256 + tokenizer version + embedding dim enter the release manifest via Epic #467 extension fields. Success criteria are re-anchored to an adversarial-paraphrase subset authored in this PR and to the Epic #22 extended corpus (`PENDING_#22` when absent), since the committed 30-query set is saturated at recall@5 = 1.0.

## Technical Context

**Language/Version**: Python 3.12+ (existing project baseline; no version bump)
**Primary Dependencies**:
- Existing (unchanged): `rank_bm25 >= 0.2.2`, `kiwipiepy >= 0.17`, `pydantic >= 2.13`, `httpx >= 0.27`, stdlib `logging`, `pytest`, `pytest-asyncio`
- **Proposed new (spec-driven)**:
  - `sentence-transformers >= 3.0` (Apache-2.0) — high-level encoder API over HF `transformers`; bundles `torch` CPU wheel transitively. Rationale: one dep instead of three; native `.encode()` with prefix handling for E5-family.
  - `numpy >= 1.26` — already a transitive of rank_bm25/sentence-transformers; named here for the in-memory cosine index.
  - No FAISS, no hnswlib (deferred until registry_size outgrows numpy; see research.md §4).
**Storage**: N/A — in-memory vector matrix + in-memory BM25 doc vectors; HF hub cache at `~/.cache/huggingface/hub/` for weights (user-scoped, not repo-committed).
**Testing**: `pytest` + `pytest-asyncio` (existing). New surfaces: `tests/retrieval/test_retriever_protocol.py`, `tests/retrieval/test_bm25_backend.py`, `tests/retrieval/test_dense_backend.py` (mocked encoder), `tests/retrieval/test_hybrid_rrf.py`, `tests/retrieval/test_fail_open.py`, `tests/retrieval/test_schema_snapshot.py`, `tests/retrieval/test_latency.py` (100-adapter synthetic). Live model load tests gated behind `@pytest.mark.live_embedder` and skipped in CI.
**Target Platform**: CPU-only. Primary: Apple M-series 8-core macOS. Fallback: Linux x86_64 8-core. No CUDA, no GPU, no MPS dependency (CPU wheel of torch only).
**Project Type**: Single Python project (existing layout under `src/kosmos/`).
**Performance Goals**:
- `backend=bm25` (default): p99 per-query latency within ±10 % of pre-#585 baseline on padded 100-adapter registry.
- `backend=hybrid`: p99 per-query latency < 50 ms on padded 100-adapter registry (reference CPU).
- Cold-start on default path: no regression.
- Cold-start on `backend=dense|hybrid` + `cold_start=eager`: ≤ 10 s model-load + initial-corpus-embed budget (ADR-worthy, disabled by default).
**Constraints**:
- NFR-MemoryBudget: < 2 GB resident for smallest candidate model, < 4 GB for largest, at registry_size = 100.
- NFR-NoNetAtRuntime: CI MUST NOT download weights; runtime post-warm-up MUST NOT egress.
- Deterministic output modulo FP noise ≤ 1e-6 for identical (weight hash, tokenizer version, corpus, query).
- Byte-identical `LookupSearchInput` / `LookupSearchResult` / `AdapterCandidate` JSON schemas (SC-004).
**Scale/Scope**:
- Today: registry_size = 4 (KOROAD, KMA, HIRA, NMC); eval set 30 queries.
- Target post-#22: registry_size ≥ 8, eval set ≥ 50.
- SC-003 synthetic envelope: registry_size = 100 (padded by cloning seed adapters with suffixed ids).
- Adversarial subset authored here: ≥ 20 queries, zero lexical overlap with `search_hint` tokens.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Reference: `.specify/memory/constitution.md` v1.1.0 (ratified 2026-04-12, amended 2026-04-13).

| Principle | Status | Evidence / Rationale |
|---|---|---|
| **I. Reference-Driven Development** | ✅ PASS | Every design decision carries a concrete citation: BM25 (rank_bm25 project, kiwipiepy tokenizer — existing), dense encoder family (MIRACL-ko benchmark, HF model cards), RRF fusion (Cormack/Clarke/Buettcher SIGIR 2009), RSF (Weaviate v1.24 release notes), Pydantic AI pattern for schema-driven tool registry (`docs/vision.md § Reference materials` row 3). `/speckit-plan` Phase 0 research.md §1–§6 carries the mapping. |
| **II. Fail-Closed Security (NON-NEGOTIABLE)** | ✅ PASS | FR-002 mandates fail-**open** on the *retrieval* path (a correctness degradation, never an auth/invocation bypass). All `requires_auth`/`is_personal_data`/`is_concurrency_safe`/`cache_ttl_seconds` defaults on `GovAPITool` are untouched by this spec (FR-003, out-of-scope §). The permission gauntlet, PIPA gates, and tool-invocation auth checks remain fail-closed by construction — this spec never enters that code path. |
| **III. Pydantic v2 Strict Typing (NON-NEGOTIABLE)** | ✅ PASS | `LookupSearchInput`, `LookupSearchResult`, `AdapterCandidate`, `GovAPITool` schemas are frozen (FR-003). New entities introduced by this spec — `RetrievalManifest`, `AdversarialQuerySet` — are Pydantic v2 models with explicit field types; zero `Any`. The `Retriever` protocol is a `typing.Protocol` with fully typed methods (`rebuild(corpus: dict[str, str]) -> None`, `score(query: str) -> list[tuple[str, float]]`). |
| **IV. Government API Compliance** | ✅ PASS — N/A to retrieval layer | This spec does not touch any adapter body, `rate_limit_per_minute`, `usage_tracker`, or `data.go.kr` call path (out-of-scope § explicit). No new CI tests against live APIs. Model-weight download is HF hub, not `data.go.kr`, and is gated by NFR-NoNetAtRuntime. |
| **V. Policy Alignment** | ✅ PASS | Paraphrase-robust retrieval directly serves Principle 8 (single conversational window: users should not have to mimic an adapter's `search_hint` vocabulary) and Principle 9 (Open API discoverability). No PII leaves the process; retrieval operates on adapter metadata (`search_hint`), not citizen queries persisted anywhere. |
| **VI. Deferred Work Accountability** | ⚠ NEEDS TRACKING RESOLUTION | Spec §"Deferred to Future Work" contains **three** `NEEDS TRACKING` markers: (1) cross-encoder re-ranking, (2) flipping default backend to `hybrid`, (3) aggressive rollout reconsideration. Phase 0 will validate that no free-text deferral appears outside the table; `/speckit-taskstoissues` will back-fill placeholder Task issues for each `NEEDS TRACKING` marker. All tracked deferrals cite live issues (#501, #467, #468, Phase 4 umbrella). |

**Gate decision**: PASS with the single caveat that Principle VI `NEEDS TRACKING` markers are legitimate per-spec placeholders; `/speckit-taskstoissues` will resolve them. No constitution violations requiring the Complexity Tracking table.

## Project Structure

### Documentation (this feature)

```text
specs/026-retrieval-dense-embeddings/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── retriever_protocol.md
│   ├── lookup_search_input.schema.json
│   ├── lookup_search_result.schema.json
│   └── adapter_candidate.schema.json
├── checklists/
│   └── requirements.md  # Already authored by /speckit-specify
├── spec.md              # Feature specification (/speckit-specify output)
└── tasks.md             # Phase 2 output (/speckit-tasks command — NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/kosmos/
├── tools/
│   ├── retrieval/                      # NEW subpackage (mirrors composite/, geocoding/ conventions)
│   │   ├── __init__.py
│   │   ├── backend.py                  # Retriever Protocol + backend factory (env-driven)
│   │   ├── bm25_backend.py             # Wraps existing BM25Index byte-identically
│   │   ├── dense_backend.py            # Sentence-transformer encoder + numpy cosine index
│   │   ├── hybrid.py                   # RRF (k=60) fusion over BM25 + Dense
│   │   ├── manifest.py                 # RetrievalManifest Pydantic v2 model
│   │   └── degrade.py                  # Fail-open WARN log helper (single emission per instance)
│   ├── bm25_index.py                   # UNCHANGED interface — may internally delegate to retrieval.bm25_backend
│   ├── registry.py                     # DI change only: BM25Index → Retriever; external API unchanged
│   ├── search.py                       # UNCHANGED signature; swaps bm25_index.score for retriever.score
│   ├── lookup.py                       # FROZEN — not touched
│   └── models.py                       # FROZEN — LookupSearchInput/Result/AdapterCandidate schemas locked
└── eval/
    └── retrieval.py                    # Extended to accept backend param + second eval file

tests/
├── retrieval/                          # NEW test suite
│   ├── __init__.py
│   ├── __snapshots__/
│   │   ├── lookup_search_input.schema.json
│   │   ├── lookup_search_result.schema.json
│   │   └── adapter_candidate.schema.json
│   ├── test_retriever_protocol.py      # Protocol conformance across all three backends
│   ├── test_bm25_backend.py            # Verifies byte-identical behaviour vs pre-#585
│   ├── test_dense_backend.py           # Mocked encoder; score determinism
│   ├── test_hybrid_rrf.py              # RRF math + tie-break invariant
│   ├── test_fail_open.py               # FR-002 degradation path
│   ├── test_schema_snapshot.py         # SC-004 byte-level contract gate
│   └── test_latency.py                 # SC-003 p99 envelope on padded 100-adapter registry
└── eval/
    └── test_retrieval_gate.py          # UNCHANGED semantics; runs under backend=bm25 for SC-004

eval/
├── retrieval_queries.yaml              # UNCHANGED committed 30-query set (baseline evidence)
└── retrieval_queries_adversarial.yaml  # NEW — ≥ 20 queries with zero lexical overlap (FR-012)

docs/
└── design/
    └── retrieval.md                    # NEW — design doc summarising Phase 0 research + decisions

pyproject.toml                          # Dependency addition: sentence-transformers (spec-driven)
```

**Structure Decision**: Single-project layout (Option 1). The retrieval subsystem is a new subpackage under `src/kosmos/tools/retrieval/`, mirroring the existing flat convention used by `composite/` and `geocoding/` packages. `lookup.py` and `models.py` are the byte-level contract surface and remain untouched. `registry.py` and `search.py` change by dependency injection only (swap a concrete `BM25Index` for a `Retriever` Protocol instance); their external signatures are unchanged. `tests/retrieval/` is the new test home for protocol conformance, fail-open behaviour, schema snapshots, and the latency envelope. `eval/retrieval_queries_adversarial.yaml` is authored in this PR to gate SC-002 independently of Epic #22.

## Post-Design Constitution Re-check

*Performed after Phase 1 artifacts (data-model.md, contracts/, quickstart.md) were authored.*

| Principle | Post-design Status | Delta vs pre-design gate |
|---|---|---|
| I. Reference-Driven Development | ✅ PASS | `contracts/retriever_protocol.md` cites Cormack SIGIR 2009 for RRF and the `feedback_no_hardcoding.md` memory rule at the Protocol boundary. `quickstart.md §2` names the MIRACL-ko MRR@10 figure for the default encoder. No uncited claim introduced. |
| II. Fail-Closed Security (NON-NEGOTIABLE) | ✅ PASS | `data-model.md §7` (DegradationRecord) documents the single-latch WARN emission and explicitly preserves Layer-3 auth-gate fail-closed posture. `quickstart.md §2–§3` repeats the invariant to operators. No new auth path. |
| III. Pydantic v2 Strict Typing (NON-NEGOTIABLE) | ✅ PASS | All three frozen schemas re-exported as byte-exact JSON snapshots under `contracts/*.schema.json` (SHA-256 captured; see Appendix B). New entities (`RetrievalManifest`, `AdversarialQuerySet`, `DegradationRecord`) are Pydantic v2 `ConfigDict(frozen=True, extra="forbid")` with zero `Any`. |
| IV. Government API Compliance | ✅ PASS — N/A | Phase 1 artifacts do not introduce any `data.go.kr` call path. Model weight downloads remain HF-hub-only and gated by NFR-NoNetAtRuntime. `quickstart.md §7` reiterates "CI MUST NOT download weights". |
| V. Policy Alignment | ✅ PASS | `quickstart.md §2` framing — "users should not have to mimic an adapter's `search_hint` vocabulary" — restates Principle 8 in operator-facing language. Principle 9 discoverability is served by the SC-001/SC-002 lift targets. |
| VI. Deferred Work Accountability | ⚠ NEEDS TRACKING (unchanged) | The three `NEEDS TRACKING` markers (cross-encoder re-ranking, default flip to `hybrid`, aggressive rollout) persist — `/speckit-taskstoissues` will back-fill them. No NEW unregistered deferrals introduced in Phase 1. |

**Gate decision**: PASS. No Complexity Tracking entries required. Phase 1 artifacts are internally consistent with the frozen contract surface and with the pre-design gate.

## Complexity Tracking

> No Constitution Check violations to justify — all six principles pass cleanly. The one Principle-VI caveat (three `NEEDS TRACKING` markers) is resolved by `/speckit-taskstoissues` per the standard workflow, not a violation.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| *(none)* | *(none)* | *(none)* |

## Phase 1 Artifact Manifest

- `research.md` (Phase 0) — resolves 3 clarifications, validates 4 tracked + 3 NEEDS TRACKING deferrals, maps every decision to a concrete reference.
- `data-model.md` — 7 entities (Retriever Protocol, BM25Backend, DenseBackend, HybridBackend, RetrievalManifest, AdversarialQuerySet, DegradationRecord). Frozen entities referenced, not redefined.
- `contracts/retriever_protocol.md` — internal Protocol contract + 6 invariants + registry integration note.
- `contracts/lookup_search_input.schema.json` — SHA-256 `422ed50f3a26c6627d8177222600e0a42afeb8348a6c3f228009bc58d4fa788b`.
- `contracts/lookup_search_result.schema.json` — SHA-256 `191c4f81ba071629b83ca99507d0c83c813c29d1a0e77723242604fd4a3d2bcb`.
- `contracts/adapter_candidate.schema.json` — SHA-256 `cf122f6949b69b2bdedb06044bc5e489b4b3dfd5b35e4e5ab0ee6c42de4bb0e7`.
- `quickstart.md` — operator walkthrough for all three backends, A/B harness, env-var reference, and frozen-surface reminder.
- `CLAUDE.md` (agent context) — `update-agent-context.sh claude` appended 026 Active Technologies entry.

## Ready-for-/speckit-tasks Gate

- [x] Phase 0 `research.md` committed, all NEEDS CLARIFICATION resolved.
- [x] Phase 1 `data-model.md`, `contracts/`, `quickstart.md` committed.
- [x] Agent context file updated (`CLAUDE.md`).
- [x] Post-design Constitution re-check passes cleanly.
- [x] No new unregistered deferrals introduced; `NEEDS TRACKING` markers accounted for by Principle VI workflow.

HALT for human review before `/speckit-tasks` per the delegation directive.
