# Format Adapter Execution Progress

Date: 2026-06-03

Checklist source:
`specs/2802-public-doc-harness/format-adapter-implementation-plan-2026-06-03.md`.

This file tracks the current Codex execution state. Each phase must keep the
UMMAYA structure anchored to Claude Code behavior first, then migrate document
domain content into the selected reference-shaped boundary.

## Phase 0 - Baseline Lock

Status: completed for the first implementation loop.

Reference bootstrap:

- UMMAYA thesis/docs: `docs/onboarding/codex-continuation.md`, `docs/vision.md`,
  `docs/requirements/ummaya-migration-tree.md`,
  `specs/2802-public-doc-harness/plan.md`, and
  `specs/2802-public-doc-harness/format-adapter-implementation-plan-2026-06-03.md`.
- CC restored-source files: `.references/claude-code-sourcemap/restored-src/src/Tool.ts`,
  `.references/claude-code-sourcemap/restored-src/src/tools/FileEditTool/FileEditTool.ts`,
  and `.references/claude-code-sourcemap/restored-src/src/tools/ToolSearchTool/`.
- CC source integrity: intact for strict tool contracts, one model-facing edit
  surface, validation before mutation, structured result rendering, and deferred
  concrete tool discovery.
- UMMAYA target files for the first slice:
  `src/ummaya/tools/documents/models.py`,
  `src/ummaya/tools/documents/intake.py`,
  `src/ummaya/tools/documents/__init__.py`,
  `tests/tools/documents/test_models.py`, and
  `tests/tools/documents/test_intake_security.py`.

Phase 0 conclusion:

- The first loop should not change the model-facing `document` primitive or
  promote new write formats.
- The correct first implementation layer is format taxonomy: split known
  national-infrastructure formats from promoted runtime formats.

## Phase 1 - Format Taxonomy Foundation

Status: completed for the first implementation loop.

Deep research migration note:

- Local anchors: existing `DocumentFormat`, `FormatCapabilityProfile`,
  `DocumentIntakeResult`, `DocumentIntakePolicy`, and the detailed adapter plan.
- Official/public-sector source signal:
  - MOIS NPAS viewer page lists HWP, PDF, PPT, XLS, and DOC as public-service
    document viewer families.
  - Public Data Portal guide treats public-data files and OpenAPI data as a
    first-class public infrastructure surface, separate from editable forms.
- Standards/source signal:
  - ECMA-376 defines OOXML document, spreadsheet, presentation vocabularies and
    packaging, so DOCX/XLSX/PPTX remain one standards family but separate
    adapters.
  - OWASP File Upload Cheat Sheet requires allowlist, content-type distrust,
    signature validation, safe storage, size limits, and active-content controls.
- Research/package signal:
  - Docling AAAI 2025 and the active Docling repository support a unified
    structured document representation for extraction, but not as the mutation
    authority for public forms.

Candidate scorecard:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Expand `DocumentFormat` to every known extension | 52 | Reject | It would imply runtime support and weaken promotion gates. |
| Keep six-format `DocumentFormat` and reject all others as unknown | 61 | Reject | It hides public-infrastructure format knowledge and blocks adapter planning. |
| Add `KnownDocumentFormat` plus `DocumentFormatFamily`, keep `DocumentFormat` runtime-only | 96 | Adopt | It separates classification from capability, preserves fail-closed behavior, and gives later adapters a stable taxonomy. |

Implemented in this slice:

- Added `KnownDocumentFormat` for HWP/HWPX/OWPML, OOXML, legacy Office, PDF/PDF-A,
  ODF, text/web exports, public-data files, image/scanned documents, and archives.
- Added `DocumentFormatFamily`.
- Added `PROMOTED_RUNTIME_DOCUMENT_FORMATS`.
- Added `KNOWN_DOCUMENT_FORMAT_FAMILIES`.
- Extended `DocumentIntakeResult` with `known_format`, `format_family`, and
  `next_safe_actions`.
- Updated intake so known but unpromoted formats fail closed with
  `unsupported_operation` instead of being treated as totally unknown.
- Preserved known format/family metadata on blocked known-format security paths.
- Added all-known-extension classifier coverage for every non-promoted
  `KnownDocumentFormat`.
- Added promoted runtime metadata coverage for HWPX, HWP, DOCX, XLSX, PPTX, and
  PDF.
- Added policy-denied known-format coverage so classification metadata survives
  allowlist rejection.

Verification:

- RED observed:
  `ImportError: cannot import name 'DocumentFormatFamily'`.
- GREEN:
  `uv run pytest tests/tools/documents/test_models.py tests/tools/documents/test_intake_security.py -q`
  -> `60 passed`.
- Diff hygiene:
  `git diff --check -- src/ummaya/tools/documents/models.py src/ummaya/tools/documents/intake.py src/ummaya/tools/documents/__init__.py tests/tools/documents/test_models.py tests/tools/documents/test_intake_security.py`
  -> pass.
- Runtime sanity:
  `uv run python` confirmed `KnownDocumentFormat` has 37 values and runtime
  `DocumentFormat` remains `hwpx`, `hwp`, `docx`, `pdf`, `xlsx`, and `pptx`.
- Intake smoke:
  a CSV file returns `blocked unsupported_operation csv data_file` with two
  next-safe actions.

Phase 1 gate decisions:

- Known-format detection precision is covered over the current fixture/test
  matrix for promoted runtime formats and every non-promoted known extension.
- Unsupported known formats fail closed with `next_safe_actions`.
- `capability.py` keeps its candidate-engine runtime literals until Phase 2,
  because broad known-format classification is not the same as engine promotion.
  Phase 2 will decide whether to replace those literals through the adapter
  registry contract instead of patching the scorecard module prematurely.

## Phase 2 - Adapter Skeleton

Status: in progress. Adapter-registry creation and runtime routing TDD slices
are green.

Deep research migration note:

- Local anchors: `formats/base.py`, `engines.py`, `inspection.py`, and
  `registry.py`.
- CC restored-source source signal: Claude Code keeps one model-facing edit tool
  while validation, permission, and rendering live under that tool boundary.
  UMMAYA should likewise keep one `document` primitive and move format-specific
  behavior below it.
- OSS/research source signal: Docling's modular, unified representation supports
  a shared IR, but its mutation behavior is not the public-form write authority.
  Therefore UMMAYA needs native format adapters rather than a single universal
  converter.

Candidate scorecard:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Reuse `DocumentEngineRegistry` as the adapter registry | 63 | Reject | Engines only know one promoted runtime format and do not classify known-but-unpromoted families. |
| Put format branches in `registry.py` | 55 | Reject | Central branching repeats the previous HWPX leakage problem. |
| Add `DocumentFormatAdapter` and separate `DocumentAdapterRegistry` | 94 | Adopt | Keeps the model-facing primitive stable while allowing HWPX/HWP/DOCX/PDF/XLSX/PPTX families to diverge safely. |

Implemented in this slice:

- Added `DocumentFormatAdapter` protocol in `formats/base.py`.
- Added `DocumentAdapterRegistry` and `UnsupportedDocumentAdapterError`.
- Added duplicate `adapter_id`, duplicate known-format, duplicate promoted-format,
  and promoted-not-known guards.
- Added `EngineBackedDocumentAdapter` wrapper for currently promoted inspection
  engines.
- Added `build_default_document_adapter_registry()` with HWPX and DOCX engine
  backed adapters.
- Added `build_document_adapter_registry_from_engine_registry()` so existing
  promoted engines can be wrapped at the document primitive boundary without
  changing the model-facing tool surface.
- Routed `inspect_document()` through `DocumentAdapterRegistry` first, while
  preserving the existing engine-registry compatibility path by wrapping engines
  into adapters.
- Routed `DocumentToolRuntime.inspect()` and stored extraction refreshes through
  the runtime's adapter registry.
- Kept HWPX semantic field inference fail-closed by matching only string field
  values and splitting the target classifier into small predicates. This fixes
  the quality gate without promoting fallback behavior.

Checkpoint: `DocumentOrchestrator` boundary.

Deep research migration note:

- Local anchors: current `DocumentToolRuntime.document()`, `inspect()`,
  `inspection.py`, `adapter_registry.py`, and the Phase 2 plan requirement to
  move intake -> classification -> capability -> inspect -> plan -> patch ->
  render -> re-read -> validate -> diff -> evidence under an internal
  orchestrator while keeping one model-facing `document` primitive.
- CC restored-source status: intact for one model-facing edit surface and
  internal validation/result-render boundaries. There is no CC-specific public
  document orchestrator, so this is an UMMAYA domain swap below the CC tool
  boundary.
- 2026-current sources:
  - Docling active upstream and docs show modular document-processing pipeline
    stages and a unified representation direction, but not a native public-form
    mutation authority:
    <https://github.com/docling-project/docling>,
    <https://docling-project.github.io/docling/reference/pipeline_options/>.
  - Pydantic v2 strict-mode docs support fail-closed typed boundaries rather
    than permissive coercion at the primitive/orchestrator edge:
    <https://pydantic.dev/docs/validation/2.12/concepts/strict_mode/>.
  - OpenHWP's Rust workspace confirms HWP/HWPX need format-native model and
    write boundaries, reinforcing adapter separation:
    <https://github.com/openhwp/openhwp>.
  - DocLLM and related layout-aware document-understanding work supports future
    DocumentIR/layout-anchor hardening, not direct mutation orchestration:
    <https://arxiv.org/abs/2401.00908>.
- Candidate scorecard:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Keep orchestration inside `DocumentToolRuntime` | 58 | Reject | Registry remains a large tool dispatcher and format logic keeps leaking upward. |
| Import a universal document pipeline dependency now | 71 | Defer | Good extraction/IR reference, but Phase 2 is boundary separation, not parser replacement. |
| Add a thin `DocumentOrchestrator` wrapping existing adapter registry | 95 | Adopt | Preserves CC-like one tool surface, avoids new dependency risk, and creates the boundary needed for future IR/planner migration. |

Migration boundary:

- Added `orchestrator.py` with `DocumentInspectionOrchestrator` protocol and
  `DocumentOrchestrator`.
- Migrated the runtime's local-path inspection call into the orchestrator.
- Did not add a new package or broaden mutation claims.

Verification:

- RED observed:
  `ModuleNotFoundError: No module named 'ummaya.tools.documents.adapter_registry'`
  and then missing `build_default_document_adapter_registry`.
- GREEN:
  `uv run pytest tests/tools/documents/test_adapter_registry.py -q`
  -> `5 passed`.
- Runtime sanity:
  default adapter registry resolves `DocumentFormat.hwpx` and
  `KnownDocumentFormat.owpml` to `hwpx-package-text-adapter`.
- Diff hygiene:
  `git diff --check -- src/ummaya/tools/documents/adapter_registry.py src/ummaya/tools/documents/formats/base.py src/ummaya/tools/documents/__init__.py tests/tools/documents/test_adapter_registry.py`
  -> pass.
- Focused combined gate:
  `uv run pytest tests/tools/documents/test_adapter_registry.py tests/tools/documents/test_models.py tests/tools/documents/test_intake_security.py -q`
  -> `65 passed`.
- Focused lint:
  `uv run ruff check ...`
  -> pass.
- Focused type check:
  `uv run mypy src/ummaya/tools/documents/adapter_registry.py src/ummaya/tools/documents/formats/base.py src/ummaya/tools/documents/intake.py src/ummaya/tools/documents/models.py`
  -> pass.
- RED observed for runtime routing:
  `TypeError: inspect_document() got an unexpected keyword argument 'adapter_registry'`
  and
  `TypeError: DocumentToolRuntime.__init__() got an unexpected keyword argument 'adapter_registry'`.
- GREEN for runtime routing:
  `uv run pytest tests/tools/documents/test_inspection_flow.py::test_inspect_document_delegates_to_registered_adapter_before_engine_registry tests/tools/documents/test_document_tool_flow.py::test_document_runtime_inspect_routes_through_adapter_registry -q`
  -> `2 passed`.
- Focused combined adapter/intake/runtime gate:
  `uv run pytest tests/tools/documents/test_inspection_flow.py tests/tools/documents/test_document_tool_flow.py tests/tools/documents/test_adapter_registry.py tests/tools/documents/test_models.py tests/tools/documents/test_intake_security.py -q`
  -> `79 passed`.
- Focused lint:
  `uv run ruff check src/ummaya/tools/documents/adapter_registry.py src/ummaya/tools/documents/formats/base.py src/ummaya/tools/documents/intake.py src/ummaya/tools/documents/models.py src/ummaya/tools/documents/__init__.py src/ummaya/tools/documents/inspection.py src/ummaya/tools/documents/registry.py tests/tools/documents/test_adapter_registry.py tests/tools/documents/test_intake_security.py tests/tools/documents/test_models.py tests/tools/documents/test_inspection_flow.py tests/tools/documents/test_document_tool_flow.py`
  -> pass.
- Focused type check:
  `uv run mypy src/ummaya/tools/documents/adapter_registry.py src/ummaya/tools/documents/formats/base.py src/ummaya/tools/documents/intake.py src/ummaya/tools/documents/models.py src/ummaya/tools/documents/inspection.py src/ummaya/tools/documents/registry.py`
  -> pass.
- Diff hygiene:
  `git diff --check -- src/ummaya/tools/documents/adapter_registry.py src/ummaya/tools/documents/formats/base.py src/ummaya/tools/documents/intake.py src/ummaya/tools/documents/models.py src/ummaya/tools/documents/__init__.py src/ummaya/tools/documents/inspection.py src/ummaya/tools/documents/registry.py tests/tools/documents/test_adapter_registry.py tests/tools/documents/test_intake_security.py tests/tools/documents/test_models.py tests/tools/documents/test_inspection_flow.py tests/tools/documents/test_document_tool_flow.py specs/2802-public-doc-harness/format-adapter-execution-progress-2026-06-03.md`
  -> pass.
- RED observed for orchestrator boundary:
  `ModuleNotFoundError: No module named 'ummaya.tools.documents.orchestrator'`
  and
  `TypeError: DocumentToolRuntime.__init__() got an unexpected keyword argument 'orchestrator'`.
- GREEN for orchestrator boundary:
  `uv run pytest tests/tools/documents/test_orchestrator.py -q`
  -> `2 passed`.
- Focused combined adapter/intake/runtime/orchestrator gate:
  `uv run pytest tests/tools/documents/test_orchestrator.py tests/tools/documents/test_inspection_flow.py tests/tools/documents/test_document_tool_flow.py tests/tools/documents/test_adapter_registry.py tests/tools/documents/test_models.py tests/tools/documents/test_intake_security.py -q`
  -> `81 passed`.
- Focused lint after orchestrator split:
  `uv run ruff check src/ummaya/tools/documents/orchestrator.py src/ummaya/tools/documents/adapter_registry.py src/ummaya/tools/documents/formats/base.py src/ummaya/tools/documents/intake.py src/ummaya/tools/documents/models.py src/ummaya/tools/documents/__init__.py src/ummaya/tools/documents/inspection.py src/ummaya/tools/documents/registry.py tests/tools/documents/test_orchestrator.py tests/tools/documents/test_adapter_registry.py tests/tools/documents/test_intake_security.py tests/tools/documents/test_models.py tests/tools/documents/test_inspection_flow.py tests/tools/documents/test_document_tool_flow.py`
  -> pass.

Remaining Phase 2 gates:

- Move HWPX semantic helper logic out of `registry.py` in the Phase 4 HWPX
  promotion slice rather than mixing that refactor into the registry skeleton.
- Extend `DocumentOrchestrator` beyond inspection in later checkpoints:
  autonomous plan, permission, patch, render, re-read, validate, diff, and
  evidence.

## Phase 3 - Shared DocumentIR Hardening

Status: in progress. IR model-foundation and first deterministic planner TDD
slices are green.

Checkpoint: `DocumentIR`, source anchors, form slots, and autonomous fill plan
model foundation.

Deep research migration note:

- Local anchors: `DocumentExtraction`, `FormField`, `DocumentPatchOperation`,
  `DocumentClipRect`, `DocumentChangedViewport`, and
  `autonomous-fill-plan-research-2026-06-03.md`.
- CC restored-source status: intact for strict tool input/output and edit-result
  structure, but no public-document IR analog exists in CC. This remains an
  UMMAYA domain model below the single CC-style `document` primitive.
- 2026-current sources:
  - Docling upstream's `DoclingDocument` and pipeline direction supports a
    structured document object with provenance/layout signals:
    <https://github.com/docling-project/docling>.
  - DocLLM supports text plus spatial layout for document understanding; this
    justifies `SourceAnchor` and optional bounding boxes:
    <https://arxiv.org/abs/2401.00908>.
  - LayoutLLM/Layout-aware document work supports instruction-tuned document
    understanding with region/layout references; adopted as a risk signal for
    future planner evaluation, not as a runtime dependency:
    <https://arxiv.org/abs/2404.05225>.
  - Pydantic v2 strict-mode remains the selected schema enforcement mechanism:
    <https://pydantic.dev/docs/validation/2.12/concepts/strict_mode/>.
- Candidate scorecard:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Keep using `DocumentExtraction` as the planner model | 62 | Reject | It lacks stable anchor and intent/slot safety semantics for autonomous fill. |
| Adopt Docling as the runtime IR dependency now | 76 | Defer | Strong reference shape, but Phase 3 needs a narrow local schema before dependency/ADR work. |
| Add UMMAYA strict `DocumentIR` wrapper with `SourceAnchor`, `FormSlot`, and `AutonomousFillPlan` | 94 | Adopt | Preserves existing engines, adds planner-safe structure, and keeps future adapter migration explicit. |

Implemented in this slice:

- Added `SourceAnchor` with native `format_path`, optional page/sheet/slide and
  bounding box fields, confidence, and engine provenance.
- Added `FormSlot` as the autonomous planner-facing slot model.
- Added `DocumentIntent` for bounded natural-language operation inference.
- Added `AutonomousFillPlan` with duplicate-slot, blocked-slot, and protected
  slot human-review validators.
