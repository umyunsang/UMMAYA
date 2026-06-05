# Public Document Design Control Hardening Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `ummaya-deep-research-migration` before each checkpoint and use `superpowers:executing-plans` or `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the `document` primitive handle official Korean public-form design controls, not just text values: tables, merged cells, font family, font size, bold/italic/underline, color, fill, alignment, render evidence, save, and reread validation.

**Architecture:** Keep one model-facing `document` primitive. Add format-scoped style routing and adapter behavior underneath it so DOCX, XLSX, HWPX, HWP, PDF, and passive formats can each fail closed or pass with reread proof. A design-control pass is not complete unless the changed style is visible in render evidence and machine-verified after save/reread.

**Tech Stack:** Python 3.12, Pydantic v2, `python-docx`, `openpyxl`, `pypdf`, `pypdfium2`, `rhwp`/`OpenHWP` research boundary, current UMMAYA Evidence Fabric.

**Checkpoint evidence:** The initial `official-form-design-stress-report.md` is the baseline failure report. Current postfix status is summarized in `.evidence/public-document-design-forms-20260604/reports/official-form-design-hardening-postfix-summary.md`, with live TUI acceptance in `official-tui-strict-alpha-postfix-report.md`.

---

## Local Anchors

- `docs/vision.md`: UMMAYA is the Claude Code harness adapted to Korean public infrastructure; the user-facing unit is a CC-style tool loop.
- `docs/requirements/ummaya-migration-tree.md`: root primitive discipline and public-service adapter boundaries.
- `specs/2802-public-doc-harness/format-adapter-implementation-plan-2026-06-03.md`: one `document` primitive plus format-specific adapters.
- `.evidence/public-document-design-forms-20260604/reports/official-form-design-stress-report.md`: official-form stress test that exposed current style-control gaps.
- `src/ummaya/tools/documents/registry.py:1727`: current `_style_patch()` always maps style patches to `set_paragraph_style`.
- `src/ummaya/tools/documents/formats/ooxml.py:501`: DOCX engine already supports `set_run_style`.
- `src/ummaya/tools/documents/formats/ooxml.py:631`: XLSX engine already supports `set_cell_style`.
- `src/ummaya/tools/documents/formats/hwpx.py:587`: HWPX engine currently accepts only text-node fill operations.

## 2026-Current Research Summary

### Standards And Official Format Contracts

- OOXML / ECMA-376 represents character formatting at run level and table/spreadsheet styling through format-specific style records. UMMAYA must not collapse DOCX run styling and XLSX cell styling into one paragraph operation.
- OWPML / KS X 6101:2024 is the native HWPX contract and includes style-linked XML signals such as paragraph properties, character properties, border/fill references, and style references. HWPX style control should be implemented by native OWPML style extraction/apply, not by plain text replacement.
- PDF / ISO 32000-2 separates interactive AcroForm fields from static page content. Static official PDFs must remain blocked for form design editing unless UMMAYA adds an explicit template overlay/flatten pipeline.
- ODF 1.4 has explicit style and table-cell schema but remains known/passive until a mutation adapter and reread validator exist.

### Library And OSS Findings

- `python-docx` official docs: direct run formatting supports font name, point size, bold, underline, and RGB color. Paragraph/table style names require existing style definitions, so generated style IDs must not be treated as proof.
- `openpyxl` official docs: styles are applied directly to cells; merged-cell formatting belongs to the top-left cell. This exactly matches UMMAYA's `/sheets/{sheet}/cells/{cell}` target path model.
- `pypdf` official docs: AcroForm fill requires `/AcroForm` and `/Fields`; appearance regeneration is a field-level concern. Static PDF mutation must fail closed.
- `pypdfium2` current docs: PDF page rendering is local and suitable for review evidence, not a static-PDF authoring engine.
- `OpenHWP` GitHub: MIT Rust workspace exposes HWP read and HWPX read/write with an IR/document-model direction. It is a candidate for HWPX style extraction/write and HWP-to-HWPX derivative validation.
- `rhwp` GitHub: Rust/WASM HWP/HWPX viewer/editor with active releases and CLI binaries. It remains the best render/editor bridge candidate for HWPX visual fidelity, but must stay behind a local-only bridge boundary.
- Docling 2025 and DocLLM/LayoutLLM 2024: document understanding should preserve text plus layout/table/spatial anchors. They support DocumentIR enrichment, not native file mutation by themselves.

## Candidate Scorecard

Weights: user-visible correctness 25, native format fidelity 20, fail-closed safety 15, implementation speed 10, reread testability 15, UMMAYA thesis fit 15.

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Prompt-only style instructions | 23 | Reject | No deterministic file mutation or reread proof. |
| Convert every format to PDF and overlay text | 42 | Reject as primary | Loses native editability and table/style anchors. |
| Keep current `_style_patch_operation` paragraph-only mapping | 31 | Reject | It returns false-positive `ok` for DOCX and blocks XLSX cell styles. |
| Add format/path-based style operation routing under `document` | 93 | Adopt P0 | Smallest high-impact fix; aligns with existing engine support and reread proof. |
| Adopt Docling as universal mutation layer | 55 | Reject for mutation, use for extraction research | Strong extraction IR, not native style authoring. |
| HWPX native style extraction/apply through OWPML + rhwp/OpenHWP bridge | 86 | Adopt P1/P2 | Correct HWPX direction, but larger boundary and license/artifact review needed. |
| Static PDF overlay authoring | 68 | Defer | Useful for explicit template overlay mode; not safe as generic PDF form editing. |

