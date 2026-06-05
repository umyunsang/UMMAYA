# Format Adapter Implementation Plan

Date: 2026-06-03

Scope: Detailed implementation plan for the Public AX document harness after the
direction correction from "all documents through one merged engine" to "one
model-facing `document` primitive orchestrating format-specific adapters."

This document is intended to become Codex progress-checklist material. It is a
plan artifact, not an implementation-complete claim.

## Decision

UMMAYA will implement:

```text
document primitive
  -> DocumentOrchestrator
    -> DocumentIntake
    -> KnownFormatClassifier
    -> FormatCapabilityResolver
    -> DocumentAdapterRegistry
      -> HwpXDocumentAdapter
      -> HwpDocumentAdapter
      -> DocxDocumentAdapter
      -> XlsxDocumentAdapter
      -> PptxDocumentAdapter
      -> PdfDocumentAdapter
      -> OdfDocumentAdapter
      -> DataFileDocumentAdapter
      -> ImageScanDocumentAdapter
      -> ArchiveDocumentSetAdapter
    -> DocumentIR
    -> AutonomousFillPlanner
    -> PermissionBoundary
    -> PatchExecutor
    -> RenderRereadValidator
    -> StructuredDiffRenderer
    -> EvidenceRecorder
```

The user-facing and model-facing unit remains one `document` primitive. Format
behavior is not merged. HWPX work is handled by an HWPX adapter, HWP by an HWP
adapter, PDF by a PDF adapter, XLSX by an XLSX adapter, and so on.

## Reference Bootstrap

Local anchors:

- `docs/vision.md`: UMMAYA is the Claude Code harness migrated to Korean
  national-infrastructure tools. Claude Code is the first reference for ambiguous
  harness behavior.
- `docs/requirements/ummaya-migration-tree.md`: root primitive discipline and
  public-service adapter boundaries.
- `specs/2802-public-doc-harness/spec.md`: all known national-infrastructure
  document families must be recognized and routed through capability profiles.
- `specs/2802-public-doc-harness/plan.md`: initial promotion matrix remains
  HWPX, HWP, DOCX, PDF, XLSX, and PPTX; the all-format track broadens known
  format classification and capability routing.
- `specs/2802-public-doc-harness/autonomous-fill-plan-research-2026-06-03.md`:
  all-format addendum selects `KnownDocumentFormat + FormatCapabilityProfile +
  Structured DocumentIR`.
- `src/ummaya/tools/documents/engines.py`: current promoted-engine registry.
- `src/ummaya/tools/documents/formats/base.py`: current adapter-protocol seed.
- `src/ummaya/tools/documents/formats/hwpx.py`, `hwp.py`, `ooxml.py`, `pdf.py`:
  current format-boundary modules.
- `src/ummaya/tools/documents/models.py`: current `DocumentFormat`,
  `FormatCapabilityProfile`, `DocumentExtraction`, `DocumentPatch`, workflow,
  validation, and promotion models.

Claude Code restored-source status:

- `.references/claude-code-sourcemap/restored-src/src/Tool.ts`: intact. Source
  of truth for strict tool definitions, permission context, tool result
  rendering hooks, and progress linkage.
- `.references/claude-code-sourcemap/restored-src/src/tools/FileEditTool/`:
  intact. Source of truth for "one edit tool, internal validation, permission,
  structured diff, and rendered result" shape.
- `.references/claude-code-sourcemap/restored-src/src/tools/ToolSearchTool/`:
  intact. Source of truth for deferred concrete-tool discovery without exposing a
  huge schema surface.

CC-to-UMMAYA mapping:

| Claude Code reference | UMMAYA document mapping |
|---|---|
| `Tool` contract | `document` primitive contract plus strict Pydantic IO |
| `FileEditTool` single model-facing edit surface | one `document` primitive, not separate inspect/fill/render tools |
| File edit validation before mutation | intake, capability, permission, and patch hard gates before any derivative write |
| File edit structured diff in UI | document structured diff rendered immediately after mutation |
| ToolSearch deferred exposure | document adapter candidates hidden below the primitive and loaded by format/capability |
| Tool result painting order | assistant prelude -> document tool use -> result/diff -> final assistant answer |

