---

description: "Tasks: P6 · Docs/API specs + Integration smoke (Epic #1637)"
---

# Tasks: P6 · Docs/API specs + Integration smoke

**Input**: Design documents from `/specs/1637-p6-docs-smoke/`
**Prerequisites**: spec.md, plan.md, research.md, data-model.md, contracts/, quickstart.md
**Parent Epic**: #1637
**Issue range**: Tasks T001–T044 → #1928–#1971 · Deferred D1–D5 → #1972–#1976 (49 sub-issues of #1637)

**Tests**: Tests are NOT explicitly requested by the user; this Epic's verification is via spec FR-010 (`bun test` recovery) and FR-013 (visual smoke). No new test-task tasks beyond fixing existing failures.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing. US1 is the MVP target; US2 gates the release; US3 is the consistency cleanup.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks).
- **[Story]**: Maps to a user story in spec.md (US1, US2, US3).
- File paths are absolute relative to repo root.

## Path Conventions

KOSMOS monorepo:

- Backend: `src/kosmos/**`
- TUI: `tui/**`
- Docs: `docs/**`
- Scripts: `scripts/**`
- Spec: `specs/1637-p6-docs-smoke/**`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: directory tree for the new `docs/api/` catalog.

- [ ] T001 Create `docs/api/` directory tree per plan.md "Source Code (repository root)" section: `docs/api/{koroad,kma,hira,nmc,nfa119,mohw,verify,submit,resolve_location,schemas}/` (use `mkdir -p`); leave directories empty pending US1 spec authoring.

---

## Phase 2: Foundational

**Purpose**: blocking prerequisites before any user story implementation.

(none — P6 has no foundational tasks beyond Phase 1; the Pydantic envelope source is already canonical from Specs 1632–1634, and the spec template is finalized in `specs/1637-p6-docs-smoke/contracts/adapter-spec-template.md`.)

**Checkpoint**: foundation ready — user story implementation can begin.

---

## Phase 3: User Story 1 — Citizen developer discovers and understands every registered KOSMOS adapter from a single index (Priority: P1) 🎯 MVP

**Goal**: produce the canonical `docs/api/` catalog for active adapters, JSON Schema exports, 1 root index, 1 deterministic build script, and absorb the legacy `docs/tools/` directory. Subscribe specs are deferred until an app/push-notification runtime exists.

**Independent Test**: a contributor opens `docs/api/README.md` cold and locates any active adapter spec in under 30 seconds with all seven mandatory fields populated and a Draft 2020-12 JSON Schema present (per `specs/1637-p6-docs-smoke/quickstart.md`).

### Implementation for User Story 1

#### Build script (acceptance gate for SC-002)

- [ ] T002 [US1] Implement `scripts/build_schemas.py` per `specs/1637-p6-docs-smoke/contracts/build-schemas-cli.md`: walks `kosmos.tools.register_all`, calls `Model.model_json_schema(mode='validation', ref_template='#/$defs/{model}')` per envelope, wraps with Draft 2020-12 `$schema` + `$id` + `title` + `$defs`, writes deterministically with `json.dumps(..., sort_keys=True, indent=2, ensure_ascii=False)`, supports `--check` / `--output-dir` / `--quiet` flags. Stdlib + Pydantic v2 only.
- [ ] T003 [US1] Run `python scripts/build_schemas.py --output-dir docs/api/schemas` to generate active JSON files; verify `python scripts/build_schemas.py --check` returns exit 0 (idempotency gate per FR-007 / SC-002). Depends on T002.

#### Live tier adapter specs (12 — parallel by file)

