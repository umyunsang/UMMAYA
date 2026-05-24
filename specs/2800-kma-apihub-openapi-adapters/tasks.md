# Tasks: KMA APIHub OpenAPI Adapters

**Input**: Design documents from `/Users/um-yunsang/UMMAYA/specs/2800-kma-apihub-openapi-adapters/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Required by FR-011 and the adapter contract. Test tasks are listed before implementation tasks for each user story.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested independently.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare source, fixture, and documentation locations without changing runtime behavior.

- [X] T001 Verify current dirty worktree scope and record owned paths for this feature in `/Users/um-yunsang/UMMAYA/specs/2800-kma-apihub-openapi-adapters/implementation-notes.md`
- [X] T002 [P] Create KMA APIHub fixture directory and placeholder README in `/Users/um-yunsang/UMMAYA/tests/tools/kma/fixtures/apihub/README.md`
- [X] T003 [P] Add structured adapter documentation stub in `/Users/um-yunsang/UMMAYA/docs/api/kma/apihub_structured_adapters.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core catalog and shared execution pieces that all user stories depend on.

**CRITICAL**: No user story implementation can start until these shared pieces are ready.

- [X] T004 Write failing catalog count/id/approval-state tests in `/Users/um-yunsang/UMMAYA/tests/tools/kma/test_apihub_catalog.py`
- [X] T005 Write failing APIHub endpoint resolver tests in `/Users/um-yunsang/UMMAYA/tests/tools/kma/test_apihub_endpoint.py`
- [X] T006 Write failing structured adapter fixture/authorization tests in `/Users/um-yunsang/UMMAYA/tests/tools/kma/test_apihub_structured_adapter.py`
- [X] T007 Implement typed KMA APIHub operation metadata catalog in `/Users/um-yunsang/UMMAYA/src/ummaya/tools/kma/apihub_catalog.py`
- [X] T008 Implement shared KMA APIHub endpoint and credential resolver in `/Users/um-yunsang/UMMAYA/src/ummaya/tools/kma/apihub_endpoint.py`
- [X] T009 Implement shared structured APIHub response normalization helpers in `/Users/um-yunsang/UMMAYA/src/ummaya/tools/kma/apihub_structured_adapter.py`
- [X] T010 Add representative XML/JSON/error fixtures in `/Users/um-yunsang/UMMAYA/tests/tools/kma/fixtures/apihub/`

**Checkpoint**: Catalog, endpoint resolver, and response normalization tests fail for expected missing implementation or pass after implementation.

---

## Phase 3: User Story 1 - Complete KMA Catalog Coverage (Priority: P1) MVP

**Goal**: Every structured KMA APIHub `typ02/openApi` operation is represented in UMMAYA's catalog with stable metadata.

**Independent Test**: Run `uv run pytest /Users/um-yunsang/UMMAYA/tests/tools/kma/test_apihub_catalog.py` and confirm exactly 85 structured operations, no duplicate tool ids, and explicit approval states.

### Tests for User Story 1

- [X] T011 [US1] Extend catalog tests for 85-operation category distribution in `/Users/um-yunsang/UMMAYA/tests/tools/kma/test_apihub_catalog.py`
- [X] T012 [US1] Extend catalog tests for operation parameter shape examples in `/Users/um-yunsang/UMMAYA/tests/tools/kma/test_apihub_catalog.py`

### Implementation for User Story 1

- [X] T013 [US1] Populate all 85 structured operations in `/Users/um-yunsang/UMMAYA/src/ummaya/tools/kma/apihub_catalog.py`
- [X] T014 [US1] Add approval-state metadata for currently approved and pending operations in `/Users/um-yunsang/UMMAYA/src/ummaya/tools/kma/apihub_catalog.py`
- [X] T015 [US1] Cross-link catalog documentation to evidence in `/Users/um-yunsang/UMMAYA/docs/api/kma/apihub_structured_adapters.md`

**Checkpoint**: User Story 1 is complete when the catalog test proves full coverage and docs identify the official evidence file.

---

## Phase 4: User Story 2 - Safe Citizen Weather Lookup Expansion (Priority: P2)

**Goal**: Structured KMA APIHub operations can be registered and invoked through the existing read-only tool path without breaking specialized current-weather and forecast tools.

**Independent Test**: Run structured adapter tests plus existing KMA weather tests and verify fixture-backed success, authorization failure, and existing weather behavior.

### Tests for User Story 2

- [X] T016 [US2] Extend structured adapter tests for generated Pydantic input schemas in `/Users/um-yunsang/UMMAYA/tests/tools/kma/test_apihub_structured_adapter.py`
- [X] T017 [US2] Extend structured adapter tests for XML/default and JSON fixture decoding in `/Users/um-yunsang/UMMAYA/tests/tools/kma/test_apihub_structured_adapter.py`
- [X] T018 [US2] Extend structured adapter tests for registry and executor binding in `/Users/um-yunsang/UMMAYA/tests/tools/kma/test_apihub_structured_adapter.py`
- [X] T019 [US2] Add regression coverage that existing specialized KMA adapter ids remain registered in `/Users/um-yunsang/UMMAYA/tests/tools/kma/test_apihub_structured_adapter.py`

### Implementation for User Story 2