External primary sources:

- MOIS NPAS document viewer page shows public-service viewer support for HWP,
  PDF, PPT, XLS, and DOC. Source catalog entry: MOIS NPAS document viewer page.
- MOIS 2026 AI-friendly administrative document material ships HWPX, PDF, and
  Markdown side by side. Source catalog entry: MOIS 2026 AI-friendly
  administrative document material.
- Public Data Portal guide requires open formats such as CSV, JSON, and XML, and
  converts HWP/XLS data files to CSV for open-data release. Source catalog
  entry: Public Data Portal data-use guide.
- National Archives preservation-format criteria evaluate HWP, HWPX, PDF,
  PDF/A, DOC, DOCX, TXT, ODT, and EPUB. Source catalog entry: National Archives
  preservation-format criteria.
- KS X 6101/OWPML/HWPX:
  <https://www.kssn.net/search/stddetail.do?itemNo=K001010149626>.
- ECMA-376 OOXML:
  <https://ecma-international.org/publications-and-standards/standards/ecma-376/>.
- ISO 32000-2 PDF 2.0:
  <https://www.iso.org/cms/%20render/live/en/sites/isoorg/contents/data/standard/07/58/75839.html>.
- OASIS OpenDocument 1.4:
  <https://docs.oasis-open.org/office/OpenDocument/part3-schema/OpenDocument-v1.4-os-part3-schema.html>.
- OWASP File Upload Cheat Sheet:
  <https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html>.

OSS and package sources:

- `rhwp`: HWP/HWPX Rust/WASM viewer/editor, MIT, with HWP/HWPX parse, render,
  save, SVG, canvas, and public-document regression work:
  <https://github.com/edwardkim/rhwp>.
- `OpenHWP`: Rust workspace with HWP read, HWPX read/write, IR, and document
  model crates:
  <https://github.com/openhwp/openhwp>.
- `pyhwp`: HWP v5 parser/processor, useful only as comparative evidence because
  AGPL blocks direct Apache-2.0 runtime adoption:
  <https://github.com/mete0r/pyhwp>.
- `python-docx`: DOCX document, paragraph, table, style, and core-property API:
  <https://python-docx.readthedocs.io/en/latest/>.
- `openpyxl`: XLSX workbook, style, merged-cell, formula, and save API:
  <https://openpyxl.readthedocs.io/>.
- `python-pptx`: PPTX slides, placeholders, shapes, text frames, tables, images,
  and chart API:
  <https://python-pptx.readthedocs.io/>.
- `pypdf`: PDF reader/writer and AcroForm update APIs:
  <https://pypdf.readthedocs.io/>.
- `pypdfium2`: local PDFium-backed page rendering with annotation/form
  rendering support; selected as the PDF visible-evidence renderer after the
  latest PyMuPDF wheel crashed in the pytest collection path on the local macOS
  ARM64/CPython 3.12 gate:
  <https://pypdfium2.readthedocs.io/en/stable/python_api.html>.
- `Docling`: local MIT document-conversion toolkit with a unified representation
  for several formats; useful as extraction/reference shape, not as mutation
  authority:
  <https://github.com/docling-project/docling>.

Recent research and benchmark signals:

- Docling AAAI 2025: unified, richly structured representation for AI-driven
  document conversion; supports the DocumentIR direction.
- DocLLM 2024: document understanding must combine text and spatial layout;
  supports layout anchors and bounding boxes in DocumentIR.
- LayoutLMv3 2022: document AI uses both text-centric and image-centric signals;
  supports OCR/VLM as extraction-only support for scanned inputs.
- Donut 2021: OCR-free visual document understanding is useful for images but
  does not replace native-package mutation for editable public forms.

## Current State Audit

Current strengths:

- The repo already has `DocumentFormat`, `FormatCapabilityProfile`,
  `PromotionGateResult`, immutable artifact lineage, workflow steps, strict
  document patch models, and render/re-read pathways.
