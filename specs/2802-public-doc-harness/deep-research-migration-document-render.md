# Deep Research Migration Note — Document Change Rendering in the TUI

Date: 2026-06-02
Pipeline: `.agents/skills/ummaya-deep-research-migration/SKILL.md`
Scope: How a document-work result renders in the TUI automatically (no "show
viewer" query), mirroring how Claude Code renders a code diff inline after an
edit.

## Problem / Bottleneck

The branch shipped a `viewer.html` browser bridge (`DocumentPagePreview.tsx`)
that auto-opens an external browser on a successful `document_render`, while the
TUI shows only a 3-line `Document viewer` status. On the success happy-path the
TUI *hides* the inline diff (`DocumentToolResultCard.tsx:55-71`,
`showDiffMetadata=false`) and pushes review out of the terminal. This is the
inverse of Claude Code, where a successful edit yields the richest inline diff.
Requirement: document changes must render **in the TUI, automatically,
per-mutation**, like CC's inline code diff.

## Local Anchors

- `docs/vision.md` — CC harness + 2 swaps, byte-identical otherwise.
- `docs/requirements/ummaya-migration-tree.md` UI-B.2/B.3 — long-output Ctrl+O
  expand; tables via CC `MarkdownTable` byte-identical.
- CC restored-source: `StructuredDiff.tsx`, `StructuredDiffList.tsx`,
  `StructuredDiff/Fallback.tsx`, `FileEditToolUpdatedMessage.tsx`,
  `Tool.ts:566 renderToolResultMessage`.
- Consumer path: `UserToolSuccessMessage.tsx:65` calls
  `tool.renderToolResultMessage?.()` for every resolved tool result.

## CC Restored-Source Status — analog is INTACT and already ported

UMMAYA's TUI already contains the CC diff pipeline byte-identical:
`tui/src/components/StructuredDiffList.tsx`, `StructuredDiff.tsx`,
`StructuredDiff/` (Fallback + colorDiff), `FileEditToolUpdatedMessage.tsx`,
`tui/src/utils/diff.ts` (`getPatchForDisplay`), the `diff` npm package
(`StructuredPatchHunk`), and `tui/src/components/MarkdownTable.tsx`. The
auto-render hook is already wired at `AdapterTool.ts:1650`. Migration is
therefore "route document changes INTO the existing CC pipeline", not "port".

## 2026-current Sources

- Claude Code issue #2266 (terminal graphics protocol) — **CLOSED, not
  implemented**. CC does not render inline terminal images. Validates: do not
  use Kitty/Sixel/iTerm2 graphics. https://github.com/anthropics/claude-code/issues/2266
- "Are We Sixel Yet?" / Terminal Trove 2026 matrix — 21 terminals image-capable,
  15 Sixel, 7 Kitty; many crash on Sixel; Alacritty unsupported. Graphics
  protocols are fragile/heterogeneous. https://www.arewesixelyet.com/
- difftastic (Wilfred/difftastic, MIT, Rust) — structural diff via tree-sitter;
  "shows what semantically changed"; side-by-side + inline modes; CLI-only, not
  a reusable library. https://github.com/Wilfred/difftastic
- SemanticDiff vs difftastic — both side-by-side default; SemanticDiff adds
  minimap + dynamic context expansion; structural/semantic diff = smaller,
  focused diffs. https://semanticdiff.com/blog/semanticdiff-vs-difftastic/
- daff tabular diff spec — schema rows + before/after columns for table data.
  Reference shape for a field-change table. https://paulfitz.github.io/daff-doc/spec.html
- andreyvit/json-diff — structural diff with dot-notation paths (≙ our
  `target_path`). https://github.com/andreyvit/json-diff
- umputun/revdiff (Go) — TUI for reviewing diffs/documents **without leaving an
  AI coding session**; two-pane, modal (collapsed/compact/word-diff), structured
  stdout. Architecture reference for a terminal review surface.
  https://github.com/umputun/revdiff
- Cognitive-load code-review research — standard diffs strip context → extraneous
  load; structural/semantic diffs reduce it. https://www.codeant.ai/blogs/cognitive-load-code-reviews
- delta (dandavison/delta) — line + intra-line (levenshtein) highlight pager.
  https://github.com/dandavison/delta

## Scorecard

Weights: CC/thesis 정합 0.20 · 자동·인라인(in-TUI) 0.18 · 견고성/포터빌리티 0.15
· 가시품질(인지부하) 0.12 · 마이그레이션 형태/비용 0.10 · 테스트성/증거 0.08
· 유지보수/zero-dep 0.07 · 보안/로컬-only 0.06 · 다포맷 확장성 0.04.

| 후보 | 정합 | 인라인 | 견고 | 가시 | 이전 | 테스트 | 유지 | 보안 | 확장 | **총점** |
|---|---|---|---|---|---|---|---|---|---|---|
| A. 브라우저 viewer.html (현행/폐기) | 0 | 1 | 3 | 4 | 2 | 2 | 2 | 1 | 4 | **1.83** |
| B. 터미널 그래픽 이미지 (Kitty/Sixel) | 0 | 4 | 1 | 4 | 2 | 1 | 2 | 4 | 4 | **2.17** |
| C. 박스 스케치 + 의미 diff | 3 | 5 | 5 | 4 | 3 | 5 | 4 | 5 | 4 | **4.17** |
| D. 구조적 diff → CC StructuredDiffList (+daff 필드 테이블) | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 4 | **4.96** |
| **D2. 구조적 diff → CC StructuredDiff + revdiff inline shell** | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | **5.00** |
| E. revdiff 2-pane 모달 앱 | 2 | 3 | 5 | 5 | 3 | 3 | 2 | 5 | 4 | **3.43** |

## Selected Approach — D2 (5.00, revised 2026-06-02)

Render document changes as a **structural field-level diff through the
already-ported CC `StructuredDiff`/`StructuredDiffFallback` pipeline**, wrapped
in a `revdiff`-style inline review shell: section list on the left, diff
viewport on the right, and a single status line carrying document name, diff
stats, hunk position, compact/expanded mode, word-diff mode, and tree-hidden
state. Trigger is **per-mutation, automatic, in-TUI** via
`renderToolResultMessage` (CC pattern). Compact (default) = capped changed
sections + diff viewport; Ctrl+O expand = all changed sections + all hunks,
still in-terminal. The rendered page raster (SVG/PNG from `render.py`) is
retained as **Evidence Fabric evidence only** (correlation_id join), never the
user surface.

Why D2 > D: D's data boundary was correct, but the `DocumentToolResultCard`
shell still looked like a boxed tool card instead of a diff-review surface.
`umputun/revdiff` provides the better terminal interaction reference: two-pane
navigation/diff structure, compact/collapsed/word-diff modes, and a status bar.
UMMAYA migrates those layout semantics into Ink inline rendering while rejecting
the separate Go modal app boundary.

Why D2 > C (box sketch): neither CC, difftastic, SemanticDiff, nor json-diff
render pixel-spatial position — the structural **path/field is the location**.
A schematic box at approximate coordinates risks false confidence
(foundations-over-gloss). The field label ("세대주 성명 칸") is more honest and
precise than an approximate box, and the real raster stays as downloadable
evidence. D also has near-zero migration cost (CC components already in tree) and
the highest legibility (structural diff = lowest extraneous cognitive load).

## Rejected Approaches

- A browser viewer.html — opens external browser (breaks in-TUI requirement),
  fails headless/SSH, ~600 lines custom HTML/CSS/JS, data-URI embeds the doc on
  disk (privacy surface). DISCARD per user direction.
- B terminal graphics — CC #2266 closed; Sixel crashes/poor quality; Alacritty
  and many terminals unsupported; not snapshot-testable. Anti-reference.
- C box sketch — robust but spatial schematic is non-reference and risks false
  visual confidence; superseded by D's structural path-as-location.
- E revdiff full app — rich but it is a separate modal review app, not CC's
  inline-in-transcript model; Go runtime and overlay-terminal mechanics are not
  adopted. D2 imports the layout contract, not the process boundary.

## Migration Boundary

- New narrow adapter `tui/src/tools/_shared/documentChangeToPatch.ts`:
  `DocumentChangePayload[] → StructuredPatchHunk[]` (the `diff` package shape CC
  uses). Each change → one hunk: header from `change_type` + humanized
  `target_path`; lines `[- before_value, + after_value]`. This is the only new
  module; everything downstream is the unchanged CC pipeline.
- `DocumentToolResultCard.tsx` kept as a compatibility filename but rewritten to
  render a non-card review surface: status/summary line + optional left
  `changes` pane + CC `StructuredDiffFallback` viewport + revdiff-style status
  bar over the synthesized patch. Box-sketch, rounded card frame, field table,
  and viewer branches deleted.
- `DocumentPagePreview.tsx` viewer.html/CSS/JS/openPath machinery DELETED.
  Honest-fail gate redefined from "raster readable?" to "structural change data
  present?".
- `AdapterTool.ts:290` `shouldHideSuccessfulIntermediateDocumentResult` narrowed
  to mechanical steps (`document_copy_for_edit`) only; substantive mutations
  (`apply_fill`/`apply_style`) render their inline diff immediately.

## UMMAYA Content Moved Into Selected Shape

`DocumentToolResultPayload.diff.changes[]` (already produced by
`src/ummaya/tools/documents/render.py`) becomes the content fed into CC's
`StructuredPatchHunk` shape. `render_artifacts` (SVG/PNG) demote to evidence.

## Tests / Evidence (measured 2026-06-02)

- TDD: `documentChangeToPatch` unit test (field → hunk lines) — red first
  (`Cannot find module`), then 4/4 green.
- `bun run typecheck` — PASS. `bun run test` (focused gate) — 331 pass / 0 fail.
- Out-of-gate dirs: `tests/tools` + `tests/scripts` 108/0; `adapterManifest`
  27/0; `dispatcher` 21/0.
- Backend parity (no Python change): `pytest tests/tools/documents` 100% pass;
  `pytest tests/evidence tests/ci` 100% pass.
- Reviewer-readable TUI evidence (frame_hash + correlation_id joinable):
  `.evidence/document-diff/{frames.md,manifest.json}` via
  `tui/scripts/dump-document-diff-frames.tsx` (replaces the retired
  `dump-document-render-png`). Captured frames show inline red/green field diffs
  for apply_fill, render, blocked, and a 40-column width-safe case.

## Remaining Blocked Gates / Follow-ups

- Human field labels: `DocumentChangePayload` carries only `target_path`, so a
  raw XML path renders as `hwpx › text[2]`. When the backend can supply a human
  label (the HWPX engine already pairs label/value cells, item 9/10), emit it on
  the change (or as a `label` field) and prefer it in `documentChangeToPatch`.
  Pure-name paths (`성명`, `근무주차`) already render cleanly today.
- The retired raster-gate functions remain as identity pass-throughs for
  call-boundary stability across the 3 primitive tools; full call-site removal
  is a tracked follow-up.
- Multi-page / table-cell anchor disambiguation stays scorecard-gated follow-up
  (geometry no longer user-facing, so de-risked).
- `render.py` page-dimension contract addition not required by D2 (no minimap).
