# Tasks: data.go.kr Live Expansion

**Input**: Design documents from `/Users/um-yunsang/UMMAYA/specs/2798-data-go-kr-live-expansion/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Required. The user requested implementation plus real terminal validation, and the spec requires fixture-only default tests.

**Organization**: Tasks are grouped by user story and preserve TDD ordering.

## Phase 1: Setup

**Purpose**: Lock the evidence-driven scope and implementation scaffolding.

- [X] T001 Update `.specify/feature.json` and confirm feature directory points to `specs/2798-data-go-kr-live-expansion`
- [X] T002 [P] Verify evidence documents exist in `docs/api/data-go-kr-candidate-docs/LIVE-API-CALL-MATRIX-2026-05-16.md` and `docs/api/data-go-kr-candidate-docs/LIVE-API-BLOCKER-RESOLUTION-2026-05-16.md`
- [X] T003 [P] Verify dispatch plan in `specs/2798-data-go-kr-live-expansion/dispatch-tree.md`

---

## Phase 2: Foundational

**Purpose**: Shared contract changes that must exist before new adapters compile.

- [X] T004 [P] Write failing manifest-count tests for the 30 included and 3 excluded dataset IDs in `tests/unit/tools/verified_data_go_kr/test_manifest.py`
- [X] T005 [P] Write failing registry-count tests for 68 total registry entries and 42 live adapters in `tests/unit/tools/test_registry_count_breakdown.py`
- [X] T006 [P] Write failing transport-contract tests for `request_headers`, HTTP endpoint allowance, and uppercase `ServiceKey` in `tests/unit/tools/verified_data_go_kr/test_manifest.py`
- [X] T007 Extend `src/ummaya/tools/verified_data_go_kr/_models.py` with `request_headers` and HTTP endpoint validation
- [X] T008 Extend `src/ummaya/tools/verified_data_go_kr/_client.py` to pass adapter-specific request headers
- [X] T009 Extend `src/ummaya/tools/models.py` Ministry literals for the new agencies represented by the 16 adapters

**Checkpoint**: Foundational tests fail before T007-T009 and pass after.

---

## Phase 3: User Story 1 - Expose the 30 Callable APIs (Priority: P1)

**Goal**: Register all 30 callable live APIs and exclude the three blockers.

**Independent Test**: Manifest and registration tests show 30 verified dataset IDs, 16 new tool IDs, and absence of blocked adapters.

### Tests for User Story 1

- [X] T010 [P] [US1] Write failing module import/registration tests for the 16 new adapters in `tests/unit/tools/verified_data_go_kr/test_registration.py`
- [X] T011 [P] [US1] Write failing fixture replay matrix rows for the 16 new adapters in `tests/unit/tools/verified_data_go_kr/test_fixture_replay.py`

### Implementation for User Story 1

- [X] T012 [US1] Add the 16 new `VerifiedAdapterSpec` entries to `src/ummaya/tools/verified_data_go_kr/_manifest.py`
- [X] T013 [P] [US1] Implement safety and medical adapter modules in `src/ummaya/tools/verified_data_go_kr/nmc_aed_site.py`, `hira_medical_institution.py`, `mois_emergency_call_box.py`, and `mfds_easy_drug_info.py`
- [X] T014 [P] [US1] Implement transport and public-status adapter modules in `src/ummaya/tools/verified_data_go_kr/djtc_subway_segment.py`, `gyeryong_assistive_charger.py`, `mof_ocean_water_quality.py`, and `moj_stay_person_counter.py`
- [X] T015 [P] [US1] Implement notice/transparency adapter modules in `src/ummaya/tools/verified_data_go_kr/mpm_public_job.py`, `mss_sme_support_notice.py`, `msit_business_announcement.py`, and `ccourt_publication_documents.py`
- [X] T016 [P] [US1] Implement remaining lookup adapter modules in `src/ummaya/tools/verified_data_go_kr/moj_village_lawyer.py`, `mois_facility_safety.py`, `pps_shopping_mall_product.py`, and `ksd_financial_term.py`
- [X] T017 [US1] Run focused fixture/registration tests for `tests/unit/tools/verified_data_go_kr/` and debug until clean

---

## Phase 4: User Story 2 - Preserve Correct Primitive Semantics (Priority: P1)

**Goal**: Ensure public-data adapters stay on the public-data fetch path and do not misuse `send` or identity-oriented `check`.

**Independent Test**: Manifest tests show every verified public-data adapter is live, read-only, and bound to current runtime semantics; transport contract tests prove special wire behavior.

### Tests for User Story 2

- [X] T018 [P] [US2] Write failing primitive/transport assertions in `tests/unit/tools/verified_data_go_kr/test_manifest.py`

### Implementation for User Story 2

- [X] T019 [US2] Ensure every new manifest row in `src/ummaya/tools/verified_data_go_kr/_manifest.py` declares read-only live metadata and correct transport quirks
- [X] T020 [US2] Run focused primitive/transport tests and debug until clean

---

## Phase 5: User Story 3 - Prove Real UMMAYA Tool-Call Behavior (Priority: P1)

**Goal**: Run UMMAYA locally, enter representative prompts, and inspect whether the LLM emits correct tool calls without abnormal flow.

**Independent Test**: `real-use-smoke.md` records prompt, root primitive, adapter ID, parameter object, result status, and abnormal-flow outcome.

### Tests for User Story 3

- [X] T021 [P] [US3] Create a smoke checklist skeleton in `specs/2798-data-go-kr-live-expansion/real-use-smoke.md`

### Implementation for User Story 3

- [X] T022 [US3] Run terminal UMMAYA smoke for safety, medical/drug, support-notice, transport, and statistics prompts and capture sanitized observations in `specs/2798-data-go-kr-live-expansion/real-use-smoke.md`
- [X] T023 [US3] Debug any wrong primitive, wrong adapter, malformed params, repeated failed calls, permission misclassification, or fabricated fallback found in `specs/2798-data-go-kr-live-expansion/real-use-smoke.md`

---

## Phase 6: User Story 4 - Keep Evidence and Safety Auditable (Priority: P2)

**Goal**: Update docs and schemas so reviewers can trace every included and excluded API.

**Independent Test**: Docs/schema checks find one schema per adapter and documentation names all 30 included and 3 excluded APIs.

### Tests for User Story 4

- [X] T024 [P] [US4] Write failing schema existence assertions for the 16 new adapters in `tests/unit/tools/verified_data_go_kr/test_manifest.py`

### Implementation for User Story 4

- [X] T025 [US4] Update `docs/api/verified-data-go-kr/README.md` with the 30-adapter matrix and 3 blocked API records
- [X] T026 [US4] Generate JSON schemas for the 16 new adapters under `docs/api/schemas/`
- [X] T027 [US4] Run schema/docs consistency tests and debug until clean

---

## Phase 7: Polish & Validation

**Purpose**: Full verification and task bookkeeping.

- [X] T028 Run `uv run ruff check src tests` and fix reported issues
- [X] T029 Run `uv run ruff format --check src tests` and fix formatting issues
- [X] T030 Run `uv run mypy src` and fix reported type issues
- [X] T031 Run `uv run pytest tests/unit/tools/verified_data_go_kr tests/unit/tools/test_registry_count_breakdown.py -m "not live"` and fix failures
- [X] T032 Run `uv run pytest -m "not live"` and fix failures
- [X] T033 Run secret scan over new docs/probes/smoke artifacts and remove any plaintext credential occurrence
- [X] T034 Update `specs/2798-data-go-kr-live-expansion/tasks.md` checkboxes as tasks complete

## Dependencies & Execution Order

- Phase 1 has no dependencies.
- Phase 2 depends on Phase 1 and blocks all adapter work.
- US1 and US2 depend on Phase 2.
- US3 depends on US1 and US2 because terminal smoke needs registered adapters.
- US4 depends on the final adapter set from US1/US2.
- Phase 7 depends on all user stories.

## Parallel Opportunities

- T002-T003 can run in parallel.
- T004-T006 can run in parallel.
- T010-T011 can run in parallel.
- T013-T016 are file-disjoint and parallel-safe if explicit subagent dispatch is later requested.
- T021 and T024 are file-disjoint.

## Implementation Strategy

1. Finish foundational RED/GREEN tests for manifest/client/model changes.
2. Add all 16 adapter specs and thin modules.
3. Prove focused registry/fixture tests.
4. Generate docs/schemas.
5. Run terminal UMMAYA smoke and debug abnormal flows.
6. Run full backend verification and secret scan.

## Notes

- Total tasks: 34, below the 90-task budget.
- No task touches `tui/src/**`; PR should declare `TUI no-change`.
- Default tests must not call live public APIs.