- `DocumentEngineRegistry` already forces a one-engine-per-format boundary and
  fail-closed behavior when no promoted engine exists.
- `formats/hwpx.py`, `formats/hwp.py`, `formats/ooxml.py`, and `formats/pdf.py`
  already seed the adapter split.
- HWPX has a bounded write smoke path and RHWP render bridge evidence.
- DOCX has a promoted read-only inspection engine.

Current gaps:

- `DocumentFormat` and `capability.py` are still limited to six values and do not
  model known-but-unpromoted national-infrastructure formats.
- `EngineBackedFormatAdapter` is too thin; it only exposes `inspect`.
- The runtime registry has engines, not full document adapters with intake,
  capability, patch, render, validation, and evidence behavior.
- HWPX semantic fill logic is still engine-local and leaks into registry helpers.
- XLSX, PPTX, PDF, HWP, ODF, data-file, image, and archive adapters are not
  default runtime adapters.
- The TUI/document result path has prior regressions where tool results rendered
  as terse cards or metadata instead of CC-style loop evidence and changed
  content.

## Architecture Principles

1. One model-facing primitive, many internal adapters.
2. Adapters are format-scoped and engine-backed.
3. A format can be known without being editable.
4. Runtime never mutates originals.
5. A write capability is invisible unless the scorecard and hard gates pass.
6. Conversion is evidence or derivative creation, not a hidden write-back path.
7. Render and re-read are mandatory after every promoted mutation.
8. TUI success follows Claude Code loop rhythm, not backend success alone.
9. No fallback can make a missing intended surface appear successful.
10. Every capability declaration is testable through local fixtures.

## Candidate Architecture Scorecard

Weights: CC parity 15, format fidelity 20, public-form safety 20,
all-format coverage 15, testability 10, license/security 10, implementation cost
5, TUI/result quality 5.

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Single merged document engine | 48 | Reject | Overclaims support and cannot respect HWPX/HWP/PDF/XLSX differences. |
| Convert all inputs to DOCX/PDF first | 61 | Reject as primary | Useful as oracle, but loses native anchors and confuses lineage. |
| HWPX-first only | 58 | Reject as final | Good first slice but fails Public AX all-format coverage. |
| External MCP document servers per format | 72 | Defer | Good taxonomy reference, but weakens native Evidence Fabric and permission control. |
| Docling-style universal extraction front door plus native mutation adapters | 84 | Support | Strong extraction reference, but not enough for public-form mutation. |
| One `document` primitive + format adapter registry + shared IR + promotion gates | 96 | Adopt | Preserves CC-style tool surface, keeps format behavior separate, and fails closed honestly. |

## Target Core Contracts

### `KnownDocumentFormat`

Purpose: classify every national-infrastructure file family without claiming
runtime edit support.

Initial values:

- `hwpx`, `hwp`, `owpml`
- `docx`, `xlsx`, `pptx`
- `doc`, `xls`, `ppt`
- `pdf`, `pdfa`
- `odt`, `ods`, `odp`
- `html`, `htm`, `txt`, `rtf`, `md`
- `csv`, `tsv`, `xml`, `json`, `jsonl`, `yaml`, `yml`
- `png`, `jpg`, `jpeg`, `tif`, `tiff`, `bmp`, `webp`
- `zip`, `7z`, `tar`, `gz`

### `DocumentFormat`

Purpose: formats that can enter promoted runtime adapter workflows. This remains
smaller than `KnownDocumentFormat`.

Initial promoted runtime values:

- `hwpx`
- `hwp`
- `docx`
- `xlsx`
- `pptx`
- `pdf`

The first expansion candidates are `odt`, `ods`, `odp`, and structured data
formats, but only after fixture-backed gates pass.

### `FormatCapabilityProfile`

Required capability flags:

- `can_intake`
- `can_read`
- `can_extract_structure`
- `can_extract_slots`
- `can_plan_autonomous_fill`
- `can_fill`
- `can_style`
- `can_render`
- `can_reread`
- `can_validate_conformance`
- `can_save_derivative`
- `can_export`