- [ ] T004 [P] [US1] Author `docs/api/koroad/accident_search.md` for `koroad_accident_search` per `contracts/adapter-spec-template.md` (7 sections + YAML front matter); cite envelope at `src/kosmos/tools/koroad/koroad_accident_search.py`.
- [ ] T005 [P] [US1] Author `docs/api/koroad/accident_hazard_search.md` for `koroad_accident_hazard_search`; cite envelope at `src/kosmos/tools/koroad/accident_hazard_search.py`.
- [ ] T006 [P] [US1] Author `docs/api/kma/current_observation.md` for `kma_current_observation`; cite envelope at `src/kosmos/tools/kma/kma_current_observation.py`.
- [ ] T007 [P] [US1] Author `docs/api/kma/short_term_forecast.md` for `kma_short_term_forecast`; cite envelope at `src/kosmos/tools/kma/kma_short_term_forecast.py`.
- [ ] T008 [P] [US1] Author `docs/api/kma/ultra_short_term_forecast.md` for `kma_ultra_short_term_forecast`; cite envelope at `src/kosmos/tools/kma/kma_ultra_short_term_forecast.py`.
- [ ] T009 [P] [US1] Author `docs/api/kma/weather_alert_status.md` for `kma_weather_alert_status`; cite envelope at `src/kosmos/tools/kma/kma_weather_alert_status.py`.
- [ ] T010 [P] [US1] Author `docs/api/kma/pre_warning.md` for `kma_pre_warning`; cite envelope at `src/kosmos/tools/kma/kma_pre_warning.py`.
- [ ] T011 [P] [US1] Author `docs/api/kma/forecast_fetch.md` for `kma_forecast_fetch`; cite envelope at `src/kosmos/tools/kma/forecast_fetch.py`.
- [ ] T012 [P] [US1] Author `docs/api/hira/hospital_search.md` for `hira_hospital_search`; cite envelope at `src/kosmos/tools/hira/hospital_search.py`.
- [ ] T013 [P] [US1] Author `docs/api/nmc/emergency_search.md` for `nmc_emergency_search` (Layer 3 gated; document both auth-required and unauthenticated paths) and inline-document the freshness sub-tool from `src/kosmos/tools/nmc/freshness.py`.
- [ ] T014 [P] [US1] Author `docs/api/nfa119/emergency_info_service.md` for `nfa_emergency_info_service`; cite envelope at `src/kosmos/tools/nfa119/emergency_info_service.py`.
- [ ] T015 [P] [US1] Author `docs/api/mohw/welfare_eligibility_search.md` for `mohw_welfare_eligibility_search`; cite envelope at `src/kosmos/tools/ssis/welfare_eligibility_search.py`.

#### Mock verify adapter specs (6 — parallel by file)

- [ ] T016 [P] [US1] Author `docs/api/verify/digital_onepass.md` for `mock_verify_digital_onepass`; cite envelope at `src/kosmos/tools/mock/verify_digital_onepass.py`; declare "Fixture-replay only" + cite public-spec source per memory `feedback_mock_evidence_based`.
- [ ] T017 [P] [US1] Author `docs/api/verify/mobile_id.md` for `mock_verify_mobile_id`; cite envelope at `src/kosmos/tools/mock/verify_mobile_id.py`; cite public-spec source.
- [ ] T018 [P] [US1] Author `docs/api/verify/gongdong_injeungseo.md` for `mock_verify_gongdong_injeungseo`; cite envelope at `src/kosmos/tools/mock/verify_gongdong_injeungseo.py`; cite public-spec source.
- [ ] T019 [P] [US1] Author `docs/api/verify/geumyung_injeungseo.md` for `mock_verify_geumyung_injeungseo`; cite envelope at `src/kosmos/tools/mock/verify_geumyung_injeungseo.py`; cite public-spec source.
- [ ] T020 [P] [US1] Author `docs/api/verify/ganpyeon_injeung.md` for `mock_verify_ganpyeon_injeung`; cite envelope at `src/kosmos/tools/mock/verify_ganpyeon_injeung.py`; cite public-spec source.
- [ ] T021 [P] [US1] Author `docs/api/verify/mydata.md` for `mock_verify_mydata`; cite envelope at `src/kosmos/tools/mock/verify_mydata.py`; cite public-spec source.