## Capability Gates

Every format must declare the strongest gate it can pass:

| Format | Value Fill | Style Control | Render | Save | Reread | Current Design Verdict |
|---|---|---|---|---|---|---|
| DOCX | Pass for paragraph/table paths | Partial; run API exists but primitive mapping false-positive | Pass | Pass | Pass when direct run target used | Fix P0 routing and direct paragraph/run style semantics. |
| XLSX | Pass for cell path | Engine pass, primitive mapping blocked | Pass | Pass | Pass | Fix P0 routing to `set_cell_style`. |
| HWPX | Existing text-node replace only | Blocked; style signals not extracted | Pass via render bridge | Pass for text-node derivative | Pass for text-node | P1 native blank-cell + style-map extraction. |
| HWP | Derivative HWPX only | Blocked direct binary style | Partial/blocked by bridge quality | HWPX derivative only | Derivative proof only | Keep fail-closed direct HWP. |
| PDF AcroForm | Pass only if fields exist | Limited to field appearance contract | Pass | Pass | Pass only for AcroForm | Static PDFs remain blocked. |
| PDF static | Blocked | Blocked | Pass | Blocked | N/A | Add explicit template-overlay mode later, not generic style editing. |
| ODT/ODS/ODP | Known/passive | Blocked | Passive only | Blocked | N/A | Defer until odfdo style mutation adapter is scored. |

## File Structure

- Modify `src/ummaya/tools/documents/registry.py`
  - Responsibility: convert model-facing `DocumentStylePatch` into the correct `DocumentPatchOperation` by `DocumentFormat` and target path.
- Modify `src/ummaya/tools/documents/formats/ooxml.py`
  - Responsibility: apply DOCX direct paragraph/run/table-cell style and XLSX cell style without false-positive no-ops.
- Test `tests/tools/documents/test_ooxml_adapters.py`
  - Responsibility: engine-level reread checks for DOCX/XLSX style mutations.
- Test `tests/tools/documents/test_document_tool_flow.py`
  - Responsibility: `document` primitive-level routing and saved/reread behavior.
- Add evidence under `.evidence/public-document-design-forms-20260604/`
  - Responsibility: official public-form stress report after each checkpoint.

## Task 1: P0 Style Operation Routing

**Files:**
- Modify: `src/ummaya/tools/documents/registry.py:1727-1778`
- Modify: `src/ummaya/tools/documents/formats/ooxml.py:501-508`
- Modify: `src/ummaya/tools/documents/formats/ooxml.py:587-639`
- Test: `tests/tools/documents/test_ooxml_adapters.py`
- Test: `tests/tools/documents/test_document_tool_flow.py`

- [x] **Step 1: Write failing primitive tests**

Add tests that call `document` with `operation="style"` for:

```python
DocumentStylePatch(
    target_path="/word/paragraphs/1/runs/1",
    font_family="Malgun Gothic",
    font_size_pt=Decimal("14"),
    bold=True,
)
```

and:

```python
DocumentStylePatch(
    target_path="/sheets/총괄표/cells/B5",
    font_family="Malgun Gothic",
    font_size_pt=Decimal("11"),
    bold=True,
    fill_color_rgb="FFF2CC",
    alignment="center",
)
```

Expected RED:

```text
DOCX reread font/size/bold not reflected
XLSX style primitive blocked: Unsupported XLSX operation: set_paragraph_style
```

- [x] **Step 2: Run tests and confirm failure**

Run:

```bash
uv run pytest tests/tools/documents/test_ooxml_adapters.py -k "style" -q
uv run pytest tests/tools/documents/test_document_tool_flow.py -k "style" -q
```

- [x] **Step 3: Route style operations by format and target path**

Change `_style_patch()` to pass `working.format` into `_style_patch_operation()`. Implement:

```python
if document_format is DocumentFormat.xlsx and _XLSX_CELL_FILL_TARGET_RE.match(target_path):
    return OperationType.set_cell_style
if document_format is DocumentFormat.docx and "/runs/" in target_path:
    return OperationType.set_run_style
if document_format is DocumentFormat.docx and _DOCX_TABLE_FILL_TARGET_RE.search(target_path):
    return OperationType.set_cell_style
return OperationType.set_paragraph_style
```

- [x] **Step 4: Make DOCX direct paragraph/cell styles real**

For `set_paragraph_style`, apply direct font properties to all runs in the paragraph when the style descriptor contains direct font/color/bold fields. For `set_cell_style`, style all paragraphs/runs in the target cell and apply cell fill using WordprocessingML shading.

