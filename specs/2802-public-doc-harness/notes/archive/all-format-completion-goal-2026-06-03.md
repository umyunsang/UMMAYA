# Public AX Document Harness All-Format Completion Goal

Date: 2026-06-03

Status: active goal plan. This is not an implementation-complete claim.

## Verdict

UMMAYA does not yet fully satisfy "real-use write, render, and save for every
Korean national-infrastructure file extension."

The current repository has a strong single-primitive foundation and promoted
write paths for a bounded set of office/form formats, but several national
infrastructure formats are correctly known-only, read-only, metadata-only, or
blocked. The correct completion target is therefore not "pretend every extension
is editable." The target is:

1. every observed national-infrastructure extension is classified before runtime
   parsing;
2. every classified format is routed to exactly one adapter family;
3. promoted document formats can inspect, plan, mutate a derivative, render,
   re-read, diff, and save;
4. non-promoted formats produce an explicit read-only, metadata-only, or
   blocked decision with next safe actions;
5. no fallback path can turn an unsupported write into a successful document
   edit.

## Local Code Audit

| Layer | Current location | Current state |
|---|---|---|
| Model taxonomy | `src/ummaya/tools/documents/models.py` | `DocumentFormat` is the promoted runtime set: HWPX, HWP, DOCX, PDF, XLSX, PPTX, ODT, ODS, ODP, HTML, HTM, TXT, RTF, MD, and structured public-data text formats. `KnownDocumentFormat` covers the broader public-document, media, GIS, archive, and code attachment universe. |
| Intake | `src/ummaya/tools/documents/intake.py` | Known-but-unpromoted formats fail closed before engine parsing and preserve `known_format`, `format_family`, and `next_safe_actions`. |
| Adapter registry | `src/ummaya/tools/documents/adapter_registry.py` | One registry maps each known format to one format adapter and each promoted runtime format to one promoted adapter. |
| HWPX/OWPML | `src/ummaya/tools/documents/formats/hwpx.py` | Promoted package text edit plus RHWP render bridge for `.hwpx` and `.owpml`. Requires continued layout-diff and style fidelity gates. |
| HWP | `src/ummaya/tools/documents/formats/hwp.py`, `docs/adr/ADR-011-hwp-conversion-bridge.md` | Promoted for read-only inspection through `unhwp-read-only`; blocked for direct mutation. `hwpxjs` can be discovered as a local HWP-to-HWPX conversion candidate, but HWP authoring remains incomplete because converted public AX HWPX derivatives must still pass render/re-read/save gates. |
| OOXML | `src/ummaya/tools/documents/formats/ooxml.py` | DOCX/XLSX/PPTX promoted with bounded structure-aware edit and SVG evidence render. Needs broader fixtures for public-form style fidelity. |
| PDF | `src/ummaya/tools/documents/formats/pdf.py` | AcroForm-only mutation and pypdfium2 visible render. Static, scanned, XFA, encrypted, or signed PDFs remain blocked. |
| Passive formats | `src/ummaya/tools/documents/formats/passive.py` | Image, archive, legacy Office, code, GIS, and media adapters are known-only/read-only/metadata-only. ODF moved to `formats/odf.py`; text/web exports moved to `formats/text_web.py`; structured public-data text formats moved to `formats/data_file.py`. |
| Completion audit | `src/ummaya/tools/documents/format_completion_audit.py` | Every `KnownDocumentFormat` is now emitted as complete, read-only, probe-blocked, or passive-context-only. |
| Primitive workflow | `src/ummaya/tools/documents/orchestrator.py`, `src/ummaya/tools/documents/registry.py` | One `document` primitive can run inspect, autonomous plan, copy-for-edit, mutation, render, validation, and save for promoted formats. |
| TUI evidence | `tui/src/components/primitive/DocumentToolResultCard.tsx` and related tests | Document result rendering is separate from backend capability. Any query-loop/TUI change still requires live `bun run tui` proof. |

## Deep Research Inputs

Primary standards and public-infrastructure evidence:

- KSSN KS X 6101 OWPML/HWPX lists OWPML as an open word-processor markup
  standard for text document content, binary HWP compatibility description,
  compatibility evaluation, and metadata extensibility.
- ECMA-376 defines OOXML vocabularies, document representation, packaging, and
  consumer/producer requirements for DOCX/XLSX/PPTX.
- OASIS OpenDocument 1.4 defines ODF packages and XML document structure for
  office documents.
- National Archives NAK 37:2025 identifies preservation formats including PDF,
  DOCX, PDF/A, ODT, and EPUB, with HWPX as an acceptable format.
- Public Data Portal search results show real Korean public-data attachments in
  TTL/RDF/LOD, SHP/GeoJSON, GPX, and FASTA.

Current open-source and package evidence:

- RHWP: Rust/WASM HWP/HWPX parser, renderer, editor, SVG/canvas direction, and
  a large test corpus. Suitable as the preferred HWPX render bridge and a future
  HWP investigation reference, but not yet a direct HWP write authority in
  UMMAYA.
- hwpxjs: MIT TypeScript/Node local CLI candidate for HWP 5.0 parsing and
  HWP-to-HWPX conversion. It converted copied public AX HWP fixtures to valid
  HWPX packages in local alpha testing, but one converted public AX derivative
  still failed the RHWP render gate, so it is not a complete HWP authoring
  promotion.
- OpenHWP: Rust crates for HWP read, HWPX read/write, IR, and document model.
  Suitable as the next HWP bridge candidate because its shape matches
  HWP-read/HWPX-write rather than unsafe HWP in-place mutation.
- python-docx: bounded DOCX creation/update, tables, paragraphs, styles, and
  save.
- openpyxl: bounded XLSX workbook/cell/style/merged-cell operations and save.
- python-pptx: bounded PPTX presentation/slide/shape/table operations and save.
- pypdf + pypdfium2: AcroForm update plus local visible page render. Static PDF
  writing remains outside the safe mutation boundary.
- Docling and 2025 document-AI papers support a unified rich
  representation for extraction and reasoning, but not native mutation authority
  for public-form originals.

Current 2026-06-03 source re-check:

- `data.go.kr` still exposes public-data file-type filters such as CSV, JSON,
  XML, TTL, SHP, RDF, and GPX, so UMMAYA must classify data/geospatial formats
  as first-class intake formats even when they are not editable public-form
  documents.
- National Archives NAK 37:2025 still identifies HWPX, PDF, PDF/A, DOCX, ODT,
  and EPUB as preservation-format relevant targets, which supports the split
  between promoted office/form adapters and read-only/passive preservation
  formats.
- KS X 6101 OWPML/HWPX, ECMA-376 OOXML, and OASIS OpenDocument 1.4 remain the
  standards-backed anchors for HWPX, DOCX/XLSX/PPTX, and ODF package handling.
- OASIS OpenDocument v1.4 Part 2/Part 3, `odfdo` v3.22.8, and LibreOffice 26.2
  command-line PDF export docs were re-checked for ODF. UMMAYA now uses odfdo
  for bounded ODT/ODS/ODP write/render/save and keeps `soffice`/`libreoffice`
  as a deferred layout-oracle bridge.
- Microsoft Office binary-format archive, Microsoft Open XML support docs,
  LibreOffice `--convert-to`/filter docs, and Apache POI HWPF notes were
  re-checked for legacy Office. The current safe direction is not direct
  `.doc/.xls/.ppt` mutation but explicit OOXML derivatives through a local
  LibreOffice bridge after ADR and fixture gates.
- `ssabro/hwpxjs` and `@ssabrojs/hwpxjs@0.4.0` were re-checked for HWP. The
  package exposes `hwpxjs convert:hwp <source.hwp> <output.hwpx>` and passed
  local conversion probes on copied public AX HWP fixtures. The renderer gate
  still blocks HWP authoring because RHWP panics on at least one converted AX
  proposal derivative.
- Attachment-context tooling was re-checked against 2026-current open-source
  anchors. Pillow's image-format support covers PNG, JPEG, TIFF, WebP, BMP, and
  GIF as raster inspection targets; Tesseract remains the preferred local OCR
  candidate but is not bundled, so OCR text must be reported as unavailable
  unless the runtime exists. GDAL/OGR is the preferred GIS feature extraction
  candidate for shapefile-family metadata, and ffprobe is the preferred media
  metadata bridge for WAV/MP3/MP4. Until those bridges are explicitly registered
  and verified, the promoted safe path is a Markdown attachment-context
  derivative that preserves the original source bytes and records only extracted
  metadata, warnings, and source hashes.

## Completion Scorecard

Weights: public-infrastructure coverage 20, native fidelity 20, write safety 20,
render/re-read evidence 15, CC-style harness parity 10, license/local execution
10, implementation cost 5.

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Claim every extension is editable | 21 | Reject | Unsafe and false for HWP, static PDF, scans, media, GIS, and archives. |
| Convert everything to DOCX/PDF first | 58 | Reject as primary | Loses native anchors, source lineage, and format-specific policy. |
| HWPX-only public-document harness | 63 | Reject as final | Useful slice, but ignores real government OOXML/PDF/data/GIS attachments. |
| Universal extraction front door plus no native writers | 74 | Partial | Good for autonomous understanding, insufficient for form submission artifacts. |
| One `document` primitive plus format adapters, promotion gates, and passive known-only coverage | 96 | Adopt | Honest capability boundary, highest debuggability, closest to CC tool-loop shape. |

## Format Capability Matrix