- Added `DocumentIR.from_extraction()` to wrap existing `DocumentExtraction`
  without replacing engines or changing the model-facing tool surface.

Verification:

- RED observed:
  `ImportError: cannot import name 'AutonomousFillPlan' from 'ummaya.tools.documents.models'`.
- GREEN:
  `uv run pytest tests/tools/documents/test_models.py::test_document_ir_wraps_extraction_with_source_anchors_and_form_slots tests/tools/documents/test_models.py::test_source_anchor_and_autonomous_fill_plan_are_strict_and_review_safe -q`
  -> `2 passed`.
- Focused combined adapter/intake/runtime/orchestrator/model gate:
  `uv run pytest tests/tools/documents/test_models.py tests/tools/documents/test_orchestrator.py tests/tools/documents/test_inspection_flow.py tests/tools/documents/test_document_tool_flow.py tests/tools/documents/test_adapter_registry.py tests/tools/documents/test_intake_security.py -q`
  -> `83 passed`.
- Focused lint:
  `uv run ruff check src/ummaya/tools/documents/orchestrator.py src/ummaya/tools/documents/adapter_registry.py src/ummaya/tools/documents/formats/base.py src/ummaya/tools/documents/intake.py src/ummaya/tools/documents/models.py src/ummaya/tools/documents/__init__.py src/ummaya/tools/documents/inspection.py src/ummaya/tools/documents/registry.py tests/tools/documents/test_orchestrator.py tests/tools/documents/test_adapter_registry.py tests/tools/documents/test_intake_security.py tests/tools/documents/test_models.py tests/tools/documents/test_inspection_flow.py tests/tools/documents/test_document_tool_flow.py`
  -> pass.
- Diff hygiene:
  `git diff --check -- src/ummaya/tools/documents/orchestrator.py src/ummaya/tools/documents/adapter_registry.py src/ummaya/tools/documents/formats/base.py src/ummaya/tools/documents/intake.py src/ummaya/tools/documents/models.py src/ummaya/tools/documents/__init__.py src/ummaya/tools/documents/inspection.py src/ummaya/tools/documents/registry.py tests/tools/documents/test_orchestrator.py tests/tools/documents/test_adapter_registry.py tests/tools/documents/test_intake_security.py tests/tools/documents/test_models.py tests/tools/documents/test_inspection_flow.py tests/tools/documents/test_document_tool_flow.py specs/2802-public-doc-harness/format-adapter-execution-progress-2026-06-03.md`
  -> pass.

Remaining Phase 3 gates:

- Add protected-range models for legal text, consent, signature, seals, identity
  fields, addresses, phone numbers, bank data, and fixed notices.
- Teach adapters/orchestrator to emit empty-or-partial `DocumentIR` consistently.

Checkpoint: deterministic `autonomous_fill_plan` planner over `DocumentIR`.

Deep research migration note:

- Local anchors: `DocumentIR`, `FormSlot`, `AutonomousFillPlan`,
  `DocumentOrchestrator`, and the autonomous-fill research plan requirement that
  the planner consumes IR rather than raw engine internals.
- CC restored-source status: intact for one edit tool, internal validation,
  permission, and structured result ordering. No public-document semantic planner
  exists in CC, so this is an UMMAYA domain stage below the CC-style `document`
  primitive.
- 2026-current sources:
  - Docling `DoclingDocument` models documents as Pydantic data with text,
    tables, pictures, hierarchy, layout boxes, and provenance. Adopted as the
    reference shape for IR/provenance, not as a runtime dependency yet:
    <https://docling-project.github.io/docling/concepts/docling_document/>.
  - `docling-core` confirms the maintained MIT Pydantic core model path.
    Adopted as package candidate evidence; dependency deferred:
    <https://github.com/docling-project/docling-core>.
  - Instructor and Outlines show the mature structured-output ecosystem around
    Pydantic/JSON Schema; adopted as future LLM drafter/validator references,
    not for the first deterministic planner:
    <https://github.com/567-labs/instructor>,
    <https://dottxt-ai.github.io/outlines/reference/generation/json/>.
  - DSPy supports structured signatures and optimizable programs; useful for
    later planner/drafter evaluation loops, but too broad for this local
    deterministic checkpoint:
    <https://dspy.ai/>.
  - JSONSchemaBench shows structured-output frameworks still need schema-level
    evaluation on real schemas; this supports keeping a code-level deterministic
    planner boundary first:
    <https://arxiv.org/abs/2501.10868>.
  - PureDocBench 2026 shows document parsing is still not solved under real
    degraded/source-traceable settings; this supports native anchors and
    fail-closed planner confidence instead of VLM-first auto-fill:
    <https://arxiv.org/abs/2605.07492>.
- Candidate scorecard:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| LLM-only planner emits patches directly | 52 | Reject | Weak provenance, hard to test, and unsafe for protected public-form slots. |
| Add Instructor/Outlines now for structured LLM output | 78 | Defer | Strong future drafter boundary, but adds provider/runtime complexity before deterministic IR gates are proven. |
| Add DSPy planner program now | 74 | Defer | Good optimization loop, but oversized for first offline public-document planner slice. |
| Deterministic `DocumentIR` planner with future LLM drafter hook | 95 | Adopt | Keeps native anchors, is fixture-testable, fails closed on protected slots, and preserves the single `document` primitive. |

Implemented in this slice:

- Added `planner.py` with `plan_autonomous_fill(document_ir, instruction=...)`.
- Planner consumes only `DocumentIR`; tests assert `DocumentExtraction` is not in
  the planner signature.
- Added deterministic weekly-activity inference:
  `13주차` -> `14주차` and
  `2026.06.01 ~ 2026.06.07` -> `2026.06.08~2026.06.14`.
- Added protected-slot handling: signature/consent/identity-like requests are
  blocked into `blocked_slot_ids` and require human review without producing an
  automatic candidate value.
- Exported `plan_autonomous_fill` from the document harness package.

Verification:

- RED observed:
  `ModuleNotFoundError: No module named 'ummaya.tools.documents.planner'`.
- GREEN:
  `uv run pytest tests/tools/documents/test_autonomous_fill_planner.py -q`
  -> `2 passed`.
- Focused combined gate:
  `uv run pytest tests/tools/documents/test_autonomous_fill_planner.py tests/tools/documents/test_models.py tests/tools/documents/test_orchestrator.py tests/tools/documents/test_inspection_flow.py tests/tools/documents/test_document_tool_flow.py tests/tools/documents/test_adapter_registry.py tests/tools/documents/test_intake_security.py -q`
  -> `85 passed`.
- Focused lint:
  `uv run ruff check src/ummaya/tools/documents/planner.py src/ummaya/tools/documents/orchestrator.py src/ummaya/tools/documents/adapter_registry.py src/ummaya/tools/documents/formats/base.py src/ummaya/tools/documents/intake.py src/ummaya/tools/documents/models.py src/ummaya/tools/documents/__init__.py src/ummaya/tools/documents/inspection.py src/ummaya/tools/documents/registry.py tests/tools/documents/test_autonomous_fill_planner.py tests/tools/documents/test_orchestrator.py tests/tools/documents/test_adapter_registry.py tests/tools/documents/test_intake_security.py tests/tools/documents/test_models.py tests/tools/documents/test_inspection_flow.py tests/tools/documents/test_document_tool_flow.py`
  -> pass.
- Focused type check:
  `uv run mypy src/ummaya/tools/documents/planner.py src/ummaya/tools/documents/orchestrator.py src/ummaya/tools/documents/adapter_registry.py src/ummaya/tools/documents/formats/base.py src/ummaya/tools/documents/intake.py src/ummaya/tools/documents/models.py src/ummaya/tools/documents/inspection.py src/ummaya/tools/documents/registry.py`
  -> pass.

Checkpoint: protected-range model and planner block gate.

Deep research migration note:

- Local anchors: `DocumentIR`, `FormSlot`, `AutonomousFillPlan`, and planner
  protection tests.
- CC restored-source status: intact for validation-before-permission and
  structured edit-result boundaries. Protected document spans are an UMMAYA
  public-service safety addition below that boundary.
- 2026-current sources:
  - Microsoft Presidio's current 2026 release line supports PII detection,
    redaction, anonymization, image handling, structured data, recognizers, and
    customizable pipelines. Adopted as the reference shape for explicit
    category/recognizer-result style protected ranges, not as a dependency yet:
    <https://github.com/microsoft/presidio>,
    <https://microsoft.github.io/presidio/getting_started/>.
  - OWASP LLM Prompt Injection guidance treats document content as untrusted
    input and emphasizes separation between data and instructions. Adopted as
    the policy basis for blocking silent document-driven writes:
    <https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html>.
  - Silent Egress 2026 and Promptware Kill Chain 2026 show that agentic document
    ingestion can become a data-exfiltration/action channel. Adopted as risk
    signal for fail-closed protected ranges:
    <https://arxiv.org/abs/2602.22450>,
    <https://arxiv.org/abs/2601.09625>.
  - Docling `DoclingDocument` provenance/bbox structure remains the anchor model
    for locating protected spans in native document coordinates:
    <https://docling-project.github.io/docling/reference/docling_document/>.
- Candidate scorecard:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| String keyword blocklist in planner only | 55 | Reject | It hides protection semantics and cannot be audited by IR/evidence. |
| Add Presidio runtime dependency now | 80 | Defer | Strong PII ecosystem, but heavy dependency/locale/CI impact before IR span plumbing is proven. |
| Add UMMAYA `DocumentProtectedRange` modeled after recognizer results and native anchors | 96 | Adopt | Keeps span provenance, is offline-testable, blocks silent mutation, and remains adapter-friendly. |

Implemented in this slice:

- Added `ProtectedRangeCategory` for legal text, consent, signature, seal,
  identity number, address, phone number, bank account, fixed notice, health
  data, and other sensitive spans.
- Added `DocumentProtectedRange` with native `SourceAnchor`, reason,
  blocked operations, and mandatory human review.
- Added `DocumentIR.protected_ranges`.
- Planner now blocks slots whose source anchor matches a protected range even if
  the slot itself was not marked `protected`.
- Exported the protected-range models from the document harness package.

Verification:

- RED observed:
  `ImportError: cannot import name 'DocumentProtectedRange' from 'ummaya.tools.documents.models'`.
- GREEN:
  `uv run pytest tests/tools/documents/test_models.py::test_document_ir_carries_protected_ranges_for_sensitive_public_form_areas tests/tools/documents/test_autonomous_fill_planner.py::test_autonomous_fill_planner_blocks_slots_matched_by_protected_ranges -q`
  -> `2 passed`.
- Focused combined gate:
  `uv run pytest tests/tools/documents/test_autonomous_fill_planner.py tests/tools/documents/test_models.py tests/tools/documents/test_orchestrator.py tests/tools/documents/test_inspection_flow.py tests/tools/documents/test_document_tool_flow.py tests/tools/documents/test_adapter_registry.py tests/tools/documents/test_intake_security.py -q`
  -> `87 passed`.
- Focused lint:
  `uv run ruff check src/ummaya/tools/documents/planner.py src/ummaya/tools/documents/orchestrator.py src/ummaya/tools/documents/adapter_registry.py src/ummaya/tools/documents/formats/base.py src/ummaya/tools/documents/intake.py src/ummaya/tools/documents/models.py src/ummaya/tools/documents/__init__.py src/ummaya/tools/documents/inspection.py src/ummaya/tools/documents/registry.py tests/tools/documents/test_autonomous_fill_planner.py tests/tools/documents/test_orchestrator.py tests/tools/documents/test_adapter_registry.py tests/tools/documents/test_intake_security.py tests/tools/documents/test_models.py tests/tools/documents/test_inspection_flow.py tests/tools/documents/test_document_tool_flow.py`
  -> pass.
- Focused type check:
  `uv run mypy src/ummaya/tools/documents/planner.py src/ummaya/tools/documents/orchestrator.py src/ummaya/tools/documents/adapter_registry.py src/ummaya/tools/documents/formats/base.py src/ummaya/tools/documents/intake.py src/ummaya/tools/documents/models.py src/ummaya/tools/documents/inspection.py src/ummaya/tools/documents/registry.py`
  -> pass.
- Diff hygiene:
  `git diff --check -- src/ummaya/tools/documents/planner.py src/ummaya/tools/documents/orchestrator.py src/ummaya/tools/documents/adapter_registry.py src/ummaya/tools/documents/formats/base.py src/ummaya/tools/documents/intake.py src/ummaya/tools/documents/models.py src/ummaya/tools/documents/__init__.py src/ummaya/tools/documents/inspection.py src/ummaya/tools/documents/registry.py tests/tools/documents/test_autonomous_fill_planner.py tests/tools/documents/test_orchestrator.py tests/tools/documents/test_adapter_registry.py tests/tools/documents/test_intake_security.py tests/tools/documents/test_models.py tests/tools/documents/test_inspection_flow.py tests/tools/documents/test_document_tool_flow.py specs/2802-public-doc-harness/format-adapter-execution-progress-2026-06-03.md`
  -> pass.

Checkpoint: orchestrator emits empty-or-partial `DocumentIR`.

Deep research migration note:

- Local anchors: `DocumentOrchestrator`, `DocumentIR.from_extraction()`, and the
  Phase 3 exit gate requiring every adapter/orchestrator path to emit a valid
  empty-or-partial IR.
- CC restored-source status: intact for a single tool boundary and strict
  validation before mutation. IR construction is an UMMAYA document-domain swap.
- 2026-current sources:
  - Docling `DoclingDocument` and `docling-core` keep source provenance in the
    structured document object. Adopted as the reference for orchestrator-level
    normalization:
    <https://docling-project.github.io/docling/reference/docling_document/>,
    <https://github.com/docling-project/docling-core>.
  - Unstructured's element model uses deterministic IDs and metadata
    coordinates, reinforcing source-anchor/provenance as the right IR boundary:
    <https://docs.unstructured.io/open-source/concepts/document-elements>.
  - Advanced Layout Analysis Models for Docling 2025 shows layout/provenance
    quality continues to improve, but also supports keeping this stage as a
    narrow boundary that can absorb better engines later:
    <https://arxiv.org/abs/2509.11720>.
- Candidate scorecard:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Let each engine return raw `DocumentExtraction` forever | 61 | Reject | Planner would keep depending on engine internals and metadata conventions. |
| Add Docling/Unstructured runtime conversion now | 77 | Defer | Useful future bridge, but too broad for HWPX/native adapter plumbing in this checkpoint. |
| Add orchestrator `build_document_ir()` wrapping existing extractions | 95 | Adopt | Small boundary, fixture-testable, keeps adapter provenance, and supports empty partial IR. |

Implemented in this slice:

- Added `DocumentOrchestrator.build_document_ir()`.
- Engine provenance is read from extraction metadata keys `engine_id`,
  `adapter_id`, or `format_adapter_id`, otherwise falls back to
  `document-orchestrator`.
- Empty extractions now produce valid empty `DocumentIR` objects instead of
  causing planner setup failure.

Verification:

- RED observed:
  `AttributeError: 'DocumentOrchestrator' object has no attribute 'build_document_ir'`.
- GREEN:
  `uv run pytest tests/tools/documents/test_orchestrator.py::test_orchestrator_builds_document_ir_from_inspection_result tests/tools/documents/test_orchestrator.py::test_orchestrator_builds_empty_partial_ir_when_extraction_has_no_blocks -q`
  -> `2 passed`.
- Focused combined gate:
  `uv run pytest tests/tools/documents/test_autonomous_fill_planner.py tests/tools/documents/test_models.py tests/tools/documents/test_orchestrator.py tests/tools/documents/test_inspection_flow.py tests/tools/documents/test_document_tool_flow.py tests/tools/documents/test_adapter_registry.py tests/tools/documents/test_intake_security.py -q`
  -> `89 passed`.
- Focused lint:
  `uv run ruff check src/ummaya/tools/documents/planner.py src/ummaya/tools/documents/orchestrator.py src/ummaya/tools/documents/adapter_registry.py src/ummaya/tools/documents/formats/base.py src/ummaya/tools/documents/intake.py src/ummaya/tools/documents/models.py src/ummaya/tools/documents/__init__.py src/ummaya/tools/documents/inspection.py src/ummaya/tools/documents/registry.py tests/tools/documents/test_autonomous_fill_planner.py tests/tools/documents/test_orchestrator.py tests/tools/documents/test_adapter_registry.py tests/tools/documents/test_intake_security.py tests/tools/documents/test_models.py tests/tools/documents/test_inspection_flow.py tests/tools/documents/test_document_tool_flow.py`
  -> pass.
- Focused type check:
  `uv run mypy src/ummaya/tools/documents/planner.py src/ummaya/tools/documents/orchestrator.py src/ummaya/tools/documents/adapter_registry.py src/ummaya/tools/documents/formats/base.py src/ummaya/tools/documents/intake.py src/ummaya/tools/documents/models.py src/ummaya/tools/documents/inspection.py src/ummaya/tools/documents/registry.py`
  -> pass.

Checkpoint: planner wired into the `document` primitive before `copy_for_edit`.

Deep research migration note:

- Local anchors: `DocumentToolRuntime.document()`,
  `DocumentOrchestrator.build_document_ir()`, `planner.py`, and
  `DocumentPrimitiveRequest`.
- CC restored-source status: intact for one model-facing edit tool, validation
  before mutation, and structured result rendering. The autonomous fill planner
  is an UMMAYA public-document domain stage below that single tool surface.
