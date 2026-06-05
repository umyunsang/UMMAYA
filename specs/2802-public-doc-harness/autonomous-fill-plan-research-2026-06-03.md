# Autonomous Fill Plan Research Note

Date: 2026-06-03

Scope: Public AX document samples copied from the user's Downloads folder into the
local evidence fixture area, plus the research decision for an
`autonomous_fill_plan` stage. The stage should let the model inspect the document,
infer what the form is asking for, plan safe fill operations, and then execute the
existing document primitive workflow without exposing internal inspect/fill/render
tools as separate normal user-facing steps.

## Local Anchors

- `docs/vision.md`: UMMAYA is a Claude Code harness migration into Korean public
  infrastructure, and document harness references are part of the official
  architecture source set.
- `specs/2802-public-doc-harness/research.md`: UMMAYA owns the harness, not a
  new parser/editor; binary HWP direct writing remains blocked unless an engine
  passes promotion gates.
- `specs/2802-public-doc-harness/document-primitive-deep-research-2026-06-02.md`:
  the model-facing unit is one `document` primitive, while inspect, copy, fill,
  render, validate, and save stay internal runtime stages.
- `tests/fixtures/documents/candidate_profiles.yaml`: HWPX has promoted bounded
  read/write smoke coverage; binary HWP engines are read-only or blocked unless
  license, fidelity, and mutation gates pass.
- `.references/claude-code-sourcemap/restored-src/src/tools/FileEditTool/`:
  Claude Code exposes one edit tool and renders one structured diff result; it
  does not ask the model to call read, patch, and render as separate public steps.

## Fixture Intake

The five user-supplied samples were copied into ignored local evidence storage:

`/Users/um-yunsang/UMMAYA/.evidence/document-fixtures/public-ax-samples/`

| Sample | Format | SHA-256 | Current runtime outcome |
|---|---|---|---|
| `2. [서식1~서식5] 2026년 경기도 공공데이터·AI 활용 창업경진대회 제출 서류.hwp` | HWP 5.x | `9252a7b5692bb44e2533326942921de060d81bc3151445e24153d35a7e2a3503` | Product runtime blocks direct HWP edit; `hwp5txt` comparative extraction returned 13,245 bytes and identified a multi-form contest submission bundle. |
| `2026년도 AX 아이디어 경진대회_데이터 활용_아이디어 기획 부문_개인정보 수집·이용 동의서.hwp` | HWP 5.x | `8ffe8877b57b5b4de11b9654b7bbb8afecea9803a15ef138a213ce2fd072ec36` | Product runtime blocks direct HWP edit; `hwp5txt` yielded only table markers plus parser errors, so this is not promotable through pyhwp text-only evidence. |
| `2026년도 AX 아이디어 경진대회_데이터 활용_아이디어 기획 부문_아이디어 기획서 양식.hwp` | HWP 5.x | `aee02b7477ae8abbafb4a2ce222c143fb43c4105876a850f80052e60f0696c3c` | Product runtime blocks direct HWP edit; `hwp5txt` yielded only table markers plus parser errors. |
| `2026년도 AX 아이디어 경진대회_데이터 활용_아이디어 기획 부문_참가서약서.hwp` | HWP 5.x | `58e23b06274ee3b2b341c521dbf5c73df078ec9d5e2db328023544d376d80cb9` | Product runtime blocks direct HWP edit; `hwp5txt` yielded only table markers plus parser errors. |
| `SW중심대학사업 현장미러형연계프로젝트 주간활동일지(ai학과_GovOn)_13.hwpx` | HWPX zip | `b6ac058e55144a8a680744e364b74c73bb54e11426e714297ded7bfe914fa35d` | Product runtime inspect succeeds with `hwpx-package-text`: 33 paragraphs, 33 fields, 2 tables, 1 warning. |

Evidence implication: the autonomous plan can be implemented and tested first on
the HWPX weekly activity document. HWP samples should be used as classification
and blocked/needs-input fixtures until an HWP engine passes promotion gates.

## 2026-Current External Sources

### Public-document writing rules

- Ministry of the Interior and Safety press material, 2026-03-24, "AI-friendly
  administrative document innovation": the attached Markdown states that
  AI-readable administrative documents should have clear subjects and predicates,
  simple sentence structures, no complex cell merging, simple tables, and the
  standard public-document numbering ladder `Ⅰ., 1., 가., 1), 가), (1), (가),
  ①, ㉮`. Source catalog entry: MOIS 2026 AI-friendly administrative document
  material. The live URL is retained only in the permitted source-catalog docs.
  Local evidence copy:
  `.evidence/document-fixtures/research-sources/mois-ai-friendly-document-2026.md`.
