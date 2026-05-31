# Feature Specification: Public AX Document Harness

**Feature Branch**: `2802-public-doc-harness`
**Originating Epic**: #3050
**Created**: 2026-06-01
**Status**: Draft
**Input**: User description: "Build the document-writing foundation required for Public AX: LLMs must accurately read and write public-document artifacts such as HWPX, HWP, DOCX, PDF, XLSX, and PPTX; control fonts, styles, layout, and official form structure; save files safely; validate whether the generated artifact conforms to public submission formats; research open-source/private HWP/HWPX editor and document harness references rather than relying on Hancom official code; evaluate whether the data.go.kr public document AI corpus helps form-conformance validation; and define a layered implementation design through a self-evaluating high-conformance loop."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Inspect and Normalize Public Document Artifacts (Priority: P1)

A citizen, civil servant, or evaluator provides an existing public-document file in HWPX, HWP, DOCX, PDF, XLSX, or PPTX format. UMMAYA reads the file without mutating it, identifies the real format and document structure, extracts text, tables, images, style cues, and candidate form fields, and returns a normalized, evidence-backed representation the LLM can reason over.

**Why this priority**: Public AX cannot safely draft or validate official documents until the harness can read the formats already exchanged in Korean national infrastructure. HWP/HWPX and office-document extraction are therefore the foundation layer.

**Independent Test**: Provide fixture files for each supported extension and verify that UMMAYA returns a structured inspection result with detected format, source checksum, extraction warnings, text blocks, tables, embedded-media references, and layout anchors where available.

**Acceptance Scenarios**:

1. **Given** a valid HWPX public form template, **When** the user asks UMMAYA to inspect it, **Then** UMMAYA returns section structure, paragraph text, table cells, form-field candidates, font/style metadata, and source anchors without changing the original file.
2. **Given** a legacy HWP file, **When** the user asks UMMAYA to read it, **Then** UMMAYA extracts readable content and reports the supported capability level for that artifact before any edit is attempted.
3. **Given** a DOCX, PDF, XLSX, or PPTX artifact, **When** the user requests document analysis, **Then** UMMAYA returns a normalized representation appropriate to the format and lists unsupported or lossy elements explicitly.
4. **Given** an encrypted, corrupted, macro-enabled, or oversized document, **When** inspection is requested, **Then** UMMAYA fails closed with a citizen-readable reason, an audit event, and no partial write.

---

### User Story 2 - Fill Official Forms While Preserving Required Formatting (Priority: P1)

A citizen needs to complete a public submission form. UMMAYA identifies fillable fields or inferred field regions, maps user-provided answers to those fields with evidence, writes only the intended fields into an editable copy, preserves required margins, fonts, tables, numbering, signature blocks, and fixed explanatory text, then returns a derivative file ready for review.

**Why this priority**: The core Public AX value is not only summarizing documents but producing artifacts that can be submitted or reviewed against public form expectations. Any uncontrolled layout drift can make a filing unusable.

**Independent Test**: Use public-form fixtures with expected field values and locked layout requirements. Fill the form through the harness, re-read the saved file, and verify that field values match, protected text is unchanged, and required formatting checks pass.

**Acceptance Scenarios**:

1. **Given** a HWPX or DOCX official form template with required fields, **When** the user supplies answers, **Then** UMMAYA creates a derivative copy, fills only mapped fields, preserves fixed template content, and records every field-to-answer mapping.
2. **Given** an XLSX workbook used as a public submission sheet, **When** UMMAYA fills structured cells, **Then** it preserves sheet names, merged regions, formulas outside edited cells, cell styles, and printable areas unless the user explicitly requests a permitted change.
3. **Given** a fillable PDF, **When** UMMAYA writes user-provided answers, **Then** it fills recognized fields and validates that visible field appearances match the saved data.
4. **Given** a static PDF or scanned PDF with no reliable fields, **When** the user asks UMMAYA to complete it, **Then** UMMAYA reports that the artifact is not safely fillable in this epic and suggests a supported editable template or the tracked OCR/overlay deferred item.

---

