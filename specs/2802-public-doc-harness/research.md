# Research: Public AX Document Harness

## Source Set

### UMMAYA and Claude Code References

- `docs/vision.md`: UMMAYA is the Claude Code-style harness with Korean public-service tool surfaces; ambiguous harness decisions use CC patterns first.
- `docs/requirements/ummaya-migration-tree.md`: active primitive roots are `find`, `locate`, `send`, and `check`; every domain capability appears as a concrete tool object.
- `.references/claude-code-sourcemap/restored-src/`: CC has adjacent patterns for document reading, PDF document blocks, extension lists, and binary output storage, but not public-form authoring.

### External Primary and Ecosystem References

- KS X 6101 OWPML/HWPX: KSSN lists KS X 6101 as the OWPML document structure standard, revised on 2024-10-30, with scope covering HWPX generation, processing, compatibility, metadata, and conformance criteria.
- ECMA-376 Office Open XML: Ecma defines the OOXML vocabularies, document representation, packaging, and consumer/producer requirements for DOCX, XLSX, and PPTX.
- MCP Tools specification: tools can expose input schema, output schema, resource links, and structured content. This validates a schema-bound tool contract design, while UMMAYA keeps its native registry.
- OWASP File Upload Cheat Sheet: document intake must use extension allowlists, content-type distrust, signature validation, safe filenames, size limits, and storage outside public roots.
- Pydantic v2 JSON Schema: model schemas are generated from strict Pydantic models, avoiding hand-maintained divergent schemas.

### HWP/HWPX Open-Source and Private-Ecosystem References

- `python-hwpx`: Python HWPX automation with open/read/edit/generate/validate, OWPML dataclass mapping, OPC handling, table filling, text/style operations, and atomic save patterns.
- `hwpx-mcp-server`: MCP-oriented HWPX server exposing document info, text, outline, search/replace, batch replace, paragraph insertion, copy, table-cell edits, markdown conversion, and validation.
- `rhwp`: Rust/WASM HWP/HWPX viewer/editor ecosystem; useful as a comparative conformance target, but adopting it in UMMAYA would require a cross-runtime bridge and extra dependency scrutiny.
- `hwp-mcp`: MCP server pattern built around HWP/HWPX operations; useful for tool taxonomy and risk mapping.
- OpenHWP, pyhwp, hwp.js, and unhwp: useful HWP binary read/extract/convert references, not sufficient evidence for safe direct HWP binary writing in this epic.

### OOXML/PDF Ecosystem References

- `python-docx`: provides WordprocessingML document and style manipulation, including character, paragraph, and table style access.
- `openpyxl`: provides XLSX workbook/cell style manipulation, named styles, page setup, number formats, and save support.
- `pypdf`: supports AcroForm field reading and updating; XFA and widget/appearance behavior must be explicitly detected and gated.
- `python-pptx`: supports creating, reading, and updating PPTX presentations without PowerPoint, including placeholders, text boxes, images, tables, charts, and core properties, with documented unsupported areas.

## Decision 1: Harness Boundary

**Decision**: Implement the document feature as a local UMMAYA tool harness registered in the existing `ToolRegistry`, not as a new service, not as a new root primitive family, and not as an external MCP dependency.

**Rationale**:

- UMMAYA's architecture already models model-facing capabilities as concrete `GovAPITool` objects with primitive metadata.
- MCP's structured content and output schema direction supports typed contracts, but UMMAYA already has a native tool loop and permission pipeline.
- Keeping the harness local avoids external document upload, preserves zero-egress posture, and allows Evidence Fabric joins.

**Alternatives Considered**:

- External MCP server for HWPX only: rejected as too narrow and inconsistent with UMMAYA's registry/evidence contract.
- Generic "file edit" tool: rejected because public-form validity requires format-specific round-trip, render, and schema evidence.
- New primitives such as `write` or `edit`: rejected because project primitives are canonical and the feature can map concrete tools to `find`, `check`, and `send`.

## Decision 2: Format Capability Profiles

**Decision**: Every format and engine is represented by a `FormatCapabilityProfile` and is promoted separately for read, write, style, render, and validation.

**Rationale**:

- HWPX, OOXML, and PDF expose different semantics. A global "can edit documents" claim would be false.
- Public-office forms depend on exact fields, tables, layout, and style persistence, not just text extraction.
- Promotion gates make the LLM's tool surface honest: unsupported operations return structured blocked results instead of best-effort mutation.

**Alternatives Considered**:

- Single library abstraction: rejected because no current OSS library reliably covers all target formats and HWP/HWPX edge cases.
- Model-only editing instructions: rejected because the LLM must save verified files, not merely describe edits.
- Always expose write tools and fail at runtime: rejected because it violates fail-closed tool discovery.

## Decision 3: HWPX Primary Path

**Decision**: Treat HWPX as the primary Korean public-document write target. Initial implementation should evaluate `python-hwpx` as the first Python-native HWPX candidate and compare it against OWPML conformance oracles and rhwp/hwp-mcp ecosystem behavior before promotion.

**Rationale**:

- HWPX is based on KS X 6101/OWPML and is XML/package-oriented, making structured extraction and deterministic mutation more realistic than binary HWP.
- `python-hwpx` exposes exactly the operation classes required by the spec: open, copy/save, table filling, paragraph/style operations, OWPML mapping, package validation, and CLI/API validation.
- OWPML assertions remain necessary as test oracles because library success does not prove public-form conformance.

**Alternatives Considered**:

- Hancom official tooling: deprioritized because the user explicitly requested OSS/private ecosystem evidence rather than closed official code paths.
- Direct raw XML editing as a product path: rejected because it would rebuild a document editor/parser instead of a harness. Direct XML assertions may be used only as test oracles for candidate-engine evaluation.
- Rust/WASM RHWP as core dependency: not selected for the initial core because it may be strong for conformance but adds runtime/language complexity that needs separate approval.

## Decision 4: Binary HWP Policy

**Decision**: Binary HWP direct writing is blocked for this epic. HWP support can be read-only, extraction, render evidence, or conversion evidence only after capability scoring passes.

**Rationale**:

- HWP remains common in Korean public workflows, but safe direct write requires stronger proof than current plan evidence.
- Binary mutation can corrupt forms silently and is difficult to validate without authoritative rendering/round-trip tools.
- A blocked-write result is more honest to the LLM and user than writing a corrupt administrative form.

**Alternatives Considered**:

- Use any available HWP OSS library for write: rejected until fidelity, license, and deterministic save evidence exist.
- Convert HWP to HWPX and edit: allowed only as a derivative workflow if conversion fidelity is scored and the result is clearly labeled as converted derivative, not original HWP mutation.

## Decision 5: OOXML and PDF Engines

**Decision**: Evaluate mature Python-native libraries for OOXML/PDF operations: `python-docx`, `openpyxl`, `python-pptx`, and `pypdf`, each behind the same promotion gate.

**Rationale**:

- DOCX/XLSX/PPTX are OOXML packages with established Python libraries that can manipulate document text, styles, tables, workbook cells, slide placeholders, and metadata.
- PDF authoring must be narrower: AcroForm field extraction/fill is feasible with `pypdf`; static scanned PDFs, XFA forms, signature-preserving mutation, and arbitrary visual layout generation must be blocked unless explicitly proven.
- The public AX need is form completion and validated file saving, not general desktop-office replacement.

**Alternatives Considered**:

- LibreOffice CLI as the primary editor: rejected as a first-class dependency because it is environment-heavy and harder to type. It can be an optional render/convert oracle in local developer evidence.
- PDF freeform painting: rejected for public forms because it can produce visually plausible but semantically invalid artifacts.

## Decision 6: Public-Form Validation and data.go.kr Use

**Decision**: Use data.go.kr national core data as a metadata/corpus anchor for public-administration document domains, not as the sole public-form conformance oracle.

**Rationale**:

- The portal's national core data category is demand-centered and spans many agencies/domains, so it helps select representative administrative form topics and metadata.
- The page itself does not provide enough file-level form templates, render baselines, or submission rules to prove document conformance.
- Therefore the validation corpus must combine data.go.kr-derived metadata, checked-in offline fixtures, expected field manifests, round-trip extraction, render snapshots, and security negatives.