Required unsupported metadata:

- `blocked_operations`
- `known_limitations`
- `required_user_confirmation`
- `security_findings`
- `next_safe_actions`

### `DocumentFormatAdapter`

Target protocol:

```python
class DocumentFormatAdapter(Protocol):
    adapter_id: str
    known_formats: tuple[KnownDocumentFormat, ...]
    promoted_formats: tuple[DocumentFormat, ...]

    def classify(self, intake: DocumentIntakeResult) -> FormatClassification: ...
    def capability_profile(self, artifact: DocumentArtifact) -> FormatCapabilityProfile: ...
    def inspect(self, artifact: DocumentArtifact) -> DocumentExtraction: ...
    def derive_form_schema(self, extraction: DocumentExtraction) -> FormSchema: ...
    def plan_fill(self, instruction: DocumentInstruction, extraction: DocumentExtraction) -> AutonomousFillPlan: ...
    def apply_patch(self, artifact: DocumentArtifact, patch: DocumentPatch) -> ArtifactDerivative: ...
    def render(self, artifact: DocumentArtifact) -> RenderSnapshot: ...
    def reread(self, artifact: DocumentArtifact) -> DocumentExtraction: ...
    def validate(self, artifact: DocumentArtifact, baseline: ConformanceBaseline | None) -> PublicFormValidationReport: ...
```

Every method after `capability_profile` may return a typed blocked result when
the format is known but not promoted for that operation.

## Adapter Family Plan

| Adapter | Formats | Initial capability | Promotion target | Core risks |
|---|---|---|---|---|
| `HwpXDocumentAdapter` | `hwpx`, `owpml` | Read, bounded text fill, render, re-read | Rich fields, tables, styles, validation | XML path drift, style loss, table semantics |
| `HwpDocumentAdapter` | `hwp` | classify, read/convert evidence only | read and render evidence | binary corruption, AGPL candidates, no direct write |
| `DocxDocumentAdapter` | `docx` | read-only | bounded paragraph/table/style fill | nested tables, tracked changes, comments |
| `XlsxDocumentAdapter` | `xlsx` | candidate only | cell fill, style, print area, merged cells | formulas not evaluated, pivots/macros |
| `PptxDocumentAdapter` | `pptx` | candidate only | placeholder/text/table/image edits | animations, masters, embedded media |
| `PdfDocumentAdapter` | `pdf` | candidate only | AcroForm fill with visible appearance | XFA, static/scanned PDFs, signatures |
| `OdfDocumentAdapter` | `odt`, `ods`, `odp` | known/read candidate | read/extract first | lower fixture coverage, conversion drift |
| `LegacyOfficeAdapter` | `doc`, `xls`, `ppt` | known/blocked | read-or-convert evidence | binary formats and macro risk |
| `DataFileDocumentAdapter` | `csv`, `tsv`, `xml`, `json`, `jsonl`, `yaml`, `yml` | schema inspect/transform | schema-safe transforms | CSV injection, schema hallucination |
| `TextWebExportAdapter` | `html`, `htm`, `txt`, `rtf`, `md` | read/normalize | derivative text export | not official form conformance |
| `ImageScanDocumentAdapter` | images | OCR/VLM extraction only | extraction-only evidence | OCR errors, no write-back |
| `ArchiveDocumentSetAdapter` | archives | secure enumerate and child route | derivative archive only | decompression bombs, traversal, nested risk |

## Engine Selection Plan

HWPX:

- Keep `hwpx-package-text` as the bounded bootstrap mutation engine.
- Keep `@rhwp/core`/`rhwp-node-wasm` as render evidence bridge.
- Evaluate `python-hwpx` and OpenHWP for richer field/style write capability.
- Promote only when HWPX table/cell/field/style fixtures pass render and re-read.

HWP:

- Keep direct write blocked.
- Evaluate OpenHWP read and HWP-to-IR conversion first.
- Retain pyhwp as comparative local evidence only unless license status changes
  through ADR.