| Family | Extensions | Current decision | Completion requirement |
|---|---|---|---|
| HWPX/OWPML | `hwpx`, `owpml` | Promoted write/render/save through the same OWPML/HWPX package-text engine boundary | Expand fixture corpus and style/layout diff gates. |
| HWP binary | `hwp` | Read-only inspection promoted, direct write blocked; HWP-to-HWPX conversion candidate available through local `hwpxjs` when installed | Complete converted-derivative render/re-read/save gates and autonomous fill planning before claiming HWP authoring. |
| HWPML/XML | `hml` | Data-file read-only | Keep read-only unless a real HWPML writer and compatibility gate is added. |
| OOXML | `docx`, `xlsx`, `pptx` | Promoted bounded write/render/save | Add public-form fixtures and style/layout evidence gates per format. |
| Legacy Office | `doc`, `xls`, `ppt` | Metadata-only, conversion-required | Do not mutate directly. Add local conversion bridge only with explicit ADR and no CI live dependency. |
| PDF | `pdf`, `pdfa` | AcroForm promoted; static/scanned/XFA/signed blocked | Improve Korean visible text rendering and form appearance checks. Do not edit signed/static PDFs. |
| ODF | `odt`, `ods`, `odp` | Promoted bounded write/render/save through odfdo structural engines | Add richer Korean fixtures and a local LibreOffice layout oracle before claiming original-page fidelity. |
| Text/web/publication | `html`, `htm`, `txt`, `rtf`, `md`, `epub` | HTML/HTM/TXT/RTF/MD promoted bounded write/render/save; EPUB archive enumeration remains passive | Add richer Korean public-notice fixtures and keep EPUB as a container/publication asset unless a safe child-routing writer is added. |
| Structured public data | `csv`, `tsv`, `xml`, `rdf`, `ttl`, `lod`, `json`, `jsonl`, `yaml`, `yml`, `geojson`, `gpx`, `kml`, `fasta`, `sgml`, `dtd`, `hml`, `etc` | Promoted bounded body-level write/render/save with structural validation where applicable | Use as context and data-source artifacts; mutation is limited to full-body replacement with JSON/YAML/XML/CSV validation where possible. |
| Image scans | `png`, `jpg`, `jpeg`, `gif`, `tif`, `tiff`, `bmp`, `webp` | Attachment-context Markdown derivative write/render/save promoted; original raster mutation blocked | Add OCR/VLM extraction later as richer evidence only. Never claim in-place raster document editing. |
| Geospatial/model assets | `shp`, `shx`, `dbf`, `prj`, `stl` | Attachment-context Markdown derivative write/render/save promoted; original GIS/model mutation blocked | Add GDAL/OGR feature extraction later as richer evidence only. Sidecar lineage must stay explicit. |
| Media assets | `wav`, `mp3`, `mp4` | Attachment-context Markdown derivative write/render/save promoted; original media mutation blocked | Add ffprobe/transcription later as richer evidence only. Media originals are not edited as documents. |
| Code attachments | `py` | Read-only source context | Not routed through document writer. |
| Archives | `zip`, `7z`, `tar`, `gz`, `epub` | Read-only enumeration | Secure child routing only; no in-place archive mutation. |

## Goal Checklist

### Checkpoint A: all-format classification foundation

- [x] Expand `KnownDocumentFormat` for currently observed Korean public
  infrastructure extensions.
- [x] Map each known format to a stable `DocumentFormatFamily`.
- [x] Extend `DocumentIntake` to classify new extensions before runtime parse.
- [x] Add next-safe-action text per new non-promoted family.
- [x] Add focused tests for known-but-unpromoted classification.

### Checkpoint B: passive adapter routing

- [x] Add read-only data inspection for TTL/LOD/GeoJSON/GPX/FASTA/HWPML-like
  text/XML/data attachments.
- [x] Add code read-only adapter for source attachments.
- [x] Add legacy Office metadata-only adapter.
- [x] Add geospatial/model metadata-only adapter.
- [x] Add media metadata-only adapter.
- [x] Register each known-only adapter in the default registry.
- [x] Verify that passive formats can inspect but cannot fill/mutate originals.

### Checkpoint C: promoted writer evidence

- [x] Re-run promoted HWPX/DOCX/XLSX/PPTX/PDF fixture matrix for inspect, fill,
  render, save, re-read, and structured diff.
- [x] Add at least one real local public-form fixture per promoted format or an
  owned synthetic equivalent when redistribution is blocked.
- [x] Record Evidence Fabric output for the promoted matrix.

Evidence:

- `tests/tools/documents/test_promoted_format_workflow_matrix.py` exercises the
  single `document(save)` primitive for HWPX, DOCX, XLSX, PPTX, and PDF. Each
  case asserts structured diff, render artifact MIME/path, local save SHA-256,
  completed save workflow step, and re-read extraction from the saved file.
- `uv run pytest tests/tools/documents/test_promoted_format_workflow_matrix.py -q`
  passed on 2026-06-03 after fixing OOXML render metadata to advertise SVG
  evidence instead of the renderer default `text/plain` MIME type.
- `uv run pytest tests/tools/documents -q` passed with 300 document harness tests.
  The Evidence Fabric runner still emits join-only document records; raw document
  bytes and changed field values remain outside `.evidence/run.json` by design.

### Checkpoint D: PDF Korean render hardening

- [x] Add Korean-font AcroForm fixture with visible filled fields.
- [x] Assert pypdfium2 render contains visible changed glyph regions.
- [x] Keep static/scanned/XFA/signed PDF mutation fail-closed.

Evidence:

- `tests/tools/documents/test_pdf_adapter.py::test_pdf_acroform_korean_fill_changes_visible_field_region`
  fills the AcroForm field with `홍길동`, renders before/after with
  pypdfium2, computes the changed image bounding box, verifies it intersects the
  field rectangle, and requires more than 100 changed pixels inside the field
  region.
- `tests/tools/documents/test_pdf_adapter.py::test_pdf_acroform_korean_font_fixture_embeds_appearance_without_viewer_regeneration`
  creates a Korean-font AcroForm fixture, fills `홍길동`, verifies an embedded
  appearance stream exists, and verifies `/NeedAppearances=True` is not required
  when the source PDF already exposes a suitable Unicode font resource.
- `tests/tools/documents/test_pdf_adapter.py::test_pdf_mutation_blocks_non_acroform_cases_with_typed_reasons`
  keeps static, scanned, XFA, signed, and encrypted PDFs fail-closed.
- Bundling a Korean font remains deferred. The current promotion uses an embedded
  font already present in the source PDF; otherwise it falls back to
  `/NeedAppearances` regeneration for non-ASCII fields.

### Checkpoint E: HWP promotion bridge

- [x] Keep direct HWP source mutation blocked.
- [x] Promote local HWP read-only extraction through `unhwp`.
- [x] Prototype richer HWP table/field IR using `unhwp` Markdown output.
- [ ] Promote richer HWP table/field IR as mutation targets only after an
  HWP-to-HWPX derivative bridge passes.
- [x] Add opt-in local HWP-to-HWPX conversion bridge registration with explicit
  executable and args configuration.
- [x] Route the top-level `document` primitive through a promoted HWP-to-HWPX
  derivative when such a conversion engine is injected, instead of forcing users
  to call lower-level inspect/copy/fill/render tools manually.
- [ ] Promote HWP-to-HWPX derivative only if license, binary size, local-only
  execution, and render/re-read gates pass.

Evidence:

- `tests/tools/documents/test_builtin_hwp_adapter.py::test_default_runtime_inspects_public_ax_hwp_with_unhwp_read_engine`
  proves the default `DocumentToolRuntime.inspect` path can read a copied local
  public AX HWP fixture through `unhwp-read-only` and extract visible Korean
  content including `제출 서류 목록`.
- `tests/tools/documents/test_builtin_hwp_adapter.py::test_default_runtime_hwp_fill_still_blocks_without_conversion_engine`
  proves the same default runtime blocks direct `document(fill)` on HWP unless a
  promoted HWP-to-HWPX conversion engine exists.
- `tests/tools/documents/test_builtin_hwp_adapter.py::test_unhwp_read_engine_promotes_markdown_tables_and_field_candidates`
  proves a copied local public AX HWP proposal template now exposes Markdown
  tables as `TableBlock`/`TableCell` and field candidates such as `팀명 -> UMMAYA`
  and `아이디어명 -> 공공데이터와 AX 기술을 활용한 UMMAYA 국가 인프라 에이전트`.
- `tests/tools/documents/test_builtin_hwp_adapter.py::test_copied_hwp_public_ax_fixtures_classify_but_document_fill_is_blocked`
  proves real local HWP public-form samples classify but `document(fill)` blocks
  before working-copy or derivative artifacts are created.

### Checkpoint F: ODF promotion readiness probe

- [x] Promote ODT, ODS, and ODP into `DocumentFormat` after bounded
  write/render/save gates pass.
- [x] Route `.odt`, `.ods`, and `.odp` through `OdfdoDocumentAdapter`, not the
  passive `OdfDocumentAdapter`, in the default registry.
- [x] Add odfdo-backed ODT paragraph, ODS sheet-cell, and ODP text-frame engines.
- [x] Add ODF package signature detection based on `mimetype`,
  `META-INF/manifest.xml`, and `content.xml`.
- [x] Add Evidence Fabric `document_odf_probe_records` so ODF cannot be
  accidentally counted as full layout-fidelity complete.
- [x] Promote ODF write/render/save after owned ODT/ODS/ODP fixtures pass
  save/re-read/structural SVG render/structured diff gates.
- [ ] Add a local-only LibreOffice layout-oracle bridge before claiming
  original-page visual fidelity.

Evidence:

- `tests/tools/documents/test_promoted_format_workflow_matrix.py` now covers ODT,
  ODS, and ODP through the single `document(save)` primitive with render
  artifacts, saved derivative files, re-read extraction, and structured diff.
