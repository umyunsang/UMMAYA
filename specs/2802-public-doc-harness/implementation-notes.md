# Implementation Notes: Public AX Document Harness

Date: 2026-06-01

## Scope Correction

This feature implements a document harness, not a parser/converter project.
UMMAYA owns the model-facing tool contracts, artifact lineage, permission
payloads, render/re-read evidence, public-form validation, and capability
promotion loop. Format-specific parsing, mutation, rendering, and validation
behavior is delegated to promoted engines behind `DocumentEngineRegistry`.

## Implemented Layers

1. Foundation: strict Pydantic models, immutable local artifact store, intake
   security checks, contract loader, engine registry, and package exports.
2. Inspection: engine-backed read-only inspection for HWPX, HWP, DOCX, PDF,
   XLSX, and PPTX fixture boundaries with unsafe-file blocking.
3. Mutation: copy-for-edit, ordered fill/style patches, derivative diffs, and
   HWP direct-write blocking.
4. Validation: public-form baselines, structural metrics, hard-rule findings,
   readiness decisions, and data.go.kr-derived metadata snapshots for semantic
   coverage only.
5. Evidence: render artifacts, derivative re-read checks, validation downgrade
   on mismatch, and Evidence Fabric records joinable by `correlation_id`.
6. Tool loop: nine concrete `GovAPITool` definitions registered under existing
   `find`, `check`, and `send` primitives with write/export auth gates.
7. Evaluation loop: candidate profile scorecards, dependency/license gates,
   promotion/deferral persistence, and documented rejected alternatives.
8. Runtime promotion: default local runtime now registers read-only DOCX
   inspection through `python-docx` after fixture-backed read promotion, plus
   bounded HWPX text-node read/write through `hwpx-package-text` for local
   public-form smoke tests.
9. HWPX form semantics: `hwpx-package-text` now extracts table blocks, table
   cells, row/column spans, and common public-form label/value cell pairs while
   preserving deterministic `/hwpx/text[n]` write paths. Table cells now expose
   the paired `field_path` when the cell maps to an editable HWPX text node, and
   HWPX fill requests normalize supported table-cell aliases such as
   `/table[n]/cells[r][c]` to that real text path before mutation. This keeps
   the harness model-facing contract field-oriented without pretending to be a
   full HWPX visual editor.
10. TUI/tool-result boundary: follow-up document actions now require an
    inspected `artifact_id`, mutation diffs expose `diff_id`, `diff_sha256`,
    and `document-diff://` resource refs, saved derivatives carry forward the
    same diff, workflow steps include artifact IDs and hashes, and HWPX render
    evidence is exposed as page-level artifact records.
11. HWPX visual render promotion: user approval on 2026-06-01 removed the
    blanket Rust/WASM prohibition. The default HWPX engine now delegates render
    only to a local `@rhwp/core` Node/WASM bridge (`rhwp-node-wasm`) while
    keeping Python text-node inspect/fill/save semantics unchanged.
12. Compact document viewport diff review: mutation diffs now carry source-side
    `before_value` evidence when the promoted engine can re-inspect the working
    copy, and rendered text anchors produce typed `DocumentChangedViewport`
    records with page clip rectangles, fallback lines, and source render
    artifact IDs. The TUI compact default shows these changed page viewports
    before text hunks so reviewers see the original public-document form region
    first, not only a terminal-friendly text diff.
13. Visual diff page evidence: `document_render` now carries forward the
    derivative diff and records page-level change anchors when changed text
    evidence is visible in full-page render artifacts. Expanded review keeps
    the full page evidence, while compact review uses the same anchor geometry
    as a viewport camera over the full-page render artifact. Compact viewport
    calculation now centers the matched changed text run and enforces a minimum
    review window so repeated or title-position changes remain visually
    recognizable instead of being clipped into a too-tight crop.
14. TUI document viewer bridge: **[SUPERSEDED by item 15 — discarded
    2026-06-02.]** The browser `viewer.html` surface and the
    pixel-viewport/minimap rendering described here were retired. Retained here
    only as the rejected-approach record.