#### Mock submit adapter specs (2 — parallel by file)

- [ ] T022 [P] [US1] Author `docs/api/submit/traffic_fine_pay.md` for `mock_traffic_fine_pay_v1`; cite envelope at `src/kosmos/tools/mock/data_go_kr/fines_pay.py`; cite public-spec source.
- [ ] T023 [P] [US1] Author `docs/api/submit/welfare_application.md` for `mock_welfare_application_submit_v1`; cite envelope at `src/kosmos/tools/mock/mydata/welfare_application.py`; cite public-spec source.

#### Meta-tool spec

- [ ] T027 [P] [US1] Author `docs/api/resolve_location/index.md` describing the `resolve_location` meta-tool with juso / sgis / kakao backends as variants; cite `src/kosmos/tools/resolve_location.py` plus the three backend modules under `src/kosmos/tools/geocoding/`.

#### Index, migration, audit (sequential after specs land)

- [ ] T028 [US1] Author `docs/api/README.md` AdapterIndex per data-model.md § 2: introduction paragraph + Matrix A (by source) + Matrix B (by primitive) + "How to use this catalog" 3-step recipe; every row links to the AdapterSpec and the JSON Schema. Depends on T003 (schemas exist) and T004–T027 (specs exist).
- [ ] T029 [US1] Migrate legacy `docs/tools/` content into `docs/api/` per research.md § R5 mapping; delete `docs/tools/road-risk-score.md`; merge `docs/tools/kma.md` into `docs/api/kma/README.md`; merge `docs/tools/koroad.md` into `docs/api/koroad/README.md`; merge `docs/tools/README.md` into `docs/api/README.md` (as "How to use this catalog" reference). After migration, remove `docs/tools/` so SC-006 verification (`test ! -d docs/tools`) passes. Depends on T028.
- [ ] T030 [US1] Manual review pass over all active specs verifying the seven-section template (per contracts/adapter-spec-template.md lint rules) and run the SC-007 30-second cold-read self-test (per quickstart.md). Record findings in `specs/1637-p6-docs-smoke/spec-review-notes.md`. Depends on T029.

**Checkpoint**: at this point US1 is fully functional and testable independently — the active adapter catalog is browsable, the JSON Schemas validate, and `docs/tools/` is gone.

---

## Phase 4: User Story 2 — Release validator confirms KOSMOS v0.1-alpha is integration-ready before tagging (Priority: P1)

**Goal**: recover `bun test` to 0 fail / 0 errors and capture a hand-driven `bun run tui` smoke run with ANSI evidence covering all 18 documented states.

**Independent Test**: on a clean checkout, `bun test` finishes with 0 fail and 0 errors, and `bun run tui` walks through all 18 smoke-checklist rows without crash, with each row backed by an `ansi.txt` + `txt` evidence pair.

### Implementation for User Story 2

- [ ] T031 [US2] Fix `tui/src/hooks/useVirtualScroll.ts:273` `new Set(itemKeys)` Set-constructor type error per research.md § R7: apply minimal nullish-coalescing fix `new Set(itemKeys ?? [])` (or hoist signature to widen `itemKeys` to `ReadonlyArray<K>`); do NOT modify the `tui/tests/components/conversation/overflowToBackbuffer.test.tsx` test contract per FR-011.
- [ ] T032 [US2] Triage and fix the remaining `bun test` failures: parse `bun test` output, classify each failure as (a) regression to fix, (b) CC-port no longer applicable to delete with rationale, or (c) deliberate behavior change requiring expectation update. Record the classification log in `specs/1637-p6-docs-smoke/test-triage.md` (per FR-012). Apply fixes file-by-file; verification: final `bun test` reports 0 fail / 0 errors / ≥ 830 total (FR-010 / SC-003). Depends on T031.
- [ ] T033 [US2] Drive the active smoke checklist per `specs/1637-p6-docs-smoke/contracts/smoke-checklist-template.md` against `bun run tui`: capture `<step-id>.ansi.txt` via `script(1)` and produce paired `<step-id>.txt` via `sed` for each row (onboarding + active primitive + slash + error + PDF). Save to `specs/1637-p6-docs-smoke/visual-evidence/`. Author the populated `specs/1637-p6-docs-smoke/smoke-checklist.md` recording pass/fail per row plus the bun-test summary line. Depends on T032 (need green tests for stable TUI).

