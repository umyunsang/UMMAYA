# Tasks: Live MobileID Check Adapter

**Input**: Design documents from `/Users/um-yunsang/.codex/worktrees/281d/UMMAYA/specs/live-mobileid-check/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md), [dispatch-tree.md](./dispatch-tree.md)

**Tests**: Required. This is identity infrastructure and must be implemented with fixture-first TDD.

**Organization**: Tasks are grouped by user story and preserve RED/GREEN ordering. Implementation may only follow tasks listed here and materialized as GitHub task issues by `/speckit-taskstoissues`.

## Task Issues

| Issue | Covered Tasks |
|-------|---------------|
| #2910 | T004-T006 |
| #2908 | T007-T010 |
| #2909 | T011-T018 |
| #2912 | T019-T021 |
| #2911 | T022-T024 |
| #2913 | T025-T032 |

## Phase 1: Setup

**Purpose**: Lock scope, source references, and feature-artifact state.

- [X] T001 Confirm branch `feat/live-mobileid-check` and feature directory `specs/live-mobileid-check`
- [X] T002 Create Epic #2886 for `Live MobileID check adapter`
- [X] T003 Create Spec Kit plan artifacts: `plan.md`, `research.md`, `data-model.md`, `contracts/mobileid-check.md`, `quickstart.md`, and `dispatch-tree.md`

---

## Phase 2: Foundational TDD - MIP Envelope And Safe Error Boundary

**Purpose**: Prove the MobileID wire envelope and redaction behavior before any registry wiring.

- [X] T004 [P] [US1] Write failing MIP envelope encode/decode, malformed base64, non-object inner JSON, and redaction tests in `tests/unit/tools/test_mobileid_client.py`
- [X] T005 [US1] Implement `src/ummaya/tools/live/mobileid_client.py` with deterministic envelope encode/decode, sanitized upstream errors, status normalization, and recursive identity-field redaction
- [X] T006 [US1] Add `src/ummaya/tools/live/__init__.py` without importing network clients at module import time

**Checkpoint**: Client tests fail before T005 and pass after T005-T006.

---

## Phase 3: User Story 1 - Verify MobileID Presentation Without Persisting Raw Identity Data (Priority: P1)

**Goal**: Return a safe `MobileIdContext` from sanitized MobileID fixture responses.

**Independent Test**: Fixture-only adapter tests prove success output contains only typed context fields and excludes raw identity data.

### Tests for User Story 1

- [X] T007 [P] [US1] Write failing adapter success tests in `tests/unit/tools/test_verify_mobile_id_live_adapter.py` for sanitized `/mip/vp` and `/mip/trxsts` responses
- [X] T008 [P] [US1] Write failing output-redaction tests in `tests/unit/tools/test_verify_mobile_id_live_adapter.py` that scan serialized results for VP data, CI, DI, resident identifiers, phone numbers, names, and birthdate-like values

### Implementation for User Story 1

- [X] T009 [US1] Implement `src/ummaya/tools/live/verify_mobile_id.py` input models, fixture-testable handler, `MobileIdContext` construction, and no-raw-VP output behavior
- [X] T010 [US1] Run focused live-tool unit tests and debug until clean

---

## Phase 4: User Story 2 - Expose MobileID As An Explicit `check` Adapter (Priority: P1)

**Goal**: Make `live_verify_mobile_id` discoverable and callable as `check` without replacing existing mock MobileID or mock `modid` behavior.

**Independent Test**: Registry and stdio dispatch tests confirm explicit tool-id selection and mock preservation.

### Tests for User Story 2

- [X] T011 [P] [US2] Write failing registry/canonical-map tests in `tests/integration/test_live_mobileid_registration.py` for `live_verify_mobile_id` under `check`
- [X] T012 [P] [US2] Write failing verify-dispatch tests proving tool-id-specific live selection does not override `mock_verify_mobile_id` in `tests/unit/primitives/test_verify_family_mismatch.py`
- [X] T013 [P] [US2] Update failing stdio canonical-map expectations in `tests/unit/ipc/test_stdio_verify_dispatch.py`

### Implementation for User Story 2

- [X] T014 [US2] Extend `src/ummaya/primitives/verify.py` with additive tool-id-specific adapter registration and dispatch
- [X] T015 [US2] Pass selected `_verify_tool_id` through `src/ummaya/ipc/stdio.py`
- [X] T016 [US2] Register live MobileID in `src/ummaya/tools/register_all.py`, `src/ummaya/tools/discovery_bridge.py`, and `src/ummaya/tools/verify_canonical_map.py`
- [X] T017 [US2] Update registry-count assertions for the new tool and verify existing mock verify tests remain unchanged
- [X] T018 [US2] Run focused registry/stdio/verify tests and debug until clean

---

## Phase 5: User Story 3 - Fail Closed On Invalid, Expired, Or Malformed MobileID Evidence (Priority: P2)

**Goal**: Prove invalid or ambiguous MobileID evidence never returns a verified context and never falls back to mock behavior.

**Independent Test**: Negative tests cover missing `trxcode`, malformed envelope, upstream non-2xx, upstream failure, expired status, and unsupported status.

### Tests for User Story 3

- [X] T019 [P] [US3] Write failing negative tests for missing `trxcode`, malformed base64, upstream non-2xx, upstream `result=false`, expired status, and unsupported status

### Implementation for User Story 3

- [X] T020 [US3] Complete fail-closed exception mapping and sanitized messages in the client/adapter
- [X] T021 [US3] Run focused negative tests and debug until clean

---

## Phase 6: User Story 4 - Record Live Readiness Evidence Separately From CI (Priority: P2)

**Goal**: Document the live contract and add opt-in live tests that skip before network access by default.

**Independent Test**: Default non-live test commands never call MobileID, while explicit live tests require complete env credentials.

### Tests for User Story 4

- [X] T022 [P] [US4] Add `tests/live/test_live_mobileid.py` with `@pytest.mark.live` and pre-network env skip for `UMMAYA_MOBILEID_BASE_URL`, `UMMAYA_MOBILEID_CLIENT_ID`, and `UMMAYA_MOBILEID_TEST_TRXCODE`

### Implementation for User Story 4

- [X] T023 [US4] Add `docs/api/verify/live_verify_mobile_id.md` with official endpoints, env names, request/response envelope, live-test command, redaction rules, and sanitized curl-evidence template
- [X] T024 [US4] Run live-test deselection/skip checks and focused docs/fixture secret scan

---

## Phase 7: Polish & Validation

**Purpose**: Full backend validation, task bookkeeping, PR, and CI.

- [X] T025 Run `uv run ruff check src tests` and fix reported issues
- [X] T026 Run `uv run ruff format --check src tests` and fix formatting issues
- [X] T027 Run `uv run mypy src` and fix reported type issues
- [X] T028 Run `uv run pytest tests/unit/tools/test_mobileid_client.py tests/unit/tools/test_verify_mobile_id_live_adapter.py tests/integration/test_live_mobileid_registration.py tests/unit/primitives/test_verify_family_mismatch.py tests/unit/ipc/test_stdio_verify_dispatch.py -m "not live"` and fix failures
- [X] T029 Run `uv run pytest -m "not live"` and fix failures
- [X] T030 Run secret/PII scan over new MobileID code/docs/tests and remove any plaintext credential or identity occurrence
- [X] T031 Update `specs/live-mobileid-check/tasks.md` checkboxes and task issue links after completion
- [ ] T032 Open PR with body containing `Closes #2886` only for the Epic closure keyword, monitor `gh pr checks --watch --interval 10`, and fix CI failures until terminal state

## Dependencies & Execution Order

- Phase 1 has no remaining dependencies.
- Phase 2 blocks adapter implementation.
- US1 depends on Phase 2.
- US2 depends on US1 because registry wiring needs a callable adapter.
- US3 can run after the client and adapter exist.
- US4 can run after the adapter contract stabilizes.
- Phase 7 depends on all user stories.

## Parallel Opportunities

- T004 and T007-T008 are file-disjoint test authoring tasks.
- T011-T013 can be authored in parallel with clear file ownership.
- T019 and T022 are file-disjoint.
- Current run is Lead solo because no compatible explicit subagent/model dispatch was requested in this Codex session.

## Implementation Strategy

1. Finish RED/GREEN tests for envelope and redaction.
2. Add the live adapter and prove sanitized success output.
3. Add explicit tool-id dispatch and registry discovery.
4. Add fail-closed negative coverage.
5. Add docs and opt-in live test.
6. Run focused and full non-live verification before PR.

## Notes

- Total tasks: 32.
- No task touches `tui/src/**`.
- No task changes `find`, `locate`, or `send`.
- Live readiness requires sanitized direct-call evidence from a credentialed operator environment before any readiness claim.