15. Inline structural diff (deep-research-migration approach D2, 2026-06-02):
    document work now renders in the TUI exactly the way Claude Code renders a
    code edit — automatically, per-mutation, inline, no "show viewer" query and
    no external browser. Field-level changes are routed INTO the already-ported
    CC diff pipeline through a single migration-boundary adapter
    (`tui/src/tools/_shared/documentChangeToPatch.ts`:
    `DocumentChangePayload[] → StructuredPatchHunk[]`) and rendered by CC's own
    `StructuredDiffFallback` (red/green, word-level, `useTheme`-only — no
    `useAppState` coupling, no Rust NAPI, no terminal-graphics protocol). The
    card shell was replaced with a `revdiff`-style inline review surface:
    optional left `changes` pane, right diff viewport, and a bottom status line
    carrying document name, diff stats, hunk position, compact/expanded mode,
    word-diff indicator, and tree-hidden state. The
    `viewer.html`/CSS/JS/`openPath` machinery and `DocumentPagePreview.tsx` were
    deleted; `shouldHideSuccessfulIntermediateDocumentResult` was narrowed to
    purely mechanical steps (`document_copy_for_edit`) so substantive mutations
    (`apply_fill`/`apply_style`) show their diff immediately; the raster
    availability gate (`applyDocumentVisualRenderGateToOutput` /
    `isDocumentVisualRenderFailedOutput`) was retired to an identity
    pass-through because the user surface no longer depends on a page raster.
    Page rasters (SVG/PNG from `render.py`) and `changed_viewports` /
    `viewport_cameras` remain Evidence-Fabric evidence only (joinable by
    `correlation_id`), never a user surface. Rationale, weighted scorecard, and
    2026 sources: `deep-research-migration-document-render.md`. The "structural
    path is the location" choice (no pixel position) follows the difftastic /
    SemanticDiff / json-diff / daff convergence and Claude Code's own closed
    terminal-graphics request (#2266).

## Parallel Development Record

The safe dispatch boundary was file ownership. US3 validation, US4 evidence,
US6 candidate evaluation, and Polish tests were parallel-safe because each
owned mostly disjoint files. US5 ToolRegistry integration was not broadly
parallel-safe because tool definitions, executor wiring, permissions, and boot
registration form one model-facing contract. The Lead integrated US5 while
subagents wrote only isolated test files.

## Evaluation Criteria Applied

The implementation follows the C1-C12 criteria in
[`parallel-evaluation-plan.md`](./parallel-evaluation-plan.md). The hard gates
are standards mapping, controlled mutation, strict tool schemas, upload safety,
unsupported-feature blocking, and headless operation. Write promotion requires
all hard gates plus scorecard evidence; read-only promotion requires security
hard gates plus read/extract evidence.

## Reference Bootstrap

- KS X 6101/OWPML and the HWPX ecosystem anchor Korean public-document format
  evidence. HWP binary direct writing remains blocked in this epic.
- ECMA-376 anchors DOCX/XLSX/PPTX package semantics; `python-docx` is promoted
  for default read-only DOCX inspection, while DOCX write and the remaining
  `openpyxl`/`python-pptx` operations stay candidate-gated until fixture
  evidence promotes each operation.
- PDF support is AcroForm- and evidence-gated; scanned/static/XFA/signature
  preserving mutation remains blocked unless future evidence promotes it.
- OWASP file-upload guidance defines intake safety: extension allowlists,
  MIME distrust, signatures, safe filenames, decompression limits, and isolated
  storage.
- MCP tool structured-output patterns validate the schema-bound harness shape,
  but UMMAYA keeps its native ToolRegistry and permission pipeline.
- data.go.kr public document/core-data metadata helps choose representative
  administrative scenarios; it is not treated as a file-level submission-form
  layout oracle.

## Current Limitations

- HWPX default write support is intentionally bounded to text-node replacement
  in existing package structure. It does not claim full style/layout fidelity
  and must be reread after mutation before external handoff.
- HWPX visual render is promoted for local SVG page evidence through
  `@rhwp/core`; PNG is generated only as review evidence when a local SVG
  rasterizer such as `rsvg-convert` is available, not as a required runtime
  dependency.
- Compact/expanded user review no longer depends on readable SVG/PNG page
  artifacts; those remain Evidence Fabric assets only. Table geometry,
  style-only changes, and multi-page anchor disambiguation stay scorecard-gated
  follow-up work for richer labels and page correlation, not for the primary TUI
  surface.
- HWPX table extraction infers simple label/value rows, including a leading
  group-header cell followed by paired label/value cells. Complex nested table
  semantics and multi-node field replacement remain promotion-gated.
- DOCX write/style/render fidelity is not promoted yet. The default
  `python-docx` engine is read-only and extracts top-level paragraphs, tables,
  and core properties; nested tables and revision-mark content remain an
  explicit warning boundary.
- HWP binary write remains blocked.
- Tool execution is local only. `document_save` writes an export artifact for
  review or handoff; it does not submit to Government24, Hometax, or another
  agency channel.

16. Document primitive boundary correction (2026-06-02): the model-facing
    document surface is now one `document` primitive. The previous
    `document_inspect` / `document_copy_for_edit` / `document_apply_fill` /
    `document_render` sequence remains internal runtime structure and legacy
    transcript compatibility, not the normal model-facing tool set. Direct
    `document({...})` calls are normalized at IPC dispatch into the concrete
    document adapter execution path, and final-answer gates require one
    successful `document` result after the latest user document request instead
    of forcing exposed stage calls. TUI tool-choice repair loads
    `select:document`, does not synthesize incomplete document arguments, hides
    workflow narration before the result card, and renders `tool_id="document"`
    through the existing revdiff-style document diff surface. IPC frame schemas,
    AdapterManifest primitive enums, routing-index invariants, and delegation
    scope grammar include `document`.