- `tests/tools/documents/test_intake_security.py::test_promoted_runtime_formats_emit_known_format_and_family_metadata`
  accepts ODF packages through mimetype-based zip signature detection.
- `tests/tools/documents/test_odf_promotion_probe.py::test_probe_reports_odf_as_bounded_promoted_without_layout_oracle`
  proves ODF reports `promoted_bounded`, `odfdo_package_registered`, and
  `libreoffice_layout_oracle_deferred`.
- `tests/tools/documents/test_odf_promotion_probe.py::test_probe_detects_libreoffice_cli_as_deferred_layout_oracle`
  proves a local `soffice` candidate is visible but still tracked as a deferred
  layout-oracle bridge.
- `tests/evidence/test_document_harness_evidence.py::test_evidence_cli_payload_includes_document_harness_records`
  now requires `document_odf_probe_records` for `odt`, `ods`, and `odp`.

### Checkpoint G: legacy Office derivative readiness and bridge

- [x] Add `.doc`, `.xls`, and `.ppt` to `DocumentFormat` as source formats
  that may enter the single `document` primitive.
- [x] Keep `.doc`, `.xls`, and `.ppt` out of
  `PROMOTED_RUNTIME_DOCUMENT_FORMATS`; they are not directly mutable runtime
  formats.
- [x] Keep legacy Office originals routed through
  `LegacyOfficeDocumentAdapter` metadata-only inspection.
- [x] Add a deterministic LibreOffice conversion readiness probe that reports
  target OOXML formats and recommended conversion args.
- [x] Add a local-only LibreOffice/soffice conversion bridge that registers
  `.doc -> .docx`, `.xls -> .xlsx`, and `.ppt -> .pptx` when a real local
  executable is available.
- [x] Route top-level `document(fill/save, legacy Office)` through immutable
  source artifact lineage, editable OOXML working derivative, promoted OOXML
  fill/render/save, and explicit local export.
- [x] Add Evidence Fabric `document_legacy_office_probe_records` so legacy
  Office cannot be accidentally counted as complete.
- [x] Add ADR and local-only dependency gate for a LibreOffice conversion
  bridge.
- [ ] Mark derivative write/render/save complete in the all-format audit only
  after real `.doc -> .docx`,
  `.xls -> .xlsx`, and `.ppt -> .pptx` fixtures pass lineage, save/re-read,
  visible render, and structured diff gates.

Evidence:

- `tests/tools/documents/test_legacy_office_promotion_probe.py::test_probe_reports_legacy_office_as_conversion_required_without_libreoffice`
  proves a clean local environment reports all legacy Office formats as blocked
  with `legacy_office_runtime_not_promoted`,
  `direct_legacy_office_write_blocked`, and `libreoffice_cli_not_found`.
- `tests/tools/documents/test_legacy_office_promotion_probe.py::test_probe_detects_libreoffice_cli_for_default_derivative_bridge`
  proves a fake local LibreOffice executable becomes `candidate_available` and
  is reported as a default derivative-bridge candidate rather than a direct
  legacy binary writer.
- `tests/tools/documents/test_conversion_registry.py::test_default_conversion_registry_registers_discovered_libreoffice_legacy_bridge`
  proves default conversion registry discovery wires the LibreOffice bridge
  when `libreoffice` or `soffice` is present.
- `tests/tools/documents/test_legacy_office_derivative_bridge.py::test_document_primitive_fills_legacy_doc_via_docx_derivative_bridge`
  proves a natural top-level `document(fill/save, .doc)` operation preserves
  source bytes, creates a DOCX working derivative, applies the patch through the
  promoted OOXML engine, and writes the user-visible DOCX export.
- `tests/evidence/test_document_harness_evidence.py::test_evidence_cli_payload_includes_document_harness_records`
  now requires `document_legacy_office_probe_records` for `doc`, `xls`, and
  `ppt`.

### Checkpoint G2: Text/Web document promotion

- [x] Promote `html`, `htm`, `txt`, `rtf`, and `md` into `DocumentFormat`.
- [x] Add UTF-8/HTML/RTF intake detection before runtime mutation.
- [x] Add `TextWebDocumentEngine` and `TextWebDocumentAdapter`.
- [x] Support `/text/body` replacement with structural SVG render, derivative
  save, re-read extraction, and structured diff.
- [x] Keep EPUB as archive/container enumeration rather than native mutation.

Evidence:

- `tests/tools/documents/test_promoted_format_workflow_matrix.py::test_text_web_document_primitive_save_renders_rereads_and_diffs`
  proves TXT, MD, HTML, HTM, and RTF use the single `document(save)` primitive
  for mutation, render artifact creation, save, re-read, and diff.
- `tests/tools/documents/test_intake_security.py::test_promoted_runtime_formats_emit_known_format_and_family_metadata`
  proves the promoted text/web formats are accepted by intake and keep their
  `text_web_export` family classification.
- `tests/tools/documents/test_passive_format_adapters.py::test_default_registry_exposes_known_only_passive_family_adapters`
  proves the default registry routes text/web formats to
  `text-web-document-adapter`, while direct passive adapter tests remain
  available for read-only extraction behavior.

### Checkpoint G3: Structured public-data text promotion

- [x] Promote `csv`, `tsv`, `xml`, `rdf`, `ttl`, `lod`, `json`, `jsonl`,
  `yaml`, `yml`, `geojson`, `gpx`, `kml`, `fasta`, `sgml`, `dtd`, `hml`, and
  `etc` into `DocumentFormat`.
- [x] Add content-aware intake checks for JSON, JSONL, YAML, XML-family files,
  and UTF-8 text data files.
- [x] Add `DataFileDocumentEngine` and `DataFileDocumentAdapter`.
- [x] Support `/data/body` full-body replacement with structural SVG render,
  derivative save, re-read extraction, and structured diff.
- [x] Validate JSON/YAML/XML/CSV-style replacement bodies before saving.

Evidence:

- `tests/tools/documents/test_promoted_format_workflow_matrix.py::test_data_document_primitive_save_renders_rereads_and_diffs`
  proves the promoted public-data text formats use the single `document(save)`
  primitive for mutation, render artifact creation, save, re-read, and diff.
- `tests/tools/documents/test_intake_security.py::test_promoted_runtime_formats_emit_known_format_and_family_metadata`
  proves promoted data formats are accepted by intake and retain `data_file`
  family classification.
- `tests/tools/documents/test_passive_format_adapters.py::test_default_registry_exposes_known_only_passive_family_adapters`
  proves the default registry routes data formats to `data-file-document-adapter`.

### Checkpoint G4: OWPML package alias promotion

- [x] Promote `owpml` into `DocumentFormat`.
- [x] Route `.owpml` through the same OWPML/HWPX package-text adapter family as
  `.hwpx`, while preserving `detected_format=owpml` and `known_format=owpml`.
- [x] Add `.owpml` package intake aliasing for HWPX package markers without
  weakening extension/signature mismatch checks for other formats.
- [x] Support `document(save)` for OWPML with fill, render artifact creation,
  local save, re-read extraction, and structured diff.
- [x] Update all-format completion audit and Evidence Fabric completion matrix.

Evidence:

- `tests/tools/documents/test_promoted_format_workflow_matrix.py::test_owpml_document_primitive_save_renders_rereads_and_diffs`
  proves OWPML uses the single `document(save)` primitive through fill, render,
  save, re-read, and diff gates.
- `tests/tools/documents/test_intake_security.py::test_promoted_runtime_formats_emit_known_format_and_family_metadata`
  proves `.owpml` package fixtures are accepted as `owpml` rather than being
  mislabeled as `hwpx`.
- `tests/tools/documents/test_format_completion_audit.py::test_audit_reports_all_known_formats_and_does_not_claim_complete_coverage`
  proves OWPML is now included in `complete_formats`, while the whole goal
  remains incomplete because PPT-to-PPTX derivative promotion and PDF/A
  conformance-preserving output remain blocked.

### Checkpoint G5: Attachment-context derivative authoring

- [x] Keep image, GIS/model, and media originals out of direct document
  mutation.
- [x] Convert extraction-only or metadata-only attachment inspections into a
  generated Markdown document surface when the top-level `document` primitive
  receives a write/save intent.
- [x] Store the generated Markdown through the existing artifact store and
  route it through working-copy, render, and save stages instead of adding a
  fallback success path.
- [x] Record source filename, source SHA-256, known format, byte size,
  mutation policy, extracted image/paragraph references, warnings, and explicit
  runtime boundaries such as unavailable OCR/transcription/GDAL extraction.
- [x] Preserve original attachment bytes and assert the saved output is the
  Markdown derivative, not an edited raster/GIS/media original.
- [x] Update all-format completion audit with
  `attachment_derivative_write_render_save_promoted` and
  `capability_scope=attachment_context`.

Evidence:

- `tests/tools/documents/test_passive_format_adapters.py::test_document_primitive_saves_image_attachment_as_markdown_derivative`
  proves `.png` attachment input can be written to a Markdown derivative,
  rendered as SVG evidence, saved to a local `.md` path, and leave the source
  image bytes unchanged.
- `tests/tools/documents/test_passive_format_adapters.py::test_document_primitive_saves_non_document_attachment_context_families`
  proves representative `.prj` GIS and `.mp3` media attachments use the same
  derivative write/render/save path without mutating originals.
- `tests/tools/documents/test_format_completion_audit.py::test_audit_classifies_promoted_read_only_probe_and_passive_families`
  proves `png`, `shp`, and `mp3` are no longer hidden as generic
  `probe_blocked`; they are complete only inside the `attachment_context`
  scope.

### Checkpoint H: all-format completion audit