**Alternatives Considered**:

- Treat data.go.kr as sufficient: rejected because metadata is not form-layout truth.
- Ignore data.go.kr: rejected because it is useful for public-domain coverage and the user explicitly asked to judge its utility.

## Decision 7: Scoring and Promotion Loop

**Decision**: Keep the 100-point scorecard from the spec and apply hard gates before exposing write capabilities:

- extraction fidelity: 20
- write fidelity: 20
- style/layout control: 15
- deterministic round trip: 15
- public-form validation: 15
- security/privacy: 10
- license/maintenance/tool-call usability: 5

Write promotion requires at least 85/100 plus all hard gates. Read-only promotion requires at least 75/100 plus all security hard gates.

**Rationale**:

- The scorecard makes the "high-fit loop" explicit and auditable.
- It prevents a library from being promoted because it passes one happy-path fixture.
- It allows the harness to expose partial capabilities honestly while blocking unsupported write paths.

**Alternatives Considered**:

- Binary pass/fail only: rejected because format support is multi-dimensional.
- Manual review only: rejected because the LLM tool surface needs deterministic machine-readable capability gates.

## Decision 8: Artifact and Security Model

**Decision**: Store originals immutably, write only derivatives, and gate all file intake through document-upload-class controls.

**Rationale**:

- OWASP file guidance applies because the target formats include ZIP/package formats, PDFs, active content risks, and misleading filenames.
- The local artifact store gives the permission UI and evidence layer stable artifact IDs, checksums, and render/report paths.
- Safe derivative naming prevents the model from overwriting user originals or writing into public roots.

**Alternatives Considered**:

- Edit in place: rejected because public forms need auditability and rollback.
- Trust MIME/content-type: rejected because MIME is user-controlled and insufficient on its own.
- Store under project root by default: rejected because user-provided documents should not become accidental source artifacts.

## Decision 9: Harness/Engine Boundary Correction

**Decision**: UMMAYA builds the LLM-facing document harness and promotion/evidence loop. It does not build general-purpose first-party parsers, converters, or office editors for HWPX, HWP, OOXML, or PDF in this epic. Format-specific modules are thin engine-adapter boundaries and candidate metadata; real broad read/write/style behavior is supplied by promoted engines such as `python-hwpx`, HWPX MCP servers, `python-docx`, `openpyxl`, `python-pptx`, `pypdf`, or future bridge engines after the scorecard passes. A bounded `hwpx-package-text` bootstrap is allowed only for existing HWPX package text-node replacement smoke tests, because it preserves package members and does not claim style/layout/render fidelity.

**Rationale**:

- The user requirement is Public AX document authoring through an LLM harness, not a new document parser project.
- Direct parsers can make tests green while hiding the actual risk: whether an engine can preserve public-office form structure, fonts, table geometry, visible PDF appearances, and deterministic saved bytes.
- The correct foundation is therefore: intake -> artifact lineage -> engine registry -> typed IR/result -> patch/render/reread/validation -> evidence -> promotion gate.
- Minimal stdlib handling is allowed for intake/security checks, test doubles, and bounded HWPX package text-node smoke edits. It must not be represented as broad document parsing, conversion, style control, or render fidelity.

**Alternatives Considered**:

- Build direct parsers for each format: rejected because it expands the scope beyond a harness and weakens fidelity claims.
- Add dependencies immediately and expose their operations: rejected because dependency/license and conformance gates must pass first.
- Keep format modules as direct extraction code: rejected after implementation review because it confuses the harness layer with engine internals.

## Dependency and License Decision Checklist

Every candidate parser, editor, renderer, converter, or MCP-style document harness must pass this checklist before it can be added as a runtime dependency or promoted into a model-visible capability profile. Passing this checklist promotes an engine behind the harness; it does not turn UMMAYA itself into a parser/converter implementation.