DOCX:

- Keep `python-docx` read-only engine.
- Add mutation tests for paragraph, run, table cell, style, and metadata.
- Use direct WordprocessingML oracle assertions and optional render oracle.

XLSX:

- Use `openpyxl` behind `XlsxDocumentAdapter`.
- Promote cell-fill only before style-fill.
- Do not claim formula evaluation. Preserve formulas outside edited cells.
- Gate merged cells, print area, sheet names, number formats, and protection.

PPTX:

- Use `python-pptx` behind `PptxDocumentAdapter`.
- Promote placeholder/text/table/image operations before charts.
- Block animations, macros, embedded objects, and master-theme rewrites.

PDF:

- Use `pypdf` only for AcroForm field fill.
- Use `pypdfium2` as the promoted local page PNG render oracle because it
  renders form/annotation appearances and passed the current pytest/macOS ARM64
  stability gate; keep qpdf as a future structure oracle candidate.
- Block static PDFs, scanned PDFs, XFA, encrypted files, signatures, and any
  invisible field appearance mismatch.

ODF:

- Use ODF standard plus `odfpy`/LibreOffice oracle as candidates.
- Start read/extract only; no write promotion until fixture coverage exists.

Data files:

- Use stdlib CSV/JSON and safe XML parsing first.
- Add schema inference and serializer round-trip tests.
- Add CSV injection detection before any spreadsheet export.

Images/scans:

- Use OCR/VLM only as extraction support.
- Never mutate raster originals.
- If user asks to write, generate a separate editable derivative and mark the
  source as extraction-only.

Archives:

- Use stdlib ZIP for ZIP first; 7z/tar/gz require separate dependency/ADR if
  runtime support is needed.
- No in-place child mutation. Repack only after all child derivatives pass.

## Implementation Checklist

### Phase 0 - Plan and baseline lock

- [ ] Record this plan as the active checklist source for the next implementation loop.
- [ ] Re-run local source audit for `models.py`, `intake.py`, `capability.py`,
  `engines.py`, `registry.py`, and `formats/*.py`.
- [ ] Record CC restored-source mapping for `Tool.ts`, `FileEditTool`, and
  `ToolSearchTool`.
- [ ] Decide whether an ADR is needed before any new dependency beyond existing
  Python/Node/Rust-WASM bridge packages.

Exit gate:

- [ ] Plan is accepted.
- [ ] No implementation task claims "all-format write" without capability split.

### Phase 1 - Format taxonomy foundation

- [ ] Add `KnownDocumentFormat` model.
- [ ] Add `DocumentFormatFamily`.
- [ ] Split "known format" from "promoted runtime format."
- [ ] Expand intake extension table and signature/container classifier.
- [ ] Add known-but-unsupported typed result.
- [ ] Add tests for HWPX/HWP/DOCX/XLSX/PPTX/PDF/ODF/legacy Office/data/text/image/archive detection.
- [ ] Add hostile fixture tests for extension mismatch, content-type mismatch,
  macro markers, active content, external links, encrypted files, decompression
  limits, path traversal, and nested archive depth.

Exit gate:

- [ ] Known-format detection precision is 1.00 on the fixture corpus.
- [ ] Unsupported known formats fail closed with a next-safe action.

### Phase 2 - Adapter skeleton

- [ ] Replace thin `EngineBackedFormatAdapter` with full `DocumentFormatAdapter`
  protocol.
- [ ] Add `DocumentAdapterRegistry`.
- [ ] Register adapters separately from promoted engines.
- [ ] Move format-specific helper logic out of `registry.py` into adapters.
- [ ] Add `DocumentOrchestrator` that runs intake -> classification ->
  capability -> inspect -> plan -> permission -> patch -> render -> re-read ->
  validate -> diff -> evidence.
- [x] Keep the public/model-facing surface as one `document` primitive.

Exit gate:

- [ ] HWPX happy path behavior remains unchanged or improves.
- [ ] HWP blocked-write behavior remains unchanged.
- [ ] No model-facing inspect/fill/render tools are needed for normal document work.