- [x] Add a machine-readable audit over every `KnownDocumentFormat`.
- [x] Mark HWPX, DOCX, XLSX, PPTX, bounded AcroForm PDF, ODT, ODS, ODP, HTML,
  HTM, TXT, RTF, MD, and structured public-data text formats as current
  `write_render_save_promoted` formats.
- [x] Mark HWP/DOC/XLS derivative bridges as
  `derivative_write_render_save_promoted` only when a verified conversion
  bridge exists.
- [x] Mark PPT and PDF/A as `probe_blocked`.
- [x] Mark image, media, and GIS/model attachments as
  `attachment_derivative_write_render_save_promoted`, not original-document
  write promotion.
- [x] Mark public-data, text/web exports, code, and archives according to their
  promoted derivative/document scope.
- [x] Emit the audit in Evidence Fabric as
  `document_format_completion_audit`.

Evidence:

- `tests/tools/documents/test_format_completion_audit.py::test_audit_reports_all_known_formats_and_does_not_claim_complete_coverage`
  proves the audit covers every known format and keeps
  `all_formats_complete=False`.
- `tests/tools/documents/test_format_completion_audit.py::test_audit_classifies_promoted_read_only_probe_and_passive_families`
  proves representative formats are classified into the correct completion
  states.
- `tests/evidence/test_document_harness_evidence.py::test_evidence_cli_payload_includes_document_harness_records`
  now requires `document_format_completion_audit` in `.evidence/run.json`.
- `tests/tools/documents/test_builtin_hwp_adapter.py::test_hwp_copy_for_edit_uses_local_cli_bridge_and_rereads_hwpx_derivative`
  proves the separate derivative bridge contract with a pinned local CLI and
  HWPX re-read, without mutating the source HWP artifact.
- `tests/tools/documents/test_conversion_registry.py` proves conversion registry
  fail-closed behavior, absolute executable pinning, HWP source immutability,
  valid HWPX output validation, and source-mutation rejection.
- `tests/tools/documents/test_conversion_registry.py::test_default_conversion_registry_registers_explicit_local_hwp_bridge`
  and
  `tests/tools/documents/test_builtin_hwp_adapter.py::test_default_runtime_uses_explicit_env_hwp_conversion_bridge`
  prove a locally configured converter can be registered by
  `UMMAYA_HWP_TO_HWPX_CONVERTER` plus explicit args JSON and used by the default
  runtime without mutating the HWP source.
- `tests/tools/documents/test_builtin_hwp_adapter.py::test_document_primitive_fills_converted_hwp_derivative_through_single_operation`
  proves the single model-facing `document` primitive can use an injected
  promoted HWP-to-HWPX conversion engine, plan against the converted HWPX
  derivative, mutate `12주차 -> 13주차`, render evidence, reread the derivative,
  and keep the original HWP bytes unchanged.
- `tests/tools/documents/test_hwp_conversion_probe.py` proves HwpForge CLI
  discovery is diagnostic-only: finding `hwpforge` on PATH produces recommended
  ADR-compatible env config, but does not auto-register a converter. Missing
  local CLI support is reported as `hwpforge_cli_not_found` instead of being
  hidden by a fallback.
- `tests/evidence/test_document_harness_evidence.py::test_evidence_cli_payload_includes_document_harness_records`
  proves Evidence Fabric emits `document_bridge_probe_records` with the current
  HWP bridge candidate state.
- `@ssabrojs/hwpxjs@0.4.0` is now recorded as an installable local conversion
  candidate. The default conversion registry can register `hwpxjs` from PATH
  and the probe records it as `hwpxjs_cli_found_for_default_registration`.
- Real public AX alpha testing on the AX idea proposal HWP fixture showed:
  conversion and structured patch/diff succeeded, but RHWP rendering of the
  converted derivative failed with a native border-rendering panic. The document
  primitive now returns `blocked(validation_failed)`, emits no render records,
  and skips save instead of crashing or claiming success.
- This is not a direct HWP write promotion. The HWP table/field IR is read-only
  extraction evidence, and HWP-to-HWPX derivative authoring remains incomplete
  until converted public AX derivatives render, re-read, validate, and save.

Loop verification:

- `uv run pytest tests/tools/documents/test_candidate_evaluation.py tests/tools/documents/test_dependency_gate.py tests/tools/documents/test_conversion_registry.py tests/tools/documents/test_builtin_hwp_adapter.py -q`
  passed with 27 focused HWP/candidate/conversion tests.
- `uv run pytest tests/agents/test_no_new_deps.py tests/permissions/test_zero_new_dependencies.py tests/ipc/test_no_new_runtime_deps.py -q`
  passed with 5 dependency-boundary tests.
- `uv run pytest tests/tools/documents -q` passed for the document harness suite.
- `uv run pytest tests/evidence tests/ci -q` passed for Evidence Fabric/CI
  gates.
- `uv run python -m ummaya.evidence --source-ref local --out .evidence/run.json`
  produced run id `ev-21f5f069-00b4-4af5-919d-0765f549eb09` with 5 promoted
  document evidence records, 11 lifecycle records, 12 beta cases, and 9 negative
  cases. HWP remains represented as read-only/blocked evidence, not a writer
  evidence record.
- Follow-up HWP rich read IR verification on 2026-06-03 produced run id
  `ev-91d2ecec-19a6-4380-ae2c-f062e73ede8a` with the same document Evidence
  Fabric join counts and HWP table/field extraction covered by focused tests.
- Follow-up explicit local HWP conversion bridge wiring verification produced
  run id `ev-5b389205-1ab0-4301-b0a7-12cf113f6b36` with 5 promoted writer
  evidence records, 11 lifecycle records, 12 beta cases, and 9 negative cases.
- PDF Korean embedded appearance verification produced run id
  `ev-76d1a06d-19bf-44a1-b8d5-48e5bc63ed78` with the same Evidence Fabric join
  counts and a focused Korean-font AcroForm appearance test.
- Single-primitive HWP derivative authoring verification produced run id
  `ev-078f806a-530c-43cc-a024-c2135bc95504` for the current Evidence Fabric
  pass. The default evidence matrix still records HWP as read-only/blocked
  because no real converter is bundled by default; the converter-injected
  top-level primitive path is covered by focused HWP tests.
- Current all-format focused re-verification produced run id
  `ev-f008310d-64db-4860-bed8-271d3f5ca383` with 5 promoted document evidence
  records, 11 lifecycle records, 12 beta cases, and 9 negative cases. The UX
  gate remains skipped in the dataset runner by design and is covered separately
  by `.evidence/document-diff/*` until a real model-backed TUI run is available.
- HwpForge CLI bridge probe verification produced run id
  `ev-55186f02-a814-4e83-a6ef-a1f9bda768b8`. The payload now includes
  `document_bridge_probe_records[0]` for
  `hwpforge-cli-convert-hwp5`; this local environment reports
  `status=missing` and `hwpforge_cli_not_found`, with recommended explicit env
  args for `hwpforge --json convert-hwp5 {source} --output {output}` once a
  pinned binary exists.
- hwpxjs bridge loop verification on 2026-06-03 registered the discovered
  `hwpxjs` CLI candidate, converted real copied public AX HWP fixtures to HWPX,
  and proved renderer exceptions are now fail-closed as typed blocked results.
  The same alpha also proves HWP remains incomplete because the converted AX
  proposal derivative fails RHWP render and the autonomous fill planner still
  needs safe target inference for `문서내용을 파악하고 알아서 작성해` prompts.
- Evidence Fabric refresh produced run id
  `ev-58ac5dac-d2ea-4329-a13f-b4b52425e05c`. The payload reports
  `all_formats_complete=False`, `complete_count=32`, `incomplete_count=27`, and
  `document_bridge_probe_records[0].candidate_id=hwpxjs-cli-convert-hwp`.

### Checkpoint F: TUI/CC parity proof

- [x] Capture a reviewer-readable Evidence Fabric UX artifact for the single
  model-facing `document` primitive result surface.
- [ ] Fresh `bun run tui` session with ordinary Korean user phrasing.
- [ ] Confirm assistant prelude, document tool use, visible changed content,
  and final assistant synthesis appear in order.
- [ ] Capture the same parity evidence from a real model-backed fresh TUI
  session with correlation or frame hash.

Evidence:

- `tui/scripts/dump-document-diff-frames.tsx` now records
  `single-primitive-document-fill`, a top-level `tool_id=document` scenario that
  renders the automatic compact diff for `12주차 -> 13주차` without requiring
  separate `document_inspect`, `document_apply_fill`, or `document_render`
  user-visible tool calls.
- `.evidence/document-diff/manifest.json` records frame hash
  `838d91c192eebe5c2269f075a127de74fdbafa5c758fd3ec5c6a901dae508cef` for
  `single-primitive-document-fill.txt`.
- `.evidence/document-diff/frames.md` shows the single-primitive compact frame
  as changed content only, with no `Document OK`, no `document_render`, no
  `viewer.html`, and no card-box glyphs.
- `bun test tests/unit/documentDiffEvidenceScript.test.ts
  tests/primitive/dispatcher.test.tsx
  tests/tools/_shared/documentToolResultRender.test.ts` passed with 28 TUI
  document-render boundary tests.
- A fresh model-backed `bun run tui` session could not be completed in this
  environment because both `UMMAYA_FRIENDLI_TOKEN` and `FRIENDLI_TOKEN` are
  unset. This keeps Checkpoint F open.

## Current Loop Result