| Gate | Required Evidence | Automatic Rejection |
|------|-------------------|---------------------|
| Format authority mapping | Candidate behavior maps to the relevant baseline: KS X 6101/OWPML for HWPX, ECMA-376/OOXML for DOCX/XLSX/PPTX, and PDF AcroForm/render semantics for PDF. | Claims broad editing support without format-structure evidence or round-trip tests. |
| License fit | SPDX-compatible license is recorded, transitive license risks are noted, and AGPL/GPL or unclear licensing is escalated before adoption. | Copyleft or unknown license is added to runtime without an explicit architecture decision. |
| Maintenance signal | Current release or repository activity, issue posture, supported Python/runtime version, and test suite presence are recorded. | Abandoned runtime, unsupported Python baseline, or no visible maintenance path for security fixes. |
| Security posture | Intake never executes macros or active content, never fetches external links, enforces extension/signature/container checks, and handles decompression limits. | Library requires opening untrusted files through a desktop office process or hidden network call. |
| Deterministic save | Saved derivatives can be re-read and normalized to stable content, metadata, style anchors, and hash-linked lineage. | Non-deterministic output cannot be normalized or produces silent data loss on fixtures. |
| Public-form fidelity | Candidate preserves protected labels, table geometry, fields, fonts/styles, page or printable-region anchors, and signature/seal regions where applicable. | Edits text but cannot preserve official layout anchors needed by validators. |
| Tool-call usability | Operations can be exposed as strict Pydantic request/result models with typed unsupported outcomes and no free-text-only parsing. | The only interface is human-interactive UI automation without structured results. |
| Evidence integration | Candidate can emit fixture-level scorecard records, blocked reasons, and render/re-read artifacts joinable to Evidence Fabric. | Candidate success cannot be audited outside an ad hoc manual screenshot. |

Reference refresh on 2026-06-01:

- [OWASP File Upload Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html) remains the security baseline for extension allowlists, signature validation, size limits, and storage outside public roots.
- [ECMA-376](https://ecma-international.org/publications-and-standards/standards/ecma-376/) remains the baseline for OOXML document, spreadsheet, presentation, and packaging semantics.
- [Model Context Protocol tools](https://modelcontextprotocol.io/specification/2025-06-18/server/tools) confirms the schema-bound tool direction through input schemas, output schemas, structured content, and resource links; UMMAYA keeps its native ToolRegistry.
- [python-hwpx](https://github.com/airmang/python-hwpx) and HWPX MCP server patterns are credible HWPX harness references, but must still pass the UMMAYA scorecard before runtime adoption.
- [pyhwp](https://github.com/mete0r/pyhwp) is useful HWP v5 parse/extract evidence, but its AGPL license and read/convert emphasis make it unsuitable for direct runtime write promotion without separate approval.
- [rhwp](https://github.com/edwardkim/rhwp) is a fast-moving HWP/HWPX viewer/editor reference with strong conformance ambitions; Rust/WASM adoption remains a separate bridge decision, not part of the Python foundation layer.
- [python-docx](https://python-docx.readthedocs.io/) is promoted for default
  read-only DOCX inspection after fixture evidence; its documented
  `Document(...)`, `paragraphs`, `tables`, `iter_inner_content`, and
  `core_properties` APIs map to the local extraction layer. [openpyxl](https://openpyxl.readthedocs.io/), [pypdf](https://pypdf.readthedocs.io/), and [python-pptx](https://python-pptx.readthedocs.io/) remain candidate engines only after fixture evidence proves the specific operation class being promoted.

## Deep-Research Evaluation Criteria

The parallel implementation loop uses the detailed C1-C12 criteria in [`parallel-evaluation-plan.md`](./parallel-evaluation-plan.md). The criteria refine the scorecard into hard gates and weighted signals:

- Hard gates: standards-valid output, controlled mutation, strict LLM tool contracts, file-ingest safety, unsupported/unsafe feature detection, and headless operation.
- Conditional hard gates: non-destructive round trip for edit engines, format-specific form/data fidelity when the workflow depends on it, and scale/resource behavior for public upload paths.
- Weighted signals: structured extraction, non-critical format fidelity, ordinary local scale behavior, supply-chain maintenance posture, and data.go.kr corpus utility.

The criteria are mapped to KS X 6101/OWPML, ECMA-376/OOXML, PDF 2.0/AcroForm semantics, OWASP file-upload controls, MCP structured tool output, and upstream engine references. They are intentionally promotion criteria for external engines behind the harness, not permission to implement first-party parsers or converters inside UMMAYA.

## Resolved Unknowns

| Unknown | Resolution |
|---------|------------|
| Is there an existing LLM/MCP-style HWPX harness? | Yes. `hwpx-mcp-server` and related ecosystem examples show HWPX read/search/edit/validate tool sets. UMMAYA should learn from their tool taxonomy but keep native ToolRegistry integration. |
| Can HWPX be a credible write target? | Yes, conditionally. KS X 6101 and `python-hwpx` make HWPX the best first Korean public-document write target, but promotion still requires local conformance evidence. |
| Can binary HWP be written safely now? | No for this epic. Read-only/conversion may be evaluated; direct write is blocked. |
| Does data.go.kr help with public-form conformance? | Partially. It helps domain/corpus selection, not file-level conformance by itself. |
| Should the model control fonts and form styles? | Yes, through typed style patches and format-specific adapters only after round-trip/render validation proves the format can preserve intended styles. |
| Should document tools be separate from government adapters? | Yes. This is a local artifact harness registered as tools; it is not an agency API adapter. |

## Implementation Tracking Items Covered By Tasks

The items below are in-epic implementation tracking work. They are covered by `tasks.md` and should not be copied into the spec's scope-exclusion table.

| Tracking Item | Covering Tasks |
|---------------|----------------|
| Common public-office form sample pack | T043, T068 |
| Exact fixture count and licensing | T016, T017, T043, T065, T068 |
| HWPX engine final selection after local scorecard run | T062, T064, T066, T069 |
| HWP read-only engine final selection | T023, T067 |
| PDF render/appearance validator final selection | T040, T046, T048, T053 |
| Dependency additions and license notes | T004, T063, T069 |
| Evidence scenario acceptance fixture set | T003, T047, T051, T077 |

The only scope exclusions for this feature are the seven rows already listed in `spec.md`; `/speckit-taskstoissues` must convert those tracking markers to issue-backed references before implementation starts.

## US6 Candidate Evaluation Decisions

Candidate evaluation is fixture-driven and offline-only. The checked-in profile fixture records
scorecard dimensions, dependency gate status, license gate status, evidence references, and
operation-level notes; the evaluation runner applies those gates before exposing any promotion
decision. This promotes engines behind the harness only. It does not add parsers, converters,
editors, runtime dependencies, or model-visible document operations.

Current fixture decisions:

| Format | Candidate | Operation | Decision | Reason |
|--------|-----------|-----------|----------|--------|
| HWPX | `python-hwpx` | read/write | Promote candidate profile | Scorecard passes read/write thresholds, dependency gate passes, license gate passes, and evidence references stay offline. |
| HWPX | `hwpx-package-text` | read/write | Promote default smoke engine | No dependency addition; supports only existing HWPX text-node reread/write smoke needed for public-form alpha tests. Style, render, and layout fidelity remain unpromoted. |
| HWPX | `direct-owpml-oracle` | write | Reject for runtime promotion | Retained only as a conformance/test oracle; it does not expose a supported runtime write operation. |
| HWP | `OpenHWP-read-only` | read | Promote candidate profile | Read-only extraction score meets the read threshold with dependency and license gates passed. |
| HWP | `OpenHWP-read-only` | write | Block | Binary HWP direct write remains blocked in this epic regardless of score. |
| HWP | `pyhwp-read-only` | read | Defer/reject runtime promotion | AGPL license gate fails, so it remains comparative read evidence only. |
| DOCX | `python-docx` | read | Promote default runtime engine | PyPI records MIT license and Python 3.9+ support; python-docx 1.2.0 documents loading DOCX files, top-level paragraphs/tables, document-order iteration, and core properties. |
| HWPX | `rhwp` | write | Defer runtime promotion | Score and license are promising, but the Rust/WASM bridge dependency gate requires a separate architecture decision. |

The offline data.go.kr metadata snapshot is evaluation context only. It supports semantic,
table, image-reference, summary, and rewrite evaluation with the FR-037 macro average
components (`paragraph_block_f1`, `table_cell_f1`, `image_reference_f1`,
`metadata_exact_match`) and the 0.85 threshold, but it is not an authoritative official-form
layout oracle.