### Phase 3 - Shared DocumentIR hardening

- [ ] Extend `DocumentExtraction` into a format-neutral `DocumentIR` with
  paragraphs, tables, fields, sheets, slides, page widgets, data schemas,
  image OCR boxes, styles, metadata, and source anchors.
- [x] Add stable `SourceAnchor` model with `format_path`, `page/sheet/slide`,
  `bbox`, `confidence`, and `engine_id`.
- [x] Add `FormSlot` and `AutonomousFillPlan` models.
- [x] Add protected-range model for legal text, consent, signature, seals,
  identity fields, addresses, phone numbers, bank data, and fixed notices.

Exit gate:

- [ ] Every adapter can emit a valid empty-or-partial `DocumentIR`.
- [x] `autonomous_fill_plan` consumes only `DocumentIR`, never raw engine internals.

### Phase 4 - HWPX adapter promotion

- [x] Wrap existing `HwpXPackageTextEngine` in `HwpXDocumentAdapter`.
- [x] Move HWPX field/table aliasing and semantic target resolution into the adapter.
- [x] Keep RHWP render bridge as render-only evidence.
- [x] Add fixture tests from the copied public AX weekly log.
- [x] Add autonomous prompt tests: "read the document and write the next week"
  without tool-name hints.
- [x] Add render/re-read/diff evidence after every mutation.

Exit gate:

- [x] HWPX text/table/field extraction precision >= 0.90.
- [x] Patch target anchor correctness = 1.00.
- [x] Render/re-read parity = 1.00 on promoted HWPX fixtures.
- [ ] TUI renders compact changed content automatically after edit.

### Phase 5 - HWP adapter read/blocked path

- [x] Wrap HWP candidate behavior in `HwpDocumentAdapter`.
- [x] Add HWP classification and read-only capability profile.
- [x] Use copied HWP samples as classification and blocked-write fixtures.
- [x] Evaluate OpenHWP read evidence.
- [x] Retain pyhwp only as comparative, non-runtime evidence unless ADR approves.
- [x] Add user-facing blocked result explaining HWP direct write boundary and safe
  next actions.

Exit gate:

- [x] Direct HWP write attempts return typed blocked result 100% of the time.
- [x] Read/convert evidence is never presented as original HWP mutation.

### Phase 6 - OOXML adapters

- [x] Split `ooxml.py` into `DocxDocumentAdapter`, `XlsxDocumentAdapter`, and
  `PptxDocumentAdapter` or keep a shared OOXML utility plus separate adapters.
- [x] DOCX: add bounded write tests for paragraph, run, table cell, core metadata,
  and style preservation.
- [x] XLSX: add `openpyxl` adapter tests for cells, merged cells, styles, number
  formats, formulas outside edited cells, sheet names, print areas, and workbook
  reload.
- [x] PPTX: add `python-pptx` adapter tests for placeholders, shapes, text
  frames, tables, images, slide metadata, and blocked animation/media cases.

Exit gate:

- [x] Each OOXML adapter has separate capability profiles.
- [x] No OOXML adapter silently ignores unsupported style or media operations.
- [x] Promoted write candidates pass 85/100 plus hard gates.

### Phase 7 - PDF adapter

- [x] Add `PdfDocumentAdapter`.
- [x] Detect AcroForm vs static vs scanned vs XFA vs encrypted vs signed PDF.
- [x] Promote only AcroForm fill.
- [x] Add visible appearance verification with render evidence.
- [x] Block static/scanned/XFA/signature-preserving mutation.

Exit gate:

- [x] AcroForm field values re-read and visibly render.
- [x] Static/scanned/XFA/signature cases block with typed reasons.

### Phase 8 - ODF, data, text, image, archive adapters

- [x] Add ODF read/extract adapter candidates.
- [x] Add data-file adapter for CSV/TSV/XML/JSON/JSONL/YAML.
- [x] Add text/web export adapter for HTML/TXT/RTF/Markdown.
- [x] Add image/scan extraction-only adapter.
- [x] Add archive adapter for secure child routing.
- [x] Route passive known-only families through the model-facing `document`
  primitive for `inspect` and `extract` while keeping mutation blocked.