- National Institute of Korean Language, `쉬운 공문서 쓰기 길잡이`, registered
  2023-02-02 and revised 2023-07-17: the official guide is the writing-quality
  baseline for easy, accurate, public-facing Korean administrative language.
  Source catalog entry: National Institute of Korean Language public-document
  writing guide. The live URL is retained only in the permitted source-catalog
  docs.
- National Law Information Center, `행정업무의 운영 및 혁신에 관한 규정 시행규칙`:
  current rule page exposes public-document body, appendix, and form sections.
  Source catalog entry: National Law Information Center administrative-work
  regulation rule page. The live URL is retained only in the permitted
  source-catalog docs.
- National Law Information Center, public document form example, prior
  `행정 효율과 협업 촉진에 관한 규정 시행규칙 [별지 제1호서식] 기안문`: the form
  shows the official public-document frame fields such as recipient, title,
  sender seal, drafter/reviewer/approver, implementation number, address,
  homepage, phone, fax, email, and disclosure category. Source catalog entry:
  National Law Information Center public-document form download. The live URL is
  retained only in the permitted source-catalog docs.

### Document-understanding technology

- DocLLM, arXiv:2401.00908: layout-aware document understanding can use text plus
  bounding boxes without a heavy image encoder. This matches UMMAYA's goal for
  editable HWPX/HWP: preserve structured text/table anchors and attach geometry
  only when render evidence is available. Source: <https://arxiv.org/abs/2401.00908>.
- LayoutLMv3, arXiv:2204.08387: a mature multimodal baseline for form
  understanding, receipt understanding, document VQA, document classification,
  and layout analysis. This is a benchmark/evaluation reference, not the default
  runtime for structured HWPX. Source: <https://arxiv.org/abs/2204.08387>.
- Donut, arXiv:2111.15664: OCR-free visual document understanding is useful for
  scanned or image-only documents, but it is a poor first runtime for editable
  HWPX because it discards native XML/package structure. Source:
  <https://arxiv.org/abs/2111.15664>.

### HWP/HWPX open-source ecosystem

- `rhwp`: Rust + WebAssembly HWP/HWPX viewer/editor work, MIT, actively oriented
  to HWP/HWPX rendering and future editing. Good render/bridge candidate when
  UMMAYA needs native page evidence. Source:
  <https://github.com/edwardkim/rhwp/blob/main/README_EN.md>.
- `openhwp`: MIT Rust workspace with HWP read, HWPX read/write, IR, and editor
  document model crates. Good candidate to evaluate for future HWP/HWPX IR
  promotion, but it still needs fixture-level parity and save-safety gates before
  UMMAYA writes user HWP/HWPX through it. Source: <https://github.com/openhwp/openhwp>.
- `pyhwp`: AGPL HWP 5 parser/processor with text and ODT conversion experiments.
  It is useful only as comparative local evidence in this Apache-2.0 project; it
  must not become the product runtime without a license decision. Source:
  <https://github.com/mete0r/pyhwp>.

## Candidate Scorecard

Weights: intent inference 20, form-schema precision 20, public-document writing
conformance 15, safety/fail-closed behavior 15, existing harness fit 15,
implementation cost 10, HWP/HWPX extensibility 5.

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Regex-only fill inference from file name and user instruction | 42 | Reject | It can handle the weekly-report week/date example, but cannot infer legal consent, proposal, and multi-form bundle semantics safely. |
| LLM-only plan from extracted text | 64 | Reject as primary | Better intent coverage, but too much hallucination risk around signatures, consent, protected fixed text, and table anchors. |
| OCR/VLM-first document understanding | 71 | Reject as default | Good for scanned PDFs, weak for editable HWPX because it throws away native package/table/style anchors and adds heavy local model dependencies. |
| Convert every HWP/HWPX to DOCX/PDF first, then plan | 57 | Reject | Conversion may help evidence, but using it as the primary edit substrate risks layout drift and breaks direct format lineage. |
| Structured DocumentIR + deterministic slot planner + LLM content drafter + validators | 93 | Adopt | Keeps format anchors, makes uncertainty explicit, lets the LLM draft only bounded free-text content, and fits the single `document` primitive. |

## Selected Autonomous Fill Architecture

The selected stage is not a new model-facing tool. It is an internal stage inside
the existing `document` primitive:

```text
document(instruction, document)
  -> intake
  -> inspect/extract DocumentIR
  -> classify document type
  -> extract FormSchema
  -> autonomous_fill_plan
  -> user-confirmation gate when required
  -> copy_for_edit
  -> apply_fill/apply_style
  -> render/re-read/diff
  -> save or ready_for_review
```

### Core records

```text
DocumentIR
  paragraphs, tables, fields, styles, page_anchors, protected_ranges

DocumentIntent
  document_type, task_type, confidence, evidence_spans, blocked_reasons

FormSlot
  label, normalized_label, field_path, required, value_type, source_policy

AutonomousFillPlan
  document_intent, slots[], proposed_operations[], missing_inputs[],
  unsafe_operations[], writing_profile, validation_plan
```

### Fill value precedence

1. Explicit user-provided values in the latest request.
2. Values that can be inferred from stable document recurrence, such as the next
   weekly-report week after an existing week/date pair.
3. Project/session context that is already inside the conversation and can be
   cited to the operation.
4. Safe draftable free text for proposal sections, marked as draft.
5. `needs_input` for legal consent, pledge, signature, personal ID, address,
   phone, bank account, resident registration number, or any field whose value
   cannot be inferred with evidence.

## Per-Sample Plan

| Sample class | Autonomous classification target | Allowed autonomous action | Block/confirmation rule |
|---|---|---|---|
| SW weekly activity log HWPX | `weekly_activity_log` | Infer next or requested week/date, preserve table/form shape, fill activity summary only from supplied/session context, render diff immediately. | Ask if week/date cannot be inferred or if activity content is not in context. |
| Gyeonggi multi-form HWP bundle | `contest_submission_bundle` | Classify included forms and list required sections when HWP extraction is available. | Direct HWP edit remains blocked until HWP engine promotion. |
| AX idea planning HWP | `idea_proposal_form` | Draft proposal section content only after a promoted HWP read/convert path exposes slot anchors; use AI-friendly administrative writing profile. | Do not fabricate applicant identity, team, company, budget, or measurable claims without evidence. |
| Personal-information consent HWP | `privacy_consent_form` | Explain required fields and prepare a plan. | Never auto-check consent or auto-sign; require explicit user confirmation and preserve legal fixed text. |
| Participant pledge HWP | `legal_pledge_form` | Explain pledge fields and prepare a plan. | Never auto-sign or imply legal acceptance without explicit user confirmation. |

## Public-Document Writing Profile

The writing profile for draftable sections should be:

- clear subject and predicate;
- short, plain, public-facing Korean sentences;
- no decorative rhetoric;
- standard public-document numbering where section hierarchy exists;
- simple tables without complex merged cells when generating new tables;
- protected labels, notices, legal consent text, signatures, seals, and dates
  preserved unless the slot is explicitly user-editable;
- proposal/free-text sections written in concise administrative prose, not
  marketing prose;
- changed fields rendered through the existing document diff path immediately.

This profile deliberately differs from older terse `개조식` habits when they omit
subjects or predicates. The 2026 MOIS AI-friendly guidance makes machine-readable
clarity the higher priority.

## Evaluation Criteria

Minimum promotion gate for `autonomous_fill_plan`:

| Gate | Pass threshold | Evidence |
|---|---:|---|
| Document type classification | >= 0.90 on local fixture set | Golden labels for the five copied samples plus negative files. |
| Form slot extraction precision | >= 0.85 for HWPX fixtures | Slot label/path/value type snapshots. |
| Unsafe auto-fill suppression | 1.00 | Consent, pledge, signature, personal ID, phone, address, bank, and legal acceptance fields remain `needs_input` unless explicit user evidence exists. |
| Patch anchor correctness | 1.00 on accepted operations | Re-read diff maps every operation to the intended `field_path` or table cell. |
| Render/re-read parity | 1.00 for HWPX happy paths | `document` result contains diff and render evidence without a separate user request. |
| Public-writing conformance | >= 0.85 | Validator checks subject/predicate clarity, standard numbering, simple table policy, and protected text preservation. |
| HWP fail-closed behavior | 1.00 | HWP samples classify or explain, but do not mutate while the promoted engine is absent. |

## Next Implementation Slice

This research note should feed a RED-first implementation loop:

1. Add a sample manifest for the copied fixtures with hashes and expected
   `document_type` labels.