### User Story 3 - Validate Public-Form Conformance Before Save or Submission (Priority: P1)

Before the user trusts a generated document, UMMAYA checks whether the artifact still matches the official form structure and reports hard failures, warnings, and confidence signals. The user can see whether the document is ready for human review, blocked for correction, or outside the supported capability profile.

**Why this priority**: The risk is not only that an LLM writes incorrect text, but that it produces a visually plausible document whose margins, page count, required labels, table structure, or signature area no longer match the public form. Validation is the safety gate.

**Independent Test**: Run the validator against known-good templates, intentionally damaged derivatives, and filled derivatives. Verify that hard rule violations block the final save, while warnings remain reviewable with exact page, section, sheet, or field anchors.

**Acceptance Scenarios**:

1. **Given** a completed derivative, **When** validation runs, **Then** UMMAYA reports hard checks for required fields, page count, protected text, table geometry, required labels, signature/seal blocks, and known submission-critical layout constraints.
2. **Given** a derivative whose font, margin, table column, or required label drifted from the baseline, **When** validation runs, **Then** UMMAYA blocks the document from being marked ready and returns exact remediation targets.
3. **Given** a semantic public document from the 행정안전부_정부 공문서 AI 학습데이터 조회 서비스 corpus, **When** it is used in evaluation, **Then** UMMAYA uses it for structure, table, image, summary, and rewrite evaluation but does not treat it as authoritative proof of official submission layout.
4. **Given** a format or template whose conformance cannot be verified, **When** validation is requested, **Then** UMMAYA returns an "unsupported for conformance" result rather than guessing.

---

### User Story 4 - Render, Re-Read, and Evidence-Gate Generated Artifacts (Priority: P1)

After any write operation, UMMAYA renders the derivative artifact into reviewer-readable evidence, re-reads the saved file, compares expected values and layout anchors, and stores a validation report tied to the original file hash and derivative hash.

**Why this priority**: A document harness is only trustworthy if saved artifacts can be independently inspected. Rendering plus re-read closes the loop between model intent, file bytes, and visible document output.

**Independent Test**: Generate filled HWPX, DOCX, XLSX, PDF, and PPTX derivatives from fixtures; render reviewer evidence; re-read each derivative; and verify that all expected values, style constraints, and validation reports are linked by document hash.

**Acceptance Scenarios**:

1. **Given** a filled HWPX or DOCX derivative, **When** evidence generation runs, **Then** UMMAYA creates page-level render evidence, a structured diff, and a re-read result that confirms expected values.
2. **Given** a workbook derivative, **When** evidence generation runs, **Then** UMMAYA captures workbook-level metadata, changed-cell diffs, printable-area checks, and a renderable preview for sheets in scope.
3. **Given** a PDF or PPTX derivative, **When** evidence generation runs, **Then** UMMAYA captures page or slide previews and compares visible text against the intended output.
4. **Given** any render or re-read mismatch, **When** UMMAYA evaluates readiness, **Then** it downgrades the artifact status and exposes the mismatch before the user can treat the document as ready.

---

### User Story 5 - Drive Document Work Through the UMMAYA Tool Loop (Priority: P2)

The LLM can plan and execute document operations through UMMAYA's existing harness. It calls explicit document capabilities for inspection, extraction, field-schema discovery, copying, filling, styling, rendering, validation, and saving. These capabilities remain concrete ToolRegistry entries discovered and invoked under UMMAYA's existing `find`, `check`, and `send` primitive families, not new root primitives. Any operation that writes or exports a document requires permission context and produces auditable evidence.

**Why this priority**: Public AX requires the model to operate documents as controlled tools, not as hidden side effects. Tool-loop integration turns the document layer into a repeatable national-infrastructure capability.

**Independent Test**: Run a conversation that asks UMMAYA to inspect a form, explain missing fields, fill the form, validate it, and save a derivative. Verify that the tool sequence, permissions, outputs, and evidence reports are observable end to end.

**Acceptance Scenarios**:

1. **Given** a user asks to complete an attached public form, **When** the LLM plans the work, **Then** it discovers concrete document capabilities through the existing tool registry and selects them in a valid order: inspect, derive field schema, copy for edit, fill, render, validate, and save.
2. **Given** a write or export operation is about to run, **When** the tool loop reaches that step, **Then** UMMAYA presents the user with a permission request that identifies the source file, derivative path, intended changes, and validation status.
3. **Given** a document contains personal data, **When** the harness processes it, **Then** audit evidence records the operation locally and does not transmit document bytes to unrelated external channels.
4. **Given** the model asks for an unsupported edit, **When** the harness evaluates the request, **Then** it returns a typed unsupported-capability result instead of performing a best-effort mutation.

---

### User Story 6 - Compare Candidate Format Harnesses With a High-Conformance Loop (Priority: P2)

The project evaluates each candidate format layer against repeatable criteria: extraction fidelity, write fidelity, style/layout control, deterministic saves, public-form validation, security posture, license fit, and tool-call usability. Only the best-scoring layer for each format is promoted to active use.

**Why this priority**: The user explicitly asked for deep reference research focused on open-source and private HWP/HWPX editor cases, plus a self-evaluating loop before final design decisions. The feature must retain that rigor as a product requirement, not a one-off research note.

**Independent Test**: Run the evaluation matrix for each supported format and verify that every promoted capability has a scorecard, evidence fixtures, failure cases, and a promotion or deferral decision.

**Acceptance Scenarios**:

1. **Given** multiple HWPX editing candidates, **When** the evaluation loop runs, **Then** UMMAYA selects the candidate profile with the strongest conformance score and records why lower-scoring candidates were rejected or deferred.
2. **Given** a format capability lacks deterministic round-trip evidence, **When** promotion is attempted, **Then** UMMAYA blocks it from active write use while still allowing read-only capability if proven safe.
3. **Given** a replacement engine or harness improves a format's score, **When** it passes the same evaluation matrix, **Then** the capability profile can be upgraded without changing the user-facing document workflow.

### Edge Cases

- A file extension does not match the detected real format.
- A document is password-protected, encrypted, corrupted, macro-enabled, or contains external links.
- A HWP binary document can be read but cannot be safely written in this epic.
- A form field label appears multiple times with different meanings.
- A table spans pages or sheets and a field crosses a visual boundary.
- A template contains locked explanatory text that the user asks the model to rewrite.
- A generated value is longer than the field's visible capacity.
- A formula-backed spreadsheet cell is selected as a fill target.
- A PDF field value saves into metadata but does not render visibly.
- A document contains Korean fonts unavailable on the local machine.
- A public-form validation source is semantic-only and lacks authoritative layout rules.
- A derivative file name conflicts with an existing artifact.

## Requirements *(mandatory)*

### Functional Requirements

#### Format Intake and Normalization

- **FR-001**: The system MUST accept document artifacts with extensions HWPX, HWP, DOCX, PDF, XLSX, and PPTX and MUST detect the real format independently of the file name.
- **FR-002**: The system MUST preserve the original artifact byte-for-byte and MUST perform any write operation only against a derivative copy with recorded lineage to the original hash.
- **FR-003**: The system MUST produce a normalized document representation that includes extracted text, structural hierarchy, tables, embedded media references, style cues, and source locators where the format exposes them.
- **FR-004**: The system MUST report a per-artifact capability profile before editing, including at minimum: readable, writable, fillable, style-controllable, renderable, conformance-verifiable, and unsupported-reason fields.
- **FR-005**: HWP binary artifacts MUST be supported only for safe read, extraction, render, or conversion evidence where available; direct HWP binary authoring MUST be blocked in this epic and represented as a deferred capability.
- **FR-006**: HWPX, DOCX, XLSX, PDF, and PPTX artifacts MUST each have explicit read, write, render, and validation capability boundaries; unsupported operations MUST return typed unsupported results.

#### Form Schema and Public-Form Rules