**Checkpoint**: at this point US2 is fully verified and the release gate is open.

---

## Phase 5: User Story 3 — Maintainer confirms zero residual references to the removed composite tool (Priority: P2)

**Goal**: clean up the 5 non-`docs/tools/` documentation locations that still describe the removed `road_risk_score` composite tool, then verify the audit invariant.

**Independent Test**: `grep -rn 'road_risk_score' docs/ | grep -vE '(release-manifests|adr|release-notes)' | wc -l` returns `0` (per SC-004).

### Implementation for User Story 3

- [ ] T034 [P] [US3] Edit `docs/phase1-acceptance.md` lines 92 and 113: remove the `road_risk_score` table rows; add a one-line footnote citing Epic #1634 / migration tree § L1-B B6 for the removal context.
- [ ] T035 [P] [US3] Edit `docs/research/tool-system-migration-plan.md` lines 32, 94, 356: remove the composite row from the inventory tree (line 32), the table (line 94), and the task list (line 356).
- [ ] T036 [P] [US3] Edit `docs/design/mvp-tools.md` line 625: rewrite the sentence to drop the `road_risk_score` example; replace with "the LLM chains primitive adapters (e.g., `koroad_accident_search` + `kma_*`) end-to-end through `lookup`".
- [ ] T037 [P] [US3] Edit `docs/requirements/epic-p3-tool-system.md` line 10: remove `road_risk_score` from the registered tool_ids list and update the count from 15 to 14.
- [ ] T038 [US3] Run audit verification: `grep -rn 'road_risk_score' docs/ | grep -vE '(release-manifests|adr|release-notes)' | wc -l` MUST return `0`. Record the command output as a one-line note in `specs/1637-p6-docs-smoke/spec-review-notes.md` (created in T030). Depends on T034–T037.

**Checkpoint**: at this point US3 audit invariant holds; no docs purport to describe the removed tool as currently callable.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: closing migration deliverables — vision rewrite, project-memory updates, CHANGELOG, and PR submission.

- [ ] T039 [P] Update `docs/vision.md § L1-A`, `§ L1-B`, and `§ L1-C` from "planned migration" to "shipped migration" prose; add date 2026-04-26 and Epic #1637 reference.
- [ ] T040 [P] Update `CLAUDE.md § Recent Changes`: prepend a P6 entry mirroring the P0–P5 prose convention (one paragraph summarizing active specs + JSON Schema + bun test recovery + smoke evidence + composite cleanup).
- [ ] T041 [P] Update `CLAUDE.md § Active Technologies`: append "1637-p6-docs-smoke: docs/api/ catalog (active adapter specs + Draft 2020-12 schemas) + scripts/build_schemas.py (stdlib + Pydantic v2) + smoke-checklist visual evidence; zero new runtime dependencies."
- [ ] T042 [P] Author `CHANGELOG.md` v0.1-alpha entry per data-model.md § 8 ChangeLogEntry template; release date filled at PR-merge time.
- [ ] T043 Submit integrated PR `feat(1637): p6 docs/api specs + integration smoke` body containing `Closes #1637`, the 18-row smoke-checklist results, and the `bun test` summary line. Push to origin, request Copilot review (per AGENTS.md Copilot Review Gate procedure), watch CI to completion. Depends on T030, T033, T038, T039, T040, T041, T042.
- [ ] T044 After PR merge, verify Initiative #1631 closure prerequisites: confirm all six Phase Epics (#1632, #1633, #1634, #1847, #1927, #1637) report MERGED / CLOSED via `gh api graphql` (Sub-Issues API per AGENTS.md GraphQL rule); record verification output in PR comment. Depends on T043.