This loop completed Checkpoints A, B, C, the bounded ODF portion of Checkpoint F,
Checkpoint G2, and Checkpoint G3 for missing public-infrastructure extension
taxonomy, passive known-only routing, promoted writer write/render/save/re-read
evidence, ODT/ODS/ODP odfdo-backed mutation, HTML/HTM/TXT/RTF/MD text-web
mutation, structured public-data text mutation, and Checkpoint G5
attachment-context derivative authoring for image/GIS/media attachments. It
also hardened part of
Checkpoint D with a Korean AcroForm visible-render pixel gate, advanced
Checkpoint E by promoting read-only HWP inspection through `unhwp`, adding an
explicit local conversion bridge contract, and wiring the top-level `document`
primitive to edit converted HWPX derivatives when a promoted converter is
injected, and partially advanced the TUI parity checkpoint by adding
reviewer-readable single-primitive TUI diff evidence. It did not complete the
whole all-format goal because PPT-to-PPTX derivative promotion and PDF/A
conformance-preserving output remain blocked, and fresh model-backed TUI/CC
parity proof remains open.

## 2026-06-03 HWP Derivative Promotion Update

The HWP slice advanced after the RHWP panic root-cause loop:

- HWP direct binary mutation remains blocked.
- HWP source preservation plus HWPX derivative write/render/save is now promoted
  for the local `hwpxjs` bridge.
- Native RHWP SVG remains the renderer for RHWP-compatible HWPX packages.
- HWPX packages produced by `hwpxjs convert:hwp` are routed to
  `hwpxjs-html-render` only when the pre-render geometry compatibility check
  finds missing RHWP table geometry. This avoids treating a failed RHWP render
  as success.
- Real copied public AX HWP fixtures: 4/4 passed inspect, convert to HWPX
  working derivative, render as reviewer-readable HTML, save to a non-hidden
  local path, and source SHA preservation.
- Autonomous prompt handling was corrected so LLM-generated field patches are
  not discarded merely because the instruction says `알아서` or
  `문서 내용을 파악`.

Latest audit:

- `all_formats_complete=False`
- `complete_count=57`
- `incomplete_count=2`
- Remaining incomplete formats: `ppt`, `pdfa`

Current interpretation:

- Major modern authoring formats are promoted: HWPX/OWPML, HWP via HWPX
  derivative, DOCX, XLSX, PPTX, fillable PDF, ODF, text/web, and structured
  public-data text formats.
- PDF/A is now recognized as PDF runtime lineage (`known_format=pdfa`,
  `detected_format=pdf`) and is inspected/rendered through the PDF adapter, but
  PDF/A-conformant post-write output remains blocked until a local veraPDF gate
  validates the saved derivative.
- Legacy Office is split: DOC and XLS have verified OOXML derivative
  write/render/save paths in the current local bridge matrix, while PPT remains
  blocked until a PPT-to-PPTX bridge passes fixture gates.
- Archive/container families now expose explicit child-routing probes and are
  counted only as child-derivative document workflows, not in-place archive
  mutation.
- Media/geospatial/raster families are now counted only as attachment-context
  Markdown derivative workflows. They are not editable public forms without OCR,
  transcription, geometry/data adapters, or domain-specific authoring engines.

## 2026-06-03 PDF/A Conformance Gate Update

Deep research migration note:

- Local anchors: `src/ummaya/tools/documents/formats/pdf.py`,
  `src/ummaya/tools/documents/intake.py`,
  `src/ummaya/tools/documents/format_completion_audit.py`, and
  `src/ummaya/evidence/runner.py`.
- CC restored-source status: no CC public PDF/A document adapter analog exists.
  The CC-aligned invariant is fail-closed visible tool evidence and no fallback
  success.
- 2026-current sources:
  - Public Data Portal extension taxonomy lists government data extensions
    including PDF, HWP/HWPX, DOC/DOCX, XLS/XLSX, PPT/PPTX, ODT, CSV, XML, JSON,
    RDF, TTL, LOD, SHP, STL, PY, image, media, and archive-like formats:
    official Public Data Portal home page (`data.go.kr`; URL omitted here to
    keep CI fixtures offline-only).
  - veraPDF home states it is an open source PDF/A validator covering all PDF/A
    parts and conformance levels, with OPF/PDF Association stewardship:
    https://verapdf.org/home/
  - veraPDF CLI validation docs expose built-in PDF/A profiles, automatic
    flavour selection (`--flavour 0` or no flavour), XML reports, and
    `isCompliant` validation output:
    https://docs.verapdf.org/cli/validation/
  - pypdf PDF/A docs explicitly state that pypdf does not currently guarantee
    PDF/A output; pypdf form docs remain valid for AcroForm field filling only:
    https://pypdf.readthedocs.io/en/stable/user/pdfa-compliance.html
    https://pypdf.readthedocs.io/en/stable/user/forms.html

Scorecard:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Treat `.pdfa` as passive unsupported | 54 | Reject | Hides real PDF runtime inspect/render capability and gives poor user diagnostics. |
| Treat `.pdfa` exactly like `.pdf` and mark complete | 38 | Reject | pypdf does not guarantee PDF/A, so this would be a false conformance claim. |
| Accept `.pdfa` as PDF runtime lineage but keep PDF/A completion probe-blocked until veraPDF post-write validation exists | 97 | Adopt | Preserves read/render/fillable-PDF behavior while keeping public archival conformance fail-closed. |

Implemented in this slice:

- `inspect_document_intake()` now accepts `.pdfa` files with `%PDF-` signature
  as `detected_format=pdf`, `known_format=pdfa`, `format_family=pdf`, and
  `mime_type=application/pdf`.
- Added `src/ummaya/tools/documents/pdfa_promotion_probe.py`, which detects a
  local `verapdf` CLI candidate but does not register PDF/A output completion.
- Evidence Fabric now emits `document_pdfa_probe_records`.
- Format completion audit now classifies `pdfa` as `probe_blocked` with
  `pdfa_conformance_probe_required`, `pdfa_conformance_write_not_promoted`, and
  `pypdf_pdfa_conformance_not_claimed`.

Verification:

- RED:
  `uv run pytest tests/tools/documents/test_pdfa_promotion_probe.py
  tests/tools/documents/test_intake_security.py::test_pdfa_extension_is_accepted_as_pdf_runtime_with_pdfa_lineage
  tests/tools/documents/test_format_completion_audit.py::test_audit_classifies_promoted_read_only_probe_and_passive_families -q`
  failed because the probe module did not exist and `.pdfa` was still treated
  as unpromoted.
- GREEN:
  the same focused test set now passes.
- GREEN:
  `uv run pytest tests/evidence/test_document_harness_evidence.py::test_document_records_attach_to_evidence_runner_output
  tests/tools/documents/test_pdfa_promotion_probe.py
  tests/tools/documents/test_intake_security.py::test_pdfa_extension_is_accepted_as_pdf_runtime_with_pdfa_lineage
  tests/tools/documents/test_format_completion_audit.py -q`
  -> pass.

Remaining PDF/A gate:

- A real local `verapdf` CLI and post-write conformance parser are required
  before `pdfa` can move from `probe_blocked` to a promoted completion state.

## 2026-06-03 Archive/Container Probe Update

Deep research migration note:

- Local anchors: `src/ummaya/tools/documents/formats/passive.py`,
  `src/ummaya/tools/documents/archive_container_probe.py`,
  `src/ummaya/tools/documents/format_completion_audit.py`, and
  `src/ummaya/evidence/runner.py`.
- CC restored-source status: no CC public archive-document writer analog exists.
  The applicable CC boundary is typed tool capability, visible result evidence,
  and fail-closed unsupported writes.
- 2026-current sources:
  - Python 3.12 `zipfile`, `tarfile`, and `gzip` remain sufficient for local
    ZIP/TAR/GZ enumeration, with tar extraction requiring explicit filtering:
    https://docs.python.org/3.12/library/zipfile.html
    https://docs.python.org/3.12/library/tarfile.html
    https://docs.python.org/3.12/library/gzip.html
  - OWASP File Upload guidance remains the archive security baseline for file
    type allowlists, size limits, decompression limits, path traversal, and
    safe storage boundaries:
    https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html
  - `py7zr` is the narrow Python candidate for 7z child enumeration, but it is
    not installed or registered in this environment:
    https://py7zr.readthedocs.io/

Scorecard:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Mark archives complete because listing works | 42 | Reject | Listing is not write/render/save and would hide missing repack validation. |
| Add direct in-place archive mutation | 31 | Reject | Unsafe for public forms; child documents must validate before a new derivative archive is emitted. |
| Add explicit archive probe and keep completion blocked until child-routing plus repack gates exist | 96 | Adopt | Gives users real diagnostics without overclaiming container authoring. |

Implemented in this slice:

- Added `src/ummaya/tools/documents/archive_container_probe.py`.
- Evidence Fabric now emits `document_archive_probe_records`.
- Completion audit now classifies `epub`, `zip`, `7z`, `tar`, and `gz` as
  `probe_blocked` instead of generic passive context.

Verification:

- RED:
  `uv run pytest tests/tools/documents/test_archive_container_probe.py
  tests/tools/documents/test_format_completion_audit.py::test_audit_classifies_promoted_read_only_probe_and_passive_families -q`
  failed because the archive probe did not exist and audit still reported
  `passive_context_only`.
- GREEN:
  `uv run pytest tests/tools/documents/test_archive_container_probe.py
  tests/tools/documents/test_format_completion_audit.py::test_audit_classifies_promoted_read_only_probe_and_passive_families
  tests/evidence/test_document_harness_evidence.py::test_document_records_attach_to_evidence_runner_output -q`
  -> pass.

Remaining archive gate:

- Add a child-document extraction/repack writer that never mutates archive
  members in place, validates every edited child through its own promoted
  adapter, then emits a new derivative archive with lineage and traversal/zip
  bomb checks.

## 2026-06-03 Passive Attachment Probe Update