- 2026-current sources:
  - Docling `DoclingDocument` and `docling-core` support a provenance-carrying
    structured document model. Adopted as the reference for routing from
    extraction to IR before mutation:
    <https://docling-project.github.io/docling/reference/docling_document/>,
    <https://github.com/docling-project/docling-core>.
  - Unstructured's element model keeps element IDs and metadata coordinates,
    reinforcing that planner inputs should be anchored document elements rather
    than raw text:
    <https://docs.unstructured.io/open-source/concepts/document-elements>.
  - OWASP LLM Prompt Injection guidance and 2026 agentic-document risk papers
    support treating document content as untrusted data and blocking protected
    silent writes before a working copy is created:
    <https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html>,
    <https://arxiv.org/abs/2602.22450>,
    <https://arxiv.org/abs/2601.09625>.
- Candidate scorecard:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Keep requiring explicit patches for every fill | 57 | Reject | The model must understand "read and fill this document" without users naming internal inspect/fill/render steps. |
| Let the LLM emit raw patch fields directly | 51 | Reject | Weak provenance and unsafe for public forms with protected identity/legal slots. |
| Run deterministic `DocumentIR` planner inside `document` before `copy_for_edit` | 96 | Adopt | Preserves one primitive, keeps mutation fail-closed, supports TDD, and blocks protected plans before derivative writes. |

Implemented in this slice:

- `DocumentToolRuntime.document()` now inspects, builds `DocumentIR`, and runs
  `plan_autonomous_fill()` when a fill-style request has no explicit patches.
- Safe autonomous plan slots are converted into bounded `DocumentFieldPatch`
  objects before `copy_for_edit`.
- Plans requiring human review return `needs_input` with blocked slot IDs before
  a working artifact is created.
- Explicit patch requests still bypass the autonomous planner and retain the
  existing mutation path.
- `DocumentInspectionOrchestrator` now declares `build_document_ir()` so the
  runtime depends on an explicit IR-capable boundary.

Verification:

- RED observed:
  - no-patch `document` fill returned `needs_input` instead of performing a safe
    autonomous plan.
  - protected identity form path did not surface
    `resident_registration_number` before copy creation.
  - focused `mypy` then caught the missing orchestrator protocol method and
    artifact-ref type drift.
- GREEN:
  `uv run pytest tests/tools/documents/test_document_tool_flow.py::test_document_primitive_uses_autonomous_plan_when_patches_are_omitted tests/tools/documents/test_document_tool_flow.py::test_document_primitive_blocks_protected_plan_before_working_copy -q`
  -> `2 passed`.
- Focused combined gate:
  `uv run pytest tests/tools/documents/test_autonomous_fill_planner.py tests/tools/documents/test_models.py tests/tools/documents/test_orchestrator.py tests/tools/documents/test_inspection_flow.py tests/tools/documents/test_document_tool_flow.py tests/tools/documents/test_adapter_registry.py tests/tools/documents/test_intake_security.py -q`
  -> pass.
- Focused type check:
  `uv run mypy src/ummaya/tools/documents/planner.py src/ummaya/tools/documents/orchestrator.py src/ummaya/tools/documents/adapter_registry.py src/ummaya/tools/documents/formats/base.py src/ummaya/tools/documents/intake.py src/ummaya/tools/documents/models.py src/ummaya/tools/documents/inspection.py src/ummaya/tools/documents/registry.py`
  -> pass.
- Focused lint:
  `uv run ruff check src/ummaya/tools/documents/planner.py src/ummaya/tools/documents/orchestrator.py src/ummaya/tools/documents/adapter_registry.py src/ummaya/tools/documents/formats/base.py src/ummaya/tools/documents/intake.py src/ummaya/tools/documents/models.py src/ummaya/tools/documents/inspection.py src/ummaya/tools/documents/registry.py tests/tools/documents/test_autonomous_fill_planner.py tests/tools/documents/test_orchestrator.py tests/tools/documents/test_adapter_registry.py tests/tools/documents/test_intake_security.py tests/tools/documents/test_models.py tests/tools/documents/test_inspection_flow.py tests/tools/documents/test_document_tool_flow.py`
  -> pass.
- Diff hygiene:
  `git diff --check -- src/ummaya/tools/documents/planner.py src/ummaya/tools/documents/orchestrator.py src/ummaya/tools/documents/adapter_registry.py src/ummaya/tools/documents/formats/base.py src/ummaya/tools/documents/intake.py src/ummaya/tools/documents/models.py src/ummaya/tools/documents/__init__.py src/ummaya/tools/documents/inspection.py src/ummaya/tools/documents/registry.py tests/tools/documents/test_autonomous_fill_planner.py tests/tools/documents/test_orchestrator.py tests/tools/documents/test_adapter_registry.py tests/tools/documents/test_intake_security.py tests/tools/documents/test_models.py tests/tools/documents/test_inspection_flow.py tests/tools/documents/test_document_tool_flow.py specs/2802-public-doc-harness/format-adapter-execution-progress-2026-06-03.md`
  -> pass.

Phase 3 status:

- Completed for the current skeleton: IR, source anchors, form slots,
  autonomous fill plan, protected ranges, orchestrator IR emission, and primitive
  planner wiring.
- Remaining work moves to Phase 4+ adapter promotion and Phase 9 broader planner
  precision gates.

## Phase 4 - HWPX Adapter Promotion

Status: in progress. HWPX target-normalization responsibility has moved from
the runtime registry into the HWPX adapter boundary.

Checkpoint: HWPX semantic target resolution and table-cell aliases live in
`HwpXDocumentAdapter`.

Deep research migration note:

- Local anchors: `src/ummaya/tools/documents/formats/hwpx.py`,
  `src/ummaya/tools/documents/adapter_registry.py`,
  `src/ummaya/tools/documents/registry.py`, and Phase 4 checklist items for
  wrapping the HWPX engine and moving alias/semantic target resolution into the
  adapter.
- CC restored-source status: intact for one model-facing edit tool and internal
  validation before mutation. HWPX target resolution is an UMMAYA format-adapter
  concern below that CC-shaped boundary.
- 2026-current sources:
  - `rhwp` is an active Rust/WASM HWP/HWPX viewer/editor with parsing, rendering,
    editing, SVG/canvas output, page layer tree, and HWPX save/compatibility work.
    Adopted as the reference direction for native HWPX adapter boundaries and
    render-only evidence, not as a new runtime dependency in this slice:
    <https://github.com/edwardkim/rhwp>.
  - `OpenHWP` provides Rust crates for HWP read, HWPX read/write, shared IR, and
    editor-oriented document models. Adopted as the architecture signal for
    format-native adapters plus a shared IR boundary:
    <https://github.com/openhwp/openhwp>.
  - `HwpForge` exposes HWPX read/write, JSON round-trip editing, and an MCP
    server direction for AI agents. Used as a secondary OSS signal that HWPX
    mutation should sit behind a HWPX-specific boundary:
    <https://github.com/ai-screams/HwpForge>.
  - `rhwp validate` issue #185 tracks DVC-like HWP/HWPX validation through a
    Rust CLI and shared IR, supporting future HWPX conformance gates:
    <https://github.com/edwardkim/rhwp/issues/185>.
- Candidate scorecard:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Keep HWPX semantic/alias regex in `registry.py` | 49 | Reject | Registry continues knowing HWPX table paths and semantic labels, violating adapter separation. |
| Adopt RHWP/OpenHWP/HwpForge as runtime dependency now | 78 | Defer | Strong ecosystem signal, but dependency/bridge/ADR work is larger than this target-resolution checkpoint. |
| Add `HwpXDocumentAdapter.normalize_fill_patches()` and let runtime call adapter hooks | 96 | Adopt | Keeps one primitive, moves HWPX quirks below the adapter boundary, is fixture-testable, and preserves current mutation behavior. |

Implemented in this slice:

- Added `normalize_fill_patches()` to the document adapter protocol.
- Added identity normalization to `EngineBackedDocumentAdapter`.
- Added `HwpXDocumentAdapter`, wrapping `HwpXPackageTextEngine` and declaring
  HWPX/OWPML known formats plus HWPX promoted runtime format.
- Moved HWPX table-cell aliases, semantic target grouping, week-label value
  normalization, and activity-period matching into `formats/hwpx.py`.
- `DocumentToolRuntime.document()` and `apply_fill()` now normalize patches
  through the promoted adapter rather than HWPX-specific registry helpers.
- Removed HWPX semantic/alias helper logic from `registry.py`; only generic
  filename/MIME handling still mentions `hwpx`.
- Added conservative HWPX text-value label promotion for plain text fixtures:
  week labels, activity periods, and non-label special-notes values.

Verification:

- RED observed:
  `ImportError: cannot import name 'HwpXDocumentAdapter'`.
- GREEN adapter contract:
  `uv run pytest tests/tools/documents/test_builtin_hwpx_engine.py::test_hwpx_adapter_normalizes_semantic_targets_and_table_cell_aliases -q`
  -> pass.
- Regression observed and fixed:
  - instruction-only HWPX fill regressed to `needs_input` because plain text
    slots were not labeled as week/activity-period slots.
  - table label cells were temporarily over-promoted as fillable
    `특이사항` targets; narrowed to value cells only.
- HWPX suite:
  `uv run pytest tests/tools/documents/test_builtin_hwpx_engine.py -q`
  -> `12 passed`.
- Focused combined gate:
  `uv run pytest tests/tools/documents/test_builtin_hwpx_engine.py tests/tools/documents/test_adapter_registry.py tests/tools/documents/test_document_tool_flow.py tests/tools/documents/test_autonomous_fill_planner.py tests/tools/documents/test_orchestrator.py tests/tools/documents/test_inspection_flow.py tests/tools/documents/test_models.py tests/tools/documents/test_intake_security.py -q`
  -> pass.
- Registry leakage check:
  `rg -n "HWPX|hwpx|semantic|_HWPX|_semantic|table_cell_alias|week_label|activity_period" src/ummaya/tools/documents/registry.py`
  -> only filename noise and MIME mapping remain.
- Focused lint:
  `uv run ruff check src/ummaya/tools/documents/formats/base.py src/ummaya/tools/documents/formats/hwpx.py src/ummaya/tools/documents/adapter_registry.py src/ummaya/tools/documents/registry.py tests/tools/documents/test_builtin_hwpx_engine.py tests/tools/documents/test_adapter_registry.py tests/tools/documents/test_document_tool_flow.py`
  -> pass.
- Focused type check:
  `uv run mypy src/ummaya/tools/documents/formats/base.py src/ummaya/tools/documents/formats/hwpx.py src/ummaya/tools/documents/adapter_registry.py src/ummaya/tools/documents/registry.py`
  -> pass.
- Diff hygiene:
  `git diff --check -- src/ummaya/tools/documents/formats/base.py src/ummaya/tools/documents/formats/hwpx.py src/ummaya/tools/documents/adapter_registry.py src/ummaya/tools/documents/registry.py tests/tools/documents/test_builtin_hwpx_engine.py specs/2802-public-doc-harness/format-adapter-execution-progress-2026-06-03.md specs/2802-public-doc-harness/format-adapter-implementation-plan-2026-06-03.md`
  -> pass.

Remaining Phase 4 gates:

- Strengthen HWPX render/re-read/diff evidence around real public-form fixtures.
- Move toward HWPX conformance/promotion scoring once fixture evidence is broad
  enough.

Checkpoint: copied public AX weekly-log fixture autonomous fill, render, and
re-read.

Deep research migration note:

- Local anchors: copied local evidence fixtures under
  `.evidence/document-fixtures/public-ax-samples/`,
  `autonomous-fill-plan-research-2026-06-03.md`, and the Phase 4 checklist item
  requiring public AX weekly-log fixture tests.
- CC restored-source status: intact for one edit tool and structured
  post-mutation result evidence. The fixture-specific behavior remains below the
  document primitive through HWPX adapter + planner + render/re-read stages.
- 2026-current sources:
  - The same HWPX OSS references from the previous Phase 4 checkpoint remain the
    selected evidence direction: RHWP for local render evidence, OpenHWP for
    native HWPX read/write/IR architecture, and HwpForge as AI-agent-oriented
    HWPX mutation signal.
  - The fixture research artifact records the copied public AX samples, hashes,
    HWP blocked status, and HWPX weekly-log editability:
    `specs/2802-public-doc-harness/autonomous-fill-plan-research-2026-06-03.md`.
- Candidate scorecard:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Keep only synthetic HWPX fixtures | 58 | Reject | It cannot prove the actual public AX weekly-log sample path. |
| Check the 215 KB HWPX fixture into `tests/fixtures` now | 73 | Defer | File size is acceptable, but redistribution/licensing and fixture manifest policy should be handled deliberately. |
| Use local `.evidence` fixture with hash-gated pytest skip when absent | 93 | Adopt | Gives strict local alpha proof without forcing CI to depend on user-provided local files. |

Implemented in this slice:

- Added `test_public_ax_weekly_hwp_fixture_autonomous_next_week_fill_render_and_reread`.
- The test locates the local `.evidence` HWPX weekly-log fixture, verifies its
  SHA-256 hash
  `b6ac058e55144a8a680744e364b74c73bb54e11426e714297ded7bfe914fa35d`, and skips
  only when the local evidence fixture is unavailable.
- The test asks the single `document` primitive to infer the next weekly log
  without explicit patches.
- Expected real-fixture diff:
  - `/hwpx/text[2]`: `13 주차 ` -> `14주차`
  - `/hwpx/text[12]`: `2026.06.01 ~ 2026.06.07` -> `2026.06.08~2026.06.14`
- The test asserts render artifact creation and re-reads the derivative to
  confirm the saved HWPX values.

Verification:

- Manual smoke before test:
  `runtime.document(... instruction="문서 내용을 파악하고 알아서 다음 주차 활동일지로 작성해.")`
  -> `ok`, one render artifact, and the expected two changed HWPX paths.
- GREEN:
  `uv run pytest tests/tools/documents/test_builtin_hwpx_engine.py::test_public_ax_weekly_hwp_fixture_autonomous_next_week_fill_render_and_reread -q`
  -> pass.
- HWPX suite:
  `uv run pytest tests/tools/documents/test_builtin_hwpx_engine.py -q`
  -> `13 passed`.
- Focused combined gate:
  `uv run pytest tests/tools/documents/test_builtin_hwpx_engine.py tests/tools/documents/test_adapter_registry.py tests/tools/documents/test_document_tool_flow.py tests/tools/documents/test_autonomous_fill_planner.py tests/tools/documents/test_orchestrator.py tests/tools/documents/test_inspection_flow.py tests/tools/documents/test_models.py tests/tools/documents/test_intake_security.py -q`
  -> pass.
- Focused lint:
  `uv run ruff check src/ummaya/tools/documents/formats/base.py src/ummaya/tools/documents/formats/hwpx.py src/ummaya/tools/documents/adapter_registry.py src/ummaya/tools/documents/registry.py tests/tools/documents/test_builtin_hwpx_engine.py tests/tools/documents/test_adapter_registry.py tests/tools/documents/test_document_tool_flow.py`
  -> pass.
- Focused type check:
  `uv run mypy src/ummaya/tools/documents/formats/base.py src/ummaya/tools/documents/formats/hwpx.py src/ummaya/tools/documents/adapter_registry.py src/ummaya/tools/documents/registry.py`
  -> pass.
- Diff hygiene:
  `git diff --check -- src/ummaya/tools/documents/formats/base.py src/ummaya/tools/documents/formats/hwpx.py src/ummaya/tools/documents/adapter_registry.py src/ummaya/tools/documents/registry.py tests/tools/documents/test_builtin_hwpx_engine.py specs/2802-public-doc-harness/format-adapter-execution-progress-2026-06-03.md specs/2802-public-doc-harness/format-adapter-implementation-plan-2026-06-03.md`
  -> pass.

Remaining Phase 4 gates:

- Move toward HWPX conformance/promotion scoring once fixture evidence is broad
  enough.

## Current Goal Loop - OWPML Package Alias Promotion

Status: completed for bounded write/render/save promotion through the HWPX package
engine boundary.

Deep research migration note:

- Local anchors: `models.py`, `intake.py`, `formats/hwpx.py`,
  `engines.py`, `adapter_registry.py`, `format_completion_audit.py`, and the
  promoted workflow matrix.
- CC restored-source status: intact at the single-tool result boundary. OWPML is
  a UMMAYA format-adapter detail below the `document` primitive, not a separate
  model-facing tool.
- 2026-current sources:
  - Hancom's `hwpx-owpml-model` describes OWPML as an OOXML-structured filter
    model that can extract and save individual document elements.
  - `@ssabrojs/hwpxjs` documents HWPX writing through OWPML package rules:
    first stored `mimetype`, container/manifest, OPF spine, and `header.xml`.
  - `pyhwpxlib` describes HWPX as a ZIP archive of OWPML XML and supports pure
    Python create/edit workflows, but its BSL/commercial boundary keeps it as a
    reference signal rather than a dependency in this loop.
  - `rhwp-python` reports HWP/HWPX parsing and SVG/PDF rendering through a
    Rust core, which reinforces the local render-bridge direction but does not
    change UMMAYA's existing write boundary.
- Candidate scorecard:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Keep OWPML passive/context-only | 51 | Reject | It loses a package-compatible editable format already addressed by the HWPX engine. |
| Add a separate OWPML parser/writer from scratch | 62 | Reject | Duplicates the HWPX package engine and increases divergence without better evidence. |
| Promote OWPML as a HWPX package-engine alias with explicit detected format preservation | 95 | Adopt | Matches OWPML/HWPX package reality, keeps one adapter boundary, and preserves truthful `owpml` metadata. |

Implemented in this slice:

- Added `DocumentFormat.owpml`.
- Added `OwpmlPackageTextEngine` as a bounded alias of the existing HWPX package
  text engine.
- Promoted `HwpXDocumentAdapter` for both `hwpx` and `owpml`.
- Added `.owpml` MIME/intake handling and package-marker aliasing so `.owpml`
  sources remain `owpml` through intake, storage, render, re-read, and audit.
- Updated completion audit and Evidence Fabric expectations to include OWPML in
  `write_render_save_promoted`.

Verification:

- RED observed:
  `DocumentFormat.owpml` missing in
  `test_owpml_document_primitive_save_renders_rereads_and_diffs`.
- GREEN:
  `uv run pytest tests/tools/documents/test_promoted_format_workflow_matrix.py::test_owpml_document_primitive_save_renders_rereads_and_diffs tests/tools/documents/test_intake_security.py::test_promoted_runtime_formats_emit_known_format_and_family_metadata tests/tools/documents/test_models.py::test_known_document_formats_separate_all_format_classification_from_runtime_promotion tests/tools/documents/test_format_completion_audit.py -q`
  -> `37 passed`.
- Registry/evidence:
  `uv run pytest tests/tools/documents/test_adapter_registry.py tests/tools/documents/test_artifact_store.py tests/evidence/test_document_harness_evidence.py -q`
  -> `30 passed`.
- Audit snapshot:
  `complete_count=32`, `incomplete_count=27`, `all_formats_complete=False`.

Remaining goal blockers:

- HWP direct write remains blocked until a vetted HWP-to-HWPX bridge passes.
- Legacy Office derivative promotion remains blocked until a local LibreOffice
  bridge is approved and fixture-proven.
- PDF/A, EPUB/archive, raster images, media, and GIS/model assets are still
  passive or blocked because they are not safely editable public-document
  originals in the current harness.

## Current Goal Loop - ODF Bounded Promotion

Status: completed for bounded ODT/ODS/ODP write/render/save. Original-page
layout oracle remains deferred.

Deep research migration note:

- Local anchors: `models.py`, `intake.py`, `engines.py`, `adapter_registry.py`,
  `formats/passive.py`, and the existing single `document(save)` primitive
  matrix.
- CC restored-source status: no native office-document format implementation
  exists in CC; parity applies to one model-facing tool surface, fail-closed
  validation, visible diff/result rendering, and no fallback success.
- 2026-current sources:
  - OASIS OpenDocument v1.4 Part 2/Part 3 define the package and `content.xml`
    structure used for intake detection and native lineage.
  - `odfdo` v3.22.8 is Apache-2.0, current, Python 3.10-3.14 compatible, and
    supports creating, parsing, editing, and saving ODT/ODS/ODP packages.
  - LibreOffice 26.2 CLI export remains the next local layout oracle candidate,
    but it is not installed locally and is not bundled in UMMAYA.

Candidate scorecard:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Keep ODF passive/read-only | 66 | Reject for this loop | It under-serves public-form ODT/ODS/ODP once a current Apache-2.0 writer is available. |
| Hand-patch ODF XML in zip packages | 54 | Reject | Too brittle for package relationships, tables, sheets, and presentation frames. |
| Promote odfdo bounded writer plus structural SVG renderer | 91 | Adopt | Provides native package save/re-read with clear limits and no unavailable layout-oracle claim. |
| Block promotion until LibreOffice is installed | 73 | Defer as visual-fidelity gate | Correct for original-page render parity, too conservative for bounded document authoring. |

Implemented in this loop:

- Added `odfdo>=3.22.8,<4` as the ODF writer dependency.
- Promoted `odt`, `ods`, and `odp` into `DocumentFormat`.
- Added MIME mappings for ODF artifacts.
- Added ODF package detection using `mimetype`, `META-INF/manifest.xml`, and
  `content.xml`.
- Added `OdfdoTextDocumentEngine`, `OdfdoSpreadsheetDocumentEngine`, and
  `OdfdoPresentationDocumentEngine`.
- Added `OdfdoDocumentAdapter` and default-registry routing for promoted ODF.
- Updated ODF probe and completion audit to report
  `promoted_bounded`/`write_render_save_promoted` with
  `libreoffice_layout_oracle_deferred`.

Verification:

- RED observed: ODF primitive save failed at intake with `signature_mismatch`.
- GREEN:
  `uv run pytest tests/tools/documents/test_promoted_format_workflow_matrix.py -q`
  -> `8 passed`, including ODT, ODS, and ODP save/render/re-read/diff cases.
- GREEN:
  `uv run pytest tests/tools/documents/test_intake_security.py -q`
  -> pass for ODF package signature metadata.
- GREEN:
  `uv run pytest tests/tools/documents/test_odf_promotion_probe.py tests/tools/documents/test_format_completion_audit.py -q`
  -> ODF reports bounded promotion while keeping LibreOffice layout oracle
  deferred.
- Focused lint/type gates passed for ODF implementation files.

Remaining gates:

- Add local-only LibreOffice layout-oracle bridge when an explicit executable
  contract is approved and present.
- Add richer Korean ODT/ODS/ODP style/layout fixtures.
- Capture TUI-facing ODF diff evidence through a real model-backed `bun run tui`
  session once credentials are available.

## Current Goal Loop - Text/Web Bounded Promotion

Status: completed for bounded HTML/HTM/TXT/RTF/MD write/render/save.

Deep research migration note:

- Local anchors: `formats/passive.py` text extraction behavior, `intake.py`
  fail-closed signature gate, and the single `document(save)` promoted matrix.
- Current public-infrastructure signal: official Korean public-data surfaces
  expose machine-readable data formats separately from office-document
  preservation formats. Text/web exports remain document-like enough to write as
  bounded derivatives, while public-data/media/GIS/archive assets remain separate
  capability families.
- Reference decision: do not mutate passive adapter behavior. Add a promoted
  text/web adapter below the existing single document primitive.

Candidate scorecard:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Keep all text/web formats passive | 69 | Reject for this loop | TXT/MD/HTML/RTF can be safely authored locally and are document-like outputs. |
| Route text/web through OOXML conversion | 55 | Reject | Adds conversion drift and unnecessary dependency for simple UTF-8 formats. |
| Add bounded text/web native writer | 93 | Adopt | Local-only, easy to inspect, produces derivative bytes and structural SVG evidence. |

Implemented in this loop:

- Promoted `html`, `htm`, `txt`, `rtf`, and `md` into `DocumentFormat`.
- Added `formats/text_web.py` with `TextWebDocumentEngine` and
  `TextWebDocumentAdapter`.
- Added UTF-8/HTML/RTF intake detection.
- Added body-level structured diff support for `/text/body`.
- Registered the text/web engines and adapter in default runtime registries.
- Updated completion audit to report text/web formats as
  `write_render_save_promoted`.

Verification:

- RED observed: `DocumentFormat('txt')` and related text/web values were invalid.
- GREEN:
  `uv run pytest tests/tools/documents/test_promoted_format_workflow_matrix.py::test_text_web_document_primitive_save_renders_rereads_and_diffs -q`
  -> `5 passed`.
- GREEN:
  `uv run pytest tests/tools/documents/test_intake_security.py tests/tools/documents/test_passive_format_adapters.py tests/tools/documents/test_format_completion_audit.py -q`
  -> promoted text/web routing and completion passed.
- Focused `ruff` and `mypy` gates passed for the text/web implementation files.

Remaining gates:

- Public-data writer promotion is still separate from text/web document writing.
- EPUB remains an archive/publication container until child-routing writer gates
  exist.

## Current Goal Loop - Structured Public-Data Text Promotion

Status: completed for bounded body-level write/render/save across promoted
public-data text formats.

Deep research migration note:

- Local anchors: passive data extraction/round-trip tests, `intake.py`
  classification, data.go.kr/public-data format coverage, and the single
  `document(save)` promoted matrix.
- Current public-infrastructure signal: public-data portals expose CSV, JSON,
  XML, TTL, SHP, RDF, GPX, and related formats as first-class public
  infrastructure assets. Textual data formats can be safely authored as bounded
  derivatives; binary GIS/media/archive formats remain separate.
- Reference decision: promote only UTF-8 text data files and require structure
  validation where a deterministic local parser exists.

Candidate scorecard:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Keep data files passive context only | 72 | Reject for text data | Useful for reasoning but insufficient for data-submission artifacts. |
| Add per-format arbitrary field mutation now | 61 | Defer | Too many schema-specific semantics; field-level mutation needs schema contracts. |
| Add body-level data writer with validation | 91 | Adopt | Local-only, deterministic, supports save/re-read/render, and avoids schema overclaiming. |

Implemented in this loop:

- Promoted CSV, TSV, XML, RDF, TTL, LOD, JSON, JSONL, YAML, YML, GeoJSON, GPX,
  KML, FASTA, SGML, DTD, HML, and ETC into `DocumentFormat`.
- Added `formats/data_file.py` with `DataFileDocumentEngine` and
  `DataFileDocumentAdapter`.
- Added intake validation for JSON, JSONL, YAML, XML-family files, and UTF-8
  text data files.
- Added body-level structured diff support for `/data/body`.
- Updated completion audit to report data text formats as
  `write_render_save_promoted`.

Verification:

- RED observed: every data suffix failed `DocumentFormat(...)` construction.
- GREEN:
  `uv run pytest tests/tools/documents/test_promoted_format_workflow_matrix.py::test_data_document_primitive_save_renders_rereads_and_diffs -q`
  -> `17 passed`.
- GREEN:
  `uv run pytest tests/tools/documents/test_intake_security.py tests/tools/documents/test_passive_format_adapters.py tests/tools/documents/test_format_completion_audit.py -q`
  -> promoted data routing and completion passed.
- Focused `ruff` and `mypy` gates passed for the data implementation files.

Remaining gates:

- Field-level data mutation needs schema-aware adapters and is intentionally
  deferred.
- Binary GIS assets, image scans, media files, and archives remain non-document
  asset families.

## Phase 10 - TUI and CC Loop Parity

Status: completed for the natural Korean document-edit alpha path.

Checkpoint: document edit must paint in the same loop rhythm as Claude Code.

Deep research migration note:

- Local anchors: `src/ummaya/ipc/stdio.py`,
  `src/ummaya/tools/documents/registry.py`, `tests/integration/test_agentic_loop.py`,
  `tests/tools/documents/test_document_tool_flow.py`, and TUI document result
  rendering under `tui/src/tools/_shared/`.
- CC restored-source status: intact for the agentic loop shape, tool-result
  repair, and visible assistant/tool/result/final ordering. The live baseline
  also confirmed that Claude Code emits assistant prelude, tool use, tool
  result, and final answer as separate visible loop stages.
- 2026-current sources:
  - Claude Code Agent SDK loop docs:
    `https://code.claude.com/docs/en/agent-sdk/agent-loop`
  - Claude tool-use loop docs:
    `https://platform.claude.com/docs/en/agents-and-tools/tool-use/how-tool-use-works`
  - OpenAI Agents SDK guardrail docs:
    `https://openai.github.io/openai-agents-python/ref/guardrail/`
  - Pydantic v2 strict-mode docs:
    `https://pydantic.dev/docs/validation/2.12/concepts/strict_mode/`
- Candidate scorecard:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Prompt-only final-answer nudging | 45 | Reject | The model still overclaimed future workflow and invented activity sections. |
| Renderer/card fallback success | 62 | Reject | It hides failures and repeats the prior fallback-debugging problem. |
| Tool-result-grounded final guardrail plus fail-closed retries | 96 | Adopt | It preserves CC loop rhythm, keeps the model in the loop, and fails when the final answer contradicts the actual diff. |

Implemented in this slice:

- Added document final-answer overclaim detection against the latest successful
  document diff.
- Added direct and nested document-result payload extraction so direct
  `document_apply_fill` outputs are not missed.
- Changed write/review termination checks so inspect-only `document` results no
  longer satisfy mutating document requests.
- Made autonomous Korean instructions planner-owned when the model supplies
  low-level or natural-language patch targets.
- Bound copied document tool-result observation text to avoid context bloat.

Live alpha evidence:

- Claude Code baseline:
  - `claude` was available at `/Users/um-yunsang/.local/bin/claude`.
  - Version observed: `2.1.160 (Claude Code)`.
  - Baseline command used a temp weekly text file and produced the expected
    assistant prelude -> Read/Edit tool use -> tool result -> final sequence.
- UMMAYA TUI:
  - Command: `cd /Users/um-yunsang/UMMAYA/tui && bun run tui`
  - Natural Korean prompt:
    `다운로드 폴더에 있는 ummaya-phase10-grounding-alpha9.hwpx 문서내용을 파악하고 알아서 다음 주차 활동일지로 작성해줘. 수정 후 변경된 부분을 바로 확인할 수 있게 보여주고 최종적으로 실제로 바뀐 내용만 답변해줘.`
  - Visible sequence: assistant prelude -> `Document(Prepare document workflow:
    ummaya-phase10-grounding-alpha9.hwpx)` -> `Changed 2 fields` diff -> final
    answer limited to the two actual changes.
  - Diff shown:
    - `13 주차` -> `14주차`
    - `2026.06.01 ~ 2026.06.07` -> `2026.06.08~2026.06.14`

Residual risk:

- Strict-alpha score: 96/100.
- The remaining 4 points are reserved for durable terminal-frame capture linked
  to Evidence Fabric. The visible live run passed, and Phase 11 now records the
  frame-hash join contract, but future work should replace the placeholder
  alpha frame hash with a captured terminal frame artifact.

Verification:

- `uv run pytest tests/tools/documents/test_document_tool_flow.py tests/integration/test_agentic_loop.py -q`
  -> `17 passed`.
- `uv run pytest tests/tools/documents -q` -> pass.
- `uv run ruff check src tests` -> pass.
- `uv run ruff format --check src tests` -> pass.
- `uv run mypy src` -> pass.
- `git diff --check` -> pass.

## Phase 11 - Evidence Fabric and Beta Matrix

Status: completed for the current Evidence Fabric v2 checkpoint.

Checkpoint: backend evidence, UX frame evidence, beta domains, and negative
flows must be joinable and fail closed.

Deep research migration note:

- Local anchors: `src/ummaya/evidence/document_harness.py`,
  `src/ummaya/evidence/runner.py`, `src/ummaya/evidence/document_viewer_ux.py`,
  `evidence/scenarios/document_harness_v1.yaml`, and
  `tests/evidence/test_document_harness_evidence.py`.
- CC restored-source status: no direct document Evidence Fabric analog exists in
  CC. The adopted shape keeps the CC loop order as the runtime source and adds
  UMMAYA-only join metadata below the document primitive boundary.
- 2026-current sources:
  - OpenTelemetry trace API for immutable trace/span context and join IDs:
    `https://opentelemetry.io/docs/specs/otel/trace/api/`
  - Pydantic v2 strict model behavior:
    `https://pydantic.dev/docs/validation/2.12/concepts/strict_mode/`
  - Playwright screenshot evidence capture:
    `https://playwright.dev/docs/next/screenshots`
  - OpenAI/Claude guardrail and tool-loop sources listed in Phase 10.
- Candidate scorecard:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Keep only derivative-level evidence records | 58 | Reject | It cannot prove intake -> TUI-frame lifecycle coverage. |
| Add free-form beta notes to the spec only | 49 | Reject | It does not make failures machine-checkable. |
| Add typed lifecycle, beta, negative, and UX-join records to Evidence Fabric | 97 | Adopt | It is local-only, schema-checked, and proves correlation/hash joins without embedding document bytes. |

Implemented in this slice:

- Added typed `DocumentLifecycleEvidenceRecord`, `DocumentBetaCase`, and
  `DocumentNegativeCase` models.
- Extended `document_harness_v1.yaml` with:
  - 11 lifecycle records: intake, classification, capability, adapter
    selection, permission, mutation, render, reread, validation, diff, and
    TUI frame.
  - 12 beta cases across weekly log, contest proposal, consent, pledge,
    spreadsheet, PDF form, presentation, public-data CSV/JSON, static PDF,
    scanned image, and archive bundle.
  - 9 negative cases: missing file, ambiguous candidates, unsupported known
    format, blocked HWP write, static PDF fill, macro/active content, path
    traversal, oversized archive, and external link.
- Evidence runner now emits:
  - `document_lifecycle_records`
  - `document_beta_cases`
  - `document_negative_cases`
- Evidence runner now rejects document viewer UX artifacts that do not join a
  backend document diff by `(document_diff_id, correlation_id)`.

Evidence output:

- Command: `uv run python -m ummaya.evidence --source-ref local --out .evidence/run.json`
- `.evidence/run.json` now contains:
  - `document_evidence_records`: 5
  - `document_lifecycle_records`: 11
  - `document_beta_cases`: 12
  - `document_negative_cases`: 9

Verification:

- RED observed:
  - `DocumentHarnessScenario` had no `lifecycle_records`, `beta_cases`, or
    `negative_cases`.
  - Evidence payload had no `document_lifecycle_records`.
  - UX artifacts were accepted even when not joined to backend diff records.
- GREEN:
  - `uv run pytest tests/evidence/test_document_harness_evidence.py tests/evidence/test_document_viewer_ux_evidence.py -q`
    -> `13 passed`.
  - `uv run pytest tests/evidence -q` -> `17 passed`.
  - `uv run python -m ummaya.evidence --source-ref local --out .evidence/run.json`
    -> pass.

Phase 11 status:

- Completed for lifecycle join records, domain beta matrix, negative beta
  matrix, UX artifact join validation, and Evidence Fabric output generation.

## 2026-06-03 Phase 9 autonomous fill planner extension

Checkpoint: cross-format IR slot extraction and fail-closed autonomous fill
planning for "read the document and write it yourself" requests.

Deep research migration note:

- Local anchors: `DocumentIR.from_extraction()`, `planner.py`,
  `DocumentToolRuntime.document()`, the copied public-document fixtures, and the
  Phase 9 checklist in `format-adapter-implementation-plan-2026-06-03.md`.
- CC restored-source status: no direct public-document semantic planner exists
  in the restored Claude Code source; the adopted boundary preserves the CC edit
  contract of one visible model-facing tool result after a mutating operation.
- 2026-current sources:
  - `autonomous-fill-plan-research-2026-06-03.md` keeps the MOIS
    AI-friendly public-writing guidance, NIKL public-language guidance,
    legal-text preservation requirements, and recent document-understanding
    research as planner constraints.
  - Phase 6/7 package decisions remain the active OSS boundary:
    `python-docx`, `openpyxl`, `python-pptx`, `pypdf`, and `pypdfium2` feed
    normalized extraction/render evidence; planner code consumes only
    `DocumentIR`, not engine internals.