Exit gate:

- [x] Each known family classifies correctly.
- [x] Each unsupported write returns typed blocked result.
- [x] Data transforms have serializer round-trip evidence.
- [x] Images never mutate originals.
- [x] Archives never mutate child files in place.
- [x] Alpha inspect succeeds for passive known-only fixtures without creating
  runtime edit artifacts.
- [x] Beta fill stays blocked for every passive known-only fixture.

### Phase 9 - Autonomous fill planner

- [x] Add deterministic form-slot extraction for label/value, table-cell, field,
  sheet-cell, slide-placeholder, and AcroForm patterns.
- [x] Add value-precedence rules: explicit user values -> safe recurrence ->
  cited session context -> draftable free text -> needs input.
- [x] Add public-document writing profile from MOIS AI-friendly guidance.
- [x] Add legal-field suppression across every format.
- [ ] Add natural-language TUI tests with no tool-name hints.

Exit gate:

- [x] Unsafe auto-fill suppression = 1.00.
- [x] Form-slot precision >= 0.90 for promoted edit formats.
- [x] Missing identity/legal inputs become `needs_input`, not fabricated text.

### Phase 10 - TUI and CC loop parity

- [x] Capture Claude Code baseline when `claude` is available, or record exact
  blocker and use restored source fallback.
- [x] Ensure UMMAYA `bun run tui` shows assistant prelude before the document tool
  call when the model emits it.
- [x] Ensure document tool use row is visible.
- [x] Ensure document tool result/diff is visible immediately after execution.
- [x] Ensure mutating document tools show changed content only, not artifact logs.
- [x] Ensure the loop continues to a final assistant answer.
- [x] Ensure compact diff does not show zero hunks when changed content exists.
- [x] Ensure browser auto-open, terminal image protocols, ASCII canvas, and
  metadata-only cards are not accepted as success.

Exit gate:

- [x] CC TUI strict alpha score >= 90.
- [x] Scores below 100 name exact residual risk.
- [x] Real `bun run tui` evidence exists for a natural Korean query.

### Phase 11 - Evidence Fabric and beta matrix

- [x] Add Evidence Fabric records for intake, classification, capability,
  adapter selection, permission, mutation, render, re-read, validation, diff,
  and TUI frame hashes.
- [x] Add beta matrix across domains: weekly log, contest proposal, consent,
  pledge, spreadsheet, PDF form, presentation, public-data CSV/JSON, static PDF,
  scanned image, archive bundle.
- [x] Add negative beta matrix: missing file, ambiguous file candidates,
  unsupported known format, blocked HWP write, static PDF fill, macro/active
  content, path traversal, oversized archive, external link.

Exit gate:

- [x] Evidence run is joinable by correlation ID and artifact hash.
- [x] User-visible TUI artifacts correspond to backend evidence records.

## Evaluation Criteria

### Adapter architecture score

Minimum shippable score: 92/100.

| Criterion | Weight | Pass standard |
|---|---:|---|
| CC harness parity | 15 | One primitive, strict tool contract, visible tool-use/result/final-answer loop |
| Adapter separation | 15 | Each format family has its own adapter and no central format-specific branches |
| Capability honesty | 15 | Known but unsupported formats fail closed with typed next actions |
| Mutation safety | 15 | No original mutation, derivative lineage, permission, render/re-read |
| Public-form conformance | 10 | protected text, fields, table geometry, style/layout anchors |
| Security | 10 | OWASP upload controls, active content blocked, archive limits |
| Evidence quality | 10 | artifact hash, frame hash, validation report, scorecard |
| TUI UX | 10 | changed content visible, no metadata/log substitute |

### Format promotion score

Existing scorecard remains active:

- extraction fidelity: 20
- write fidelity: 20
- style/layout control: 15
- deterministic round trip: 15
- public-form validation: 15
- security/privacy: 10
- license/maintenance/tool-call usability: 5