- **FR-007**: The system MUST derive a form schema from supported templates with fields for stable field ID, label, required/optional status, expected value type, layout anchor, evidence excerpt, and confidence.
- **FR-008**: The system MUST distinguish explicit fields from inferred fields and MUST expose confidence and evidence for every inferred field.
- **FR-009**: The system MUST preserve protected template content such as official labels, guidance text, table structure, numbering, signature/seal blocks, and required attachment lists unless the user explicitly requests a change that the validator allows.
- **FR-010**: The public-form validator MUST check required fields, page count, protected text, table geometry, margins or printable area, visible overflow, required labels, and signature/seal regions when the relevant baseline data exists.
- **FR-011**: The validator MUST classify findings as hard failure, warning, or informational, and every hard failure MUST include a document anchor and remediation hint.
- **FR-012**: The system MUST use the 행정안전부_정부 공문서 AI 학습데이터 조회 서비스 corpus for semantic, structural, table, image, summary, and rewrite evaluation only; it MUST NOT use that corpus as sole proof of official submission-form layout conformance.

#### Editing, Styling, and Saving

- **FR-013**: The system MUST support field filling for promoted HWPX, DOCX, XLSX, and fillable PDF capability profiles.
- **FR-014**: The system MUST support bounded style operations for promoted editable formats, including font family, font size, paragraph style, cell style, table geometry, and page or printable-region constraints where the format exposes them.
- **FR-015**: The system MUST reject global restyling or template rewriting that would remove required official structure unless the user explicitly requests it and validation confirms the derivative is no longer being marked as an official-form-ready artifact.
- **FR-016**: The system MUST re-read every saved derivative and compare expected field values, protected content, and visible layout evidence before marking the derivative ready for review.
- **FR-017**: The system MUST produce a structured diff between original and derivative artifacts, including changed field values, changed style regions, changed tables or cells, and saved file path.
- **FR-018**: The system MUST block "ready" status when a rendered derivative has critical overlap, missing required text, hidden filled values, broken tables, or validation hard failures.

#### Tool-Loop Integration

- **FR-019**: The system MUST expose model-callable document capabilities for inspect, extract, field-schema discovery, copy-for-edit, fill, style, render, validate, and save operations.
- **FR-020**: Every document capability MUST have a deterministic input/output contract with typed success, warning, unsupported, and failure results, and MUST return structured results that can be validated without relying on free-text parsing.
- **FR-021**: Any operation that writes, exports, overwrites, deletes, or marks a derivative as ready MUST require an explicit permission boundary that identifies the source artifact, target artifact, intended change class, and validation status.
- **FR-022**: The system MUST record audit evidence for every document operation, including source hash, derivative hash when present, capability profile, validation result, and correlation ID.
- **FR-023**: The system MUST fail closed when the model requests an operation outside the active capability profile.

#### Evaluation and Promotion

- **FR-024**: The system MUST maintain a 100-point scorecard for each format capability profile using these weights: extraction fidelity 20, write fidelity 20, style/layout control 15, deterministic round trip 15, public-form validation 15, security and privacy posture 10, and license/maintenance/tool-call usability 5.
- **FR-025**: A write capability MUST NOT be promoted unless it scores at least 85/100 and passes every hard gate: no original-file mutation, deterministic save or normalized-equivalent save, exact re-read equality for intended values, render evidence, structured result validation, and no critical security finding.
- **FR-026**: The system MUST retain rejected or deferred candidate profiles with reasons so subsequent plan or research work can compare upgrades against the same standard.
- **FR-027**: The system MUST run evaluation against representative fixtures for HWPX, HWP, DOCX, PDF, XLSX, and PPTX before declaring the feature complete; the fixture manifest MUST list source, redistribution status, expected fields, expected layout anchors, and negative cases for each fixture.

#### Security and Data Handling