- Candidate scorecard:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| LLM writes patches directly from raw extracted text | 51 | Reject | Weak provenance, hard to test, and unsafe for legal/identity fields. |
| Per-format planner branches call engine internals | 66 | Reject | Duplicates adapter logic and breaks the format-neutral primitive boundary. |
| Extend `DocumentIR` slots plus deterministic precedence and protected-field suppression | 96 | Adopt | Keeps native anchors, is cross-format fixture-testable, and fails closed before mutation. |

Implemented in this slice:

- `DocumentIR.from_extraction()` now promotes label/value table cells,
  sheet-cell targets, slide text placeholders, and AcroForm fields into
  planner-facing `FormSlot`s with `SourceAnchor` sheet/slide indexes.
- Protected field detection is shared across extracted fields and inferred
  slots so legal, signature, consent, address, phone, account, resident-number,
  applicant/name-like identity ranges require human review before mutation.
- `plan_autonomous_fill()` now accepts cited `session_context`, applies
  precedence of explicit values, safe recurrence, session context, keyed free
  text, then `needs_input`, and suppresses protected values even when context
  supplies them.
- `public_document_writing_profile()` exposes the current public-form writing
  constraints: clear subject/predicate, plain public Korean, standard numbering,
  simple tables, and legal text preservation.
- The single `document` primitive review message now names blocked or missing
  slots instead of pretending every review case is only a protected edit.

Verification:

- RED observed:
  `uv run pytest tests/tools/documents/test_autonomous_fill_planner.py -q`
  initially failed on missing cross-format IR slots, missing
  `session_context`, and missing writing profile.
- GREEN:
  `uv run pytest tests/tools/documents/test_autonomous_fill_planner.py -q`
  -> `7 passed`.
- Focused document harness gate:
  `uv run pytest tests/tools/documents/test_models.py tests/tools/documents/test_orchestrator.py tests/tools/documents/test_adapter_registry.py tests/tools/documents/test_document_tool_flow.py tests/tools/documents/test_inspection_flow.py tests/tools/documents/test_intake_security.py tests/tools/documents/test_autonomous_fill_planner.py -q`
  -> pass.

Remaining Phase 9/10 gate:

- Natural Korean TUI query tests with no tool-name hints are still pending and
  are tracked in Phase 10 because they verify loop painting, not only planner
  semantics.

## Phase 7 - PDF Adapter

Status: completed for AcroForm-only PDF fill promotion and typed blocked cases.

Checkpoint: PDF AcroForm adapter, visible render evidence, and fail-closed
non-AcroForm mutation.

Deep research migration note:

- Local anchors: `formats/pdf.py`, `adapter_registry.py`, `engines.py`,
  `patch.py`, `render.py`, `test_pdf_adapter.py`, `test_pdf_fill.py`,
  `candidate_profiles.yaml`, and the Phase 7 checklist.
- CC restored-source status: no direct public-document PDF authoring adapter is
  present in Claude Code. The applicable CC shape remains one model-facing tool
  boundary, typed validation before mutation, immediate diff/result evidence,
  and no fallback success when the intended mutation path is unsupported.
- 2026-current sources:
  - `pypdf` 6.12.2 official forms guide documents `get_form_text_fields()`,
    `get_fields()`, and `update_page_form_field_values(...,
    auto_regenerate=False)` for AcroForm fill.
  - `pypdf` security docs document decompression/output-size guards that support
    using it as the local AcroForm structure/value engine.
  - `PyMuPDF` 1.27.2.3 was initially selected as the render oracle, but the
    local pytest collection path consistently segfaulted while importing
    `pymupdf.mupdf` on macOS ARM64/CPython 3.12. Standalone import passed, so the
    hard failure is the pytest/runtime stability gate, not PDF rendering quality.
  - `pypdfium2` 5.9.0 official docs expose PDFium page render and form
    environment support, PyPI ships a macOS ARM64 wheel uploaded 2026-06-01, and
    licensing is Apache-2.0/BSD-3-Clause.
  - `reportlab` 4.5.1 is BSD and used only as a dev/test fixture generator for
    AcroForm, static, scanned, XFA, signed, and encrypted PDF samples.
- Candidate scorecard:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| pypdf-only AcroForm fill without render oracle | 72 | Reject | Re-read passes, but visible appearance mismatch is not proven. |
| pypdf + PyMuPDF render oracle | 54 | Reject | Officially strong renderer, but local pytest/macOS ARM64 gate segfaults and cannot be promoted. |
| pypdf + pypdfium2 render oracle | 96 | Adopt | AcroForm values re-read, page PNG evidence changes visibly, local pytest gate is stable, and licenses are compatible. |
| qpdf/Poppler external CLI oracle | 78 | Defer | Good structure/render comparison candidates, but adds external binary management and is not needed after pypdfium2 passes. |

Implemented in this slice:

- Added `PdfDocumentAdapter` backed by `PypdfAcroFormEngine`.
- Added `PdfDocumentKind` and `classify_pdf_document()` for `acroform`,
  `static`, `scanned`, `xfa`, `encrypted`, and `signed`.
- Added `DocumentMutationBlockedError` so engines can return typed block
  reasons instead of collapsing everything to `validation_failed`.
- Added PDF-specific block reasons:
  `static_pdf`, `scanned_pdf`, `xfa_detected`, and `signature_detected`.
- Registered PDF in the default adapter and engine registries.
- Added AcroForm field fill through `pypdf` and PNG render evidence through
  `pypdfium2`.
- Added visible-render verification by comparing before/after rendered page PNGs
  and re-reading AcroForm values before saving a successful derivative.
- Added candidate profile promotion for `pdf/pypdf-acroform` write.
- Kept XFA, static, scanned, encrypted, and signed PDFs blocked from mutation.

Verification:

- RED observed:
  `ImportError: cannot import name 'PdfDocumentAdapter'`.
- First render candidate rejected:
  `uv run pytest tests/tools/documents/test_pdf_adapter.py -q`
  -> PyMuPDF import segfault under pytest collection.
- pypdfium2 probe:
  ReportLab AcroForm -> pypdf fill -> pypdfium2 render produced PNG bytes and
  before/after page renders differed.
- GREEN focused:
  `uv run pytest tests/tools/documents/test_pdf_adapter.py -q`
  -> `7 passed`.
- Focused PDF/registry/render gate:
  `uv run pytest tests/tools/documents/test_pdf_adapter.py tests/tools/documents/test_pdf_fill.py tests/tools/documents/test_adapter_registry.py tests/tools/documents/test_builtin_engine_promotion.py tests/tools/documents/test_candidate_evaluation.py tests/tools/documents/test_render_and_reread.py -q`
  -> `36 passed`.
- Full document harness:
  `uv run pytest tests/tools/documents -q`
  -> pass.
- Static gates:
  `uv run ruff check src tests` -> pass.
  `uv run ruff format --check src tests` -> pass.
  `uv run mypy src` -> pass.

Phase 7 status:

- Completed for PDF AcroForm-only fill, typed blocked non-AcroForm mutation,
  visible page-render evidence, default registry promotion, and candidate
  profile promotion.

## Phase 8 - Passive Known-Only Format Families

Status: completed for ODF, data-file, text/web export, image/scan, and archive
known-only adapters.

Checkpoint: non-promoted national-infrastructure document families classify,
inspect safely when addressed by known-format registry, and never present a
write-capable runtime surface.

Deep research migration note:

- Local anchors: `KnownDocumentFormat`, `DocumentFormatFamily`, `intake.py`,
  `adapter_registry.py`, `formats/passive.py`, and
  `test_passive_format_adapters.py`.
- CC restored-source status: no direct ODF/data/image/archive public-document
  writer exists in Claude Code. The applicable CC shape is fail-closed tool
  capability and explicit result evidence below one document primitive.
- 2026-current sources:
  - OASIS OpenDocument 1.4 states package conformance around `content.xml`,
    `styles.xml`, `settings.xml`, and `meta.xml`; UMMAYA adopts ZIP/XML
    extraction only, not write promotion.
  - Python 3.12 stdlib `csv`, `json`, `html.parser`, `zipfile`, `tarfile`, and
    `gzip` are sufficient for local passive parsing and archive enumeration.
  - PyYAML documentation requires `safe_load` for untrusted YAML; UMMAYA uses
    `safe_load/safe_dump` only.
  - defusedxml remains the XML parser boundary for passive XML/ODF content.
  - OWASP file-upload guidance from the base plan still applies to archive,
    extension, size, and traversal controls.
- Candidate scorecard:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Treat these families as unknown | 52 | Reject | Loses national-infrastructure format guidance and next-safe actions. |
| Promote universal read/write adapters now | 43 | Reject | Would overclaim unsupported ODF/image/archive mutation and weaken public-form safety. |
| Convert all to DOCX/PDF before inspection | 60 | Reject | Conversion drift hides native identity and lineage. |
| Register known-only passive adapters with serializer/child-routing evidence | 94 | Adopt | Classifies all families, provides safe read evidence, and keeps writes blocked. |

Implemented in this slice:

- Added `formats/passive.py` with:
  - `OdfDocumentAdapter` for ODT/ODS/ODP read-only package text extraction;
  - `DataFileDocumentAdapter` for CSV/TSV/XML/JSON/JSONL/YAML safe parsing and
    serializer round-trip evidence;
  - `TextWebExportAdapter` for HTML/TXT/RTF/Markdown visible text extraction;
  - `ImageScanDocumentAdapter` for image references with extraction-only
    mutation policy;
  - `ArchiveDocumentSetAdapter` for ZIP/TAR/GZ child enumeration and derivative
    routing policy.
- Registered all passive adapters as known-only adapters in the default
  `DocumentAdapterRegistry`.
- Preserved `promoted_formats=()` for every passive family.
- Kept runtime intake for these families blocked with
  `unsupported_operation`, so normal document writes cannot reach a passive
  adapter as a mutation path.

Verification:

- RED observed:
  `ModuleNotFoundError: No module named 'ummaya.tools.documents.formats.passive'`.
- GREEN focused:
  `uv run pytest tests/tools/documents/test_passive_format_adapters.py -q`
  -> `9 passed`.
- Focused family/registry/intake gate:
  `uv run pytest tests/tools/documents/test_passive_format_adapters.py tests/tools/documents/test_adapter_registry.py tests/tools/documents/test_intake_security.py tests/tools/documents/test_orchestrator.py tests/tools/documents/test_inspection_flow.py -q`
  -> pass.
- Full document harness:
  `uv run pytest tests/tools/documents -q`
  -> pass.
- Static gates:
  `uv run ruff check src tests` -> pass.
  `uv run ruff format --check src tests` -> pass.
  `uv run mypy src` -> pass.
  `git diff --check` -> pass.

Phase 8 status:

- Completed for known-only passive adapter registration, safe serializer
  round-trip evidence, extraction-only image behavior, archive child-routing
  policy, and typed runtime blocked writes for non-promoted families.

## Phase 8 Hardening - Primitive-Level Passive Inspect

Status: completed for the current all-format passive inspection loop.

Checkpoint: passive known-only adapters must not be unreachable implementation
details. The model-facing `document` primitive should be able to inspect and
extract passive read-only formats when the file is present, while every mutation
operation remains blocked with a typed `unsupported_operation`.

Deep research migration note:

- Local anchors: Phase 8 passive adapters, `inspection.py`,
  `registry.py`, `test_passive_format_adapters.py`, and the extension matrix
  under `.evidence/document-alpha-beta/2026-06-03/`.
- CC restored-source status: there is no direct CC office-document parser, so
  the reference shape remains a single tool boundary that exposes the richest
  available result without pretending a non-editable target is editable.
- 2026-current sources:
  - Apache Tika 3.2.2 documents broad metadata/text extraction across HTML,
    XML-derived formats, Microsoft Office, OpenDocument, PDF, RTF, text, image,
    and archive-related families; this supports passive extraction as a real
    capability, not a mutation claim:
    <https://tika.apache.org/3.2.2/formats.html>.
  - Docling supported-format docs show a unified extraction representation for
    PDF, OOXML, Markdown, HTML/XHTML, CSV, and image formats; this supports a
    shared extraction surface while keeping native mutation adapters separate:
    <https://docling-project.github.io/docling/usage/supported_formats/>.
  - Unstructured partitioning routes detected file types to structured elements
    and supports DOCX/DOC/ODT/PPTX/PPT/XLSX/CSV/TSV/RTF/HTML/XML/PDF/images/TXT;
    this reinforces inspect/extract-first handling for known document families:
    <https://docs.unstructured.io/open-source/core-functionality/partitioning>.
  - OASIS OpenDocument 1.4 package conformance requires ZIP/XML package
    structure and manifest constraints, which fits read-only package inspection
    but does not justify write promotion:
    <https://docs.oasis-open.org/office/OpenDocument/v1.4/part2-packages/OpenDocument-v1.4-os-part2-packages.html>.
- Candidate scorecard:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Keep passive adapters registered but unreachable from `document` | 41 | Reject | The runtime still behaves like it cannot read known public-infrastructure formats. |
| Promote passive formats into editable `DocumentFormat` values | 38 | Reject | It overclaims write/render/save capability and creates false-positive debug paths. |
| Add tool-specific `document_inspect_*` wrappers | 54 | Reject | It reintroduces tool confusion and breaks the approved single primitive direction. |
| Let `document` inspect/extract known-only passive formats and block mutation | 97 | Adopt | It exposes the real read capability, preserves fail-closed mutation, and keeps the adapter boundary honest. |

Implemented in this slice:

- Added a passive read family gate in `inspection.py` for ODF, text/web export,
  data-file, image/scan, and archive formats.
- `inspect_document()` now delegates blocked known passive formats to their
  known-only adapter only when the adapter has no promoted runtime formats.
- `DocumentToolRuntime.document()` now returns a successful primitive-level
  inspect/extract result for passive known-only local files.
- The same primitive returns typed `unsupported_operation` for fill/style/render
  or save attempts on passive known-only files.
- `DocumentToolRuntime.extract()` now supports path-based passive known-only
  extraction and applies table/image/field include filters.
- `DocumentToolRuntime.inspect()` no longer creates runtime edit artifacts when
  a successful inspection has no promoted `DocumentFormat`.
- Updated the extension alpha/beta matrix so alpha is `inspect` and beta is
  `fill`, making read-only capability visible instead of treating all passive
  formats as identical blocked failures.

Verification:

- RED observed:
  `uv run pytest tests/tools/documents/test_passive_format_adapters.py::test_document_primitive_inspects_passive_known_formats_without_promoting_write -q`
  -> failed because `.odt` remained blocked at the primitive boundary.
- GREEN focused:
  `uv run pytest tests/tools/documents/test_passive_format_adapters.py::test_document_primitive_inspects_passive_known_formats_without_promoting_write -q`
  -> pass.
- Focused passive/inspection gate:
  `uv run pytest tests/tools/documents/test_passive_format_adapters.py tests/tools/documents/test_inspection_flow.py -q`
  -> `18 passed`.
- Static gates:
  `uv run ruff check src/ummaya/tools/documents/inspection.py src/ummaya/tools/documents/registry.py tests/tools/documents/test_passive_format_adapters.py`
  -> pass.
  `uv run mypy src/ummaya/tools/documents/inspection.py src/ummaya/tools/documents/registry.py`
  -> pass.
- Alpha/beta extension matrix:
  `uv run python .evidence/document-alpha-beta/run_document_extension_matrix.py`
  -> `PASS_EDITABLE: 5`, `PASS_SAFE_BLOCKED: 6`,
  `PASS_READONLY_INSPECT_BLOCKED_WRITE: 26`.
- Full regression gate found and closed two adjacent contract gaps:
  - `document` inspect-only success no longer satisfies write/review final-answer
    termination checks; mutating or review requests need a real `document`
    completion result or explicit render result.
  - Spec 2802-owned runtime dependencies are registered in both SC-008
    dependency gates instead of appearing as unowned dependency growth.
- Full live-excluded regression:
  `uv run pytest -m "not live" -q`
  -> pass.
- Final static/evidence gates:
  `uv run ruff check src tests`, `uv run ruff format --check src tests`,
  `uv run mypy src`, `uv run python -m ummaya.evidence --source-ref local --out .evidence/run.json`,
  and `git diff --check`
  -> pass.

Phase 8 hardening status:

- Completed for primitive-level passive inspect/extract reachability, no-artifact
  edit-surface preservation, fill blocked behavior, and refreshed alpha/beta
  extension evidence.

Checkpoint: Phase 6 OOXML adapter split and write promotion.

Deep research migration note:

- Local anchors: `formats/ooxml.py`, `adapter_registry.py`, `engines.py`,
  `test_ooxml_adapters.py`, `test_builtin_engine_promotion.py`, and
  `candidate_profiles.yaml`.
- CC restored-source status: not present for office document format engines.
  The CC-shaped boundary remains the single `document` primitive result loop;
  the OOXML engines are UMMAYA-specific format adapters below that primitive.
- 2026-current sources:
  - ECMA-376 confirms DOCX/XLSX/PPTX share Office Open XML vocabularies and
    package semantics, but the standard separates word-processing,
    spreadsheet, and presentation vocabularies:
    <https://ecma-international.org/publications-and-standards/standards/ecma-376/>.
  - `python-docx` 1.2.0 documents DOCX creation/update, paragraphs, runs,
    tables, styles, and core properties:
    <https://python-docx.readthedocs.io/en/latest/>.
  - `openpyxl` 3.1.5 is the current PyPI release for XLSX read/write;
    official docs cover cell styles, merged-cell formatting, formulas, and
    the security note to install `defusedxml`:
    <https://pypi.org/project/openpyxl/>,
    <https://openpyxl.readthedocs.io/en/stable/>.
  - `python-pptx` 1.0.2 is the current PyPI release and documents PPTX
    create/read/update, placeholders, text, tables, images, charts, and
    unsupported rich PowerPoint features:
    <https://pypi.org/project/python-pptx/>,
    <https://python-pptx.readthedocs.io/en/latest/>.
