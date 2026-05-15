# Tasks: data.go.kr Verified Adapter Wave

**Input**: Design documents from `/Users/um-yunsang/UMMAYA/specs/2797-data-go-kr-verified-adapters/`  
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: Required. User explicitly requested implementation through real-use validation, and the spec requires fixture-only CI tests.

**Organization**: Tasks are grouped by user story to enable independent verification.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare feature package, fixture paths, and registration constants.

- [X] T001 Create `src/ummaya/tools/verified_data_go_kr/__init__.py` package scaffold (#2799)
- [X] T002 Create `tests/tools/verified_data_go_kr/__init__.py` and fixture test package scaffold (#2800)
- [X] T003 Add verified adapter ID/evidence manifest in `src/ummaya/tools/verified_data_go_kr/_manifest.py` (#2801)
- [X] T004 Add documentation index stub in `docs/api/verified-data-go-kr/README.md` (#2802)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared typed models, parsers, and fixture replay harness that all adapters depend on.

**CRITICAL**: No user story adapter implementation can begin until this phase is complete.

- [X] T005 [P] Write failing model contract tests in `tests/tools/verified_data_go_kr/test_models.py` (#2803)
- [X] T006 [P] Write failing JSON/XML parser tests in `tests/tools/verified_data_go_kr/test_parsing.py` (#2804)
- [X] T007 [P] Write failing registration exclusion tests in `tests/tools/verified_data_go_kr/test_no_scoped_new_30_registration.py` (#2805)
- [X] T008 Implement typed public-data models in `src/ummaya/tools/verified_data_go_kr/_models.py` (#2806)
- [X] T009 Implement fixture-safe JSON/XML parser helpers in `src/ummaya/tools/verified_data_go_kr/_parsing.py` (#2807)
- [X] T010 Implement shared HTTP param/client helpers in `src/ummaya/tools/verified_data_go_kr/_client.py` (#2808)
- [X] T011 Update `src/ummaya/tools/verified_data_go_kr/__init__.py` exports for shared helpers (#2809)

**Checkpoint**: Foundational parser/model tests fail before implementation and pass after T008-T011.

---

## Phase 3: User Story 1 - Discover Verified Public Service Adapters (Priority: P1) MVP

**Goal**: The routing surface exposes only the 14 direct-success verified adapters and excludes unauthorized/blocked candidates.

**Independent Test**: Run registration/search tests and verify all 14 included IDs are present while 30 newly scoped IDs are absent.

### Tests for User Story 1

- [X] T012 [P] [US1] Write failing adapter registration tests in `tests/tools/verified_data_go_kr/test_adapter_registration.py` (#2810)
- [X] T013 [P] [US1] Write failing routing/search tests in `tests/tools/verified_data_go_kr/test_verified_search.py` (#2811)

### Implementation for User Story 1

- [X] T014 [US1] Implement first representative adapter `bfc_funeral_area_fee` in `src/ummaya/tools/verified_data_go_kr/bfc_funeral_cost.py` (#2812)
- [X] T015 [US1] Register `bfc_funeral_area_fee` from `src/ummaya/tools/register_all.py` (#2813)
- [X] T016 [US1] Implement and register remaining verified adapter modules listed in `contracts/adapter-wave.md` (#2814)
- [X] T017 [US1] Update `docs/api/verified-data-go-kr/README.md` with the 14-adapter matrix and deferred exclusions (#2815)

**Checkpoint**: All 14 verified adapters are discoverable through registry/search; no unauthorized 30-candidate adapter is registered.

---

## Phase 4: User Story 2 - Fetch Read-Only Public Data Through `find` (Priority: P1)

**Goal**: Each verified adapter can parse fixture-backed upstream data and return a normalized `find` collection output without live network calls in CI.

**Independent Test**: Run fixture replay tests for JSON, XML, zero-result, and upstream error behavior.

### Tests for User Story 2

- [X] T018 [P] [US2] Write failing fixture replay tests in `tests/tools/verified_data_go_kr/test_adapter_fixture_replay.py` (#2816)
- [X] T019 [P] [US2] Write failing upstream error parsing tests in `tests/tools/verified_data_go_kr/test_error_parsing.py` (#2817)

### Implementation for User Story 2

- [X] T020 [US2] Add fixture-injected adapter call path to `src/ummaya/tools/verified_data_go_kr/_client.py` (#2818)
- [X] T021 [US2] Ensure all verified adapter modules normalize successful fixtures into `kind="collection"` outputs (#2819)
- [X] T022 [US2] Ensure parser/client errors produce fail-closed tool-domain exceptions with sanitized upstream codes (#2820)

**Checkpoint**: Fixture replay proves successful and error-path behavior without external API calls.

---

## Phase 5: User Story 3 - Maintain Evidence-Gated Scope (Priority: P2)

**Goal**: Maintainers can trace included adapters to saved direct-call evidence and deferred APIs to concrete blockers.

**Independent Test**: Run manifest/docs consistency tests against the live probe report and candidate manifest.

### Tests for User Story 3

- [X] T023 [P] [US3] Write failing evidence consistency tests in `tests/tools/verified_data_go_kr/test_evidence_consistency.py` (#2821)

### Implementation for User Story 3

- [X] T024 [US3] Add evidence path validation to `src/ummaya/tools/verified_data_go_kr/_manifest.py` (#2822)
- [X] T025 [US3] Update `docs/api/README.md` to link the verified data.go.kr adapter wave (#2823)
- [X] T026 [US3] Generate or update adapter schemas for the new verified adapters under `docs/api/schemas/` (#2824)

**Checkpoint**: Evidence consistency and docs/schema checks prove every included adapter is traceable.

---

## Phase 6: Polish & Validation

**Purpose**: Full verification, UMMAYA real-use smoke, and PR-ready evidence.

- [X] T027 Run `uv run ruff check src tests` and fix all reported issues (#2825)
- [X] T028 Run `uv run ruff format --check src tests` and fix all reported issues (#2826)
- [X] T029 Run `uv run mypy src` and fix all reported issues (#2827)
- [X] T030 Run `uv run pytest -m "not live"` and fix all reported issues (#2828)
- [X] T031 Run UMMAYA real-use smoke from `quickstart.md` with direct live adapter mode and record summary in `specs/2797-data-go-kr-verified-adapters/real-use-smoke.md` (#2829)
- [X] T032 Inspect real-use smoke output for abnormal flow, fabricated fallback, wrong adapter selection, permission misclassification, and debug until clean (#2830)
- [X] T033 Update `specs/2797-data-go-kr-verified-adapters/tasks.md` task checkboxes as each task completes (#2831)

---

## Dependencies & Execution Order

### Phase Dependencies

- Phase 1 has no dependencies.
- Phase 2 depends on Phase 1 and blocks all user stories.
- Phase 3 and Phase 4 both depend on Phase 2; execute Phase 3 first for registry visibility, then Phase 4 for fixture execution.
- Phase 5 depends on Phase 3 and Phase 4.
- Phase 6 depends on all user stories.

### User Story Dependencies

- US1: Starts after foundational helpers exist.
- US2: Starts after at least one representative adapter exists, then applies to all 14 adapters.
- US3: Starts after adapter set is known and fixture replay behavior is stable.

### Parallel Opportunities

- T005-T007 can run in parallel.
- T012-T013 can run in parallel.
- T018-T019 can run in parallel.
- Individual adapter modules inside T016 are parallel-safe by file, but Lead may execute them solo in this session.

## Implementation Strategy

### MVP First

1. Complete setup and foundational helpers.
2. Implement `bfc_funeral_area_fee` as the first representative verified adapter.
3. Prove discovery, fixture replay, and one real-use smoke.
4. Extend the same pattern to the remaining 13 verified adapters.

### Full Wave Completion

1. Complete all 14 adapter registrations.
2. Run fixture-only tests and full backend checks.
3. Run UMMAYA real-use smoke with at least 부산 장례비산출, AirKorea, and TAGO prompts.
4. Debug abnormal flow before PR.

## Notes

- Total tasks: 33, below the 90-task hard budget.
- No task may add a dependency.
- No task may call live public APIs from default tests.
- `tui/src/**` is not touched by this plan; PR should declare `TUI no-change`.
