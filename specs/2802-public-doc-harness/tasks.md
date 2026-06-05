# Tasks: Public AX Document Harness

**Input**: Design documents from `/specs/2802-public-doc-harness/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/document-tools.schema.json](./contracts/document-tools.schema.json), [quickstart.md](./quickstart.md)

**Tests**: Required. The feature specification defines independent tests and measurable outcomes for every user story, so each user story starts with test tasks that must fail before implementation.

**Task Budget**: 80 total tasks. This stays below the 90-task hard budget for a single Epic.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files and does not depend on incomplete tasks.
- **[Story]**: User-story task label. Setup, Foundational, and Polish tasks do not use story labels.
- Every task includes exact repository paths.

## Reference Bootstrap For Implementers

- UMMAYA thesis/docs: `docs/vision.md`, `docs/requirements/ummaya-migration-tree.md`, `docs/onboarding/codex-continuation.md`
- CC restored-source references: `.references/claude-code-sourcemap/restored-src/src/tools/FileReadTool/`, `.references/claude-code-sourcemap/restored-src/src/constants/files.ts`, `.references/claude-code-sourcemap/restored-src/src/utils/mcpOutputStorage.ts`
- CC source integrity: partial adjacent, not present for public-form authoring
- External standards and OSS sources: KS X 6101/OWPML, ECMA-376 OOXML, MCP Tools structured output, OWASP file upload controls, `python-hwpx`, `hwpx-mcp-server`, RHWP/HWP ecosystem references, `python-docx`, `openpyxl`, `pypdf`, `python-pptx`
- Implementation constraints: local-only document bytes, no original mutation, no direct HWP binary writing, no live government/data.go.kr calls in CI, no new root primitives beyond `find`, `locate`, `check`, `send`

## Phase 1: Setup

**Purpose**: Create the package, fixture, and evidence skeleton without implementing behavior.

- [X] T001 Create document harness package skeleton in `src/ummaya/tools/documents/__init__.py` and `src/ummaya/tools/documents/formats/__init__.py`
- [X] T002 [P] Create document test package and fixture directories in `tests/tools/documents/__init__.py` and `tests/fixtures/documents/corpus_manifest.yaml`
- [X] T003 [P] Create minimal valid Evidence Fabric scenario skeleton in `evidence/scenarios/document_harness_v1.yaml`
- [X] T004 [P] Add dependency/license decision checklist for candidate engines in `specs/2802-public-doc-harness/research.md`
- [X] T005 [P] Add generated contract schema smoke test in `tests/tools/documents/test_contract_schema.py`

---

## Phase 2: Foundational

**Purpose**: Build shared typed models, artifact storage, security intake, capability gates, and fixture helpers. No user story implementation may start before this phase is complete.

- [X] T006 [P] Add failing Pydantic model tests for document entities in `tests/tools/documents/test_models.py`
- [X] T007 Implement strict document Pydantic models in `src/ummaya/tools/documents/models.py`
- [X] T008 [P] Add artifact-store security and lineage tests in `tests/tools/documents/test_artifact_store.py`
- [X] T009 Implement immutable-source artifact store in `src/ummaya/tools/documents/artifact_store.py`
- [X] T010 [P] Add intake security tests for extension, signature, MIME mismatch, package expansion, paths, macros, and external links in `tests/tools/documents/test_intake_security.py`
- [X] T011 Implement fail-closed document intake policy in `src/ummaya/tools/documents/intake.py`
- [X] T012 [P] Add capability profile and promotion scorecard tests in `tests/tools/documents/test_capability_profiles.py`
- [X] T013 Implement capability profiles and promotion scorecard in `src/ummaya/tools/documents/capability.py` and `src/ummaya/tools/documents/scorecard.py`
- [X] T014 [P] Add contract request/result model validation tests in `tests/tools/documents/test_contract_models.py`
- [X] T015 Implement contract schema loader and Pydantic schema export helpers in `src/ummaya/tools/documents/contracts.py`
- [X] T016 [P] Add fixture manifest parser tests in `tests/tools/documents/test_fixture_manifest.py`
- [X] T017 Implement fixture manifest models and helpers in `src/ummaya/tools/documents/fixtures.py`
- [X] T018 Wire public package exports in `src/ummaya/tools/documents/__init__.py`

**Checkpoint**: Shared document models, artifact lineage, intake security, capability gates, and fixture manifest support are ready.

---

## Phase 3: User Story 1 - Inspect and Normalize Public Document Artifacts (Priority: P1) MVP

**Goal**: Read supported document artifacts without mutation, detect the real format, extract normalized structure, and expose capability boundaries.

**Independent Test**: Fixture files for HWPX, HWP, DOCX, PDF, XLSX, and PPTX return structured inspection results with hashes, detected format, text blocks, tables, media references, style cues, warnings, and blocked results for unsafe files.

### Tests for User Story 1

- [X] T019 [P] [US1] Add engine-backed all-format inspection journey tests in `tests/tools/documents/test_inspection_flow.py`
- [X] T020 [P] [US1] Add mismatch, encrypted, corrupt, macro-enabled, oversized, and unsafe package tests in `tests/tools/documents/test_inspection_negatives.py`

### Implementation for User Story 1

- [X] T021 [US1] Implement shared engine-backed format adapter protocol in `src/ummaya/tools/documents/formats/base.py` and `src/ummaya/tools/documents/engines.py`
- [X] T022 [US1] Implement HWPX engine-adapter boundary and candidate metadata in `src/ummaya/tools/documents/formats/hwpx.py`
- [X] T023 [US1] Implement HWP read-only engine boundary and blocked-write candidate policy in `src/ummaya/tools/documents/formats/hwp.py`
- [X] T024 [US1] Implement DOCX, XLSX, and PPTX OOXML engine-adapter boundaries in `src/ummaya/tools/documents/formats/ooxml.py`
- [X] T025 [US1] Implement PDF engine-adapter boundary and form-capability candidate metadata in `src/ummaya/tools/documents/formats/pdf.py`
- [X] T026 [US1] Implement inspection orchestration service in `src/ummaya/tools/documents/inspection.py`
- [X] T027 [US1] Add source checksum no-mutation regression coverage in `tests/tools/documents/test_inspection_flow.py`
- [X] T028 [US1] Register read-only capability profile results for inspected fixtures in `src/ummaya/tools/documents/capability.py`

**Checkpoint**: US1 is independently testable with `uv run pytest tests/tools/documents/test_inspection_flow.py tests/tools/documents/test_inspection_negatives.py -q`.

---

## Phase 4: User Story 2 - Fill Official Forms While Preserving Required Formatting (Priority: P1)

**Goal**: Fill promoted editable document derivatives while preserving protected form content and bounded style/layout constraints.

**Independent Test**: Public-form fixtures are copied, filled, saved, re-read, and verified so intended values match, protected text is unchanged, and unsupported static/scanned PDF or HWP write attempts are blocked.

### Tests for User Story 2

- [X] T029 [P] [US2] Add engine-backed HWPX and DOCX form-fill and protected-content tests in `tests/tools/documents/test_form_fill.py`
- [X] T030 [P] [US2] Add engine-backed XLSX merged-cell, formula, style, and print-area fill tests in `tests/tools/documents/test_xlsx_fill.py`
- [X] T031 [P] [US2] Add engine-backed PDF AcroForm fill and static-PDF blocked tests in `tests/tools/documents/test_pdf_fill.py`

### Implementation for User Story 2

- [X] T032 [US2] Implement copy-for-edit and ordered engine-backed document patch harness in `src/ummaya/tools/documents/patch.py`
- [X] T033 [US2] Implement HWPX and DOCX mutation engine-boundary validators in `src/ummaya/tools/documents/formats/hwpx.py` and `src/ummaya/tools/documents/formats/ooxml.py`
- [X] T034 [US2] Implement XLSX mutation engine-boundary validators for merged cells, formulas, styles, and print areas in `src/ummaya/tools/documents/formats/ooxml.py`
- [X] T035 [US2] Implement PDF mutation engine-boundary validators for AcroForm support and static/scanned PDF blocked handling in `src/ummaya/tools/documents/formats/pdf.py`
- [X] T036 [US2] Implement bounded style patch validation in `src/ummaya/tools/documents/style.py`
- [X] T037 [US2] Implement derivative diff generation for changed fields, tables, cells, and styles in `src/ummaya/tools/documents/diff.py`

**Checkpoint**: US2 is independently testable with `uv run pytest tests/tools/documents/test_form_fill.py tests/tools/documents/test_xlsx_fill.py tests/tools/documents/test_pdf_fill.py -q`.

---

## Phase 5: User Story 3 - Validate Public-Form Conformance Before Save or Submission (Priority: P1)

**Goal**: Validate generated derivatives against form schemas, protected structure, layout anchors, semantic corpus metrics, and hard failure rules before ready status.

**Independent Test**: Known-good templates pass, damaged derivatives fail with exact anchors, data.go.kr-derived semantic records are used only for semantic/structural evaluation, and unsupported conformance returns typed unsupported results.

### Tests for User Story 3

- [X] T038 [P] [US3] Add public-form hard-rule validator tests in `tests/tools/documents/test_public_form_validator.py`
- [X] T039 [P] [US3] Add data.go.kr semantic metric and aggregate-threshold tests in `tests/tools/documents/test_public_form_scorecard.py`

### Implementation for User Story 3

- [X] T040 [US3] Implement conformance baseline models for HWPX, OOXML, PDF, and HWP blocked-write policy in `src/ummaya/tools/documents/baselines.py`
- [X] T041 [US3] Implement validation report, findings, anchors, remediation hints, and readiness decision logic in `src/ummaya/tools/documents/validate.py`
- [X] T042 [US3] Implement paragraph-block F1, table-cell F1, image-reference F1, metadata exact-match, and aggregate metrics in `src/ummaya/tools/documents/scorecard.py`
- [X] T043 [US3] Add public-form baseline fixture manifests in `tests/fixtures/documents/public_forms/baselines.yaml`
- [X] T044 [US3] Implement unsupported-for-conformance blocked outcomes in `src/ummaya/tools/documents/validate.py`
- [X] T045 [US3] Integrate validation readiness state into result models in `src/ummaya/tools/documents/models.py`

**Checkpoint**: US3 is independently testable with `uv run pytest tests/tools/documents/test_public_form_validator.py tests/tools/documents/test_public_form_scorecard.py -q`.

---

## Phase 6: User Story 4 - Render, Re-Read, and Evidence-Gate Generated Artifacts (Priority: P1)

**Goal**: After writes, render reviewer evidence, re-read derivative bytes, compare intended values/layout anchors, and store reports tied to source and derivative hashes.

**Independent Test**: Filled HWPX, DOCX, XLSX, PDF, and PPTX derivatives produce render artifacts, structured diffs, re-read checks, validation reports, and evidence records joined by correlation ID.

### Tests for User Story 4

- [X] T046 [P] [US4] Add render, re-read, and mismatch downgrade tests in `tests/tools/documents/test_render_and_reread.py`
- [X] T047 [P] [US4] Add Evidence Fabric join tests for document reports in `tests/evidence/test_document_harness_evidence.py`

### Implementation for User Story 4

- [X] T048 [US4] Implement renderer facade and local render capability detection in `src/ummaya/tools/documents/render.py`
- [X] T049 [US4] Implement derivative re-read comparison against intended patches in `src/ummaya/tools/documents/reread.py`
- [X] T050 [US4] Extend structured diff and render artifact records in `src/ummaya/tools/documents/diff.py`
- [X] T051 [US4] Populate document harness Evidence Fabric scenario in `evidence/scenarios/document_harness_v1.yaml`
- [X] T052 [US4] Integrate document evidence records with the evidence runner in `src/ummaya/evidence/document_harness.py`
- [X] T053 [US4] Add render/re-read mismatch downgrade integration in `src/ummaya/tools/documents/validate.py`

**Checkpoint**: US4 is independently testable with `uv run pytest tests/tools/documents/test_render_and_reread.py tests/evidence/test_document_harness_evidence.py -q`.

---

## Phase 7: User Story 5 - Drive Document Work Through the UMMAYA Tool Loop (Priority: P2)

**Goal**: Expose inspect, extract, form-schema, copy, fill, style, render, validate, and save operations as concrete ToolRegistry tools under existing primitives and permission boundaries.

**Independent Test**: A conversation-like flow discovers document tools, calls them in valid order, requests permission before derivative writes, returns typed blocked results for unsupported edits, and emits local evidence without document-byte egress.

### Tests for User Story 5

- [X] T054 [P] [US5] Add ToolRegistry document tool contract tests in `tests/tools/documents/test_tool_registry_document_tools.py`
- [X] T055 [P] [US5] Add document artifact permission boundary tests in `tests/permissions/test_document_artifact_permissions.py`

### Implementation for User Story 5

- [X] T056 [US5] Implement concrete document tool definitions for all nine contracts in `src/ummaya/tools/documents/tool_defs.py`
- [X] T057 [US5] Implement document tool execution orchestration in `src/ummaya/tools/documents/registry.py`
- [X] T058 [US5] Register document tools through the existing registry boot path in `src/ummaya/tools/register_all.py`
- [X] T059 [US5] Implement document write/export permission payloads in `src/ummaya/tools/documents/permissions.py`
- [X] T060 [US5] Implement typed unsupported-capability tool results in `src/ummaya/tools/documents/tool_defs.py`
- [X] T061 [US5] Add full inspect-to-save tool-flow regression in `tests/tools/documents/test_document_tool_flow.py`

**Checkpoint**: US5 is independently testable with `uv run pytest tests/tools/documents/test_tool_registry_document_tools.py tests/tools/documents/test_document_tool_flow.py tests/permissions/test_document_artifact_permissions.py -q`.

---

## Phase 8: User Story 6 - Compare Candidate Format Harnesses With a High-Conformance Loop (Priority: P2)

**Goal**: Evaluate candidate engines and format layers through the scorecard, promote only evidence-backed capabilities, and retain rejection/deferral decisions.

**Independent Test**: Every promoted capability has a scorecard, fixture evidence, failure cases, dependency/license review, and a promotion or deferral decision; HWP direct write remains blocked.

### Tests for User Story 6

- [X] T062 [P] [US6] Add candidate profile scorecard tests in `tests/tools/documents/test_candidate_evaluation.py`
- [X] T063 [P] [US6] Add dependency and license gate tests in `tests/tools/documents/test_dependency_gate.py`

### Implementation for User Story 6

- [X] T064 [US6] Implement candidate evaluation runner in `src/ummaya/tools/documents/evaluation.py`
- [X] T065 [US6] Add checked-in candidate profile fixtures in `tests/fixtures/documents/candidate_profiles.yaml`
- [X] T066 [US6] Implement promotion and deferral persistence in `src/ummaya/tools/documents/capability.py`
- [X] T067 [US6] Add HWP read-only and HWP write-block promotion assertions in `tests/tools/documents/test_candidate_evaluation.py`
- [X] T068 [US6] Add data.go.kr-derived offline metadata corpus snapshot in `tests/fixtures/documents/public_forms/data_go_kr_metadata.yaml`
- [X] T069 [US6] Record promotion decisions and rejected alternatives in `specs/2802-public-doc-harness/research.md`

**Checkpoint**: US6 is independently testable with `uv run pytest tests/tools/documents/test_candidate_evaluation.py tests/tools/documents/test_dependency_gate.py -q`.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Repository-level validation, documentation, privacy hardening, and final evidence.

- [X] T070 [P] Add quickstart contract validation coverage in `tests/tools/documents/test_quickstart_contract.py`
- [X] T071 [P] Add document harness reference materials to `docs/vision.md`
- [X] T072 [P] Add CI guard that document tests never call live data.go.kr or agency endpoints in `tests/ci/test_document_harness_ci.py`
- [X] T073 [P] Add raw document log redaction and scoped evidence tests in `tests/tools/documents/test_document_privacy.py`
- [X] T074 Update public document harness quickstart outcomes in `specs/2802-public-doc-harness/quickstart.md`
- [X] T075 Run focused document gates for `src/ummaya/tools/documents/`, `tests/tools/documents/`, `tests/evidence/`, and `tests/ci/`
- [X] T076 Run backend quality gates for `src/ummaya/tools/documents/`, `src/ummaya/evidence/document_harness.py`, and related tests
- [X] T077 Run Evidence Fabric output validation for `.evidence/run.json` and `evidence/scenarios/document_harness_v1.yaml`
- [X] T078 Add final implementation notes and reference bootstrap summary in `specs/2802-public-doc-harness/implementation-notes.md`
- [X] T079 [P] Add document p95 performance budget tests for inspect/extract and fill/style/save/validate in `tests/tools/documents/test_document_performance_budget.py`
- [X] T080 [P] Add conversation-style inspect-to-save smoke evidence test in `tests/tools/documents/test_document_conversation_smoke.py`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**: No dependencies.
- **Phase 2 Foundational**: Depends on Phase 1 and blocks all user stories.
- **US1 Inspection MVP**: Depends on Foundational.
- **US2 Filling**: Depends on Foundational and uses US1 inspection artifacts for full end-to-end verification.
- **US3 Validation**: Depends on Foundational and can run after US1 models exist; final ready-status tests combine with US2 derivatives.
- **US4 Render/Re-read/Evidence**: Depends on US1 and US2 output structures, then feeds US3 readiness decisions.
- **US5 Tool Loop**: Depends on US1 through US4 services and contracts.
- **US6 Evaluation Loop**: Depends on Foundational and can run in parallel with US1 through US4, but final promotion decisions need adapter results.
- **Polish**: Depends on all desired user stories.

### User Story Completion Order

1. US1 is the MVP and must complete first for a useful inspect-only harness.
2. US2, US3, and US4 are the P1 authoring safety loop and should be completed before any write capability is presented as ready.
3. US5 integrates the proven services into the model-facing ToolRegistry.
4. US6 can evaluate candidate engines continuously, but cannot promote a capability until the matching user-story tests pass.

### Within Each User Story

- Write test tasks first and verify they fail before implementation.
- Implement models, engine registry, and adapter boundaries before orchestration services.
- Implement services before ToolRegistry exposure.
- Validate each story independently at its checkpoint before advancing.

---

## Parallel Opportunities

- T002, T003, T004, and T005 can run in parallel after T001 is understood.
- T006, T008, T010, T012, T014, and T016 can run in parallel as foundational test authorship.
- After Phase 2, US1 adapter-boundary tasks for HWPX, HWP, OOXML, and PDF can be split across teammates once `formats/base.py` and `engines.py` exist.
- US2 test tasks T029, T030, and T031 can run in parallel.
- US3 validation tests T038 and T039 can run in parallel.
- US4 render/evidence tests T046 and T047 can run in parallel.
- US5 registry and permission tests T054 and T055 can run in parallel.
- US6 evaluation and dependency gate tests T062 and T063 can run in parallel.
- Polish tests T070, T072, T073, T079, and T080 can run in parallel.

## Parallel Example: US1

```text
Task: "T022 Implement HWPX engine-adapter boundary and candidate metadata in src/ummaya/tools/documents/formats/hwpx.py"
Task: "T023 Implement HWP read-only engine boundary and blocked-write candidate policy in src/ummaya/tools/documents/formats/hwp.py"
Task: "T024 Implement DOCX, XLSX, and PPTX OOXML engine-adapter boundaries in src/ummaya/tools/documents/formats/ooxml.py"
Task: "T025 Implement PDF engine-adapter boundary and form-capability candidate metadata in src/ummaya/tools/documents/formats/pdf.py"
```

## Parallel Example: US2

```text
Task: "T033 Implement HWPX and DOCX mutation engine-boundary validators in src/ummaya/tools/documents/formats/hwpx.py and src/ummaya/tools/documents/formats/ooxml.py"
Task: "T034 Implement XLSX mutation boundary guards that preserve merged regions, formulas, styles, and printable areas in src/ummaya/tools/documents/formats/ooxml.py plus src/ummaya/tools/documents/style.py"
Task: "T035 Implement PDF mutation engine-boundary validators for AcroForm support and static/scanned PDF blocked handling in src/ummaya/tools/documents/formats/pdf.py"
```

## Implementation Strategy

### MVP First

1. Complete Phase 1 and Phase 2.
2. Complete US1.
3. Stop and validate inspection-only behavior across HWPX, HWP, DOCX, PDF, XLSX, and PPTX.
4. Do not expose write-ready capability until US2, US3, US4, and US6 gates pass.

### Incremental Delivery

1. Setup plus Foundational -> typed document artifact base.
2. US1 -> inspect-only public document harness.
3. US2 -> derivative fill/style operations behind capability gates.
4. US3 -> public-form conformance validation.
5. US4 -> render, re-read, and evidence loop.
6. US5 -> model-facing ToolRegistry integration.
7. US6 -> promotion loop and final capability decisions.

### Team Dispatch Shape

```text
Phase 1-2: Lead solo until shared contracts stabilize
US1 engine-adapter boundaries after base protocol: parallel teammates by format family
US2 fill/style: parallel teammates by HWPX/DOCX, XLSX, PDF
US3 validation and US4 evidence: coupled review by Lead, selective parallel tests
US5 ToolRegistry integration: Lead solo because it touches model-facing surface
US6 candidate evaluation: parallel with adapter implementation, Lead reviews promotion decisions
```

## Summary Metrics

- Total tasks: 80
- Setup tasks: 5
- Foundational tasks: 13
- US1 tasks: 10
- US2 tasks: 9
- US3 tasks: 8
- US4 tasks: 8
- US5 tasks: 8
- US6 tasks: 8
- Polish tasks: 11
- MVP scope: Phase 1, Phase 2, and US1
- Parallel task candidates: 25

## Notes

- The optional `speckit.git.commit` before/after task-generation hooks are available through `.specify/extensions.yml` but were not executed automatically.
- `/speckit-analyze` must run after this file is approved.
- `/speckit-taskstoissues` must convert this task list and the seven spec scope-tracking rows before implementation starts.
- Direct binary HWP writing remains blocked for every task in this epic.