2. Add `AutonomousFillPlan`, `DocumentIntent`, and `FormSlot` models.
3. Add a planner that consumes `DocumentExtraction` and the user instruction.
4. Add HWPX weekly-log tests:
   - "read the document and write the next week automatically" infers week/date
     from current document content when safe;
   - explicit user values override recurrence;
   - missing activity content becomes `needs_input`, not fabricated prose.
5. Add HWP legal/consent tests:
   - classify the file when extraction evidence exists;
   - never auto-fill consent, pledge, signature, or identity fields.
6. Wire the planner into `document` before `copy_for_edit`, preserving the single
   model-facing primitive contract.
7. Run focused document tests, then real `bun run tui` with a natural Korean
   query that does not mention tool names.

## All-Format Broadening Addendum

Date: 2026-06-03

User correction: the document harness cannot remain an HWPX-only design. Public
AX needs a format-universe layer that can recognize and safely route every file
family commonly seen in Korean national-infrastructure document exchange, while
still being honest about which formats can be edited, filled, rendered, or only
explained.

### Current local gap

The current product code is narrower than the public-infrastructure target:

- `DocumentFormat` currently enumerates only `hwpx`, `hwp`, `docx`, `pdf`,
  `xlsx`, and `pptx`.
- `inspect_document_intake()` maps only those six extensions.
- `build_default_document_engine_registry()` promotes only
  `hwpx-package-text` and `python-docx`; XLSX, PPTX, PDF, HWP, ODF, data-file,
  image, and archive families are not registered as active default engines.
- `OOXML_CANDIDATE_ENGINES` records XLSX and PPTX candidates, and PDF/HWP
  boundary modules exist, but the runtime still cannot claim all-format
  autonomous fill.

Therefore the next plan must separate "known national-infrastructure format"
from "currently promoted editable document format." Without that split, adding
extensions either overclaims write support or hides unsupported behavior.

### National-infrastructure format evidence

Official and standard sources indicate the format universe is broader than the
initial six-format epic scope:

- The MOIS NPAS document-viewer page exposes viewer support for HWP, PDF, PPT,
  XLS, and DOC files, which is a direct signal of public-service document
  distribution formats. Source catalog entry: MOIS NPAS document viewer page.
- National Law Information Center save/download surfaces expose HWP, HWPX, PDF,
  DOC, XLS, HTML, and TXT outputs on current law/form pages. Source catalog
  entry: National Law Information Center law/form save surface.
- The Public Data Portal guide says data files should be provided as open
  formats such as CSV, JSON, and XML, and that HWP/XLS should be converted to
  CSV for open-data release. Source catalog entry: Public Data Portal data-use
  guide.
- The Public Data Portal standard dataset list shows live public datasets
  distributed as CSV, XML, and JSON. Source catalog entry: Public Data Portal
  standard dataset list.
- KS X 6101 defines OWPML/HWPX as an open XML-based word-processor document
  standard and explicitly discusses OWPML compatibility with HWP, OOXML, and
  ODF:
  <https://www.kssn.net/search/stddetail.do?itemNo=K001010149626>.
- ECMA-376 defines the OOXML representation and packaging used by DOCX, XLSX,
  and PPTX:
  <https://ecma-international.org/publications-and-standards/standards/ecma-376/>.
- ISO 32000-2:2020 is the current PDF 2.0 standard and was confirmed current in
  2026:
  <https://www.iso.org/cms/%20render/live/en/sites/isoorg/contents/data/standard/07/58/75839.html>.
- OASIS OpenDocument 1.4 is the current ODF standard family for ODT, ODS, and
  ODP:
  <https://docs.oasis-open.org/office/OpenDocument/part3-schema/OpenDocument-v1.4-os-part3-schema.html>.
- OWASP File Upload Cheat Sheet remains the security baseline for extension
  allowlists, content-type validation, decompression limits, parser risk, and
  active-content controls:
  <https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html>.

Secondary procurement evidence also shows public-sector document components
asking for HWPX/HWP, ODT, PDF/PDF-A, public-document XML, HTML, and UTF text.
Treat this as format-inventory evidence, not as a runtime dependency decision.

### Format universe for UMMAYA

The all-format target is a capability matrix, not universal write support.