---

## Dependencies & Execution Order

### Story-level dependencies

- **US1** depends on Phase 1 setup (T001).
- **US2** is logically independent of US1 but the validator workflow recommends US1 lands first so the catalog is in place when smoke is captured. Execution order: Phase 3 → Phase 4 → Phase 5 → Phase 6.
- **US3** is independent of US1 and US2; tasks T034–T037 are pure-text edits and parallel-safe with the rest. T038 audit check runs last.

### Task-level dependencies

```text
T001 (setup)
  └─ T002 build_schemas.py
       └─ T003 generate schemas
            └─ T004…T027 [P] active adapter specs (writable in any order; envelope citations are line-stable)
                 └─ T028 AdapterIndex (depends on all spec files existing)
                      └─ T029 migrate docs/tools (depends on AdapterIndex)
                           └─ T030 spec review pass

T031 useVirtualScroll fix
  └─ T032 test triage + remaining fixes
       └─ T033 smoke checklist drive

T034…T037 [P] composite cleanups (independent of US1/US2)
  └─ T038 audit verification

T039…T042 [P] cross-cutting docs (depend on T030 + T033 + T038)
  └─ T043 PR submit
       └─ T044 Initiative closure verification
```

### Parallel execution opportunities

- **US1 spec authoring**: T004–T027 all parallel-safe. Suggested teammate sharding: by ministry group.
- **US3 cleanups**: T034–T037 (4 tasks) all parallel-safe.
- **Polish docs**: T039–T042 (4 tasks) parallel-safe.

Total maximum parallel-safe Tasks at any instant depends on active spec count plus US3 and Polish tasks. In practice, schedule by phase.

---

## Implementation Strategy

**MVP**: complete Phase 3 (User Story 1). The active-adapter catalog with JSON Schema and AdapterIndex satisfies the migration tree § L1-B B7 mandate by itself; release readiness (US2) and consistency cleanup (US3) ride on top.

**Incremental delivery sequence**:

1. **Phase 1 setup** → directory tree exists.
2. **Phase 3 US1** → catalog usable; cold-read test passes.
3. **Phase 4 US2** → release-readiness gate green.
4. **Phase 5 US3** → consistency audit clean.
5. **Phase 6 polish** → migration is officially closed.

**Agent team assignment** (per AGENTS.md § Agent Teams):

- Active spec writes (T004–T027): parallel teammates (Sonnet — Backend Architect or Technical Writer agent), one teammate per ministry group.
- Test triage (T031–T032): single teammate (Sonnet — API Tester) plus Lead synthesis review.
- Smoke checklist (T033): solo Lead (project lead is the validator; cannot be delegated).
- Composite cleanups (T034–T037): single teammate (Sonnet — Technical Writer) sequentially in one session is faster than 4 parallel due to context-switching overhead.
- Polish (T039–T042): single teammate (Sonnet — Technical Writer).
- PR + verification (T043–T044): solo Lead (Opus).

---

## Notes

- **Task budget**: 44 tasks total. Well under the 90-task hard cap (memory `feedback_subissue_100_cap`).
- **No new dependencies**: all tasks honor AGENTS.md hard rule + spec FR-022.
- **All source text English**: spec authoring respects FR-021; bilingual search hints are the only Korean inside the new docs.
- **Visual-evidence convention**: `script(1)` + `sed` is stdlib-only per research.md § R6.
- **Deferred items**: spec.md's 5 deferred-to-future-work rows remain `NEEDS TRACKING`; `/speckit-taskstoissues` will resolve them.
- **PR target**: `Closes #1637` only (memory `feedback_pr_closing_refs`); Task sub-issues are closed after merge.
- **Initiative #1631** is closed by the project lead manually after T044.