- Candidate scorecard:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Keep one generic OOXML wrapper | 59 | Reject | It hides divergent WordprocessingML, SpreadsheetML, and PresentationML failure modes. |
| DOCX-only promotion, XLSX/PPTX known-only | 74 | Reject for Phase 6 | Safer than overclaiming, but leaves checked Phase 6 write tests incomplete. |
| Split adapters and promote bounded `python-docx` / `openpyxl` / `python-pptx` engines | 94 | Adopt | Matches ECMA family split, uses mature MIT OSS packages, and passes fixture-backed write + blocked-media gates. |

Implemented in this slice:

- Reworked `formats/ooxml.py` into:
  - `DocxDocumentAdapter` + `PythonDocxDocumentEngine`;
  - `XlsxDocumentAdapter` + `OpenPyxlDocumentEngine`;
  - `PptxDocumentAdapter` + `PythonPptxDocumentEngine`.
- Registered DOCX/XLSX/PPTX default engines and adapters while preserving
  known-only XLSX/PPTX behavior when a custom engine registry does not promote
  those formats.
- Added core runtime dependencies with justification:
  - `openpyxl>=3.1.5` for bounded XLSX read/write/style;
  - `python-pptx>=1.0.2` for bounded PPTX read/write;
  - `defusedxml>=0.7.1` to satisfy openpyxl's XML attack mitigation guidance.
- Added DOCX tests for paragraph, run, table cell, core metadata, and style
  preservation.
- Added XLSX tests for cells, merged cells, styles, number formats, formula
  preservation outside edited cells, sheet names, print areas, and workbook
  reload.
- Added PPTX tests for placeholders, text frames, tables, image retention, slide
  metadata, and blocked media targets.
- Added separate DOCX/XLSX/PPTX capability profiles with write scores above the
  85/100 hard gate.

Verification:

- RED observed:
  `uv run pytest tests/tools/documents/test_ooxml_adapters.py -q`
  failed with
  `ImportError: cannot import name 'DocxDocumentAdapter'`.
- RED observed:
  `uv run pytest tests/tools/documents/test_builtin_engine_promotion.py -q`
  failed with missing `openpyxl` and `python-pptx` profile decisions.
- GREEN:
  `uv run pytest tests/tools/documents/test_ooxml_adapters.py tests/tools/documents/test_builtin_docx_engine.py tests/tools/documents/test_xlsx_fill.py tests/tools/documents/test_form_fill.py tests/tools/documents/test_adapter_registry.py tests/tools/documents/test_inspection_flow.py tests/tools/documents/test_document_tool_flow.py tests/tools/documents/test_builtin_engine_promotion.py tests/tools/documents/test_candidate_evaluation.py -q`
  -> `45 passed`.
- Document harness gate:
  `uv run pytest tests/tools/documents -q`
  -> pass.
- Static gates:
  - `uv run ruff check src tests` -> pass.
  - `uv run ruff format --check src tests` -> pass.
  - `uv run mypy src` -> pass.
  - `git diff --check` -> pass.

Phase 6 status:

- Completed for OOXML adapter split, bounded promoted write engines, separate
  capability profiles, unsupported media/style blocking, and full document
  harness regression tests.

Checkpoint: HWPX public AX weekly-log extraction precision gate.

Deep research migration note:

- Local anchors: `test_public_ax_weekly_hwp_fixture_extraction_precision_gate`,
  FR-003, FR-010, FR-037, and the Phase 4 exit gate requiring HWPX
  text/table/field extraction precision >= 0.90.
- CC restored-source status: not a CC feature; this is an UMMAYA
  public-document promotion metric below the single document tool boundary.
- 2026-current sources:
  - Docling/Unstructured remain the reference shape for structured extraction
    with element identity and provenance.
  - RHWP/OpenHWP/HwpForge remain HWPX ecosystem signals, but this checkpoint
    uses local fixture extraction truth rather than adding a new dependency.
- Candidate scorecard:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Treat inspect success as extraction precision | 45 | Reject | It misses label/path/value and table-cell correctness. |
| Use broad semantic data.go.kr aggregate only | 69 | Reject as sole gate | Good macro metric, but not authoritative for this local HWPX form layout. |
| Add fixture-specific text/table/field precision assertions over the copied HWPX sample | 94 | Adopt | Directly measures the promoted fixture, uses source anchors, and fails when expected text-node granularity is wrong. |

Implemented in this slice:

- Added a precision gate for the copied public AX HWPX weekly-log fixture.
- The gate checks:
  - critical field label/path/current-value triples,
  - critical table-cell text,
  - critical paragraph text nodes.
- Minimum threshold is 0.90 for each component.

Verification:

- RED observed:
  paragraph precision failed at `0.8` because the expected value used combined
  `차주 계획`, while HWPX extraction correctly emits two native text nodes:
  `차주 ` and `계획`.
- GREEN:
  `uv run pytest tests/tools/documents/test_builtin_hwpx_engine.py::test_public_ax_weekly_hwp_fixture_extraction_precision_gate -q`
  -> pass.
- HWPX suite:
  `uv run pytest tests/tools/documents/test_builtin_hwpx_engine.py -q`
  -> `14 passed`.
- Focused combined gate:
  `uv run pytest tests/tools/documents/test_builtin_hwpx_engine.py tests/tools/documents/test_adapter_registry.py tests/tools/documents/test_document_tool_flow.py tests/tools/documents/test_autonomous_fill_planner.py tests/tools/documents/test_orchestrator.py tests/tools/documents/test_inspection_flow.py tests/tools/documents/test_models.py tests/tools/documents/test_intake_security.py tests/tools/documents/test_candidate_evaluation.py -q`
  -> pass.
- Focused lint and type check remain green.

Phase 4 backend status:

- Completed for backend adapter promotion, real HWPX fixture auto-fill,
  render/re-read/diff evidence, RHWP render-only boundary, target-anchor
  correctness, and extraction precision.
- Remaining TUI compact auto-render gate is tracked under Phase 10 TUI and CC
  loop parity.

## Phase 5 - HWP Adapter Read/Blocked Path

Status: completed for the current known-only adapter slice.

Checkpoint: HWP known-only adapter and copied HWP blocked-write fixture gate.

Deep research migration note:

- Local anchors: `formats/hwp.py`, `adapter_registry.py`,
  `test_builtin_hwp_adapter.py`, copied local HWP fixtures under
  `.evidence/document-fixtures/public-ax-samples/`, candidate profile HWP
  decisions, and Phase 5 checklist items.
- CC restored-source status: intact for fail-closed tool boundaries and
  validation before mutation. HWP binary read/write policy is an UMMAYA format
  adapter concern below the single document tool boundary.
- 2026-current sources:
  - OpenHWP remains the best permissive HWP/HWPX native architecture signal, but
    current runtime integration is deferred until read fixture evidence passes.
  - `pyhwp` remains useful comparative HWP v5 parser evidence, but AGPL prevents
    direct Apache-2.0 runtime adoption.
  - HwpForge/HWPX MCP direction reinforces adapter separation, but not HWP binary
    direct write promotion.
- Candidate scorecard:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Treat HWP as unknown/unsupported only | 61 | Reject | Loses national-infrastructure format knowledge and weakens user guidance. |
| Promote empty HWP inspection as read success | 47 | Reject | That would be a fallback masquerading as read support. |
| Register HWP as known-only adapter, keep promoted read/write absent, and use copied HWP samples as blocked fixtures | 95 | Adopt | Honest capability boundary, fixture-backed, and no derivative write risk. |

Implemented in this slice:

- Added `HwpDocumentAdapter` with `known_formats=(hwp,)` and no promoted runtime
  formats.
- Registered HWP known-only adapter in default adapter registries only when no
  explicit HWP engine is injected.
- Preserved injected HWP read-engine behavior for tests/future promotion by not
  pre-registering the known-only adapter when a promoted HWP engine is supplied.
- Added copied public AX HWP fixture tests:
  - all local HWP sample hashes are verified;
  - intake classifies HWP as known/promoted document format;
  - document fill is blocked with `unsupported_operation`;
  - no working or derivative artifact is created.

Verification:

- RED observed:
  `ImportError: cannot import name 'HwpDocumentAdapter'`.
- GREEN:
  `uv run pytest tests/tools/documents/test_builtin_hwp_adapter.py -q`
  -> `2 passed`.
- Focused HWP policy gate:
  `uv run pytest tests/tools/documents/test_builtin_hwp_adapter.py tests/tools/documents/test_inspection_flow.py tests/tools/documents/test_candidate_evaluation.py tests/tools/documents/test_capability_profiles.py tests/tools/documents/test_public_form_validator.py -q`
  -> pass.
- Focused lint:
  `uv run ruff check src/ummaya/tools/documents/formats/hwp.py src/ummaya/tools/documents/adapter_registry.py tests/tools/documents/test_builtin_hwp_adapter.py tests/tools/documents/test_inspection_flow.py tests/tools/documents/test_candidate_evaluation.py tests/tools/documents/test_capability_profiles.py`
  -> pass.
- Focused type check:
  `uv run mypy src/ummaya/tools/documents/formats/hwp.py src/ummaya/tools/documents/adapter_registry.py src/ummaya/tools/documents/inspection.py`
  -> pass.
- Diff hygiene:
  `git diff --check -- src/ummaya/tools/documents/formats/hwp.py src/ummaya/tools/documents/adapter_registry.py tests/tools/documents/test_builtin_hwp_adapter.py specs/2802-public-doc-harness/format-adapter-execution-progress-2026-06-03.md specs/2802-public-doc-harness/format-adapter-implementation-plan-2026-06-03.md`
  -> pass.

Checkpoint: HWP blocked result UX and candidate evidence audit.

Deep research migration note:

- Local anchors: `inspection.py`, `test_builtin_hwp_adapter.py`,
  `test_dependency_gate.py`, and `candidate_profiles.yaml`.
- CC restored-source status: intact for typed blocked tool results. HWP boundary
  wording is an UMMAYA format-policy message.
- 2026-current sources:
  - OpenHWP is retained as permissive read-only candidate evidence.
  - pyhwp is retained as comparative HWP parser evidence only because its AGPL
    license gate fails for direct runtime adoption.
- Candidate scorecard:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Generic `no promoted adapter` message | 58 | Reject | It does not explain the HWP direct-write boundary or safe next action. |
| Promote pyhwp read runtime now | 46 | Reject | License gate fails for Apache-2.0 runtime adoption. |
| Keep OpenHWP/pyhwp as scored evidence and show HWP-specific blocked next actions | 96 | Adopt | Honest to capability, user-visible, and backed by candidate fixtures. |

Implemented in this slice:

- HWP unsupported inspection now returns a HWP-specific summary:
  HWP binary direct writing is blocked; use HWPX/DOCX editable templates for
  safe fill/save, or keep HWP as classification/read-only evidence until a
  promoted read adapter passes gates.
- The copied HWP fixture test now loops across every local HWP public AX sample.
- The test asserts no working or derivative artifact is produced for HWP fill
  attempts.

Verification:

- RED observed:
  HWP copied-fixture test still saw generic
  `Document inspection blocked: no promoted adapter is registered for hwp.`
- GREEN:
  `uv run pytest tests/tools/documents/test_builtin_hwp_adapter.py::test_copied_hwp_public_ax_fixtures_classify_but_document_fill_is_blocked -q`
  -> pass.
- Candidate/dependency evidence:
  `uv run pytest tests/tools/documents/test_dependency_gate.py tests/tools/documents/test_candidate_evaluation.py::test_hwp_read_only_candidate_promotes_read_and_blocks_write -q`
  -> pass.
- Focused HWP policy gate, lint, type check, and diff hygiene remain green.

Phase 5 status:

- Completed for known-only adapter registration, copied HWP classification and
  blocked-write fixtures, OpenHWP/pyhwp evidence decisions, user-facing blocked
  next actions, and 100% blocked direct HWP fill attempts across the copied HWP
  local fixture set.

Checkpoint: RHWP render bridge remains render-only evidence.

Deep research migration note:

- Local anchors: `tests/fixtures/documents/candidate_profiles.yaml`,
  `tests/tools/documents/test_candidate_evaluation.py`,
  `src/ummaya/tools/documents/render.py`, and `formats/hwpx.py`.
- CC restored-source status: intact for result evidence after the single edit
  tool. RHWP is only an UMMAYA document-render evidence bridge below that tool
  boundary.
- 2026-current sources:
  - RHWP remains the strongest OSS renderer signal for HWP/HWPX local SVG/page
    evidence, including current HWPX rendering and validation work.
  - OpenHWP and HwpForge remain future native write/IR references, but neither
    changes this checkpoint's decision: RHWP Node/WASM is render evidence only.
- Candidate scorecard:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Promote RHWP write/export now | 57 | Reject | Current UMMAYA field-safe mutation evidence is from the in-repo HWPX package text engine, not RHWP write/export. |
| Remove RHWP bridge until all HWPX validation is complete | 62 | Reject | It would drop already-proven local SVG evidence and weaken render/re-read gates. |
| Keep RHWP Node/WASM as render-only evidence | 95 | Adopt | Matches current candidate profile, produces local SVG artifacts, and avoids overclaiming write capability. |

Verification:

- Candidate profile states:
  - `rhwp` supports read/render but write is deferred.
  - `rhwp-node-wasm` supports and evaluates render only.
  - `rhwp-node-wasm` decision note says page-level SVG evidence is promoted and
    write/export remains separate.
- GREEN:
  `uv run pytest tests/tools/documents/test_candidate_evaluation.py -q`
  -> `4 passed`.

Remaining Phase 4 gates:

- Move toward HWPX conformance/promotion scoring once fixture evidence is broad
  enough.

Checkpoint: HWP hwpxjs conversion candidate and render-gate fail-closed repair.

Deep research migration note:

- Local anchors: `docs/adr/ADR-011-hwp-conversion-bridge.md`,
  `src/ummaya/tools/documents/conversion.py`,
  `src/ummaya/tools/documents/hwp_conversion_probe.py`,
  `src/ummaya/tools/documents/render.py`, and copied public AX HWP fixtures in
  `.evidence/document-fixtures/public-ax-samples/`.
- CC restored-source status: no Korean HWP/HWPX converter analog exists. The CC
  parity rule is fail-closed visible tool evidence, not fallback success.
- 2026-current sources:
  - `ssabro/hwpxjs` / `@ssabrojs/hwpxjs@0.4.0`: MIT, local TypeScript/Node CLI,
    HWP 5.0 parser, HWPX writer, and `convert:hwp <source.hwp> <output.hwpx>`.
  - OpenHWP and HwpForge remain stronger long-term Rust IR/HWPX references, but
    `hwpxjs` is the currently installable local conversion CLI candidate.
  - RHWP remains the promoted HWPX SVG render bridge, but real converted public
    AX output exposed a border-rendering panic.
- Candidate scorecard:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Treat HWP conversion as complete once HWPX bytes exist | 41 | Reject | It skips render/re-read/save gates and would mislead the user. |
| Auto-register discovered `hwpxjs` CLI behind conversion registry | 89 | Adopt candidate | Exact npm pin, MIT license, local-only CLI, valid HWPX output, and real public AX conversion evidence. |
| Direct HWP binary write | 19 | Reject | No safe write engine has passed public-form gates. |
| Catch renderer exceptions as typed blocked results | 96 | Adopt | Preserves fail-closed evidence and prevents native bridge panics from crashing the tool loop. |

Implemented in this slice:

- Added `@ssabrojs/hwpxjs@0.4.0` to the root package manifest/shrinkwrap.
- Default conversion registry now discovers `hwpxjs` on PATH and registers
  `hwpxjs-cli-convert-hwp` with `convert:hwp {source} {output}`.
- HWP bridge probe reason for `hwpxjs` is now
  `hwpxjs_cli_found_for_default_registration`.
- `render_document_evidence()` now catches native render bridge exceptions and
  returns `blocked(validation_failed)`, `render_passed=False`, and no render
  artifacts instead of throwing.
- Real public AX HWP alpha with explicit patch converted and diffed, but RHWP
  render failed. Save was skipped. This keeps HWP authoring incomplete.

Verification:

- RED:
  `uv run pytest tests/tools/documents/test_render_and_reread.py::test_render_engine_exception_returns_blocked_result_without_artifacts -q`
  failed because the renderer exception escaped.
- GREEN:
  same test passed after fail-closed repair.
- RED/GREEN:
  `uv run pytest tests/tools/documents/test_hwp_conversion_probe.py::test_probe_detects_hwpxjs_cli_on_path_without_mutating_registry -q`
  first failed on the old reason string, then passed.
- Focused bridge check:
  `uv run pytest tests/tools/documents/test_hwp_conversion_probe.py::test_probe_detects_hwpxjs_cli_on_path_without_mutating_registry tests/tools/documents/test_conversion_registry.py::test_default_conversion_registry_registers_discovered_hwpxjs_bridge -q`
  -> pass.

Remaining gates:

- Root-cause RHWP border-rendering panic on converted HWPX public AX output.
- Add deterministic converted-HWPX sanitation or renderer swap only after a new
  research/scorecard loop.
- Add safe autonomous HWP fill-target inference for prompts like
  `문서내용을 파악하고 알아서 작성해`.
- Do not mark HWP authoring or all-format completion complete until converted
  derivatives render, re-read, validate, save, and show TUI evidence.

Checkpoint: HWP derivative render/save promotion through hwpxjs HTML.

Deep research migration note:

- Local anchors: `src/ummaya/tools/documents/formats/hwpx.py`,
  `src/ummaya/tools/documents/render.py`,
  `src/ummaya/tools/documents/conversion.py`, and the copied public AX HWP
  fixtures under `.evidence/document-fixtures/public-ax-samples/`.
