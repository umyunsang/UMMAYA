# PDF Korean Render Hardening and HWP Compatibility Note

Date: 2026-06-03

## Local Anchors

- UMMAYA thesis: `docs/vision.md` document harness reference materials.
- Requirement tree: `docs/requirements/ummaya-migration-tree.md` L1-B tool system and L1-C primitive boundaries.
- Runtime files:
  - `src/ummaya/tools/documents/formats/pdf.py`
  - `src/ummaya/tools/documents/formats/hwp.py`
  - `src/ummaya/tools/documents/registry.py`
- Evidence:
  - `.evidence/document-alpha-beta/2026-06-03/matrix-report.md`
  - `.evidence/document-alpha-beta/2026-06-03/artifacts/pdf/extension-alpha-beta-pdf/render/render-extension-alpha-beta-pdf-001/render-extension-alpha-beta-pdf-001.png`

Claude Code restored-source status: not present for public PDF/HWP document adapters. This is a UMMAYA public-service document-harness adapter boundary.

## Current Sources

- pypdf forms docs: `update_page_form_field_values(..., auto_regenerate=False)` is usually recommended to avoid viewer save prompts, but `/NeedAppearances` is the flag that tells processors to recompute visual field rendering. The same API accepts `(value, font_id, font_size)` tuples when a font id exists in the AcroForm resources.
  - https://pypdf.readthedocs.io/en/stable/user/forms.html
- ReportLab fonts docs: Korean requires Asian font support such as `HYSMyeongJoStd-Medium` / `HYGothic-Medium` or a Unicode TrueType font; basic Type 1/WinAnsi paths are not enough for CJK glyph rendering.
  - https://docs.reportlab.com/reportlab/userguide/ch3_fonts/
- pypdf appearance-stream path requires `fontTools` for embedded TrueType font encoding. UMMAYA now records this as a Spec 2802 runtime dependency for Korean AcroForm appearance generation.
- pyhwp docs: HWP5 is an OLE2 structured storage format; pyhwp can validate and parse HWP5 structures, not provide promoted safe authoring.
  - https://pyhwp.readthedocs.io/en/latest/hwp5.html
- OpenHWP upstream: current README states HWP 5.0 supports read only and HWPX supports read/write.
  - https://github.com/openhwp/openhwp

## Scorecard

| Candidate | Correctness | Local/offline | User-visible quality | Migration cost | Risk | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Keep `auto_regenerate=False` for all PDF fields | 2 | 5 | 1 | 5 | 4 | Reject: Korean appears mojibake in pypdfium evidence. |
| Set `auto_regenerate=True` for all PDF fields | 4 | 5 | 4 | 5 | 3 | Reject as global default: pypdf docs warn about viewer save prompts. |
| Set `auto_regenerate=True` only for non-ASCII field values | 4 | 5 | 4 | 5 | 2 | Adopt: fixes Korean render while preserving ASCII behavior. |
| Embed Korean appearance streams when the PDF already contains a Unicode TrueType resource | 5 | 5 | 5 | 3 | 2 | Adopt: uses pypdf's tuple API and the document's own embedded font resource; avoids viewer-side regeneration for capable forms. |
| Bundle a Korean font into UMMAYA | 5 | 4 | 5 | 1 | 4 | Defer: needs font license, binary-size, package, and cross-platform policy gates. |
| Add external PDF form dependency now | 4 | 3 | 4 | 2 | 3 | Reject for this checkpoint: pypdf + fontTools is enough for the current embedded-font AcroForm gate. |

## Decision

PDF AcroForm mutation now uses a two-tier Korean appearance strategy:

1. If a non-ASCII field value is written and the PDF already contains an embedded Unicode TrueType or Type0 font resource, UMMAYA registers that font under the AcroForm default resources and calls pypdf with `(value, font_id, font_size)`. This creates an embedded appearance stream without setting `/NeedAppearances=True`.
2. If no suitable embedded font exists, UMMAYA falls back to the earlier non-ASCII `auto_regenerate=True` path and filters only pypdf's expected unsupported-font warning for that intentional fallback.

UMMAYA does not bundle a Korean font yet.

## HWP Compatibility Verdict

Current runtime supports `.hwp` for read-only inspection/extraction through `unhwp-read-only`. It is intentionally not promoted for direct fill/render/save mutation through the `document` primitive.

Reason:

- Binary HWP is not the same boundary as HWPX. It is an OLE2 HWP5 structure.
- Existing local adapter `HwpDocumentAdapter` is `known_only`; the default runtime wraps the promoted `unhwp-read-only` inspection engine separately.
- Open-source ecosystem evidence currently supports safe HWP read/extract more strongly than safe binary HWP write. OpenHWP explicitly lists HWP 5.0 read as supported and write as unsupported, while HWPX is read/write.
- The active editable first phase remains `hwpx`, `docx`, `xlsx`, `pptx`, and AcroForm `pdf`.

Promotion path for `.hwp`:

1. Continue improving read-only HWP IR using `unhwp`, OpenHWP, or RHWP behind the adapter boundary.
2. Verify real Korean public `.hwp` fixtures: schema-valid, text/table extraction, encrypted/corrupt blocked cases.
3. If authoring is needed, convert HWP to HWPX/IR first and edit HWPX, or wait for an OSS HWP write engine with license, fixture, render, and reread gates.
4. Do not claim direct HWP binary write compatibility until read/write/render/reread gates pass.

## Tests and Evidence

- `test_pdf_acroform_fill_sets_need_appearances_for_korean_field_rendering`
- `test_pdf_acroform_korean_fill_changes_visible_field_region`
- `test_pdf_acroform_korean_font_fixture_embeds_appearance_without_viewer_regeneration`
- `test_pdf_acroform_korean_fill_suppresses_misleading_font_encoding_warning`
- Full document matrix: `PASS_EDITABLE=5`, `PASS_SAFE_BLOCKED=32`

## Development Loop - Embedded Korean AcroForm Appearance

Status: implemented for PDFs that already contain an embedded Unicode font resource. Bundling fonts remains deferred.

RED:

- `uv run pytest tests/tools/documents/test_pdf_adapter.py::test_pdf_acroform_korean_font_fixture_embeds_appearance_without_viewer_regeneration -q` failed because the filled PDF still set `/NeedAppearances=True`.

GREEN:

- Added `fonttools>=4.60` as a Spec 2802 runtime dependency because pypdf uses it to encode embedded TrueType appearance streams.
- Added embedded-font discovery from page resources and AcroForm `/DR` registration.
- Added pypdf tuple-value updates for non-ASCII AcroForm fields when a suitable font exists.
- `uv run pytest tests/tools/documents/test_pdf_adapter.py -q` -> pass.
- `uv run pytest tests/agents/test_no_new_deps.py tests/permissions/test_zero_new_dependencies.py tests/ipc/test_no_new_runtime_deps.py -q` -> pass.
- `uv run mypy src/ummaya/tools/documents/formats/pdf.py` -> pass.
- `uv run pytest tests/tools/documents -q` -> pass.
- `uv run pytest tests/evidence tests/ci -q` -> pass.
- `uv run python -m ummaya.evidence --source-ref local --out .evidence/run.json`
  -> pass; run id `ev-76d1a06d-19bf-44a1-b8d5-48e5bc63ed78`.