Deep research migration note:

- Local anchors: `src/ummaya/tools/documents/formats/passive.py`,
  `src/ummaya/tools/documents/passive_capability_probe.py`,
  `src/ummaya/tools/documents/format_completion_audit.py`, and
  `src/ummaya/evidence/runner.py`.
- CC restored-source status: no CC public image/GIS/media/code document writer
  analog exists. The relevant CC invariant is one visible primitive result with
  typed capability boundaries.
- 2026-current sources:
  - Tesseract OCR is the local CLI candidate for scanned/image text extraction:
    https://tesseract-ocr.github.io/
  - FFmpeg/ffprobe is the local candidate for media metadata extraction, but
    not a speech-to-text writer:
    https://ffmpeg.org/ffprobe.html
  - GDAL/OGR, pyshp, and trimesh are candidate families for GIS/3D metadata and
    geometry extraction, but none is currently installed in this runtime:
    https://gdal.org/programs/ogrinfo.html
    https://github.com/GeospatialPython/pyshp
    https://trimesh.org/

Scorecard:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Mark image/media/GIS/code as public-form writable | 24 | Reject | These are attachments or source/data artifacts, not directly editable public forms. |
| Keep all as generic passive context | 55 | Reject | Too vague; hides whether OCR, media, or geospatial extraction runtime exists. |
| Add passive capability probes and keep document writing blocked | 95 | Adopt | Gives the LLM/user accurate next action without false write/render/save claims. |

Implemented in this slice:

- Added `src/ummaya/tools/documents/passive_capability_probe.py`.
- Evidence Fabric now emits `document_passive_probe_records` for 17 formats:
  `py`, 8 raster/image formats, 5 geospatial/3D formats, and 3 media formats.
- Completion audit now classifies these formats as `probe_blocked` rather than
  generic `passive_context_only`.
- In this local environment, `tesseract`, `ffmpeg`, and `ffprobe` are present,
  so image OCR and media metadata appear as candidates in the live probe. GIS
  runtimes remain missing.

Verification:

- RED:
  `uv run pytest tests/tools/documents/test_passive_capability_probe.py
  tests/tools/documents/test_format_completion_audit.py::test_audit_classifies_promoted_read_only_probe_and_passive_families -q`
  failed because the passive probe did not exist and audit still reported
  `passive_context_only`.
- GREEN:
  `uv run pytest tests/tools/documents/test_passive_capability_probe.py
  tests/tools/documents/test_format_completion_audit.py::test_audit_classifies_promoted_read_only_probe_and_passive_families
  tests/evidence/test_document_harness_evidence.py::test_document_records_attach_to_evidence_runner_output -q`
  -> pass.

Current audit interpretation after this checkpoint:

- Completion states after the passive-probe checkpoint were
  `write_render_save_promoted=32`, `derivative_write_render_save_promoted=1`,
  `probe_blocked=26`.
- There are no longer any generic `passive_context_only` records; every
  incomplete format now has a concrete missing gate.

## 2026-06-03 Legacy Office Bridge Status Update

Current audit command:

```bash
uv run python - <<'PY'
from collections import Counter
from ummaya.tools.documents.format_completion_audit import audit_document_format_completion
report = audit_document_format_completion()
print(report.all_formats_complete)
print(Counter(record.completion_state for record in report.records))
print(list(report.incomplete_formats))
PY
```

Result after the LibreOffice derivative bridge implementation:

- `all_formats_complete=False`
- `write_render_save_promoted=32`
- `derivative_write_render_save_promoted=1`
- `probe_blocked=26`
- incomplete formats:
  `doc`, `xls`, `ppt`, `pdfa`, `epub`, `py`, `png`, `jpg`, `jpeg`, `gif`,
  `tif`, `tiff`, `bmp`, `webp`, `shp`, `shx`, `dbf`, `prj`, `stl`, `wav`,
  `mp3`, `mp4`, `zip`, `7z`, `tar`, `gz`

Interpretation:

- Legacy Office now has a source-format to OOXML derivative bridge in code and
  TDD coverage.
- The all-format audit correctly stays incomplete because the current local
  runtime still lacks real LibreOffice fixture evidence for `.doc`, `.xls`, and
  `.ppt`, and several attachment/container/conformance families are still
  probe-blocked.

## 2026-06-03 Archive Container Promotion Update

Implemented checkpoint:

- Added promoted archive source formats: `epub`, `zip`, `tar`, and `gz`.
- Added `ArchiveContainerDocumentEngine` for safe child-payload replacement.
- Added archive intake detection for generic ZIP, EPUB mimetype ZIP, TAR, and
  GZIP.
- Registered default archive engines for `epub`, `zip`, `tar`, and `gz`; `7z`
  remains probe-blocked until a local `py7zr`/7z runtime and repack gate is
  accepted.
- Proved single `document(save)` workflow for all four promoted container
  formats: source archive preservation, child payload replacement, structural
  SVG render, local export save, re-read, and structured diff.

Current audit after this checkpoint:

- `all_formats_complete=False`
- `write_render_save_promoted=36`
- `derivative_write_render_save_promoted=1`
- `probe_blocked=22`
- incomplete formats:
  `doc`, `xls`, `ppt`, `pdfa`, `py`, `png`, `jpg`, `jpeg`, `gif`, `tif`,
  `tiff`, `bmp`, `webp`, `shp`, `shx`, `dbf`, `prj`, `stl`, `wav`, `mp3`,
  `mp4`, `7z`

## 2026-06-03 7z Archive Promotion Update

Deep research migration note:

- Local anchors: `src/ummaya/tools/documents/formats/archive.py`,
  `src/ummaya/tools/documents/intake.py`, `src/ummaya/tools/documents/models.py`,
  `src/ummaya/tools/documents/engines.py`,
  `src/ummaya/tools/documents/adapter_registry.py`, and
  `src/ummaya/tools/documents/format_completion_audit.py`.
- CC restored-source status: no CC archive public-document writer analog exists.
  The adopted CC invariant is still one visible `document` primitive, no hidden
  fallback, deterministic validation before write, and source artifact
  immutability.
- 2026-current sources:
  - libarchive 3.8.7 is the current stable release family and includes
    command-line tools such as `bsdtar`.
  - libarchive upstream lists 7-Zip archives among supported read formats and
    documents streaming read/write architecture.
  - `bsdtar(1)` documents that this implementation can extract and create
    7-zip archives and can convert archive formats through `-c/-x/-f` plus
    `--format`.
  - OWASP file upload guidance keeps archive traversal, parser exploitation,
    expansion limits, and least-privilege filesystem handling in scope.
- OSS/package candidates:
  - `py7zr`: rejected for now because it would add a new LGPL runtime
    dependency and several transitive compression dependencies.
  - local `bsdtar/libarchive`: adopted because macOS already provides it in the
    current runtime, it is a narrow CLI bridge, and the existing archive child
    derivative contract can be reused without changing the model-facing tool.
- Selected approach: extend `ArchiveContainerDocumentEngine` to `DocumentFormat`
  value `seven_z = "7z"` and use local `bsdtar` only at the archive-engine
  boundary. Missing `bsdtar` fails closed as `unsupported_operation`.
- Rejected approaches:
  - direct 7z in-place mutation;
  - adding `py7zr` before an ADR/dependency gate;
  - treating 7z as a generic passive attachment after a local write gate passed.
- Migration boundary: original `.7z` bytes are never mutated. The engine lists
  members, validates safe relative names, extracts into a temporary directory,
  replaces the requested child payload, repacks a new `.7z` derivative, renders
  structural SVG evidence, re-reads the saved export, and emits structured diff.
- Tests/evidence:
  - `tests/tools/documents/test_archive_container_workflow.py` now covers
    `document(save)` for 7z with source preservation, child replacement,
    structural render, local save, re-read, and diff.
  - `tests/tools/documents/test_archive_container_probe.py` verifies both
    available and missing `bsdtar` probe states.
  - Focused gate passed:
    `uv run pytest tests/tools/documents/test_archive_container_probe.py
    tests/tools/documents/test_archive_container_workflow.py
    tests/tools/documents/test_intake_security.py
    tests/tools/documents/test_format_completion_audit.py
    tests/tools/documents/test_models.py
    tests/tools/documents/test_passive_format_adapters.py
    tests/evidence/test_document_harness_evidence.py -q`.

Current audit after this checkpoint:

- `all_formats_complete=False`
- `write_render_save_promoted=37`
- `derivative_write_render_save_promoted=1`
- `probe_blocked=21`
- incomplete formats:
  `doc`, `xls`, `ppt`, `pdfa`, `py`, `png`, `jpg`, `jpeg`, `gif`, `tif`,
  `tiff`, `bmp`, `webp`, `shp`, `shx`, `dbf`, `prj`, `stl`, `wav`, `mp3`,
  `mp4`

Image/OCR checkpoint verdict:

- Pillow 12.2.0 is already available transitively and official docs confirm
  current read/write coverage for the common raster formats UMMAYA classifies.
- Tesseract is installed locally, but `tesseract --list-langs` currently exposes
  only `eng`, `osd`, and `snum`; Korean `kor` traineddata is absent.
- Therefore raster scan formats remain `probe_blocked` for "accurate Korean
  public-document reading." UMMAYA should not promote image scans as fully
  readable/writable public documents until Korean OCR or a local VLM/OCR bridge
  has reproducible fixture gates. Bounded visual annotation derivatives may be a
  future feature, but it is not enough for the user's stated "LLM reads the
  document accurately" requirement.

## 2026-06-03 Python Source Attachment Promotion Update

Deep research migration note:

- Local anchors: `src/ummaya/tools/documents/models.py`,
  `src/ummaya/tools/documents/intake.py`,
  `src/ummaya/tools/documents/formats/code_file.py`,
  `src/ummaya/tools/documents/engines.py`,
  `src/ummaya/tools/documents/adapter_registry.py`,
  `src/ummaya/tools/documents/diff.py`, and
  `src/ummaya/tools/documents/format_completion_audit.py`.
- CC restored-source status: CC has source-code edit tooling, but no public
  document-format adapter boundary for code attachments. The adopted invariant
  is the CC-style visible edit result plus deterministic structured diff through
  the single `document` primitive.
- 2026-current sources:
  - Python 3.14.5 `ast` docs define `ast.parse()` as the standard helper for
    producing Python syntax trees from source without executing the module.
  - Python 3.14.5 `tokenize` docs explicitly warn that tokenization helpers are
    only designed for syntactically valid Python, so the promotion gate validates
    with `ast.parse()` before line-addressed handling.
  - OWASP File Upload guidance keeps extension allowlisting, content-type and
    signature validation, filename safety, content validation, storage location,
    filesystem permissions, and upload limits in scope.
- Candidate scorecard:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Keep `.py` passive context-only | 61 | Supersede | Safe but fails code-attachment update/save workflows for public submissions. |
| Add Pygments rendering | 66 | Reject now | Improves color only; adds dependency without improving write safety. |
| Execute or import source for validation | 0 | Reject | Violates public-document safety boundary. |
| Promote UTF-8 source writer with `ast.parse()` gate | 91 | Adopt | Uses stdlib, never executes code, supports write/render/save/reread/diff. |

Implemented:

- Added `DocumentFormat.python = "py"` to promoted runtime formats.
- Added `.py` MIME/intake recognition with UTF-8, NUL-byte, non-empty, and
  `ast.parse()` syntax gates.
- Added `PythonSourceDocumentEngine` and `PythonSourceDocumentAdapter`.
- Supported `/code/body` full replacement and `/code/lines/N` bounded line
  replacement, with syntax validation after every operation.
- Added structural SVG render evidence and `/code/body` structured diff support.
- Removed `.py` from passive attachment probe/audit classification.

Current audit after this checkpoint:

- `all_formats_complete=False`
- `write_render_save_promoted=38`
- `derivative_write_render_save_promoted=1`
- `probe_blocked=20`
- incomplete formats:
  `doc`, `xls`, `ppt`, `pdfa`, `png`, `jpg`, `jpeg`, `gif`, `tif`, `tiff`,
  `bmp`, `webp`, `shp`, `shx`, `dbf`, `prj`, `stl`, `wav`, `mp3`, `mp4`

## 2026-06-03 Legacy DOC Derivative Promotion Update

Deep research migration note:

- Local anchors: `src/ummaya/tools/documents/conversion.py`,
  `src/ummaya/tools/documents/legacy_office_promotion_probe.py`,
  `src/ummaya/tools/documents/diff.py`, and
  `src/ummaya/tools/documents/format_completion_audit.py`.
- Local runtime proof: `/usr/bin/textutil` exists on the current macOS host and
  `textutil -convert doc` followed by `textutil -convert docx` produced a valid
  DOCX package with `[Content_Types].xml` and `word/document.xml`.
- 2026-current source decision:
  - LibreOffice remains the broad `.doc/.xls/.ppt` bridge candidate, but it is
    not installed locally.
  - macOS `textutil` documents conversion support for `doc` and `docx`, so it
    is valid for `.doc -> .docx` only.
  - `xls` and `ppt` stay fail-closed because `textutil` does not support their
    spreadsheet/presentation binary formats.
- Implemented:
  - Added `macos-textutil-doc-to-docx-bridge` discovery to the default
    conversion registry.
  - Added legacy-office probe output that reports textutil as a DOC-only
    candidate while leaving `xls` and `ppt` blocked without LibreOffice.
  - Promoted `doc` to `derivative_write_render_save_promoted` with source
    preservation and DOCX derivative lineage.
  - Fixed structured diff path matching so `/paragraph/1` matches extracted
    `engine://.../paragraph/1` paths and displays both before and after values.
- Local alpha result:
  - Created a `.doc` fixture through real `textutil`.
  - Ran `document(save)` with `expected_format=doc`.
  - Saved a `.docx` derivative, rendered one evidence artifact, re-read the
    derivative, and produced diff `13주차 활동일지 -> 14주차 활동일지`.

Current audit after this checkpoint:

- `all_formats_complete=False`
- `write_render_save_promoted=38`
- `derivative_write_render_save_promoted=2`
- `probe_blocked=19`
- incomplete formats:
  `xls`, `ppt`, `pdfa`, `png`, `jpg`, `jpeg`, `gif`, `tif`, `tiff`, `bmp`,
  `webp`, `shp`, `shx`, `dbf`, `prj`, `stl`, `wav`, `mp3`, `mp4`

## 2026-06-03 Derivative Audit Truthfulness Update

Problem found after the DOC loop:

- `format_completion_audit` statically counted derivative formats such as
  `hwp` and `doc` as complete.
- That was only true when a verified conversion bridge existed. In probe-isolated
  Evidence Fabric runs, `hwp/doc` could be reported as complete while the bridge
  probe said missing.

Correction:

- `audit_document_format_completion()` now accepts
  `derivative_promoted_formats`.
- The default local audit derives that set from the current conversion registry.
- Evidence Fabric derives the set from the same HWP and legacy Office probe
  records it emits, so probe output and completion audit cannot contradict each
  other.
- With explicit empty bridge probes, `hwp`, `doc`, `xls`, and `ppt` all remain
  `probe_blocked`.

Current local default evidence after this correction:

- `hwp_probe=available hwpxjs-cli-convert-hwp`
- `doc_probe=candidate_available macos-textutil-doc-to-docx`
- `complete_count=40`
- `incomplete_count=19`
- incomplete formats:
  `xls`, `ppt`, `pdfa`, `png`, `jpg`, `jpeg`, `gif`, `tif`, `tiff`, `bmp`,
  `webp`, `shp`, `shx`, `dbf`, `prj`, `stl`, `wav`, `mp3`, `mp4`

## 2026-06-03 Legacy XLS Excel Derivative Promotion Update

Deep research migration note:

- Local anchors: `src/ummaya/tools/documents/conversion.py`,
  `src/ummaya/tools/documents/legacy_office_promotion_probe.py`,
  `src/ummaya/tools/documents/registry.py`, and
  `src/ummaya/tools/documents/format_completion_audit.py`.
- CC restored-source status: CC has no binary public-document writer analog.
  The adopted invariant remains CC-style visible mutation result, single
  primitive orchestration, explicit derivative lineage, and no silent fallback.
- 2026-current sources:
  - Microsoft Learn `Workbook.SaveAs` defines the `FileFormat` parameter for
    saving Excel workbooks in another format.
  - Microsoft Learn `XlFileFormat` defines `xlExcel8 = 56` for Excel 97-2003
    `.xls` workbooks.
  - LibreOffice Help documents `soffice --convert-to` and filter-based
    conversion as the broad cross-format CLI bridge candidate.
- Candidate scorecard:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Keep `xls` blocked | 67 | Supersede locally | Accurate without a bridge, but current macOS host has a verified Excel bridge. |
| Direct BIFF `.xls` mutation | 8 | Reject | High corruption risk and poor style/render parity. |
| LibreOffice `xls -> xlsx` bridge | 86 | Defer/Prefer when installed | Broad, headless, covers `doc/xls/ppt`, but not present locally. |
| Microsoft Excel AppleScript `xls -> xlsx` bridge | 84 | Adopt for local XLS | Official Excel save contract, preserves source through temp-copy isolation, reuses XLSX adapter. |
| Microsoft PowerPoint AppleScript `ppt -> pptx` bridge | 25 | Reject now | Local dry run hung and produced no output; keep `ppt` fail-closed. |

Implemented:

- Added `microsoft-excel-applescript-xls-to-xlsx-bridge` default discovery when
  `osascript` and `Microsoft Excel.app` are available.
- Added legacy Office probe reporting `xls` as `candidate_available` only for a
  verified local Excel app boundary; `ppt` remains blocked without LibreOffice.
- Hardened `LocalCliDocumentConversionEngine` so external converters receive a
  temporary input copy instead of the original artifact path. This preserves
  the original `.xls` even when Excel rewrites workbook metadata while opening.
- Added `xls` derivative completion reasons distinct from `hwp` and `doc`.
- Added regression coverage for `document(fill/save)`:
  `source.xls -> working.xlsx -> derivative.xlsx -> render evidence -> saved
  .xlsx`, with saved workbook re-read confirming the intended cell value.

Local alpha result:

- Created a real `.xls` fixture from XLSX through Microsoft Excel `SaveAs`
  `file format 56`.
- Ran the single document primitive with `expected_format=xls`.
- Saved an `.xlsx` derivative, emitted one render artifact, produced one
  structured diff change, and re-read `제출서류!B1 = 14주차`.

Current audit after this checkpoint:

- `all_formats_complete=False`
- `complete_count=41`
- `incomplete_count=18`
- incomplete formats:
  `ppt`, `pdfa`, `png`, `jpg`, `jpeg`, `gif`, `tif`, `tiff`, `bmp`, `webp`,
  `shp`, `shx`, `dbf`, `prj`, `stl`, `wav`, `mp3`, `mp4`

## 2026-06-03 Completion Scope Split

The audit now separates completion state from capability scope:

- `document_write_render_save`: native document forms that must support direct
  write, render, and save.
- `derivative_document_write_render_save`: legacy source formats that are
  complete only through a verified editable derivative while preserving the
  source.