Write promotion:

- score >= 85
- all hard gates pass
- render/re-read evidence exists
- no critical security finding
- no unsupported operation silently ignored

Read-only promotion:

- score >= 75
- security hard gates pass
- write/fill/style explicitly blocked

### TUI alpha score

Minimum shippable score for user-visible document work: 90/100.

- 25 CC loop parity
- 20 real TUI proof
- 20 document/diff UX
- 15 root-cause rigor and no fallback success
- 10 evidence joinability
- 10 regression coverage

## Alpha Test Matrix

Run in a fresh UMMAYA TUI session with natural Korean prompts. Prompts must not
name internal tool IDs.

1. HWPX weekly log: "Find the weekly activity log in Downloads and write the next
   week based on the document contents."
2. HWP contest proposal: "Read the contest proposal form and tell me what can be
   filled automatically and what needs my input."
3. HWP consent form: "Understand this consent form and prepare it safely."
4. DOCX form: "Fill the provided public form from the information in this chat."
5. XLSX sheet: "Complete the submission sheet while preserving formulas and print
   area."
6. PDF AcroForm: "Fill this permit PDF and show changed fields."
7. Static/scanned PDF: "Complete this PDF." Expected: blocked or needs editable
   template.
8. PPTX briefing: "Update this slide deck with the project summary."
9. CSV/JSON public data: "Normalize this downloaded public-data file and show
   what changed."
10. ZIP bundle: "Inspect this submission package and handle each document inside."

Required visible sequence:

```text
user prompt
assistant intent/progress text
Document(...)
document result with changed content or typed blocked/needs_input reason
assistant final answer
```

## Beta Test Matrix

Beta adds breadth and regression pressure:

- 3 departments or agencies represented by fixture provenance.
- 3 document intents: fill, explain missing fields, validate/save.
- 3 risk classes: normal, ambiguous, hostile.
- 3 display modes: compact, expanded transcript, evidence artifact.
- 3 output classes: edited derivative, needs input, blocked.

Beta must include:

- all promoted formats;
- all known-but-unsupported families;
- at least one legal/consent document;
- at least one public-data file;
- at least one archive bundle;
- at least one scanned/image-only artifact.

## Risk Register

| Risk | Mitigation |
|---|---|
| HWP direct write corrupts files | Block direct write; evaluate read/convert only. |
| Universal parser hides unsupported operations | Use format-specific adapters and capability profiles. |
| Conversion loses official layout | Conversion is oracle/derivative only, not hidden mutation. |
| PDF field saves but is visually blank | Require visible render appearance verification. |
| XLSX formulas appear stale | Do not claim formula evaluation; preserve formulas and warn. |
| PPTX masters/animations drift | Block complex media and master rewrites until promoted. |
| ODF support becomes shallow | Start read-only; require fixture parity before write. |
| Image OCR hallucination | Mark extraction confidence and require editable derivative for writes. |
| TUI displays backend logs | Strict alpha gate rejects metadata/log substitute. |
| Fallback masks root cause | Any fallback success is a failure unless root cause and removal are tracked. |

## Dependency and ADR Rules

No new runtime dependency is allowed without:

- source mapping to the adapter it serves;
- SPDX and transitive license review;
- local-only execution proof;
- artifact size and CI impact;
- fixture-backed scorecard;
- Evidence Fabric join plan;
- ADR if it introduces a new runtime class, external CLI, Rust/WASM bridge,
  LibreOffice dependency, OCR/VLM model, or archive library.

## Completion Definition

The all-format adapter architecture is complete only when:

- one `document` primitive orchestrates all document work;
- each known format family has an adapter or typed unsupported profile;
- HWPX remains promoted and does not regress;
- every write-enabled adapter passes the scorecard and hard gates;
- HWP direct write remains blocked;
- the TUI alpha score is >= 90 with real `bun run tui` evidence;
- Evidence Fabric records the complete lifecycle;
- no success path depends on hidden fallback, browser auto-open, terminal image
  protocols, ASCII canvas, or metadata-only cards.
