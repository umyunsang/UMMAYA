---
description: "Task list for Feature 026 — Retrieval Backend Evolution (BM25 → Dense + Hybrid RRF)"
---

# Tasks: Retrieval Backend Evolution — BM25 → Dense Embeddings (+ Hybrid Fusion)

**Input**: Design documents from `/specs/026-retrieval-dense-embeddings/`
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/` (all present)

**Tests**: REQUIRED. The spec mandates regression gates (`tests/retrieval/test_schema_snapshot.py`, `tests/eval/test_retrieval_gate.py`) for SC-004, a latency harness for SC-003, and backend-specific correctness tests for SC-001/SC-002/SC-005. Test tasks are first-class citizens in this plan.

**Organization**: Tasks are grouped by user story from `spec.md` (US1/US2 P1, US3/US4 P2) so each story is independently implementable and testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallelisable (different files, no hard dependency on another open task in the same phase).
- **[Story]**: Which user story this task serves (US1 / US2 / US3 / US4). Setup, Foundational, and Polish tasks carry no `[Story]` label.
- Exact file paths are embedded in every description.

## Path Conventions

Single Python project. Retrieval subpackage lives at `src/kosmos/tools/retrieval/`. New tests under `tests/retrieval/`. New eval file under `eval/`. Path structure verified against `plan.md § Project Structure`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project-level scaffolding — dependency registration, package skeletons, test directory skeletons. No behaviour yet.

- [X] T001 [P] Add `sentence-transformers >= 3.0` (Apache-2.0) and `numpy >= 1.26` to `[project].dependencies` in `/Users/um-yunsang/KOSMOS-585/pyproject.toml` with a `# spec 026 — retrieval dense backend` comment on each line. Do NOT run `uv lock` in this task (covered by T003).
- [X] T002 [P] Create subpackage skeleton at `/Users/um-yunsang/KOSMOS-585/src/kosmos/tools/retrieval/__init__.py` — empty module docstring only. Do not import backend modules yet (they don't exist).
- [X] T003 Run `uv lock` from repo root to refresh `uv.lock` with the new deps from T001; commit the lockfile diff in the same task. Depends on T001. Must run before any task that imports `sentence_transformers` or `numpy`.
- [X] T004 [P] Create test directory skeleton at `/Users/um-yunsang/KOSMOS-585/tests/retrieval/__init__.py` (empty) and `/Users/um-yunsang/KOSMOS-585/tests/retrieval/__snapshots__/.gitkeep`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The Protocol, the BM25 wrapper, the registry DI seam, the schema-snapshot gate, and the manifest model. These MUST land before ANY user story can progress — every user story reads `Retriever`, and US2 depends on the schema-snapshot gate being live before any behaviour change.

**CRITICAL**: No US1/US2/US3/US4 task may start until this phase is complete.

- [X] T005 Implement `Retriever` Protocol in `/Users/um-yunsang/KOSMOS-585/src/kosmos/tools/retrieval/backend.py` exactly per `contracts/retriever_protocol.md` and `data-model.md §1` (`@runtime_checkable` Protocol with `rebuild(corpus: dict[str, str]) -> None` and `score(query: str) -> list[tuple[str, float]]`). Include module-level docstring citing Cormack SIGIR 2009 and `feedback_no_hardcoding.md`. Depends on T002.
- [X] T006 Add the backend factory `build_retriever_from_env(*, bm25_index_factory) -> Retriever` to `/Users/um-yunsang/KOSMOS-585/src/kosmos/tools/retrieval/backend.py` reading `KOSMOS_RETRIEVAL_BACKEND` (default `bm25`; unknown → `ValueError` per FR-001). Do NOT construct `DenseBackend` here yet — route `dense`/`hybrid` to a `NotImplementedError` placeholder to be replaced in US1. Depends on T005.
- [X] T007 [P] Implement `BM25Backend` in `/Users/um-yunsang/KOSMOS-585/src/kosmos/tools/retrieval/bm25_backend.py` per `data-model.md §2`: accept an injected `BM25Index`, delegate `rebuild`/`score` verbatim, no new logic. Depends on T005.
- [X] T008 [P] Implement `RetrievalManifest` Pydantic v2 model in `/Users/um-yunsang/KOSMOS-585/src/kosmos/tools/retrieval/manifest.py` exactly per `data-model.md §5` (`ConfigDict(frozen=True, extra="forbid")`, `backend` pattern, dense-specific fields optional-and-correlated, `built_at` ISO 8601). Include `@model_validator(mode="after")` enforcing the bm25↔None and dense/hybrid↔populated correlation. Depends on T002.
- [X] T009 [P] Implement `DegradationRecord` in-memory latch in `/Users/um-yunsang/KOSMOS-585/src/kosmos/tools/retrieval/degrade.py` per `data-model.md §7`: one-shot `emit_if_needed(logger, requested_backend, effective_backend, reason)` helper using stdlib `logging.warning` with structured `extra={"event": "retrieval.degraded", ...}`. Idempotent after first call. Depends on T002.
- [X] T010 Rewire `/Users/um-yunsang/KOSMOS-585/src/kosmos/tools/registry.py` to own a `self._retriever: Retriever` attribute built via `build_retriever_from_env(...)`; keep `self.bm25_index` as a read-only alias pointing at the `BM25Backend._index` for one release cycle (FR-009). Every `register`/`unregister` path MUST call `self._retriever.rebuild(...)` with the `{tool_id: search_hint}` corpus. Depends on T006, T007.
- [X] T011 Rewire `/Users/um-yunsang/KOSMOS-585/src/kosmos/tools/search.py` to call `registry._retriever.score(query)` in place of `registry.bm25_index.score(query)`. External function signature unchanged. Tie-break (score DESC, tool_id ASC) and adaptive top_k clamp MUST remain the only place they live. Depends on T010.
- [X] T012 Generate and commit byte-exact JSON-schema snapshots by running `uv run python -c "from kosmos.tools.models import LookupSearchInput, LookupSearchResult, AdapterCandidate; import json; open('tests/retrieval/__snapshots__/lookup_search_input.schema.json','w').write(json.dumps(LookupSearchInput.model_json_schema(), indent=2, sort_keys=True, ensure_ascii=False)); ..."` for all three models into `/Users/um-yunsang/KOSMOS-585/tests/retrieval/__snapshots__/`. Hashes MUST match the SHA-256 values recorded in `plan.md § Phase 1 Artifact Manifest`. Depends on T004.
- [X] T013 Implement the schema-snapshot regression test at `/Users/um-yunsang/KOSMOS-585/tests/retrieval/test_schema_snapshot.py`: for each of `LookupSearchInput`, `LookupSearchResult`, `AdapterCandidate` assert `model_json_schema()` equals the committed snapshot byte-for-byte. Fails the build on any diff (SC-004, FR-003, Appendix B of spec). Depends on T012.
- [X] T014 [P] Implement `Retriever` protocol conformance test at `/Users/um-yunsang/KOSMOS-585/tests/retrieval/test_retriever_protocol.py` asserting `isinstance(BM25Backend(...), Retriever)` via `runtime_checkable`, empty-corpus → `score() == []`, empty-query → all-zero vector of length `len(corpus)`, non-negative scores everywhere. Depends on T005, T007.
- [X] T015 [P] Implement `BM25Backend` parity test at `/Users/um-yunsang/KOSMOS-585/tests/retrieval/test_bm25_backend.py`: load the 4 seed adapters, rebuild both a raw `BM25Index` and a `BM25Backend(BM25Index(...))`, and assert `score(q)` outputs are identical for every query in the committed 30-query set. Guards FR-009 and SC-004. Depends on T007.
- [X] T016 [P] Implement `RetrievalManifest` validation test at `/Users/um-yunsang/KOSMOS-585/tests/retrieval/test_manifest.py`: covers `backend=bm25`→dense-fields-None, `backend=dense`→dense-fields-required, invalid SHA pattern, invalid `built_at`. Depends on T008.

**Checkpoint**: Foundation ready. Registry + search.py use the `Retriever` seam. BM25 default path is byte-identical to `main`. Schema-snapshot and BM25-parity gates are live. User-story phases can now proceed in parallel.

---

## Phase 3: User Story 1 — Paraphrase-robust tool discovery (Priority: P1) 🎯 MVP

**Goal**: Citizens can ask about a tool using natural language (e.g., "아이 열이 40도 넘어요 지금 응급실 가려면 어디가 가까워요?") and retrieve the correct adapter even when the query shares no morphemes with the adapter's `search_hint`. Realised via `DenseBackend` + `HybridBackend` (RRF k=60) with `KOSMOS_RETRIEVAL_BACKEND=hybrid` opt-in.

**Independent Test**: Run the adversarial 20-query subset under `backend=hybrid` vs `backend=bm25`; assert recall@5 ≥ 0.80 on hybrid and < 0.50 on bm25 (SC-002). No live API calls, no #22 dependency.

### Tests for User Story 1 (write first; fail before implementation)

- [X] T017 [P] [US1] RRF math unit test at `/Users/um-yunsang/KOSMOS-585/tests/retrieval/test_hybrid_rrf.py` asserting `fused = 1/(k + rank_bm25) + 1/(k + rank_dense)` at `k=60` across the Cormack SIGIR 2009 worked examples; missing-from-one-list handled as `rank = N+1`; fused score strictly positive for any `tool_id` in the union; determinism under identical inputs.
- [X] T018 [P] [US1] DenseBackend mocked-encoder test at `/Users/um-yunsang/KOSMOS-585/tests/retrieval/test_dense_backend.py`: monkey-patch `SentenceTransformer` to a deterministic stub returning fixed vectors; verify query-prefix vs passage-prefix application, L2-normalisation, `cos < 0 → 0.0` clamp, empty-corpus short-circuit (no encoder call), and cardinality (`len(score(q)) == len(corpus)`).
- [X] T019 [P] [US1] Adversarial overlap CI check at `/Users/um-yunsang/KOSMOS-585/tests/retrieval/test_adversarial_overlap.py`: loads `eval/retrieval_queries_adversarial.yaml`, tokenises each query with the same kiwipiepy configuration as `bm25_index.py`, loads the 4 seed adapter `search_hint`s, asserts every entry's `lexical_overlap_score == 0.0` (FR-012). Fails at author time if a new adapter's `search_hint` introduces overlap.

### Implementation for User Story 1

- [X] T020 [US1] Author `/Users/um-yunsang/KOSMOS-585/eval/retrieval_queries_adversarial.yaml` with ≥ 20 adversarial paraphrase queries across all 4 seed adapters (KOROAD / KMA / HIRA / NMC), each with zero lexical overlap against its target adapter's `search_hint` tokens. Schema per `data-model.md §6` (`query`, `expected_tool_id`, `lexical_overlap_score=0.0`, `notes`). Depends on T019 (author-time overlap check must be green).
- [X] T021 [US1] Implement `DenseBackend` in `/Users/um-yunsang/KOSMOS-585/src/kosmos/tools/retrieval/dense_backend.py` per `data-model.md §3`: lazy load of `intfloat/multilingual-e5-small` on first `rebuild`; E5-family `"query: "`/`"passage: "` prefixes; in-memory `numpy.ndarray` L2-normalised matrix; SHA-256 weight capture; `DenseBackendLoadError` on load/tokenizer/hash failure. Depends on T005, T008, T014.
- [X] T022 [US1] Implement `HybridBackend` RRF fusion in `/Users/um-yunsang/KOSMOS-585/src/kosmos/tools/retrieval/hybrid.py` per `data-model.md §4`: compose one `BM25Backend` + one `DenseBackend`; `k=60` default overridable via `KOSMOS_RETRIEVAL_FUSION_K`; union ranking with missing-list `rank = N+1`; fused score strictly positive. Depends on T007, T017, T021.
- [X] T023 [US1] Complete `build_retriever_from_env` in `/Users/um-yunsang/KOSMOS-585/src/kosmos/tools/retrieval/backend.py` for `dense` and `hybrid` paths — wire in `DenseBackend` / `HybridBackend`, read `KOSMOS_RETRIEVAL_MODEL_ID` (default `intfloat/multilingual-e5-small`), `KOSMOS_RETRIEVAL_FUSION` (default `rrf`; non-`rrf` → `ValueError`), `KOSMOS_RETRIEVAL_FUSION_K` (default 60; `< 1` → `ValueError`), `KOSMOS_RETRIEVAL_COLD_START` (default `lazy`). Replaces the T006 placeholder. Depends on T021, T022.
- [X] T024 [US1] SC-002 adversarial eval test at `/Users/um-yunsang/KOSMOS-585/tests/retrieval/test_adversarial_recall.py` gated by `@pytest.mark.live_embedder` (skipped in CI per NFR-NoNetAtRuntime): loads the 4 seed registry + `retrieval_queries_adversarial.yaml`, runs `backend=hybrid` → recall@5 ≥ 0.80 AND `backend=bm25` → recall@5 < 0.50. Marks the expected gap that justifies the spec. Depends on T020, T022.

**Checkpoint**: US1 delivers the Epic's core value. `KOSMOS_RETRIEVAL_BACKEND=hybrid` is fully wired. Adversarial subset ships in the PR. Live-embedder test exists but is skipped in CI (operators run it locally).

---

## Phase 4: User Story 2 — Zero-change default path (Priority: P1)

**Goal**: With `KOSMOS_RETRIEVAL_BACKEND` unset or `=bm25`, behaviour is byte-identical to `main`: same rankings, same `why_matched`, same `recall_at_5 == 1.0` / `recall_at_1 == 0.9667` on the committed 30-query set, and the frozen schema snapshots unchanged. Plus: `backend=dense` with a forced model-load failure degrades gracefully to BM25 (FR-002 / SC-005).

**Independent Test**: Run `tests/eval/test_retrieval_gate.py` with `KOSMOS_RETRIEVAL_BACKEND` unset; assert exact baseline. Run the fail-open test with a monkey-patched `sentence_transformers` that raises on import; assert registry serves on BM25 and emits exactly one WARN line.

### Tests for User Story 2 (write first; fail before implementation)

- [X] T025 [P] [US2] Baseline preservation test at `/Users/um-yunsang/KOSMOS-585/tests/retrieval/test_baseline_preservation.py`: programmatic invocation of `kosmos.eval.retrieval._build_registry()` + `_evaluate()` on `eval/retrieval_queries.yaml` with `KOSMOS_RETRIEVAL_BACKEND` unset; assert `recall_at_5 == 1.0` and `recall_at_1 == 0.9666666666666667` exactly (Appendix A of spec). SC-004 evidence.
- [X] T026 [P] [US2] Fail-open degradation test at `/Users/um-yunsang/KOSMOS-585/tests/retrieval/test_fail_open.py`: `monkeypatch.setenv("KOSMOS_RETRIEVAL_BACKEND", "dense")`; patch `sentence_transformers.SentenceTransformer` to raise `RuntimeError("simulated")` on construction; build a `ToolRegistry` with 4 seed adapters; assert effective retriever is `BM25Backend`, `caplog.records` contains exactly one WARN with `event=retrieval.degraded`, `requested_backend="dense"`, `effective_backend="bm25"`; second `search()` call MUST NOT emit another WARN. SC-005 evidence.

### Implementation for User Story 2

- [X] T027 [US2] Wire `DegradationRecord` into the backend factory in `/Users/um-yunsang/KOSMOS-585/src/kosmos/tools/retrieval/backend.py`: wrap `DenseBackend` / `HybridBackend` construction in a `try/except (DenseBackendLoadError, ImportError, RuntimeError)`; on failure emit via `DegradationRecord.emit_if_needed` and return a `BM25Backend` instead. Auth/invocation gates untouched. Depends on T009, T023.
- [X] T028 [US2] Extend the `HybridBackend.score` path in `/Users/um-yunsang/KOSMOS-585/src/kosmos/tools/retrieval/hybrid.py` to catch mid-session `DenseBackend.score` failures (OOM, tokenizer crash) per `quickstart.md §3`, return the `BM25Backend.score` output unchanged, and call `DegradationRecord.emit_if_needed`. Depends on T022, T009.
- [X] T029 [US2] Verify `tests/eval/test_retrieval_gate.py` still passes with `KOSMOS_RETRIEVAL_BACKEND` unset (no edit expected; this task is the verification run). If any side-effect of T010/T011 changed the output, root-cause and fix inside the retrieval subpackage — never in `lookup.py` / `models.py`. Depends on T010, T011, T025.

**Checkpoint**: US1 + US2 together satisfy SC-001 (in `PENDING_#22` state), SC-002 (locally), SC-004, SC-005. The byte-level contract is preserved.

---

## Phase 5: User Story 3 — Extended-corpus A/B uplift (Priority: P2)

**Goal**: Extend `kosmos.eval.retrieval` so the same harness runs either the committed 30-query set or the combined ≥50-query set once Epic #22 lands, with an explicit `PENDING_#22` status emitted when the extended file is absent (FR-013 / SC-001).

**Independent Test**: With #22 absent, the harness emits `PENDING_#22` in the JSON report and returns a non-green exit code for SC-001. With #22 present (simulated via an inline fixture), `backend=hybrid` MUST show recall@5 ≥ 0.90 AND recall@1 ≥ `bm25_recall@1 + 0.05`.

### Tests for User Story 3 (write first; fail before implementation)

- [X] T030 [P] [US3] Extended-corpus harness test at `/Users/um-yunsang/KOSMOS-585/tests/retrieval/test_extended_corpus_harness.py`: with no `retrieval_queries_extended.yaml` or Phase-3-adapter registration present, assert the harness emits `status: "PENDING_#22"` in its JSON output and does NOT mark SC-001 green. Uses a tmp-path fixture — no changes to the committed `eval/` directory.

### Implementation for User Story 3

- [X] T031 [US3] Extend `/Users/um-yunsang/KOSMOS-585/src/kosmos/eval/retrieval.py`: add `--backend {bm25,dense,hybrid}` CLI flag (threaded through to `build_retriever_from_env` via env-var overlay), add `--report` flag (pre-existing or add) writing a JSON artifact, add a `--queries` flag accepting either the committed file or the adversarial file. Preserve the existing output schema for `tests/eval/test_retrieval_gate.py` compatibility. Depends on T023.
- [X] T032 [US3] Add `PENDING_#22` emission logic in `/Users/um-yunsang/KOSMOS-585/src/kosmos/eval/retrieval.py`: when the harness detects `registry_size < 8` or no Phase-3 adapter ids present, the JSON report MUST include `sc_01_status: "PENDING_#22"` and exit with a non-zero-but-non-fail status code (`2` — WARN). Depends on T031, T030.

**Checkpoint**: US3 makes SC-001 measurable the instant #22 lands, without requiring any further #585 PRs.

---

## Phase 6: User Story 4 — Operator-grade performance (Priority: P2)

**Goal**: Establish a hard p99 latency envelope on a synthetic 100-adapter padded registry. `backend=hybrid` p99 < 50 ms. `backend=bm25` p99 within ±10 % of the pre-#585 baseline (SC-003).

**Independent Test**: `tests/retrieval/test_latency.py` under `backend=hybrid` (mocked encoder for CI, real encoder under `@pytest.mark.live_embedder`) and under `backend=bm25` both pass the p99 threshold across 500 warm queries.

### Tests for User Story 4

- [X] T033 [US4] Latency harness at `/Users/um-yunsang/KOSMOS-585/tests/retrieval/test_latency.py`: build a 100-adapter padded registry by cloning the 4 seed adapters with suffixed ids (`koroad_accident_hazard_search__clone_001`, …, `__clone_096`) — **padding methodology**: strict tool_id suffixing only; `search_hint`, `required_params`, and every other `GovAPITool` field MUST remain byte-identical to the source adapter (this keeps BM25 token distributions and Dense vector matrices representative of the real 4-seed baseline without introducing synthetic noise). Do NOT perturb or mutate `search_hint` text. Run 500 warm queries with `time.perf_counter_ns()`; assert `p99 < 50e6` ns on hybrid (mocked encoder) and `p99_bm25 <= 1.10 * baseline_p99_bm25` (baseline captured on-the-fly from the default backend on the same padded registry for stability). Two subtests. Depends on T011, T022.

**Checkpoint**: SC-003 is live. Any future refactor that regresses p99 breaks the build on the same run.

---

## Phase N: Polish & Cross-Cutting Concerns

- [X] T034 [P] Author `/Users/um-yunsang/KOSMOS-585/docs/design/retrieval.md` summarising Phase 0 research (model shortlist, fusion decision, index decision, cold-start decision), the `Retriever` Protocol diagram, and the SC framework. Cite Cormack SIGIR 2009, Weaviate v1.24, MIRACL-ko numbers, HF licence rows. No new claims beyond `research.md`.
- [X] T035 [P] Validate `/Users/um-yunsang/KOSMOS-585/specs/026-retrieval-dense-embeddings/quickstart.md` by running sections §1 (BM25 default), §3 (hybrid on local-cached encoder), §4 (A/B harness) in a clean shell and confirming every command prints the claimed output shape. Fix any drift by editing `quickstart.md` — never the frozen contract surface.
- [X] T036 [P] Run `uv run pytest tests/retrieval/ tests/eval/test_retrieval_gate.py -q` and capture the green summary in the PR description. Confirms SC-004 + SC-005 on CI-reachable surfaces. Live-embedder tests remain skipped.
- [X] T037 Run `uv run ruff check src/kosmos/tools/retrieval/ src/kosmos/eval/retrieval.py tests/retrieval/` and `uv run mypy src/kosmos/tools/retrieval/` (if mypy is in scope); resolve any reported issue inside the new subpackage. No edits to frozen surfaces.
- [X] T038 Final review pass: verify no `Any` types in the new subpackage, no `print()` outside CLI surfaces, no new OTEL attribute names introduced (FR-007), no new `.env`/`secrets/` edits, no files > 1 MB committed (FR-010). Depends on T034–T037.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**: no external deps, start immediately.
- **Phase 2 Foundational**: depends on Phase 1. BLOCKS all user-story phases.
- **Phase 3 US1 (P1)** and **Phase 4 US2 (P1)**: both depend on Phase 2 only. US1 and US2 can run in parallel.
- **Phase 5 US3 (P2)** and **Phase 6 US4 (P2)**: both depend on Phase 2. US3 additionally depends on T023 (backend factory complete, from US1). US4 additionally depends on T022 (HybridBackend, from US1).
- **Phase N Polish**: depends on all chosen user-story phases being complete.

### User Story Dependency Graph

```
Phase 1 Setup ──► Phase 2 Foundational ──┬──► US1 (P1) ──┬──► US3 (P2, needs factory)
                                          │              └──► US4 (P2, needs hybrid)
                                          └──► US2 (P1, independent of US1)
                                                                  │
                                                                  └──► Phase N Polish
```

### Within Each Phase

- Tests first, implementation second (tests FAIL before impl lands — spec §Appendix B gate).
- Models (`RetrievalManifest`, `AdversarialQuery`) before services (`DenseBackend`, `HybridBackend`).
- Services before integration (backend factory → registry DI).
- Story complete before advancing to the next priority.

### Parallel Opportunities

- Phase 1: T001 / T002 / T004 in parallel (different files).
- Phase 2: T007 / T008 / T009 in parallel (different files); T014 / T015 / T016 in parallel after their source tasks.
- Phase 3 tests: T017 / T018 / T019 in parallel.
- Phase 4 tests: T025 / T026 in parallel.
- Polish: T034 / T035 / T036 in parallel.

---

## Parallel Example: Phase 2 Foundational kick-off

```bash
# Once Phase 1 completes, launch three Foundational models in parallel:
Task: "Implement BM25Backend in src/kosmos/tools/retrieval/bm25_backend.py (T007)"
Task: "Implement RetrievalManifest in src/kosmos/tools/retrieval/manifest.py (T008)"
Task: "Implement DegradationRecord latch in src/kosmos/tools/retrieval/degrade.py (T009)"
```

## Parallel Example: US1 test authoring

```bash
# Write three independent test files in parallel before any US1 implementation lands:
Task: "RRF math unit test in tests/retrieval/test_hybrid_rrf.py (T017)"
Task: "DenseBackend mocked-encoder test in tests/retrieval/test_dense_backend.py (T018)"
Task: "Adversarial overlap CI check in tests/retrieval/test_adversarial_overlap.py (T019)"
```

---

## Implementation Strategy

### MVP First (US1 + US2 — both P1)

1. Complete Phase 1 Setup.
2. Complete Phase 2 Foundational (CRITICAL — blocks everything).
3. Complete Phase 3 US1 — Epic's core value.
4. Complete Phase 4 US2 — byte-level contract preservation.
5. STOP and VALIDATE: `uv run pytest tests/retrieval/ tests/eval/test_retrieval_gate.py -q`; adversarial eval locally with `@pytest.mark.live_embedder`.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. US1 → paraphrase robustness opt-in (`KOSMOS_RETRIEVAL_BACKEND=hybrid`).
3. US2 → zero-change default + fail-open (ships with US1 since both are P1; they are test-independent but share the factory).
4. US3 → extended-corpus A/B harness (`PENDING_#22` first; green when #22 lands).
5. US4 → performance envelope gate.
6. Polish → docs, quickstart validation, lint sweep.

### Parallel Team Strategy

- Team completes Setup + Foundational together.
- Once Foundational lands:
  - Teammate A: US1 (DenseBackend + HybridBackend + adversarial subset).
  - Teammate B: US2 (fail-open + baseline preservation).
  - Teammate C: US3 (extended-corpus harness + `PENDING_#22`).
  - Teammate D: US4 (latency harness).
- All four integrate on top of the shared Foundational surface.

---

## Notes

- `[P]` = different files, no dependency on another open task in the same phase.
- `[Story]` label maps every story-phase task to its user story for traceability.
- Every user story is independently completable and independently testable.
- Live-embedder tests are marked `@pytest.mark.live_embedder` and skipped in CI per NFR-NoNetAtRuntime; operators run them locally against the HF hub cache.
- Commit after each task or logical group; never amend published commits; PR body uses `Closes #585` only.
- Avoid: vague tasks, cross-file edits without [P], cross-story dependencies that break independence, edits to `lookup.py` / `models.py` / any adapter body (frozen surfaces).