- **FR-028**: The system MUST process document bytes locally unless a separately approved agency channel grants explicit permission and policy citation for transfer.
- **FR-029**: The system MUST block active content execution, macro execution, and external-link fetching during inspection, rendering, validation, and saving.
- **FR-030**: The system MUST redact or scope personal-data evidence in logs and reports so reviewer evidence remains useful without leaking unnecessary sensitive values.
- **FR-031**: The system MUST NOT call live data.go.kr, government, identity, payment, certificate, utility, or external citizen-infrastructure channels from CI tests.
- **FR-032**: The system MUST validate every input artifact with an allowlist extension check, detected container or signature check, declared MIME mismatch check, maximum raw size, maximum expanded package size, and maximum page/sheet/slide count before format-specific processing.
- **FR-033**: The system MUST treat user-provided filenames and paths as untrusted, generate safe derivative names, block overwrite/path traversal/hidden-file targets, and store derivatives outside any public serving root.
- **FR-034**: The HWPX conformance baseline MUST reference KS X 6101/OWPML for package structure, document structure, compatibility, metadata, and format-conformance evaluation; HWP binary remains read/extract/render/convert evidence only in this epic.
- **FR-035**: The DOCX, XLSX, and PPTX conformance baselines MUST reference the Office Open XML document, spreadsheet, presentation, and packaging semantics; validators MUST check core package integrity, required parts, relationships, and format-specific anchors before style or field edits are promoted.
- **FR-036**: The PDF conformance baseline MUST separate file validity, form-field data, visible field appearance, rendered page evidence, and signature/certification state; signed or certified PDF mutation MUST be blocked unless the tracked signature/certificate deferred item explicitly authorizes it.
- **FR-037**: The data.go.kr semantic evaluation metric MUST be a macro average of paragraph-block F1, table-cell F1, image-reference F1, and metadata exact-match score, with each component reported separately before the aggregate 0.85 threshold is applied.
- **FR-038**: A read-only capability MAY be promoted with a 75/100 or higher score only when all security hard gates pass and unsupported write/fill/style operations remain explicitly blocked.
- **FR-039**: A style-control capability MUST NOT be promoted unless the render/re-read loop proves that font, paragraph, table/cell, page, or printable-region changes are bounded to the requested anchors and do not alter protected template content.
- **FR-040**: Document capabilities MUST be registered as concrete UMMAYA tool entries under the existing tool-discovery and primitive flow; this feature MUST NOT introduce additional root primitive verbs beyond `find`, `locate`, `check`, and `send`.

### Key Entities *(include if feature involves data)*

- **DocumentArtifact**: Original or derivative file with path, extension, detected format, MIME or container signature, size, hash, source, and lineage.
- **FormatCapabilityProfile**: Per-format and per-engine capability declaration for read, write, fill, style, render, validate, and unsupported operations, with evidence score and promotion status.
- **DocumentIR**: Normalized representation of text blocks, sections, tables, cells, sheets, slides, pages, media references, style cues, and source locators.
- **FormSchema**: Extracted or inferred set of fields with stable IDs, labels, required status, value constraints, layout anchors, evidence, and confidence.
- **EditOperation**: User-approved document mutation such as fill, style, table/cell update, copy, render, validate, or save, with before/after anchors.
- **RenderSnapshot**: Reviewer-readable output generated from a document artifact, tied to artifact hash and page, sheet, or slide anchors.
- **ValidationReport**: Hard failures, warnings, informational findings, readiness status, conformance score, and remediation hints.
- **EvidenceRun**: End-to-end evaluation record connecting input artifact, tool sequence, capability profile, render snapshots, validation report, and final artifact status.
- **ConformanceBaseline**: Format-specific rule set that identifies the authoritative standard, required structural checks, layout or appearance anchors, unsupported operations, and validator tolerances.
- **PromotionGate**: Hard-gate and weighted-score decision record that determines whether a capability profile is read-only, fillable, writable, style-controllable, renderable, or deferred.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least 95% of fixture artifacts across HWPX, HWP, DOCX, PDF, XLSX, and PPTX complete inspection without crash, original mutation, or untyped failure.
- **SC-002**: 100% of promoted write-capability fixtures re-read the intended filled values exactly after save.
- **SC-003**: 100% of official-form-ready derivatives pass all hard validation checks before they can be marked ready for review.
- **SC-004**: At least 90% of supported public-form fixtures preserve protected labels, table geometry, signature/seal regions, and required layout anchors within the validator tolerance.
- **SC-005**: 100% of generated derivatives have source hash, derivative hash, structured diff, render evidence, validation report, and tool correlation ID.
- **SC-006**: The semantic evaluation subset using 행정안전부_정부 공문서 AI 학습데이터 조회 서비스 records achieves at least 0.85 measured agreement for paragraph structure, table extraction, and image-reference extraction against the prepared expected outputs.
- **SC-007**: Unsupported or unsafe operations return an unsupported or blocked result in 100% of negative fixtures, with no derivative save.
- **SC-008**: No CI evaluation test performs live calls to government, data.go.kr, identity, payment, certificate, utility, or external citizen-infrastructure endpoints.
- **SC-009**: In a full conversation smoke scenario, the LLM completes inspect -> schema -> copy -> fill -> render -> validate -> save through observable tool calls with no hidden document mutation.
- **SC-010**: 100% of promoted write and style-control capability profiles meet the score threshold and every hard gate defined in FR-024 through FR-039.
- **SC-011**: 100% of negative security fixtures for extension mismatch, container/signature mismatch, path traversal, unsafe filename, expanded package limit, macro/active content, and external-link fetching are blocked before write or ready status.
- **SC-012**: 100% of direct HWP binary write attempts return a typed blocked result in this epic, while safe HWP read/extract/render/convert fixtures still produce evidence where supported.