- `attachment_context`: evidence/attachment formats where direct in-place
  writing remains blocked and future completion requires extraction, lineage,
  and generated derivative-document gates.
- `passive_context`: known-only context formats with no promoted write path.

This prevents false completion claims:

- `xls` is complete only as `derivative_document_write_render_save`.
- `ppt` and `pdfa` are still incomplete document-write scopes.
- image/geospatial/media formats are not silently treated as writable document
  forms; they are complete only in the attachment-context Markdown derivative
  scope while OCR/GDAL/transcription enrichment remains deferred.

## 2026-06-03 Attachment/PPT/PDF-A Final Loop Update

Attachment-context derivative promotion:

- Image scan formats (`png`, `jpg`, `jpeg`, `gif`, `tif`, `tiff`, `bmp`,
  `webp`) now have a safe top-level `document(save/fill)` path that writes a
  Markdown derivative, renders it through the promoted text/web SVG renderer,
  and optionally saves it to a local `.md` path.
- GIS/model formats (`shp`, `shx`, `dbf`, `prj`, `stl`) and media formats
  (`wav`, `mp3`, `mp4`) use the same attachment-context derivative path.
- This is not original raster/GIS/media mutation. The generated document records
  source filename, source SHA-256, known format, byte size, mutation policy,
  extracted references, warnings, and unavailable OCR/GDAL/transcription
  boundaries.
- Focused evidence:
  - `test_document_primitive_saves_image_attachment_as_markdown_derivative`
  - `test_document_primitive_saves_non_document_attachment_context_families`
  - `test_document_primitive_routes_attachment_known_formats_to_markdown_derivative`
  - `test_format_completion_audit.py` attachment derivative assertions
  - `test_evidence_cli_payload_includes_document_harness_records`

PPT remains blocked:

- Microsoft documents `.ppt` as the PowerPoint 97/2000/2002/2003 binary format
  and continues to publish the binary format specification. This makes native
  parsing possible in principle but not safe to claim without a bridge.
- LibreOffice 26.2 command-line help documents `--convert-to` with optional
  output filters and `--outdir`; that remains the preferred local PPT-to-PPTX
  derivative bridge because it can be run headlessly and verified through OOXML
  re-read/render gates.
- Apache POI HSLF can read/create/modify PPT, but it requires a Java scratchpad
  dependency and is not currently integrated into UMMAYA.
- Current local probe: `/Applications/Microsoft PowerPoint.app` exists and
  `osascript` exists, but no stable PowerPoint AppleScript/VBA SaveAs bridge was
  validated in terminal probes. The app-local
  `/Applications/Microsoft PowerPoint.app/Contents/Resources/PowerPoint.sdef`
  exposes `EPPSaveAsFileType` including `save as Open XML presentation`, but
  the terminal `save active presentation in outputPath as save as Open XML
  presentation` probe created only a PowerPoint lock file and hung without a
  `.pptx` output. `soffice`/`libreoffice` are absent, so PPT stays
  `probe_blocked`.
- Evidence now reports this explicitly with converter id
  `microsoft-powerpoint-applescript-ppt-to-pptx-unverified` and reason
  `microsoft_powerpoint_app_found_but_applescript_bridge_unverified` when the
  app and `osascript` are visible.

PDF/A remains blocked:

- veraPDF is the primary open-source PDF/A validator and covers all PDF/A parts
  and conformance levels. UMMAYA cannot truthfully mark PDF/A write/render/save
  complete without a post-write conformance validation gate.
- Current local probe: `verapdf`, `qpdf`, `gs`, and `mutool` are absent.
  `pdftotext` exists, and pypdf/reportlab are available, but those do not prove
  PDF/A conformance preservation.
- PDF/A therefore stays `probe_blocked` while normal AcroForm PDF remains
  `write_render_save_promoted`.

Latest local Evidence Fabric audit after this loop:

- Run id: `ev-a74674ef-17bc-4bd4-83c0-a3182b6305fd`
- `all_formats_complete=False`
- `complete_count=57`
- `incomplete_count=2`
- Remaining incomplete formats: `ppt`, `pdfa`
- States:
  - `write_render_save_promoted`: 38
  - `derivative_write_render_save_promoted`: 3
  - `attachment_derivative_write_render_save_promoted`: 16
  - `probe_blocked`: 2

## 2026-06-04 PPT/PDF-A Runtime Promotion Loop

Local runtime changes:

- Installed local verification runtimes for this host:
  - LibreOffice 26.2.3 from Homebrew Cask, exposing `/opt/homebrew/bin/soffice`.
  - veraPDF 1.30.1 from Homebrew, exposing `/opt/homebrew/bin/verapdf`.
  - Ghostscript 10.07.1 from Homebrew, exposing `/opt/homebrew/bin/gs`,
    `PDFA_def.ps`, and `srgb.icc`.
- These runtimes are not bundled UMMAYA dependencies. They are optional local
  bridges detected at runtime and remain behind explicit promotion gates.

Deep research migration note:

- Local anchors:
  - `docs/vision.md` public-document harness reference rows.
  - `docs/requirements/ummaya-migration-tree.md` L1-B tool-system and L1-C
    primitive boundaries.
  - `.references/claude-code-sourcemap/restored-src/` has no native document
    format writer analog; the CC parity requirement applies to tool-loop and
    visible result ordering, not to file-format internals.
- 2026-current sources:
  - LibreOffice Help documents `--convert-to`, `--outdir`, and filter-based
    headless conversion. Adopted for `ppt -> pptx` because it is the only
    validated local CLI path for legacy PowerPoint binaries.
  - Microsoft publishes the MS-PPT binary format specification. Adopted as the
    native-format risk anchor; direct binary mutation remains rejected.
  - Apache POI HSLF exists for PPT read/write but requires a Java scratchpad
    dependency and is not selected while LibreOffice CLI is available.
  - veraPDF documents PDF/A validation and its CLI supports flavour selection.
    Adopted as the post-write conformance oracle.
  - Ghostscript 10.07.1 documents `pdfwrite` and ships `PDFA_def.ps` plus
    `srgb.icc`. Adopted only as a local PDF/A exporter before veraPDF
    validation.
- Scorecard:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Keep PPT blocked | 70 | Superseded on this host | Correct without `soffice`, but local LibreOffice now passes the bridge gate. |
| PowerPoint AppleScript PPT SaveAs | 25 | Reject | Local probes hung and produced no `.pptx`; keep as unverified evidence only. |
| Apache POI HSLF write | 61 | Defer | Viable OSS path, but adds Java scratchpad dependency and weaker renderer parity. |
| LibreOffice `ppt -> pptx` bridge | 91 | Adopt | Headless CLI, source copy isolation, OOXML validation, and PPTX render/save reuse. |
| pypdf-only PDF/A | 28 | Reject | Can fill/render PDF but cannot claim PDF/A conformance. |
| veraPDF-only PDF/A | 64 | Partial | Validates but cannot generate a conformant post-write artifact. |
| Ghostscript PDF/A export + veraPDF validation | 92 | Adopt | Local-only export, explicit ICC/prefix assets, and independent conformance oracle. |

Implemented after this loop:

- Added `src/ummaya/tools/documents/pdfa_conformance.py` with a narrow
  `LocalPdfaConformanceBridge`:
  - validates absolute `gs` and `verapdf` executables;
  - copies Ghostscript `PDFA_def.ps` and `srgb.icc` into an isolated temp dir;
  - runs `gs --permit-file-read=srgb.icc -dPDFA=2 ... -sDEVICE=pdfwrite`;
  - validates the output through `verapdf --format text --flavour 2b`;
  - fails closed if either command times out, exits non-zero, produces no PDF,
    or veraPDF does not emit `PASS`.
- Extended `pdfa_promotion_probe` so `candidate_available` requires both:
  `verapdf` and Ghostscript PDF/A assets. A validator alone is still blocked.
- Extended `DocumentToolRuntime.save` so `.pdfa` destinations for PDF
  derivatives trigger the post-write PDF/A bridge. Non-PDF artifacts still fail
  with `extension_mismatch` when asked to save as `.pdfa`.
- Extended `format_completion_audit` so `pdfa` becomes
  `write_render_save_promoted` only when the PDF/A conformance gate is promoted.
- `ppt` now moves to `derivative_write_render_save_promoted` when the
  LibreOffice bridge is available through the conversion registry.

Local alpha evidence:

- PDF/A real smoke:
  - Created a local AcroForm PDF through ReportLab.
  - Ran `DocumentToolRuntime.inspect -> copy_for_edit -> save` with destination
    `.pdfa`.
  - UMMAYA saved a PDF/A artifact and reported:
    `PDF/A post-write conformance passed through
    ghostscript-pdfa2b-pdfwrite-exporter and
    verapdf-pdfa-conformance-validator`.
  - External re-check required `verapdf --nonpdfext --format text --flavour 2b
    <output.pdfa>` because veraPDF's default file filter ignores non-`.pdf`
    suffixes. The re-check returned `PASS`.
- PPT real smoke:
  - Created a synthetic PPTX fixture and converted it to legacy `.ppt` with
    `soffice --headless --convert-to 'ppt:MS PowerPoint 97'`.
  - Ran UMMAYA runtime through:
    `inspect -> copy_for_edit(PPT to PPTX) -> extract -> apply_fill -> render -> save`.
  - The filled `.pptx` derivative rendered through `python-pptx` SVG evidence
    and saved successfully while the original `.ppt` source remained unchanged.

Latest local Evidence Fabric audit after runtime promotion:

- `all_formats_complete=True`
- `complete_count=59`
- `incomplete_count=0`
- `ppt`: `derivative_write_render_save_promoted`
- `pdfa`: `write_render_save_promoted`
