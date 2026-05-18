# Tasks: Live BaroCert Identity Check

**Input**: Design documents from `specs/live-barocert-identity-check/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/
**Tests**: Required. Use TDD: write tests first, confirm RED, then implement.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish feature package, fixtures, and docs scaffold.

- [X] T001 (#2924) Create live tools package scaffold in `src/ummaya/tools/live/__init__.py`
- [X] T002 (#2925) [P] Add sanitized BaroCert fixture files in `tests/fixtures/barocert/`
- [X] T003 (#2926) [P] Add adapter docs scaffold in `docs/api/verify/live_verify_ganpyeon_injeung.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Provider client models and redaction helpers needed by all stories.

- [X] T004 (#2927) [P] [US1] Write failing provider model and redaction tests in `tests/unit/tools/live/test_barocert_identity_client.py`
- [X] T005 (#2928) [US1] Implement provider models and redaction helpers in `src/ummaya/tools/live/barocert_identity_client.py`
- [X] T006 (#2929) [P] [US1] Write failing Toss fixture parsing tests in `tests/unit/tools/live/test_barocert_identity_client.py`
- [X] T007 (#2930) [US1] Implement Toss request/status/verify fixture parsing in `src/ummaya/tools/live/barocert_identity_client.py`

**Checkpoint**: Provider client parses sanitized fixtures and redacts sensitive fields.

---

## Phase 3: User Story 1 - Toss-backed identity check (Priority: P1) MVP

**Goal**: Explicit live tool id returns a redacted `GanpyeonInjeungContext`.

**Independent Test**: Direct adapter unit tests produce a context for a complete
Toss fixture and fail closed for incomplete or malformed provider states.

### Tests for User Story 1

- [X] T008 (#2931) [P] [US1] Write failing live adapter context tests in `tests/unit/tools/live/test_verify_barocert_identity.py`
- [X] T009 (#2932) [P] [US1] Write failing negative-path tests in `tests/unit/tools/live/test_verify_barocert_identity.py`

### Implementation for User Story 1

- [X] T010 (#2933) [US1] Implement `live_verify_ganpyeon_injeung` adapter in `src/ummaya/tools/live/verify_barocert_identity.py`
- [X] T011 (#2934) [US1] Preserve selected check `tool_id` in session context in `src/ummaya/ipc/stdio.py`

**Checkpoint**: Explicit live adapter path works through direct unit tests.

---

## Phase 4: User Story 2 - Provider variants and discovery metadata (Priority: P2)

**Goal**: The client and registry expose Toss live plus Kakao/Naver fixture variants.

**Independent Test**: Registry and mapping tests prove the live tool is
discoverable under `check` and maps to `ganpyeon_injeung` without breaking mock
tool ids.

### Tests for User Story 2

- [X] T012 (#2935) [P] [US2] Write failing provider selection tests in `tests/unit/tools/live/test_barocert_identity_client.py`
- [X] T013 (#2936) [P] [US2] Write failing registry and mapping tests in `tests/integration/test_live_barocert_discovery.py` and `tests/integration/test_tool_id_to_family_hint_translation.py`

### Implementation for User Story 2

- [X] T014 (#2937) [US2] Add live check metadata to `src/ummaya/tools/discovery_bridge.py` and `src/ummaya/tools/verify_canonical_map.py`
- [X] T015 (#2938) [US2] Import/register live BaroCert adapter from `src/ummaya/tools/register_all.py`

**Checkpoint**: Live tool id is discoverable; existing mock ids still resolve.

---

## Phase 5: User Story 3 - Live validation and documentation (Priority: P3)

**Goal**: Live tests are opt-in and docs state credential/redaction boundaries.

**Independent Test**: Live test skips without env and default non-live tests do
not touch BaroCert.

### Tests for User Story 3

- [X] T016 (#2939) [P] [US3] Add live skip-gated test in `tests/live/test_live_barocert_identity.py`
- [X] T017 (#2940) [P] [US3] Add or update no-live-network regression coverage for BaroCert in `tests/agents/test_zero_live_api.py`

### Implementation for User Story 3

- [X] T018 (#2941) [US3] Complete BaroCert live adapter documentation in `docs/api/verify/live_verify_ganpyeon_injeung.md`

**Checkpoint**: Live validation is opt-in and documented.

---

## Final Phase: Polish & Cross-Cutting Concerns

**Purpose**: Verification and PR readiness.

- [X] T019 (#2942) Run targeted non-live BaroCert and verify-registry tests
- [X] T020 (#2943) Run `uv run pytest -m "not live"` or document any pre-existing blocker
- [ ] T021 (#2944) Open PR with `Closes #2887` only and monitor CI with `gh pr checks --watch --interval 10`

---

## Dependencies & Execution Order

### Phase Dependencies

- Phase 1 has no dependencies.
- Phase 2 depends on fixture scaffold from Phase 1.
- Phase 3 depends on provider client models and parsing from Phase 2.
- Phase 4 depends on adapter implementation from Phase 3.
- Phase 5 depends on adapter and registry behavior from Phases 3-4.
- Final verification depends on all selected user stories.

### Parallel Opportunities

- T002 and T003 can run in parallel.
- T004 and T006 can be authored together before T005/T007 implementation.
- T008 and T009 can run in parallel after the client foundation exists.
- T012 and T013 can run in parallel.
- T016 and T017 can run in parallel after adapter registration exists.

### Implementation Strategy

1. MVP first: complete T001-T011 so Toss fixture verification returns a redacted context.
2. Add discovery and provider variants: complete T012-T015.
3. Add live skip-gated validation and docs: complete T016-T018.
4. Run T019-T021 before reporting completion.