- [X] T020 [US2] Implement generated `GovAPITool` construction for catalog operations in `/Users/um-yunsang/UMMAYA/src/ummaya/tools/kma/apihub_structured_adapter.py`
- [X] T021 [US2] Implement structured operation executor binding in `/Users/um-yunsang/UMMAYA/src/ummaya/tools/kma/apihub_structured_adapter.py`
- [X] T022 [US2] Register structured APIHub tools in `/Users/um-yunsang/UMMAYA/src/ummaya/tools/register_all.py`
- [X] T023 [US2] Export public structured adapter symbols in `/Users/um-yunsang/UMMAYA/src/ummaya/tools/kma/__init__.py`
- [X] T024 [US2] Update KMA docs index entries in `/Users/um-yunsang/UMMAYA/docs/api/README.md`

**Checkpoint**: User Story 2 is complete when structured tools register, fixture invocation works, and existing KMA weather tests still pass.

---

## Phase 5: User Story 3 - Approval-Aware Adapter Operations (Priority: P3)

**Goal**: Runtime and docs distinguish APIHub key presence from per-operation utilization approval.

**Independent Test**: Run endpoint and structured adapter tests and confirm missing key, wrong provider key, and approval-pending states fail closed without secret leakage.

### Tests for User Story 3

- [X] T025 [US3] Extend endpoint tests for missing key and data.go.kr key rejection in `/Users/um-yunsang/UMMAYA/tests/tools/kma/test_apihub_endpoint.py`
- [X] T026 [US3] Extend structured adapter tests for approval-pending authorization error messages in `/Users/um-yunsang/UMMAYA/tests/tools/kma/test_apihub_structured_adapter.py`
- [X] T027 [US3] Add credential-provider mapping tests for structured KMA APIHub tools in `/Users/um-yunsang/UMMAYA/tests/permissions/test_credentials.py`

### Implementation for User Story 3

- [X] T028 [US3] Add structured KMA APIHub credential provider mapping in `/Users/um-yunsang/UMMAYA/src/ummaya/permissions/credentials.py`
- [X] T029 [US3] Add approval-state fail-closed messaging in `/Users/um-yunsang/UMMAYA/src/ummaya/tools/kma/apihub_structured_adapter.py`
- [X] T030 [US3] Document approval-state operations in `/Users/um-yunsang/UMMAYA/docs/api/kma/apihub_structured_adapters.md`

**Checkpoint**: User Story 3 is complete when approval-pending behavior is visible in tests and documentation without exposing secrets.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate the full feature and update generated schema/docs surfaces.

- [X] T031 [P] Update API schema generation expectations in `/Users/um-yunsang/UMMAYA/docs/api/schemas/` if structured tools are exported there
- [X] T032 [P] Update feature quickstart evidence with final test commands in `/Users/um-yunsang/UMMAYA/specs/2800-kma-apihub-openapi-adapters/quickstart.md`
- [X] T033 Run focused validation: `uv run pytest tests/tools/kma/test_apihub_catalog.py tests/tools/kma/test_apihub_endpoint.py tests/tools/kma/test_apihub_structured_adapter.py`
- [X] T034 Run regression validation: `uv run pytest tests/tools/kma/test_kma_current_observation.py tests/tools/kma/test_kma_short_term_forecast.py tests/tools/kma/test_kma_ultra_short_term_forecast.py tests/tools/kma/test_vilage_fcst_endpoint.py`
- [X] T035 Run formatting/lint validation for touched Python files with `uv run ruff check` and `uv run ruff format --check`
- [X] T036 Update `/Users/um-yunsang/UMMAYA/specs/2800-kma-apihub-openapi-adapters/implementation-notes.md` with final evidence and unresolved approval limits

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup completion and blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational; delivers catalog coverage MVP.
- **User Story 2 (Phase 4)**: Depends on Foundational and can begin after catalog shape stabilizes.
- **User Story 3 (Phase 5)**: Depends on Foundational and can run after approval-state fields exist.
- **Polish (Phase 6)**: Depends on all selected user stories.

### User Story Dependencies

- **US1**: No dependency on US2/US3 after Foundational.
- **US2**: Depends on catalog data from US1 for complete 85-operation registration.
- **US3**: Depends on approval-state metadata from US1 and executor behavior from US2.

### Parallel Opportunities

- T002 and T003 can run in parallel.
- T031 and T032 can run in parallel after implementation.
- Test authoring tasks that edit the same file are sequential even if conceptually independent.

## Dispatch Tree

Phase 1 Setup (T001-T003): Lead solo
Phase 2 Foundational (T004-T010): Lead solo because shared files are tightly coupled
Phase 3 US1 (T011-T015): Lead solo
Phase 4 US2 (T016-T024): Lead solo; shared structured adapter file prevents safe parallelism
Phase 5 US3 (T025-T030): Lead solo
Phase 6 Polish (T031-T036): Lead solo

Reason: The feature has many conceptual operations but only a few shared source files. Parallel agents would contend on the same files and increase merge risk.

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Setup and Foundational tasks.
2. Complete US1 catalog coverage.
3. Validate that all 85 operations are represented and approval state is explicit.

### Incremental Delivery

1. US1: catalog coverage.
2. US2: generated tool registration and fixture execution.
3. US3: approval-aware failure behavior.
4. Polish: docs/schema validation and regression checks.

## Notes

- Total tasks: 36, under the 90-task cap.
- No default task may call live KMA APIHub, data.go.kr, or another citizen-infrastructure API.
- Live validation for unapproved operations remains deferred until APIHub approvals exist.