- Upstream source comparison:
  - RHWP SVG rendering is still preferred for native RHWP-compatible HWPX
    packages.
  - Real `hwpxjs convert:hwp` outputs valid HWPX packages, but their table
    geometry is not RHWP-render compatible in the copied public AX samples.
  - `hwpxjs html` is therefore selected only by a pre-render HWPX geometry
    compatibility gate, not by catching a failed RHWP render.
- Decision: HWP remains immutable; HWP authoring is promoted as
  HWP-source-preserved, HWPX-derivative write/render/save. Direct HWP binary
  write remains blocked.

Implemented in this slice:

- Default conversion registry now discovers repo-local
  `node_modules/.bin/hwpxjs` when no explicit converter env is set.
- HWPX render engines may declare artifact-specific render extension, MIME, and
  engine id.
- `HwpXPackageTextEngine` keeps RHWP SVG for RHWP-compatible packages and
  selects `hwpxjs-html-render` for HWPX packages missing the table geometry
  required by RHWP.
- The document primitive no longer discards LLM-generated patches only because
  the Korean instruction contains autonomous wording such as `알아서` or
  `문서 내용을 파악`.
- The format completion audit now classifies HWP as
  `derivative_write_render_save_promoted` with
  `direct_hwp_binary_mutation_blocked`.

Verification:

- GREEN:
  `uv run pytest tests/tools/documents/test_builtin_hwp_adapter.py
  tests/tools/documents/test_format_completion_audit.py -q`
  -> `15 passed`.
- GREEN:
  `uv run pytest tests/tools/documents/test_builtin_hwp_adapter.py::test_document_primitive_keeps_llm_planned_patches_for_autonomous_hwp_prompt
  tests/tools/documents/test_builtin_hwp_adapter.py::test_default_runtime_converts_public_ax_hwp_derivative_renders_html_and_saves
  tests/tools/documents/test_autonomous_fill_planner.py -q`
  -> `9 passed`.
- Real public AX HWP alpha:
  all 4 copied `.hwp` fixtures passed inspect, HWPX derivative copy, HTML
  render through `hwpxjs-html-render`, save to a non-hidden local path, and
  source SHA preservation.

Remaining gates:

- `.doc`, `.xls`, and `.ppt` remain blocked because this environment has no
  local `soffice`/`libreoffice` conversion bridge.
- PDF/A is now accepted as PDF runtime lineage but remains conformance
  probe-blocked until a local veraPDF post-write gate exists.
- EPUB, raster scans, GIS sidecars, media, and archives remain non-authoring or
  unpromoted capability families and need separate terminal criteria instead of
  being silently counted as editable public forms.

Checkpoint: PDF/A conformance gate and intake lineage.

Deep research migration note:

- Local anchors: `src/ummaya/tools/documents/intake.py`,
  `src/ummaya/tools/documents/pdfa_promotion_probe.py`,
  `src/ummaya/tools/documents/format_completion_audit.py`, and
  `src/ummaya/evidence/runner.py`.
- Upstream source comparison:
  - Public Data Portal continues to list PDF and broad public-data extension
    families as active Korean public-infrastructure surface area.
  - veraPDF is the selected OSS conformance oracle because it covers all PDF/A
    parts and levels and exposes CLI validation profiles/reports.
  - pypdf remains the AcroForm mutation engine, but its own docs state it makes
    no PDF/A guarantees.
- Decision: `.pdfa` intake is promoted to PDF runtime lineage, while PDF/A
  post-write completion remains `probe_blocked`.

Implemented in this slice:

- `.pdfa` files with PDF signature now pass intake as
  `detected_format=pdf` and `known_format=pdfa`.
- Added `probe_pdfa_promotion()` with `verapdf` CLI detection, recommended
  `--format xml --flavour 0 {source}` args, and explicit conformance gates.
- Evidence Fabric emits `document_pdfa_probe_records`.
- Completion audit records `pdfa` as `probe_blocked`, not passive.

Verification:

- `uv run pytest tests/tools/documents/test_pdfa_promotion_probe.py
  tests/tools/documents/test_intake_security.py::test_pdfa_extension_is_accepted_as_pdf_runtime_with_pdfa_lineage
  tests/tools/documents/test_format_completion_audit.py::test_audit_classifies_promoted_read_only_probe_and_passive_families -q`
  -> pass.
- `uv run pytest tests/evidence/test_document_harness_evidence.py::test_document_records_attach_to_evidence_runner_output
  tests/tools/documents/test_pdfa_promotion_probe.py
  tests/tools/documents/test_intake_security.py::test_pdfa_extension_is_accepted_as_pdf_runtime_with_pdfa_lineage
  tests/tools/documents/test_format_completion_audit.py -q`
  -> pass.

Checkpoint: archive/container child-routing probe.

Deep research migration note:

- Local anchors: `src/ummaya/tools/documents/formats/passive.py`,
  `src/ummaya/tools/documents/archive_container_probe.py`,
  `src/ummaya/tools/documents/format_completion_audit.py`, and
  `src/ummaya/evidence/runner.py`.
- Upstream source comparison:
  - Python stdlib `zipfile`, `tarfile`, and `gzip` are selected only for local
    enumeration and child-routing candidates.
  - OWASP file-upload guidance keeps archive path traversal, size, and
    decompression limits in scope.
  - `py7zr` is the rejected-until-installed 7z candidate.
- Decision: classify archive families as explicit probe-blocked candidates,
  not generic passive context and not complete write/render/save formats.

Implemented in this slice:

- Added `probe_archive_container_promotion()` for `epub`, `zip`, `7z`, `tar`,
  and `gz`.
- Evidence Fabric emits `document_archive_probe_records`.
- Completion audit now reports archive formats as `probe_blocked` with
  repack/write and runtime-gate reasons.

Verification:

- `uv run pytest tests/tools/documents/test_archive_container_probe.py
  tests/tools/documents/test_format_completion_audit.py::test_audit_classifies_promoted_read_only_probe_and_passive_families
  tests/evidence/test_document_harness_evidence.py::test_document_records_attach_to_evidence_runner_output -q`
  -> pass.

Checkpoint: passive attachment capability probes.

Deep research migration note:

- Local anchors: `src/ummaya/tools/documents/formats/passive.py`,
  `src/ummaya/tools/documents/passive_capability_probe.py`,
  `src/ummaya/tools/documents/format_completion_audit.py`, and
  `src/ummaya/evidence/runner.py`.
- Upstream source comparison:
  - Tesseract CLI is the image OCR candidate.
  - FFmpeg/ffprobe is the media metadata candidate, not a full transcription
    writer.
  - GDAL/OGR, pyshp, and trimesh are geospatial/3D candidates.
- Decision: image, media, geospatial, and code files remain blocked for
  document writing but now have explicit extraction/runtime probes.

Implemented in this slice:

- Added `probe_passive_capabilities()` for 17 passive attachment formats.
- Evidence Fabric emits `document_passive_probe_records`.
- Completion audit now reports these formats as `probe_blocked`; no known
  format remains in generic `passive_context_only`.

Verification:

- `uv run pytest tests/tools/documents/test_passive_capability_probe.py
  tests/tools/documents/test_format_completion_audit.py::test_audit_classifies_promoted_read_only_probe_and_passive_families
  tests/evidence/test_document_harness_evidence.py::test_document_records_attach_to_evidence_runner_output -q`
  -> pass.

## 2026-06-03 Legacy Office Derivative Bridge Update

Deep research migration note:

- Local anchors: `src/ummaya/tools/documents/models.py`,
  `src/ummaya/tools/documents/conversion.py`,
  `src/ummaya/tools/documents/registry.py`,
  `src/ummaya/tools/documents/legacy_office_promotion_probe.py`, and
  `tests/tools/documents/test_legacy_office_derivative_bridge.py`.
- CC restored-source status: no CC legacy Office format engine exists. The
  relevant CC invariant is one model-facing edit operation with visible
  intermediate tool result and fail-closed validation.
- 2026-current sources:
  - Microsoft Open Specifications classify `.doc`, `.xls`, and `.ppt` as
    Office 97-2003 binary formats.
  - Microsoft Support documents `.docx`, `.xlsx`, and `.pptx` as current Open
    XML extensions.
  - LibreOffice Help documents `soffice --convert-to ... --outdir ...` and OOXML
    export filters for Writer, Calc, and Impress.

Scorecard:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Direct legacy binary write | 22 | Reject | No safe runtime and high corruption risk. |
| Keep metadata-only forever | 66 | Partial | Safe, but fails user expectation for editable submitted derivatives. |
| Java POI mutation bridge | 58 | Reject | Heavy runtime boundary and weaker write-safety fit. |
| LibreOffice local conversion to OOXML derivative | 88 | Adopt | Preserves source bytes and reuses promoted OOXML write/render/save engines. |
| Remote conversion service | 18 | Reject | Violates local-only document privacy. |

Implemented in this slice:

- Added `docs/adr/ADR-012-legacy-office-libreoffice-bridge.md`.
- Added `DocumentFormat.doc`, `DocumentFormat.xls`, and `DocumentFormat.ppt`
  as source formats while keeping them out of
  `PROMOTED_RUNTIME_DOCUMENT_FORMATS`.
- Added default LibreOffice/soffice discovery in
  `build_default_document_conversion_registry()` for `.doc -> .docx`,
  `.xls -> .xlsx`, and `.ppt -> .pptx`.
- Generalized `DocumentToolRuntime.copy_for_edit()` from HWP-only derivative
  conversion to source-format -> editable-derivative conversion.
- Added TDD coverage proving top-level `document(fill/save, .doc)` creates a
  DOCX working derivative, preserves source bytes, patches through the OOXML
  engine, and writes a user-visible DOCX export.
- Updated intake tests so known-but-unpromoted classification is based on
  `PROMOTED_RUNTIME_DOCUMENT_FORMATS`, not the wider `DocumentFormat` source
  enum.

Verification:

- RED:
  `uv run pytest tests/tools/documents/test_legacy_office_derivative_bridge.py
  tests/tools/documents/test_conversion_registry.py::test_default_conversion_registry_registers_discovered_libreoffice_legacy_bridge -q`
  failed first because legacy Office was not a `DocumentFormat`, then because
  the test still assumed obsolete result fields.
- GREEN:
  `uv run pytest tests/tools/documents/test_legacy_office_derivative_bridge.py
  tests/tools/documents/test_conversion_registry.py::test_default_conversion_registry_registers_discovered_libreoffice_legacy_bridge -q`
  -> pass.
- Broader focused:
  `uv run pytest tests/tools/documents/test_legacy_office_derivative_bridge.py
  tests/tools/documents/test_conversion_registry.py
  tests/tools/documents/test_legacy_office_promotion_probe.py
  tests/tools/documents/test_format_completion_audit.py
  tests/tools/documents/test_intake_security.py -q`
  -> pass.
- Full document harness:
  `uv run pytest tests/tools/documents -q`
  -> pass.

Remaining gate:

- The all-format audit remains incomplete because this local runtime still has
  no real `soffice`/`libreoffice` executable and no real `.doc/.xls/.ppt`
  fixture conversion evidence for all three legacy Office families.

## 2026-06-03 Archive Container Promotion Update

Deep research migration note:

- Local anchors: `src/ummaya/tools/documents/intake.py`,
  `src/ummaya/tools/documents/formats/passive.py`,
  `src/ummaya/tools/documents/formats/archive.py`,
  `src/ummaya/tools/documents/adapter_registry.py`,
  `src/ummaya/tools/documents/engines.py`, and
  `src/ummaya/tools/documents/format_completion_audit.py`.
- CC restored-source status: no CC archive document writer analog exists. The
  relevant CC invariant remains one visible primitive result, deterministic
  validation, and no hidden in-place mutation.
- 2026-current sources:
  - Python `zipfile`, `tarfile`, and `gzip` are the selected local stdlib
    runtimes for ZIP/EPUB, TAR, and GZIP.
  - Python tarfile extraction-filter documentation informs the safety criterion:
    member names, links, devices, and traversal are blocked before use.
  - EPUB OCF is ZIP-container based, so UMMAYA treats EPUB as a child-payload
    container and preserves the `mimetype` member as the first stored ZIP entry.
  - OWASP file upload guidance keeps archive traversal, active content,
    expansion limit, entry-count limit, and nested archive blocking in scope.

Scorecard:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Keep all archives metadata-only | 55 | Supersede | Safe, but misses common public-submission bundle workflows. |
| Extract archive to workspace, edit files, repack | 41 | Reject | Creates path traversal and workspace mutation risk. |
| Promote child-payload replacement inside artifact store | 91 | Adopt | Preserves source archive bytes, keeps writes in `document`, and uses stdlib runtimes. |
| Promote 7z immediately | 38 | Reject for now | Requires `py7zr`/7z runtime and a separate dependency gate. |

Implemented in this slice:

- Added `ArchiveContainerDocumentEngine` for `epub`, `zip`, `tar`, and `gz`.
- Added archive MIME and intake detection for ZIP, EPUB, TAR, and GZIP.
- Registered archive engines in the default engine/adapter registries.
- Changed passive archive adapter registration so only unpromoted archive
  formats such as `7z` remain known-only.
- Added single `document(save)` workflow coverage for ZIP/EPUB/TAR/GZ with
  source immutability, child payload replacement, render artifacts, local save,
  re-read, and diff.
- Updated `probe_archive_container_promotion()` and Evidence Fabric assertions
  to report promoted child-derivative archive support for ZIP/EPUB/TAR/GZ.

Verification:

- RED:
  `uv run pytest tests/tools/documents/test_archive_container_workflow.py -q`
  failed first because `DocumentFormat.zip` did not exist.
- GREEN:
  `uv run pytest tests/tools/documents/test_archive_container_workflow.py
  tests/tools/documents/test_archive_container_probe.py
  tests/tools/documents/test_format_completion_audit.py
  tests/tools/documents/test_intake_security.py
  tests/tools/documents/test_passive_format_adapters.py
  tests/evidence/test_document_harness_evidence.py::test_document_records_attach_to_evidence_runner_output -q -x`
  -> pass.

Current audit interpretation:

- `write_render_save_promoted=36`
- `derivative_write_render_save_promoted=1`
- `probe_blocked=22`
- Remaining archive gap: `7z` only, pending local `py7zr` or 7z runtime and
  dependency/license/CI gate.

## 2026-06-03 7z Archive Runtime Promotion Loop

Status: completed for the bounded 7z child-derivative archive contract. The
overall all-format goal remains incomplete.

Deep research migration note:

- Local anchors:
  - `src/ummaya/tools/documents/models.py`
  - `src/ummaya/tools/documents/intake.py`
  - `src/ummaya/tools/documents/formats/archive.py`
  - `src/ummaya/tools/documents/engines.py`
  - `src/ummaya/tools/documents/adapter_registry.py`
  - `src/ummaya/tools/documents/archive_container_probe.py`
  - `src/ummaya/tools/documents/format_completion_audit.py`
- CC restored-source status: not present in CC for public-document archive
  mutation. The relevant CC parity rule is fail-closed tool execution with a
  visible structured result and no hidden recovery/fallback path.
- 2026-current sources:
  - libarchive.org lists the 2026 stable release family and the `bsdtar` CLI.
  - libarchive upstream documents 7-Zip archive support and streaming read/write
    APIs.
  - `bsdtar(1)` documents extract/create support for 7-zip archives.
  - OWASP File Upload guidance keeps parser exploitation, traversal, overwrite,
    archive expansion, and filesystem permissions as required controls.
- Candidate scorecard:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Keep 7z permanently passive | 58 | Supersede | Safe but leaves a common submission-bundle extension without a write/save path. |
| Add `py7zr` now | 61 | Reject | Adds LGPL and compression transitive dependencies before a dependency ADR. |
| Shell out to local `7z` binary | 52 | Reject | No `7z` binary exists in the current local runtime. |
| Reuse local `bsdtar/libarchive` behind archive engine boundary | 90 | Adopt | Current runtime can create 7z, no new dependency, fits existing child-derivative archive contract. |

Implemented:

- Added `DocumentFormat.seven_z = "7z"` and promoted it in
  `PROMOTED_RUNTIME_DOCUMENT_FORMATS`.
- Added 7z MIME/signature detection in intake.
- Extended `ArchiveContainerDocumentEngine` with `bsdtar/libarchive` list,
  extract, child replacement, and repack flow.
- Registered 7z in default engine and adapter registries.
- Updated archive probe records to report `libarchive-bsdtar-7zip` and both
  available/missing runtime states.
- Moved 7z out of the passive/blocked audit set into
  `write_render_save_promoted` with the existing archive-child derivative
  reasons.

Verification:

- Focused 7z/archive/evidence gate:
  `uv run pytest tests/tools/documents/test_archive_container_probe.py
  tests/tools/documents/test_archive_container_workflow.py
  tests/tools/documents/test_intake_security.py
  tests/tools/documents/test_format_completion_audit.py
  tests/tools/documents/test_models.py
  tests/tools/documents/test_passive_format_adapters.py
  tests/evidence/test_document_harness_evidence.py -q`
  -> pass.
- Current audit:
  `all_formats_complete=False`,
  `write_render_save_promoted=37`,
  `derivative_write_render_save_promoted=1`,
  `probe_blocked=21`.
- Remaining incomplete formats:
  `doc`, `xls`, `ppt`, `pdfa`, `py`, `png`, `jpg`, `jpeg`, `gif`, `tif`,
  `tiff`, `bmp`, `webp`, `shp`, `shx`, `dbf`, `prj`, `stl`, `wav`, `mp3`,
  `mp4`.

Image/OCR loop decision:

- Local `Pillow` is available, but it is not yet a direct declared runtime
  dependency and Pillow-based raster annotation alone would not prove accurate
  Korean public-document reading.