| Family | Extensions | Initial UMMAYA action | Write stance |
|---|---|---|---|
| Korean word-processing | `hwpx`, `hwp`, `owpml` | HWPX inspect/fill/render through promoted engines; HWP inspect/convert evidence when engine passes. | HWPX bounded write allowed; binary HWP direct write blocked until promotion. |
| OOXML office | `docx`, `xlsx`, `pptx` | Inspect, field/slot extraction, style metadata, and per-format candidate engines. | Promote DOCX/XLSX/PPTX writes only after mutation + render + re-read gates. |
| Legacy MS Office binary | `doc`, `xls`, `ppt` | Detect, classify, and optionally convert/read through local oracle engines. | Direct binary write blocked; derivative output should be OOXML/PDF unless a safe engine is promoted. |
| PDF documents | `pdf`, `pdfa` marker on `.pdf` | Extract, render, identify AcroForm fields, classify static/scanned PDFs. | Fill only AcroForm with visible appearance verification; static/scanned/signature PDFs blocked. |
| ODF office | `odt`, `ods`, `odp` | Detect and inspect through ODF/LibreOffice candidate path. | Defer writes until ODF engine passes the same gates as OOXML. |
| Legal/public web exports | `html`, `htm`, `txt`, `rtf`, `md` | Read, normalize structure, and preserve text lineage. | Text/HTML transforms are allowed only as derivative exports, not as proof of official form conformance. |
| Open-data files | `csv`, `tsv`, `xml`, `json`, `jsonl`, `yaml`, `yml` | Treat as structured public-data artifacts: schema infer, validate, transform, summarize. | Write via structured serializers with schema and injection guards; no visual form claim. |
| Scanned/image documents | `png`, `jpg`, `jpeg`, `tif`, `tiff`, `bmp`, `webp` | OCR/VLM-assisted extraction only, with uncertainty. | No form writing; generate separate draft document or require editable template. |
| Archive/container attachments | `zip`, `7z`, `tar`, `gz` | Secure unpack, enumerate contained documents, route each child file. | Never write archive members in place; only create a new derivative archive after child validations pass. |

### Deep-research implementation direction

Candidate approaches were rescored with all-format coverage:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Keep HWPX-first and document unsupported formats later | 58 | Reject | It improves the current demo but fails the Public AX requirement because the model still cannot reason over common law, data, PDF, and office outputs. |
| Convert every file to PDF or DOCX first | 64 | Reject as primary | Conversion is useful as an oracle, but it loses native anchors, can drift layout, and cannot safely write back to source formats. |
| Adopt a document-AI parser as the universal runtime | 76 | Support only | Docling-style parsers are strong for extraction, but they are not deterministic mutation engines for public forms. |
| Use VLM/OCR-first for all documents | 69 | Reject as default | This helps scanned PDFs/images but discards native XML/package/form anchors for editable files. |
| `KnownFormat` + capability profile + format adapter + shared `DocumentIR` | 95 | Adopt | This preserves native anchors where available, fails closed where editing is unsafe, and keeps the user-facing primitive as one `document` operation. |

Recent research reinforces the selected direction. DocLLM and LayoutLMv3 support
layout-aware understanding; Donut and Mistral OCR-style processors are useful for
image-only/scanned inputs; Docling demonstrates local structured conversion for
AI pipelines; and BabelDOC 2026 shows that an intermediate representation is the
right way to preserve layout metadata while allowing semantic operations. For
UMMAYA, those are extraction and evaluation references. The mutation runtime must
still be native-format and gate-backed.

### Engine strategy by family

| Family | Reference packages / modules | UMMAYA role |
|---|---|---|
| HWPX | `hwpx-package-text`, `@rhwp/core`, `python-hwpx`, OpenHWP | Keep current HWPX as the promoted write smoke path; use RHWP render evidence; evaluate python-hwpx/OpenHWP for richer field/style gates. |
| HWP | OpenHWP, pyhwp, hwp.js, unhwp | Read/convert/render evidence only; AGPL candidates remain comparative, not runtime. |
| DOCX | `python-docx`, direct WordprocessingML oracle | Promote read first, then bounded table/paragraph/style writes with re-read and render evidence. |
| XLSX | `openpyxl` | Promote structured cell fills, styles, merged cells, formulas outside edited cells, print areas; formula evaluation is not claimed. |
| PPTX | `python-pptx` | Promote text placeholder, table, image, and slide metadata edits; animations, macros, and complex media blocked. |
| PDF | `pypdf`, PyMuPDF, Poppler/qpdf oracles | Promote AcroForm fill only; use PyMuPDF/Poppler for visible render verification; scanned/XFA/signature PDFs blocked. |
| ODF | `odfpy`, LibreOffice headless oracle | Add read/extract first; defer writes until ODT/ODS/ODP fixtures pass style/layout parity. |
| Data files | stdlib `csv`, `json`, XML parsers, schema validators | Treat as structured data, not visual forms; add schema inference, transform diff, and injection-safe serializers. |
| Images/scans | OCR/VLM candidates, PyMuPDF image path | Extraction-only; any write creates a separate editable derivative, never edits the original raster. |
| Archives | stdlib `zipfile`, external archive candidates only with ADR | Secure enumeration and child routing; no in-place archive mutation. |

