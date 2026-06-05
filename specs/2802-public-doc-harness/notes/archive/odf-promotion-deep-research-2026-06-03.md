# ODF Promotion Deep Research

Date: 2026-06-03

## Local Position

UMMAYA now provides bounded real-use write/render/save for ODF extensions:
`.odt`, `.ods`, and `.odp`.

Current code boundary:

- `src/ummaya/tools/documents/models.py` promotes `odt`, `ods`, and `odp` into
  `DocumentFormat` while retaining the broader `KnownDocumentFormat` taxonomy.
- `src/ummaya/tools/documents/formats/odf.py` adds odfdo-backed ODT paragraph,
  ODS sheet-cell, and ODP text-frame engines.
- `src/ummaya/tools/documents/engines.py` registers the ODF engines by default.
- `src/ummaya/tools/documents/adapter_registry.py` routes default ODF handling to
  `OdfdoDocumentAdapter` and skips the passive ODF adapter for promoted ODF
  formats.
- `src/ummaya/tools/documents/intake.py` detects ODF zip packages through the
  package `mimetype`, `META-INF/manifest.xml`, and `content.xml` contract.
- `src/ummaya/tools/documents/odf_promotion_probe.py` now reports ODF as
  `promoted_bounded` when odfdo and the runtime adapter are present, while still
  exposing the missing/deferred LibreOffice layout-oracle bridge.
- Local runtime still has no `soffice` or `libreoffice` executable, so original
  page-layout rendering remains deferred. The current renderer is a structural
  SVG evidence renderer, not a LibreOffice pixel/layout oracle.

## 2026-Current Sources

| Source | Signal | UMMAYA impact |
|---|---|---|
| OASIS OpenDocument v1.4 Part 2 Packages, 2025-10-06, <https://docs.oasis-open.org/office/OpenDocument/v1.4/part2-packages/OpenDocument-v1.4-os-part2-packages.html> | ODF package is a ZIP package and must contain `META-INF/manifest.xml`; package document content is covered by the ODF work product. | Existing read-only ZIP/XML inspection is directionally correct, but full promotion must preserve package manifest and content relationships. |
| OASIS OpenDocument v1.4 Part 3 Schema, <https://docs.oasis-open.org/office/OpenDocument/v1.4/os/part3-schema/OpenDocument-v1.4-os-part3-schema.html> | `content.xml` contains the `office:document-content` element in package form. | Writer promotion must be schema-aware rather than plain XML string patching. |
| `odfdo`, <https://github.com/jdum/odfdo> | Apache-2.0 Python ODF library; README states it can create, parse, edit, save `.odt`, `.ods`, `.odp`, manipulate text/tables/styles, and was latest at v3.22.8 on 2026-05-08. | Best 2026-current permissive candidate for bounded ODF writer implementation. Requires dependency approval and fixture gates. |
| `odfpy`, <https://pypi.org/project/odfpy/> | Stable but old 1.4.1 release from 2020; supports ODF 1.2 read/write and has mixed Apache/GPL/LGPL metadata. | Keep as comparative parser/reference; do not choose as primary runtime writer while `odfdo` is current and cleanly Apache-2.0. |
| LibreOffice 26.2 Help, PDF command-line parameters, <https://help.libreoffice.org/latest/km/text/shared/guide/pdf_params.html> | Official examples show `soffice --convert-to ...` for Writer documents and macOS/ZSH usage. | Preferred local layout oracle for future ODF visual-fidelity promotion, but not bundled or present locally. Must be an explicit local tool bridge, not CI/live dependency. |

## Candidate Scorecard

Weights: native ODF fidelity 25, write safety 20, render oracle 15,
save/re-read determinism 15, license/current maintenance 10, local-only execution
10, implementation cost 5.

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Claim current read-only adapter as complete ODF support | 31 | Reject | No writer, no render oracle, no save/reread gate. |
| Hand-patch `content.xml` with stdlib ZIP/XML | 54 | Reject as writer | Too easy to break manifest, styles, tables, formulas, and presentation structures. |
| Use `odfpy` as primary writer | 68 | Defer | Functional but old ODF 1.2-oriented release and mixed license metadata. |
| Use `odfdo` for bounded writer plus structural SVG render now; keep LibreOffice as deferred layout oracle | 91 | Adopted for this loop | Current, Apache-2.0, covers ODT/ODS/ODP creation/edit/save, passes save/re-read gates, and avoids overclaiming unavailable local layout tooling. |
| Convert ODF to OOXML and edit OOXML only | 59 | Reject as primary | Loses native ODF lineage and may alter public-form structure/styles. Valid only as an explicitly labeled derivative path. |

## Final Direction

ODF is promoted for bounded public-form operations, not for full visual-layout
parity yet.

Runtime contract:

1. `.odt`, `.ods`, and `.odp` are `DocumentFormat` runtime formats.
2. Mutations are limited to stable ODF structural paths:
   `/odf/text/p[n]`, `/odf/sheets/{sheet}/cells/{cell}`, and
   `/odf/slides/{slide}/frames/{n}`.
3. Save is derivative bytes through odfdo and must pass re-read extraction.
4. Render is structural SVG evidence that exposes changed content to the
   document primitive/TUI diff pipeline.
5. LibreOffice headless remains the next visual-fidelity bridge; until that
   bridge exists, evidence must say `libreoffice_layout_oracle_deferred`.

## Implemented Loop

This loop promoted bounded ODF support:

- Added dependency `odfdo>=3.22.8,<4` with explicit public-document justification
  in `pyproject.toml`.
- Added ODF MIME mappings to `src/ummaya/tools/documents/artifact_store.py`.
- Added ODF runtime literals to `src/ummaya/tools/documents/capability.py`.
- Added ODF package signature detection to `src/ummaya/tools/documents/intake.py`.
- Added `src/ummaya/tools/documents/formats/odf.py`:
  - `OdfdoTextDocumentEngine` for ODT paragraph replacement.
  - `OdfdoSpreadsheetDocumentEngine` for ODS sheet-cell mutation.
  - `OdfdoPresentationDocumentEngine` for ODP text-frame mutation.
  - `OdfdoDocumentAdapter` for adapter-registry routing.
- Updated `src/ummaya/tools/documents/engines.py` and
  `src/ummaya/tools/documents/adapter_registry.py` so default runtime routes ODF
  through promoted ODF engines, not passive ODF.
- Updated `src/ummaya/tools/documents/format_completion_audit.py` so ODF records
  are `write_render_save_promoted` with
  `bounded_odfdo_write_render_save_promoted` and
  `libreoffice_layout_oracle_deferred` reasons.

Verification:

- `uv run pytest tests/tools/documents/test_promoted_format_workflow_matrix.py -q`
  passes ODT, ODS, and ODP save/render/re-read/diff cases.
- `uv run pytest tests/tools/documents/test_intake_security.py -q` accepts ODF
  packages through mimetype-based signature detection.
- `uv run pytest tests/tools/documents/test_odf_promotion_probe.py -q` reports
  `promoted_bounded` when odfdo is present and keeps LibreOffice layout oracle
  deferred.
- Focused `ruff` and `mypy` gates pass for the ODF implementation files.

## Next Gates

- Add a local-only LibreOffice layout-oracle bridge with explicit executable
  discovery and no CI live dependency.
- Add richer ODT/ODS/ODP fixtures with Korean text, styles, tables, formulas,
  and presentation layout constraints.
- Add TUI-facing evidence that ODF structural diffs render through the same
  document primitive path as HWPX/OOXML/PDF.