- Local `tesseract` exists, but Korean `kor` traineddata is absent; current
  language set is `eng`, `osd`, and `snum`.
- Image scan formats therefore remain fail-closed for full public-document
  authoring. The next valid promotion path is a Korean OCR/VLM bridge with
  fixture-backed extraction, confidence, render, and re-read gates, not a simple
  raster overlay.

## 2026-06-03 Python Source Attachment Promotion Loop

Status: completed for the bounded Python source attachment contract. The overall
all-format goal remains incomplete.

Deep research migration note:

- Local anchors:
  - `src/ummaya/tools/documents/models.py`
  - `src/ummaya/tools/documents/intake.py`
  - `src/ummaya/tools/documents/formats/code_file.py`
  - `src/ummaya/tools/documents/engines.py`
  - `src/ummaya/tools/documents/adapter_registry.py`
  - `src/ummaya/tools/documents/diff.py`
  - `src/ummaya/tools/documents/passive_capability_probe.py`
  - `src/ummaya/tools/documents/format_completion_audit.py`
- CC parity rule: no hidden fallback, one visible `document` primitive, source
  bytes preserved unless the user requests a derivative save, and structured
  red/green diff emitted from the actual patch.
- 2026-current sources:
  - Python 3.14.5 `ast` docs: `ast.parse()` produces a syntax tree from source
    and does not require importing or executing the module.
  - Python 3.14.5 `tokenize` docs: tokenization is intended for syntactically
    valid Python, so syntax validation must precede any line/token-level source
    handling.
  - OWASP File Upload Cheat Sheet: extension allowlist, content validation,
    storage isolation, filesystem permissions, and upload limits remain required
    for user-supplied file handling.
- Candidate scorecard:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Passive read-only code context | 61 | Supersede | Does not satisfy write/render/save for submitted code attachments. |
| Pygments syntax-color renderer | 66 | Reject now | Render polish only, extra dependency, no safety improvement. |
| Execute/import code to inspect it | 0 | Reject | Unsafe and outside document-harness boundary. |
| UTF-8 + `ast.parse()` bounded writer | 91 | Adopt | Stdlib-only, fail-closed, no execution, full primitive lifecycle. |

Implemented:

- Added `DocumentFormat.python = "py"` and promoted it in
  `PROMOTED_RUNTIME_DOCUMENT_FORMATS`.
- Added `.py` intake acceptance through UTF-8, NUL-byte, non-empty, and
  `ast.parse()` validation.
- Added `PythonSourceDocumentEngine` with inspect, `/code/body`,
  `/code/lines/N`, structural SVG render, and save/reread support.
- Added `PythonSourceDocumentAdapter` and registered it before passive adapters.
- Removed `.py` from passive capability probe and completion blocked reasons.
- Added `/code/body` support to structured derivative diff.

Verification:

- RED:
  `uv run pytest tests/tools/documents/test_promoted_format_workflow_matrix.py::test_python_source_document_primitive_save_renders_rereads_and_diffs -q`
  failed first because `DocumentFormat.python` did not exist.
- GREEN:
  `uv run pytest tests/tools/documents/test_promoted_format_workflow_matrix.py::test_python_source_document_primitive_save_renders_rereads_and_diffs
  tests/tools/documents/test_intake_security.py
  tests/tools/documents/test_format_completion_audit.py
  tests/tools/documents/test_models.py
  tests/tools/documents/test_passive_format_adapters.py
  tests/tools/documents/test_passive_capability_probe.py
  tests/evidence/test_document_harness_evidence.py -q`
  -> pass.
- Broad gate:
  - `uv run ruff check src/ummaya/tools/documents tests/tools/documents tests/evidence/test_document_harness_evidence.py`
    -> pass.
  - `uv run ruff format --check src/ummaya/tools/documents tests/tools/documents tests/evidence/test_document_harness_evidence.py`
    -> pass.
  - `uv run mypy src/ummaya/tools/documents src/ummaya/evidence/runner.py`
    -> pass.
  - `uv run pytest tests/tools/documents -q`
    -> pass.
  - `uv run pytest tests/evidence tests/ci -q`
    -> pass.
  - `uv run python -m ummaya.evidence --source-ref local --out .evidence/run.json`
    -> pass.
  - `git diff --check`
    -> pass.
- Current audit:
  `all_formats_complete=False`,
  `write_render_save_promoted=38`,
  `derivative_write_render_save_promoted=1`,
  `probe_blocked=20`.
- Remaining incomplete formats:
  `doc`, `xls`, `ppt`, `pdfa`, `png`, `jpg`, `jpeg`, `gif`, `tif`, `tiff`,
  `bmp`, `webp`, `shp`, `shx`, `dbf`, `prj`, `stl`, `wav`, `mp3`, `mp4`.

## 2026-06-03 Legacy DOC Textutil Derivative Promotion Loop

Status: completed for `.doc -> .docx` derivative write/render/save through the
local macOS `textutil` bridge. The overall all-format goal remains incomplete.

Deep research migration note:

- Local anchors:
  - `src/ummaya/tools/documents/conversion.py`
  - `src/ummaya/tools/documents/legacy_office_promotion_probe.py`
  - `src/ummaya/tools/documents/diff.py`
  - `src/ummaya/tools/documents/format_completion_audit.py`
  - `tests/tools/documents/test_conversion_registry.py`
  - `tests/tools/documents/test_legacy_office_promotion_probe.py`
  - `tests/tools/documents/test_render_and_reread.py`
- CC parity rule: the source `.doc` is never mutated; the user-visible edit is
  a derivative artifact with structured before/after diff and render evidence.
- Runtime decision:
  - LibreOffice remains the broad `doc/xls/ppt` conversion reference, but no
    `libreoffice` or `soffice` executable exists in the current runtime.
  - macOS `textutil` exists and supports `doc`/`docx` conversion, but not
    spreadsheet or presentation binaries.
  - Therefore `doc` can be promoted as a DOCX derivative path; `xls` and `ppt`
    remain blocked until LibreOffice or another verified bridge exists.
- Candidate scorecard:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Keep all legacy Office blocked | 62 | Supersede for DOC | Accurate for `xls/ppt`, but leaves local DOC bridge unused. |
| Install LibreOffice during this loop | 54 | Defer | Large external runtime; needs separate dependency/ADR gate. |
| Use macOS `textutil` for all legacy Office | 31 | Reject | It does not support `xls/ppt`. |
| Use macOS `textutil` for `.doc -> .docx` only | 88 | Adopt | Local, narrow, source-preserving, reuses existing DOCX engine. |

Implemented:

- Added `macos-textutil-doc-to-docx-bridge` to default conversion discovery.
- Updated legacy Office probe so textutil makes only `doc` a candidate while
  `xls/ppt` remain blocked without LibreOffice.
- Promoted `doc` in completion audit as
  `derivative_write_render_save_promoted`.
- Fixed structured diff path matching for converted DOCX paragraph paths.

Verification:

- RED:
  `uv run pytest tests/tools/documents/test_conversion_registry.py::test_default_conversion_registry_registers_discovered_textutil_doc_bridge -q`
  failed because no `doc -> docx` default conversion was registered.
- RED:
  `uv run pytest tests/tools/documents/test_legacy_office_promotion_probe.py::test_probe_detects_textutil_for_doc_only_derivative_bridge -q`
  failed because the probe only checked LibreOffice.
- RED:
  `uv run pytest tests/tools/documents/test_render_and_reread.py::test_structured_diff_matches_engine_tail_against_absolute_document_path -q`
  failed because `/paragraph/1` did not match `engine://.../paragraph/1`.
- GREEN:
  `uv run pytest tests/tools/documents/test_conversion_registry.py::test_default_conversion_registry_registers_discovered_textutil_doc_bridge
  tests/tools/documents/test_legacy_office_promotion_probe.py
  tests/tools/documents/test_format_completion_audit.py
  tests/evidence/test_document_harness_evidence.py -q`
  -> pass.
- Local alpha:
  real `textutil` `.doc` fixture -> `document(save)` -> `.docx` derivative
  saved, one render artifact emitted, re-read text `14주차 활동일지`, diff
  `13주차 활동일지 -> 14주차 활동일지`.
- Current audit:
  `all_formats_complete=False`,
  `write_render_save_promoted=38`,
  `derivative_write_render_save_promoted=2`,
  `probe_blocked=19`.
- Remaining incomplete formats:
  `xls`, `ppt`, `pdfa`, `png`, `jpg`, `jpeg`, `gif`, `tif`, `tiff`, `bmp`,
  `webp`, `shp`, `shx`, `dbf`, `prj`, `stl`, `wav`, `mp3`, `mp4`.

## 2026-06-03 Completion Audit Bridge-Truthfulness Loop

Status: completed for dynamic derivative completion audit. The overall
all-format goal remains incomplete.

Root cause:

- `format_completion_audit` used a static derivative-promoted set for `hwp` and
  `doc`.
- Evidence Fabric could intentionally probe with empty bridge env/search path
  and report missing bridges, while completion audit still counted the formats
  as complete.
- This violated the fail-closed rule and made future format loops harder to
  trust.

Implemented:

- Added `derivative_promoted_formats` and `conversion_registry` inputs to
  `audit_document_format_completion()`.
- Added default detection from `build_default_document_conversion_registry()`.
- Added `hwp` blocked reasons for no-bridge audit states.
- Connected Evidence Fabric completion audit to the actual HWP and legacy Office
  probe records emitted in the same payload.
- Kept `hwpxjs` available/configured and DOC textutil candidate as completion
  signals; did not treat unregistered HwpForge availability as automatic
  completion.

Verification:

- RED:
  `uv run pytest tests/tools/documents/test_format_completion_audit.py::test_audit_does_not_claim_derivative_legacy_formats_without_verified_bridge -q`
  failed because the audit did not accept a derivative bridge set and then lacked
  `hwp` blocked reasons.
- RED:
  `uv run pytest tests/evidence/test_document_harness_evidence.py::test_evidence_cli_payload_includes_document_harness_records -q`
  failed because probe-isolated evidence still counted `hwp/doc` complete.
- GREEN:
  `uv run pytest tests/tools/documents/test_format_completion_audit.py
  tests/evidence/test_document_harness_evidence.py -q`
  -> pass.
- Static:
  `uv run ruff check src/ummaya/tools/documents/format_completion_audit.py
  src/ummaya/evidence/runner.py
  tests/tools/documents/test_format_completion_audit.py
  tests/evidence/test_document_harness_evidence.py`
  -> pass.
  `uv run mypy src/ummaya/tools/documents src/ummaya/evidence/runner.py`
  -> pass.
- Current default Evidence Fabric:
  `complete_count=40`,
  `incomplete_count=19`,
  `hwp_probe=available hwpxjs-cli-convert-hwp`,
  `doc_probe=candidate_available macos-textutil-doc-to-docx`.

## 2026-06-03 Legacy XLS Excel Derivative Promotion Loop

Status: completed for `.xls -> .xlsx` derivative write/render/save through the
local Microsoft Excel AppleScript bridge. The overall all-format goal remains
incomplete.

Deep research migration note:

- Local anchors:
  - `src/ummaya/tools/documents/conversion.py`
  - `src/ummaya/tools/documents/legacy_office_promotion_probe.py`
  - `src/ummaya/tools/documents/format_completion_audit.py`
  - `tests/tools/documents/test_conversion_registry.py`
  - `tests/tools/documents/test_legacy_office_derivative_bridge.py`
- CC parity rule: the source `.xls` is never mutated; all edits happen in an
  editable `.xlsx` derivative with structured diff and render evidence.
- 2026-current sources:
  - Microsoft Learn `Workbook.SaveAs` documents the `FileFormat` parameter.
  - Microsoft Learn `XlFileFormat` documents `xlExcel8 = 56` for `.xls`.
  - LibreOffice Help documents `--convert-to` as the broad headless bridge
    candidate, still preferred for future `doc/xls/ppt` parity when installed.
- Runtime decision:
  - LibreOffice is still absent locally, so it cannot be claimed.
  - Microsoft Excel exists locally and a real dry run converted `.xls` to valid
    `.xlsx`.
  - Microsoft PowerPoint AppleScript dry run was rejected because it hung and
    failed to emit `converted.pptx`.

Candidate scorecard:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Leave `xls` blocked | 67 | Supersede locally | Safe but underclaims the verified Excel bridge. |
| Direct BIFF mutation | 8 | Reject | Binary corruption and style loss risk. |
| LibreOffice bridge | 86 | Defer/prefer when installed | Best broad bridge, but unavailable in current runtime. |
| Microsoft Excel AppleScript bridge | 84 | Adopt for XLS | Local verified bridge using official Excel save format contract. |
| Microsoft PowerPoint AppleScript bridge | 25 | Reject now | Local dry run failed; no output artifact. |

Implementation:

- Registered `microsoft-excel-applescript-xls-to-xlsx-bridge` when
  `osascript` and `Microsoft Excel.app` are discoverable.
- Added legacy Office probe output for the Excel-backed `xls` candidate.
- Hardened `LocalCliDocumentConversionEngine` to pass a temp input copy to
  converter CLIs, preventing source mutation when Excel rewrites metadata.
- Added format audit reasons:
  `xls_source_preserved`,
  `xls_to_xlsx_derivative_write_render_save_promoted`, and
  `direct_legacy_xls_binary_mutation_blocked`.

Verification:

- RED:
  `uv run pytest tests/tools/documents/test_conversion_registry.py::test_local_cli_conversion_uses_temporary_input_copy_to_preserve_source -q`
  failed because the converter received and mutated the original path.
- GREEN:
  `uv run pytest tests/tools/documents/test_conversion_registry.py -q`
  -> pass.
- GREEN:
  `uv run pytest tests/evidence/test_document_harness_evidence.py
  tests/tools/documents/test_legacy_office_promotion_probe.py
  tests/tools/documents/test_legacy_office_derivative_bridge.py
  tests/tools/documents/test_conversion_registry.py -q`
  -> pass.
- Local alpha:
  real Excel `.xls` fixture -> `document(fill/save)` -> `.xlsx` derivative
  saved, one render artifact emitted, one diff change emitted, re-read
  `제출서류!B1 = 14주차`.
- Current Evidence Fabric:
  `all_formats_complete=False`,
  `complete_count=41`,
  `incomplete_count=18`,
  `xls=derivative_write_render_save_promoted`,
  `ppt=probe_blocked`.
- Remaining incomplete formats:
  `ppt`, `pdfa`, `png`, `jpg`, `jpeg`, `gif`, `tif`, `tiff`, `bmp`, `webp`,
  `shp`, `shx`, `dbf`, `prj`, `stl`, `wav`, `mp3`, `mp4`.

## 2026-06-03 PDF/A and PPT Fail-Closed Recheck

Status: completed as a negative promotion loop. No runtime promotion was made.

PDF/A decision:

- Local runtime has `pypdf`, `pypdfium2`, `reportlab`, and `PIL`.
- Local runtime does not have `verapdf` or `qpdf`.
- Existing PDF adapter can write/render/save AcroForm PDFs, but PDF/A
  conformance cannot be truthfully claimed after mutation without a post-write
  conformance validator.
- `pdfa` therefore remains `probe_blocked` with
  `pdfa_conformance_probe_required` and `pypdf_pdfa_conformance_not_claimed`.

PPT decision:

- LibreOffice/soffice remains absent, so the preferred broad legacy Office
  bridge is still unavailable.
- Re-tested Microsoft PowerPoint AppleScript with temp-only files:
  - `save active presentation in outputPath as save as presentation` timed out
    after 90 seconds.
  - `save active presentation in outputPath as presentation` returned
    PowerPoint error `-9074`.
  - `save active presentation in outputPath` also returned PowerPoint error
    `-9074`.
  - No `.ppt` source or `.pptx` derivative artifact was created.
- Because the local bridge is non-deterministic and leaves app state behind,
  `ppt` remains `probe_blocked`. This prevents a false completion claim.

Current blocked gate summary:

- `ppt`: needs LibreOffice or another verified local `.ppt -> .pptx` bridge.
- `pdfa`: needs veraPDF or equivalent local conformance validator wired as a
  post-write gate.
- image/geospatial/media attachments: need separate attachment-context
  promotion criteria; direct in-place document writing remains intentionally
  blocked.

## 2026-06-03 Capability Scope Audit Split

Status: completed for audit model hardening. No blocked format was falsely
promoted.

Problem:

- The previous completion audit only had `completion_state`, so `ppt`, `pdfa`,
  images, geospatial sidecars, and media attachments all appeared as the same
  kind of incomplete item.
- That made it too easy to confuse a missing document writer (`ppt`, `pdfa`)
  with an attachment-context format where direct mutation should remain
  blocked (`png`, `shp`, `mp3`, etc.).

Implemented:

- Added `capability_scope` to each `DocumentFormatCompletionRecord`:
  - `document_write_render_save`
  - `derivative_document_write_render_save`
  - `document_read_only`
  - `attachment_context`
  - `passive_context`
- Evidence Fabric now serializes this scope in
  `document_format_completion_audit.records`.
- Current examples:
  - `xlsx`: `write_render_save_promoted` / `document_write_render_save`
  - `xls`: `derivative_write_render_save_promoted` /
    `derivative_document_write_render_save`
  - `pdfa`: `probe_blocked` / `document_write_render_save`
  - `png`, `shp`, `mp3`: `probe_blocked` / `attachment_context`

Verification:

- RED:
  `uv run pytest tests/tools/documents/test_format_completion_audit.py::test_audit_classifies_promoted_read_only_probe_and_passive_families -q`
  failed because `DocumentFormatCompletionRecord` lacked `capability_scope`.
- GREEN:
  `uv run pytest tests/tools/documents/test_format_completion_audit.py
  tests/evidence/test_document_harness_evidence.py -q`
  -> pass.
- Evidence spot check:
  `.evidence/run.json` includes `capability_scope` for promoted document,
  derivative document, and attachment-context records.