### All-format implementation plan

1. Add a two-level format model:
   - `KnownDocumentFormat`: every recognized national-infrastructure extension.
   - `DocumentFormat`: currently promoted editable/inspectable runtime formats.
   This avoids schema overclaiming while letting TUI and LLM messages say "known
   but unsupported for write" instead of "unknown file."
2. Expand intake detection:
   - add extension + magic-signature detection for legacy Office, ODF, data
     files, text/HTML, images, and archives;
   - record `format_family`, `detected_known_format`, `container_children`,
     active-content findings, and decompressed-size evidence;
   - keep fail-closed behavior for encryption, macros, external links, path
     traversal, and parser-risk findings.
3. Introduce `FormatCapabilityProfile`:
   - `can_read`, `can_extract_slots`, `can_fill`, `can_style`, `can_render`,
     `can_validate_conformance`, `can_save_derivative`;
   - every unsupported operation must carry a typed blocked reason and a
     next-safe action.
4. Normalize all engines into shared `DocumentIR`:
   - text blocks, tables, fields, sheet cells, slide shapes, page widgets,
     data schemas, image OCR boxes, and source anchors all map to one IR shape;
   - `autonomous_fill_plan` consumes only this IR, never raw format internals.
5. Promote family engines in order:
   - P0: HWPX current path remains promoted.
   - P1: XLSX `openpyxl` cell-fill and PDF AcroForm `pypdf` fill, because both
     have clear field/cell anchors and focused tests already exist in the spec.
   - P2: DOCX `python-docx` write and PPTX `python-pptx` placeholder/shape edits.
   - P3: ODF read/extract and legacy DOC/XLS/PPT read-or-convert evidence.
   - P4: data-file schema transforms and scanned-image extraction-only mode.
6. Extend fixture corpus:
   - keep the five copied public AX samples;
   - add representative benign/hostile fixtures for DOC, XLS, PPT, ODT, ODS,
     ODP, CSV, TSV, XML, JSON, HTML, TXT, PNG/JPG/TIFF, and ZIP;
   - each fixture declares provenance, redistribution status, expected
     capability, expected blocked reason, and layout/schema anchors.
7. Extend autonomous planning:
   - planning becomes format-family aware;
   - legal consent, pledge, signature, ID, address, phone, bank, and explicit
     consent fields remain `needs_input` across all formats;
   - if a document is only readable, the plan may draft a separate derivative
     but must not mutate the source.
8. Extend evidence and TUI:
   - every document edit still renders a user-visible structured diff;
   - data files render schema/value diffs;
   - image/scanned inputs render extraction confidence and blocked-write status;
   - no internal inspect/fill/render logs are exposed as separate user tasks.

### All-format evaluation gates

Minimum promotion thresholds:

| Gate | Threshold |
|---|---:|
| Known-format detection precision | 1.00 on fixture corpus |
| Unsupported-operation fail-closed rate | 1.00 |
| Extraction/slot precision for editable document families | >= 0.90 |
| Patch target anchor correctness | 1.00 |
| Protected text / legal field preservation | 1.00 |
| Render or re-read parity for write-enabled engines | 1.00 |
| Style/layout preservation for form templates | >= 0.90 |
| Data serializer round trip | 1.00 for schema-preserving transforms |
| Security findings for macro/archive/external link cases | 1.00 |

The final Public AX claim should be: UMMAYA recognizes all known
national-infrastructure document families, routes each through a capability
profile, edits only promoted safe formats, and fails closed with useful next
actions for the rest. It must not claim universal authoring until each family
passes the same promotion loop.

## Decision

Adopt `KnownDocumentFormat + FormatCapabilityProfile + Structured DocumentIR +
deterministic slot planner + LLM bounded drafting + validator` as the
`autonomous_fill_plan` direction.

Do not promote binary HWP direct editing in this slice. The four HWP samples are
valuable fixtures for classification, missing-engine blocked behavior, and
future HWP engine promotion. HWPX remains the first edit-capable fixture, but it
is now one promoted adapter inside the broader all-format document harness, not
the scope boundary.