- [x] **Step 5: Rerun focused gates**

Run:

```bash
uv run pytest tests/tools/documents/test_ooxml_adapters.py -k "docx or xlsx or style" -q
uv run pytest tests/tools/documents/test_document_tool_flow.py -k "document_primitive" -q
```

Expected: PASS.

## Task 2: Official Form Reread Evidence Gate

**Files:**
- Create or update: `.evidence/public-document-design-forms-20260604/reports/official-form-design-stress-report.json`
- Create or update: `.evidence/public-document-design-forms-20260604/reports/official-form-design-stress-report.md`

- [x] **Step 1: Re-run the official public-form design stress script**
- [x] **Step 2: Verify DOCX style reread includes `Malgun Gothic`, point size, and bold**
- [x] **Step 3: Verify XLSX style reread includes font, fill, alignment, and bold**
- [x] **Step 4: Keep HWPX/HWP/PDF static blockers explicit**

## Task 3: HWPX Style-Map Extraction Research Spike

**Files:**
- Modify: `src/ummaya/tools/documents/formats/hwpx.py`
- Test: `tests/tools/documents/test_builtin_hwpx_engine.py`

- [x] **Step 1: Extract `charPr`, `paraPr`, `style`, `borderFill`, and font-face references into `StyleDescriptor`**
- [x] **Step 2: Link `ParagraphBlock.style_id` and table-cell style constraints**
- [x] **Step 3: Prove the three official HWPX forms no longer report `style_map=0`**
- [x] **Step 4: Do not implement HWPX style mutation until extraction and reread are stable**

## Task 4: HWPX Blank-Cell Authoring

**Files:**
- Modify: `src/ummaya/tools/documents/formats/hwpx.py`
- Test: `tests/tools/documents/test_builtin_hwpx_engine.py`

- [x] **Step 1: Add a table-cell target resolver for empty value cells**
- [x] **Step 2: Insert text runs into empty cells while preserving surrounding paragraph/table structure**
- [x] **Step 3: Re-render the official 재난안전기업 신청서 and verify the new value lands in the blank cell, not the label**

## Task 5: PDF Static Form Policy Split

**Files:**
- Modify: `src/ummaya/tools/documents/formats/pdf.py`
- Test: `tests/tools/documents/test_pdf_adapter.py`

- [x] **Step 1: Keep generic static PDF fill blocked**
- [x] **Step 2: Add a future `template_overlay` capability profile only when a template baseline provides bounding boxes**
- [x] **Step 3: Require pypdfium2 render comparison after overlay**

## Task 6: TUI And Evidence Fabric Acceptance

**Files:**
- Modify only if needed: `tui/src/components/primitive/DocumentToolResultCard.tsx`
- Evidence: `.evidence/run.json`

- [x] **Step 1: Run natural Korean `bun run tui` queries on official HWPX and DOCX public-form copies**
- [x] **Step 2: Confirm assistant prelude -> document tool use -> changed content diff -> final answer**
- [x] **Step 3: Run Evidence Fabric**

```bash
uv run pytest tests/evidence tests/ci -q
uv run python -m ummaya.evidence --source-ref local --out .evidence/run.json
```

Postfix evidence:

- HWPX live prompt: `공식 재난안전기업 지원 신청서 사본 /tmp/ummaya-tui-official-hwpx-empty-cell-alpha-modelvisible-20260604-135111.hwpx 내용을 파악해서 접수번호 옆 빈칸에는 UMMAYA-2026-0008을 넣고, 수정 후 변경된 부분만 바로 확인할 수 있게 보여줘.`
- HWPX observed TUI sequence: assistant prelude -> `document(...)` tool-use row -> `Changed 1 field` -> `-접수번호:` / `+접수번호: UMMAYA-2026-0008` -> final answer using `접수번호`.
- DOCX live prompt: `공식 공모전 참가신청서 DOCX 사본 /tmp/ummaya-tui-official-docx-form-20260604-135445.docx 내용을 파악해서 붙임 1 옆 빈칸에는 UMMAYA-DOCX-2026을 넣고, 수정 후 변경된 부분만 바로 확인할 수 있게 보여줘.`
- DOCX observed TUI sequence: assistant prelude -> `document(...)` tool-use row -> `Changed 1 field` -> `-붙임 1:` / `+붙임 1: UMMAYA-DOCX-2026` -> final answer using `붙임 1`.
- Evidence: `.evidence/public-document-design-forms-20260604/reports/official-tui-strict-alpha-postfix-report.md`.

## Completion Criteria

- DOCX value fill, direct run style, paragraph/cell style, render, save, reread pass on an official-style fixture.
- XLSX value fill and cell style pass through the `document` primitive, not only engine-level patch calls.
- HWPX official forms expose nonzero style maps before any HWPX style mutation is promoted.
- HWPX blank table cells can be filled without replacing labels.
- Static PDF remains fail-closed unless an explicit template overlay baseline exists.
- Final report names any residual blocked gates instead of overclaiming all-format design control.