## Assumptions

- Users provide documents, templates, and answers they are authorized to process.
- This feature prepares and validates document artifacts; direct agency submission remains a separate adapter capability.
- The 행정안전부_정부 공문서 AI 학습데이터 조회 서비스 dataset is useful for semantic and structural public-document evaluation but is not an authoritative official-form layout oracle.
- Earlier document-write exclusions are superseded for this feature scope because Public AX requires document authoring as a first-class harness capability.
- HWP binary direct authoring is high risk and remains deferred for this epic; planning may research it, but implementation tasks for this epic must not promote direct HWP binary writing.
- Specific open-source libraries, conversion engines, and renderers will be selected in `/speckit-plan` after license, maintenance, determinism, and conformance evidence are compared.
- Public-form conformance fixtures may include locally stored templates or synthetic templates when redistribution rights for the official template are unclear.
- The existing UMMAYA permission, audit, and evidence surfaces remain the required outer harness for document operations.

## Scope Boundaries & Deferred Items *(mandatory)*

### Out of Scope (Permanent)

- Requiring Korean government agencies or Hancom to change official formats or publish new APIs - UMMAYA is a client-side caller and harness, not a standards authority.
- Bypassing official identity, certificate, payment, consent, or submission flows - document generation does not replace legally required channels.
- Guaranteeing legal acceptance of a submitted artifact - the harness can validate known technical conformance, but agencies remain the final authority.
- Using opaque external conversion services as the default path for user documents - document bytes must stay local unless an approved policy-cited channel explicitly authorizes transfer.

### Deferred to Future Work

| Item | Reason for Deferral | Target Epic/Phase | Tracking Issue |
|------|---------------------|-------------------|----------------|
| Deterministic direct HWP binary authoring | Legacy HWP write safety requires separate proof beyond read/convert capability | Document Harness HWP Write Hardening | #3131 |
| Agency-specific direct submission after document generation | Submission belongs to one-adapter-per-agency tool work and requires policy citation | Public AX Submit Adapters | #3132 |
| Digital signature, certificate embedding, and official seal automation | Requires identity/certificate permission pipeline and legal-policy review | Identity and Certificate Document Actions | #3133 |
| OCR and layout reconstruction for scanned static PDFs | High error risk; this epic blocks unsafe static-PDF fill instead | Scanned PDF OCR Form Recovery | #3134 |
| Interactive graphical document editor | The first scope is tool-loop document operations and reviewer evidence, not a full WYSIWYG editor | Document Review UI | #3135 |
| Template marketplace or automatic public-form crawler | Redistribution rights and freshness governance need a separate catalog feature | Public Form Template Catalog | #3136 |
| Advanced PPTX presentation design generation | PPTX is supported as a document artifact, but design-authoring decks are outside the public-form MVP | Presentation Authoring Harness | #3137 |
