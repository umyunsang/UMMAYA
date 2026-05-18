# Tasks: Live KB Identity Check Adapter

**Input**: Design documents from `/Users/um-yunsang/.codex/worktrees/3340/UMMAYA/specs/live-kbcert-identity-check/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)
**Epic**: #2888

**Tests**: Required. Follow TDD: write failing tests before production implementation.

**Organization**: Tasks are grouped by user story and preserve RED/GREEN ordering.

## Phase 1: Setup

**Purpose**: Add fixture/test scaffolding without production behavior.

- [X] T001 [P] Create sanitized KB fixture payloads in `tests/fixtures/kbcert/request_success.json`, `tests/fixtures/kbcert/result_success.json`, `tests/fixtures/kbcert/result_failed.json`, and `tests/fixtures/kbcert/result_mismatch.json`
- [X] T002 [P] Create failing client tests for header/body construction, response parsing, failure mapping, and recursive redaction in `tests/unit/tools/live/test_kb_identity_client.py`
- [X] T003 [P] Create failing adapter and registry tests for `live_verify_kb_identity`, `kb_identity` family dispatch, and mock adapter non-regression in `tests/unit/tools/live/test_verify_kb_identity.py`
- [X] T004 [P] Create skipped-by-default live smoke tests requiring `UMMAYA_KBCERT_*` credentials in `tests/live/test_live_kb_identity.py`

---

## Phase 2: Foundational

**Purpose**: Add the typed check family needed before the live adapter can return a valid AuthContext.

- [X] T005 Add `kb_identity_aal2` tier support to `src/ummaya/tools/registry.py` and `src/ummaya/tools/models.py`
- [X] T006 Add `KbIdentityContext` and `kb_identity` family support to `src/ummaya/primitives/verify.py`

**Checkpoint**: T002/T003 should still fail because client and adapter implementation do not exist yet, but type imports for `KbIdentityContext` should resolve.

---

## Phase 3: User Story 1 - Start KB Identity Check (Priority: P1)

**Goal**: Build the KB client request path and return opaque transaction references.

**Independent Test**: `uv run pytest tests/unit/tools/live/test_kb_identity_client.py::test_request_body_and_headers_are_constructed_without_identity_fields tests/unit/tools/live/test_verify_kb_identity.py::test_request_mode_returns_kb_identity_context -m "not live"`

### Tests for User Story 1

- [X] T007 [US1] Run T002/T003 request-mode tests and confirm they fail for missing `ummaya.tools.live.kb_identity_client` and `live_verify_kb_identity` implementation

### Implementation for User Story 1

- [X] T008 [US1] Implement `src/ummaya/tools/live/kb_identity_client.py` request body/header construction and request-response parsing
- [X] T009 [US1] Implement request mode in `src/ummaya/tools/live/verify_kb_identity.py` and package import in `src/ummaya/tools/live/__init__.py`
- [X] T010 [US1] Run request-mode focused tests and debug until green

---

## Phase 4: User Story 2 - Poll KB Identity Result Safely (Priority: P2)

**Goal**: Parse result lookup fixtures, recognize successful identity evidence, and drop all identity payload values.

**Independent Test**: `uv run pytest tests/unit/tools/live/test_kb_identity_client.py tests/unit/tools/live/test_verify_kb_identity.py -m "not live"`

### Tests for User Story 2

- [X] T011 [US2] Run T002/T003 result-mode, redaction, failed-status, missing-identifier, and mismatched-transaction tests and confirm they fail before implementation

### Implementation for User Story 2

- [X] T012 [US2] Extend `src/ummaya/tools/live/kb_identity_client.py` with result lookup parsing, status validation, mismatch detection, non-2xx handling, timeout handling, and recursive redaction
- [X] T013 [US2] Extend `src/ummaya/tools/live/verify_kb_identity.py` result mode and sanitized `VerifyMismatchError` conversion
- [X] T014 [US2] Run result/redaction focused tests and debug until green

---

## Phase 5: User Story 3 - Discover KB Check as an Explicit Tool (Priority: P3)

**Goal**: Make `live_verify_kb_identity` discoverable as a non-core `check` adapter without changing BaroCert, MobileID, or mock behavior.

**Independent Test**: `uv run pytest tests/unit/tools/live/test_verify_kb_identity.py tests/unit/test_verify_canonical_map_parser.py tests/integration/test_discovery_bridge_path_b.py -m "not live"`

### Tests for User Story 3

- [X] T015 [US3] Run registry/canonical-map tests and confirm they fail before discovery registration updates

### Implementation for User Story 3

- [X] T016 [US3] Register live check discovery metadata in `src/ummaya/tools/discovery_bridge.py`, `src/ummaya/tools/verify_canonical_map.py`, `src/ummaya/tools/mvp_surface.py`, and `src/ummaya/tools/register_all.py`
- [X] T017 [US3] Update registry count and canonical-map tests for the additive live KB adapter in `tests/integration/test_discovery_bridge_path_b.py`, `tests/ipc/test_stdio_verify_dispatch.py`, and `tests/unit/test_verify_canonical_map_parser.py`
- [X] T018 [US3] Run discovery/registry focused tests and debug until green

---

## Phase 6: Documentation and Live Evidence Guardrails

**Purpose**: Document official KB contract and keep credentialed evidence out of default CI.

- [X] T019 [P] Add adapter documentation in `docs/api/verify/live-kb-identity.md` citing official KB source pages and sanitized curl evidence requirements
- [X] T020 [P] Ensure `tests/live/test_live_kb_identity.py` uses `@pytest.mark.live` and skips unless all required `UMMAYA_KBCERT_*` variables are present

---

## Phase 7: Polish & Validation

**Purpose**: Verify default no-live behavior and task completion.

- [X] T021 Run `uv run pytest tests/unit/tools/live/test_kb_identity_client.py tests/unit/tools/live/test_verify_kb_identity.py -m "not live"` and fix failures
- [X] T022 Run `uv run pytest tests/unit/test_verify_canonical_map_parser.py tests/integration/test_discovery_bridge_path_b.py tests/ipc/test_stdio_verify_dispatch.py -m "not live"` and fix failures
- [X] T023 Run `uv run pytest tests/live/test_live_kb_identity.py -m "not live"` and confirm live tests do not call KB by default
- [X] T024 Run `uv run ruff check src/ummaya/primitives/verify.py src/ummaya/tools/live tests/unit/tools/live tests/live/test_live_kb_identity.py` and fix issues
- [X] T025 Run `uv run ruff format --check src/ummaya/primitives/verify.py src/ummaya/tools/live tests/unit/tools/live tests/live/test_live_kb_identity.py` and fix issues
- [X] T026 Run `uv run mypy src/ummaya/primitives/verify.py src/ummaya/tools/live` and fix type issues
- [X] T027 Run `uv run pytest -m "not live"` if focused suites are clean and fix feature-related failures
- [X] T028 Update `specs/live-kbcert-identity-check/tasks.md` checkboxes as tasks complete

## Dependencies & Execution Order

- Phase 1 has no dependencies.
- Phase 2 depends on Phase 1 tests existing.
- US1 depends on Phase 2.
- US2 depends on US1 client/adapter structure.
- US3 depends on US1 and US2 because discovery should point to a working adapter.
- Phase 6 can run after US1/US2 data shapes are stable.
- Phase 7 depends on all user stories.

## Parallel Opportunities

- T001-T004 are file-disjoint and parallel-safe.
- T019-T020 are file-disjoint after implementation stabilizes.
- Implementation tasks touching shared registry or verify files must run sequentially in this branch.

## Implementation Strategy

1. Write fixtures and failing tests.
2. Add the typed `kb_identity` AuthContext.
3. Implement the KB client and adapter request mode.
4. Extend result parsing and redaction.
5. Wire discovery/canonical-map registration.
6. Add docs and live smoke guardrails.
7. Run focused suites, then broader non-live tests.

## Notes

- Total tasks: 28, below the 90-task budget.
- This branch intentionally avoids BaroCert, MobileID, and Government24 submit implementation files.
- Default tests must not call KB live endpoints.
