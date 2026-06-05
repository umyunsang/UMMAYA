# Document Viewport Diff Research Note

Date: 2026-06-01
Scope: Compact and expanded TUI rendering for Public AX document mutations.

## Local Anchors

- UMMAYA thesis: document operations stay inside the Claude Code-style tool loop and existing ToolRegistry primitive flow.
- Active feature artifacts: `specs/2802-public-doc-harness/spec.md`, `plan.md`, `data-model.md`, `tasks.md`,
  `implementation-notes.md`, and `tui-document-implementation-research-2026-06-01.md`.
- Claude Code restored-source status: no direct analog exists for public-document page viewport diffs. The closest
  intact analogs are code/file diff surfaces:
  - `.references/claude-code-sourcemap/restored-src/src/hooks/useTurnDiffs.ts`
  - `.references/claude-code-sourcemap/restored-src/src/components/diff/DiffDialog.tsx`
  - `.references/claude-code-sourcemap/restored-src/src/components/diff/DiffDetailView.tsx`
  - `.references/claude-code-sourcemap/restored-src/src/components/StructuredDiff*.tsx`
  - `.references/claude-code-sourcemap/restored-src/src/components/permissions/FilePermissionDialog/`

Decision: preserve the CC shape of "turn-scoped change source -> compact review -> expandable detail", but replace
text-only hunks with document-render-derived changed viewports whenever page evidence exists.

## 2026-Current Sources

Primary specs and tool-contract references:

- MCP Tools 2025-06-18: tool results may return image content, resource links, embedded resources, structured content,
  and output schemas. Applicability: UMMAYA document tools should expose viewport artifacts as typed structured content
  plus resource-like references, not only prose.
  https://modelcontextprotocol.io/specification/2025-06-18/server/tools
- MCP Resources 2025-06-18: resources have URI, name, title, description, MIME type, size, annotations, and can hold
  text or binary content. Applicability: `document-viewport://...` and local file artifacts should use this resource
  shape for stable TUI/evidence joins.
  https://modelcontextprotocol.io/specification/2025-06-18/server/resources
- WCAG 2.2 Use of Color and Non-text Contrast: color must not be the only cue, and graphical state indicators need
  sufficient contrast. Applicability: changed viewport cards must include before/after labels, sign/text labels, or
  symbols in addition to green/red text.
  https://www.w3.org/WAI/WCAG22/Understanding/use-of-color
  https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast

Document rendering and viewport extraction references:

- `rhwp`: Rust/WASM HWP/HWPX parser, renderer, CLI, SVG export, Canvas/WASM render, and ongoing 2026 HWPX render/save
  compatibility work. Applicability: HWPX page geometry and visual evidence should remain owned by the renderer bridge,
  while UMMAYA owns the harness, artifact lineage, diff anchors, and promotion gate.
  https://github.com/edwardkim/rhwp
- `python-hwpx`: pure Python HWPX parse/edit/generate/validate stack with OPC/XML-first design. Applicability:
  useful for deterministic HWPX write/validation evaluation; not sufficient alone for page-level visual viewport proof.
  https://github.com/airmang/python-hwpx
- `hwpx-mcp-server`: read/search/edit/validate HWPX operations for AI agents. Applicability: confirms that AI-facing
  HWPX operations should be explicit tools and that "read first, copy before risky edits" is the right operational
  shape; UMMAYA keeps native tools instead of adopting an external server wholesale.
  https://github.com/airmang/hwpx-mcp-server
- Playwright `page.screenshot({ clip })`: stable screenshot API with `x`, `y`, `width`, `height`, `fullPage`, `mask`,
  and deterministic styling controls. Applicability: adopt the `clip` contract shape for page viewport artifacts.
  https://playwright.dev/docs/api/class-page
- Sharp `extract`: crop/extract uses integral `left`, `top`, `width`, and `height` coordinates with pre/post resize
  ordering. Applicability: use as the raster extraction boundary if a PNG artifact is produced from SVG/PDF pages.
  https://sharp.pixelplumbing.com/api-resize/#extract

Diff and change-model references:

- ProseMirror `prosemirror-changeset`: maps edit steps into added/deleted ranges with serializable change objects.
  2026 releases added JSON serialization and changed-range support in the surrounding ecosystem. Applicability:
  document diffs need serializable change records and a separate mapping from logical changes to visible ranges.
  https://github.com/ProseMirror/prosemirror-changeset
  https://prosemirror.net/docs/changelog/
- `diff-pdf`: visual PDF diff outputs highlighted PDF differences and supports zoomed visual review. Applicability:
  good visual-diff reference, but GPL/maintenance risk means it is a comparison pattern, not a direct dependency.
  https://github.com/vslavik/diff-pdf
- `pixelmatch`: small image diff library with thresholding, anti-alias handling, and diff output. Applicability:
  useful for optional regression scoring of viewport images, not for primary semantic diff anchoring.
  https://github.com/mapbox/pixelmatch

Terminal rendering references:

- Kitty graphics protocol: supports image identifiers, placements, replacement, deletion, and relative placements.
  Applicability: high-fidelity terminal image mode can be an optional renderer when terminal capability is detected.
  It must not be the only UI because many terminals and test captures cannot guarantee support.
  https://sw.kovidgoyal.net/kitty/graphics-protocol/
- iTerm2 inline images: supports inline image/file transfer through proprietary escape sequences with width, height,
  preserveAspectRatio, and size controls. Applicability: optional macOS-friendly image path, not the base contract.
  https://iterm2.com/3.4/documentation-images.html
- Chafa: converts image data to graphics formats or ANSI/Unicode character art across old and modern terminals.
  Applicability: good fallback/reference for terminal-friendly previews when inline images are unavailable.
  https://github.com/hpjansson/chafa

Recent research and benchmarks:

- DELEGATE-52 (2026): long delegated workflows cause severe silent document corruption, even in frontier models.
  Applicability: UMMAYA must keep immutable originals, deterministic patches, re-read validation, and human-visible
  changed viewport evidence; "LLM says it edited only one field" is not acceptable proof.
  https://arxiv.org/abs/2604.15597
- PPTArena (2025/2026): reliable PowerPoint editing requires native structure, structural diffs, slide images,
  instruction-fidelity checks, visual/layout quality checks, and iterative plan-edit-check loops. Applicability:
  document harness evaluation must combine structural diff and rendered page evidence.
  https://arxiv.org/abs/2512.03042
- OdysseyBench (2025): long-horizon office workflows require multi-step reasoning across Word, Excel, PDF, email,
  and calendars. Applicability: document review must be conversation/tool-loop observable, not hidden in a one-shot
  converter path.
  https://arxiv.org/abs/2508.09124

## Evaluation Criteria

All candidates are scored out of 100.

| Dimension | Weight |
| --- | ---: |
| Original-form visual fidelity in TUI/evidence | 25 |
| Change locality and review clarity | 20 |
| Deterministic typed contract and Evidence Fabric joinability | 20 |
| Terminal compatibility and graceful fallback | 15 |
| Security/privacy/local-only posture | 10 |
| Maintenance, license, and migration cost | 10 |

Hard gates:

- Do not rely on color alone for change meaning.
- Do not claim compact visual diff when no page/render anchor is available.
- Do not render document bytes through remote services.
- Do not mark a mutation ready when structured diff, re-read, or render evidence is missing.
- Do not make terminal inline-image protocol support a required runtime dependency.

## Candidate Loop

| Candidate | Score | Decision | Rationale |
| --- | ---: | --- | --- |
| A. Text-only git-style diff in compact mode | 61 | Reject as final compact UX | It is terminal-friendly and CC-like, but loses original public-form geometry. User specifically asked for original document shape and changed viewport capture. |
| B. TUI parses SVG and draws a text-canvas page preview | 76 | Keep as fallback | Useful when only SVG artifacts are available, but it moves too much render interpretation into Ink and can drift from the renderer's geometry. |
| C. Backend/render bridge generates changed viewport artifacts from rendered pages, TUI displays compact viewport cards, expand shows full pages | 95 | Selected | Best preserves original form, keeps renderer ownership of page geometry, supports artifact/resource contracts, and lets TUI remain a review surface. |
| D. Kitty/iTerm2/Sixel inline images as the primary UI | 73 | Reject as primary, keep optional enhancement | High fidelity when supported, but terminal support and capture reproducibility are uneven. Must be a capability ladder above artifact-backed fallback. |
| E. Full-page expanded render only, no compact changed viewport | 69 | Reject | Full pages are necessary for expand, but compact review still forces the user to visually search for the change. |
| F. Pixel-only visual diff without logical anchors | 70 | Reject as primary, keep regression helper | Pixel diff can detect visual drift but cannot explain field/table/style intent, and anti-alias/font noise can create false positives. |

Selected final shape: Candidate C, with B and D as rendering fallbacks/enhancements and F as optional regression scoring.

## Migration Boundary

Reference-shaped migration:

1. Adopt the CC diff source pattern:
   - turn-scoped change source;
   - compact change summary;
   - expandable detail view;
   - bounded inline payload with artifact spillover.
2. Adopt Playwright/Sharp-style viewport contracts:
   - `page_number`;
   - `clip_rect` with `x`, `y`, `width`, `height`;
   - `scale`;
   - `source_render_artifact_id`;
   - derivative artifact URI/path.
3. Adopt MCP resource/result shape:
   - structuredContent carries `DocumentChangedViewport[]`;
   - content/resource links point to SVG/PNG/text fallback artifacts;
   - output schema validates all required fields.
4. Keep UMMAYA content:
   - document artifact lineage;
   - source and derivative hashes;
   - public-form anchors;
   - HWPX/DOCX/XLSX/PDF/PPTX capability profiles;
   - TUI status/workflow semantics.

## Proposed Model Additions

Add a typed changed-viewport layer, not a TUI-only parser:

```text
DocumentChangedViewport
  viewport_id: string
  change_ids: list[string]
  page_number: int
  source_render_artifact_id: string
  clip_rect: { x: float, y: float, width: float, height: float }
  padding: { x: float, y: float }
  artifact_refs:
    before_svg?: string
    before_png?: string
    after_svg?: string
    after_png?: string
    legacy_svg?: string
    legacy_png?: string
    text_fallback?: string
  anchor_strategy: exact_text_run | table_cell | field_locator | overlay_marker | visual_bbox | unavailable
  confidence: float
  warnings: list[string]
```

TUI rendering rule:

- Compact default: render `DocumentChangedViewport` cards first. Each card shows clean before/after cropped document
  regions in their original page frame, page number, field/table anchor, and short before/after values.
- Expanded mode: render full page evidence artifacts without mutating the page image, plus visible links to each changed
  viewport.
- Fallback: if `changed_viewports` is empty, render structured text diff and a typed reason such as
  `render_anchor_unavailable`.

## Implementation Gates Before Coding

No implementation should be promoted until these tests exist and fail first:

1. Backend: HWPX mutation with clean before/after render crops produces at least one `DocumentChangedViewport` clipped
   around the changed field/table cell.
2. Backend: missing visual anchor returns a valid render result plus `render_anchor_unavailable`, not a false visual
   diff claim.
3. TUI: compact mode prefers changed viewport cards over text hunks when `changed_viewports` exists.
4. TUI: expanded mode shows full page evidence, not only the compact crop.
5. TUI: viewport cards do not rely on color alone; before/after labels, `+`, `-`, page, and anchor labels remain visible
   in text capture.
6. Evidence: PNG/SVG/text captures are generated under `.evidence/` and linked by correlation ID, source hash, derivative
   hash, diff ID, and viewport ID.

## Final Direction

The highest-conformance direction is not "make the terminal look like a full GUI document editor" and it is not "draw
review overlays into the document image". It is:

1. render real document pages with promoted engines;
2. map logical document changes to renderer-visible page anchors;
3. generate deterministic clean before/after changed viewport artifacts around those anchors;
4. show those viewports in compact TUI as the default review unit;
5. preserve full-page expanded evidence for final human review;
6. keep text diff as a fallback and audit companion.

This direction should supersede text-only compact diff as the final UX target for Public AX document review.

## Implementation Loop 1

Status: applied on 2026-06-01.

Implemented the first selected Candidate C slice:

- Added typed `DocumentChangedViewport` and `DocumentClipRect` records to the document diff contract.
- Extended SVG render overlay generation so a visible text anchor produces both an `ummaya-diff-overlay` SVG group and
  a structured changed viewport record linked to the source render artifact.
- Propagated changed viewports through `document_render` tool results.
- Updated the TUI compact document result view to render changed page viewport cards before text hunks.
- Kept expanded mode as the full-page evidence view and retained text diff as fallback/audit companion.

Loop score after implementation:

| Dimension | Target | Current | Notes |
| --- | ---: | ---: | --- |
| Original-form compact review | 25 | 21 | Compact TUI now crops around rendered text anchors, but standalone clipped SVG/PNG artifacts are still follow-up. |
| Change locality and clarity | 20 | 18 | Text-field changes show page crop, `+`/`-` fallback lines, page, and anchor labels. |
| Typed contract/evidence join | 20 | 18 | Viewports are typed and linked to render artifact IDs; Evidence Fabric JSON capture remains to be refreshed. |
| Terminal compatibility | 15 | 13 | SVG-to-text canvas fallback works in Ink; inline image protocol remains optional. |
| Security/privacy/local-only | 10 | 10 | All rendering remains local and artifact-backed. |
| Maintenance/migration cost | 10 | 9 | Reuses existing render bridge and TUI document card; no new dependency. |
| **Total** | **100** | **89** | Promoted over text-only diff, but not final 95 until standalone viewport artifacts and live evidence refresh land. |

## Implementation Loop 2

Status: applied on 2026-06-01.

Raised Candidate C from structured viewport metadata to artifact-backed viewport evidence:

- Each matched SVG change anchor now produces a standalone cropped SVG derivative using the same page-coordinate
  `clip_rect` contract carried by `DocumentChangedViewport`.
- `DocumentChangedViewport` now carries `svg_artifact_ref` and `svg_artifact_path`, so compact TUI rendering can open the
  changed viewport artifact directly instead of reparsing the full-page render first.
- TUI compact mode prefers the viewport SVG artifact when present, while retaining full-page SVG cropping as a fallback.
- Runtime and TUI tests verify that the viewport artifact exists, is tagged with `data-ummaya-viewport-id`, and is the
  source used by compact viewport rendering.

Loop score after implementation:

| Dimension | Target | Current | Notes |
| --- | ---: | ---: | --- |
| Original-form compact review | 25 | 24 | Compact TUI now renders from standalone changed viewport SVG artifacts, with full-page fallback. |
| Change locality and clarity | 20 | 19 | Text-field changes show page crop, `+`/`-` fallback lines, page, anchor labels, and viewport-only evidence. |
| Typed contract/evidence join | 20 | 20 | Viewports are typed and joined by diff ID, render artifact ID, viewport ID, source hash, and local artifact path. |
| Terminal compatibility | 15 | 14 | SVG-to-text canvas fallback works in Ink; inline image protocols remain optional enhancements. |
| Security/privacy/local-only | 10 | 10 | All rendering and viewport extraction remain local and artifact-backed. |
| Maintenance/migration cost | 10 | 9 | Reuses existing render bridge and artifact store; no new dependency. |
| **Total** | **100** | **88** | Superseded by live visual inspection: the SVG artifact existed, but the TUI evidence still rendered as an ASCII/text canvas and did not justify a 96-point claim. |

Reassessment note:

- The previous 96-point score was too high because it counted "artifact-backed viewport exists" as equivalent to
  "user can visually inspect an original-form viewport in the TUI".
- The actual Codex-visible capture showed terminal box drawing and sparse text placement, not a high-fidelity
  original document crop.
- Candidate C remains the correct architecture, but the evidence ladder must add raster viewport artifacts and
  optional terminal inline-image presentation before any 95+ score is defensible.

Remaining scorecard-gated follow-up:

1. Add PNG raster evidence when a local rasterizer is available, without making rasterization a hard runtime dependency.
2. Add Evidence Fabric UX artifacts that show compact viewport and expanded full-page render side by side.
3. Add table-cell/style-only anchor strategies instead of relying only on exact text-run matching.
4. Add optional Kitty/iTerm2/Sixel image presentation above the text-canvas fallback.

## 2026 Refresh: Terminal Image and Resource Contract Loop

Status: applied on 2026-06-01 after the live visual reassessment.

Current primary-source update:

- Kitty graphics protocol defines raster graphics as the terminal-side target and is already used by image-capable
  terminal applications such as file managers, diff tools, and terminal viewers.
- iTerm2 inline images use OSC 1337 `File=...` and support inline display of PNG and other macOS-supported image
  formats, with width/height controls.
- MCP 2025-06-18 tool results explicitly support image content, resource links, embedded resources, structured
  content, and output schemas; this matches UMMAYA's typed viewport records plus local artifact paths.
- Chafa remains a useful fallback/reference for converting images to ANSI/Unicode output, but its LGPL-3 licensing
  and native dependency surface make it a later optional adapter, not the first migration target.

Candidate refresh:

| Candidate | Score | Decision | Rationale |
| --- | ---: | --- | --- |
| Keep SVG-to-ASCII canvas as primary | 64 | Reject | The live capture proves users cannot reliably inspect original document form this way. |
| Add Chafa as required runtime | 78 | Reject for now | Good terminal fallback, but license/native install footprint is too heavy for a required UMMAYA dependency. |
| Generate local PNG viewport artifacts and expose them in typed payloads | 92 | Select | Preserves renderer-owned geometry, produces user-inspectable raster evidence, and keeps local-only privacy. |
| Add Kitty/iTerm2 inline image presentation when supported | 89 | Select as optional tier | High fidelity in compatible terminals, but must gracefully fall back in Codex/CI/headless terminals. |
| Use remote/browser service to render document crops | 0 | Blocked | Violates local document privacy and public-document intake constraints. |

Implementation Loop 3:

- `DocumentChangedViewport` now carries `png_artifact_ref` and `png_artifact_path`.
- SVG changed viewports are optionally rasterized to PNG via local `rsvg-convert` when present; missing rasterizer is
  not a hard failure.
- Compact TUI viewport cards display PNG evidence through the existing Kitty/iTerm2 graphics-protocol ladder when
  supported, and retain visible path + SVG text-canvas fallback otherwise.
- The capture script embeds viewport PNGs above the terminal text frame so reviewer evidence shows the actual crop
  instead of only an ASCII approximation.

Loop score after implementation:

| Dimension | Target | Current | Notes |
| --- | ---: | ---: | --- |
| Original-form compact review | 25 | 23 | PNG viewport artifacts now exist and are embedded in evidence captures; terminals without graphics still fall back to text canvas. |
| Change locality and clarity | 20 | 19 | Compact cards keep page, anchor, `+`/`-` labels, and viewport artifacts. |
| Typed contract/evidence join | 20 | 20 | SVG and PNG viewports are linked by viewport ID, render artifact ID, diff ID, and path. |
| Terminal compatibility | 15 | 14 | Kitty/iTerm2 image tier is optional; headless/Codex capture remains deterministic. |
| Security/privacy/local-only | 10 | 10 | Rasterization is local only; no remote render channel is introduced. |
| Maintenance/migration cost | 10 | 9 | Reuses existing render bridge and prior PDF inline-image pattern; no required new dependency. |
| **Total** | **100** | **95** | Defensible only when PNG evidence is generated; otherwise the runtime should report the lower SVG-text fallback score. |

## Implementation Loop 4

Status: applied on 2026-06-01 after the overlay rejection review.

Research/evaluation correction:

- The overlay approach was demoted because it mutates the review image and can be mistaken for document content. That is
  weak for public-form conformance review, where the evidence should show the original document shape.
- The selected pattern is now clean before/after viewport comparison: the renderer produces unmodified page evidence,
  UMMAYA crops the same viewport from the baseline working copy and the derivative, and the TUI carries the `-`/`+`
  semantic diff outside the document image.
- Pixel/overlay diff may remain a later diagnostic artifact, but it is not the primary compact review surface.

Candidate refresh:

| Candidate | Score | Decision | Rationale |
| --- | ---: | --- | --- |
| After-only crop with text hunk | 82 | Reject as final | Clearer than text-only, but users still need to trust that the shown crop is the changed state rather than compare it to the original. |
| Overlay highlight on derivative page | 80 | Reject as primary | Draws non-document marks into the page image, reducing public-form evidence purity. |
| Pixel-diff mask as primary | 74 | Reject | Good at detecting visual drift, but weak at explaining document intent and noisy under font/raster differences. |
| Clean before/after viewport crops plus external `-`/`+` hunk | 97 | Selected | Preserves original document imagery, makes the change visually comparable, and keeps semantic diff outside the page image. |

Implementation changes:

- `render_document_evidence` now accepts an optional baseline artifact and renders it through the same engine when a diff
  is present.
- Page render artifacts stay clean; no `ummaya-diff-overlay` or `ummaya-diff-change` markup is injected into the
  rendered document.
- `DocumentChangedViewport` now carries clean before/after SVG and PNG artifact refs/paths. Legacy `svg_artifact_path`
  and `png_artifact_path` remain aliases for the after crop for backward compatibility.
- `document_render` resolves the diff source artifact from the runtime store and passes it as the baseline, so compact
  evidence can compare the working copy and derivative.
- Compact TUI cards now show `Before viewport evidence` and `After viewport evidence` paths/inline-image entries, then
  retain the text hunk as the semantic audit layer.
- The PNG capture script now embeds before/after clean crops side by side above the terminal text frame.

Loop score after implementation:

| Dimension | Target | Current | Notes |
| --- | ---: | ---: | --- |
| Original-form compact review | 25 | 25 | Before/after PNG crops are clean page evidence, not marked-up derivative pages. |
| Change locality and clarity | 20 | 20 | Compact evidence shows only changed viewports plus the semantic `-`/`+` hunk. |
| Typed contract/evidence join | 20 | 20 | Before/after SVG/PNG artifacts are joined by viewport ID, render artifact ID, diff ID, source hash, and derivative hash. |
| Terminal compatibility | 15 | 14 | Image-capable terminals can inline PNGs; Codex/headless capture embeds PNGs; plain terminals keep path + SVG text fallback. |
| Security/privacy/local-only | 10 | 10 | Baseline and derivative renders remain local; no remote document rendering. |
| Maintenance/migration cost | 10 | 9 | Reuses the render bridge and artifact store; no required dependency added. |
| **Total** | **100** | **98** | Highest current score. Remaining point loss is from plain-terminal fallback quality and non-text/style anchor coverage. |

## Implementation Loop 5: Full-Page Render Camera Contract

Status: selected on 2026-06-01 after user approval of the viewport-camera final rendering direction.

Research/evaluation correction:

- Clean before/after crop artifacts improved visual evidence, but they still made the cropped image the apparent runtime
  contract. The approved direction is stricter: full-page render artifacts are the source of truth, and changed regions
  are selected by `viewport_rect` as a camera/viewBox.
- Claude Code has no direct public-document analog. The closest intact restored-source references remain the message
  expand/collapse and diff-detail surfaces: turn-scoped changes stay compact by default and expand into a richer detail
  view. UMMAYA's sanctioned divergence is the document renderer bridge and public-form evidence contract.
- Current primary references reinforce this boundary:
  - MCP Tools 2025-06-18 structured content keeps machine-readable result data separate from textual fallback.
  - MCP Resources 2025-06-18 resource metadata supports MIME typed binary artifacts.
  - Kitty graphics protocol supports display source rectangles (`x`, `y`, `w`, `h`) and bounded cell placement.
  - iTerm2 inline images support terminal image display, but not a portable source-rectangle contract; therefore it
    stays an optional whole-image display tier.
  - Ink remains the React/Yoga layout host; image escape sequences are an enhancement, not a replacement for typed
    artifact/resource metadata.

Candidate refresh:

| Candidate | Score | Decision | Rationale |
| --- | ---: | --- | --- |
| Persist cropped viewport artifacts as the primary contract | 88 | Demote to compatibility | Visually useful, but it hides whether the crop came from the full page and weakens lineage semantics. |
| Full-page raster/SVG artifact + `viewport_rect` camera for compact and expand | 99 | Selected | Best matches user approval, keeps renderer output immutable, lets compact focus only changed regions, and lets expand show the whole page with anchors. |
| Terminal image protocols as the required primary renderer | 84 | Reject as required | Kitty is strong and supports source rectangles, but iTerm2/headless/CI do not provide the same contract. |
| Browser/WebView document review surface | 79 | Reject for this TUI pass | High visual fidelity but leaves the Claude Code-style terminal harness and adds a second UI runtime. |
| ASCII/SVG text canvas fallback | 52 | Reject as final | Useful only as a diagnostic fallback; it is not original-form document rendering. |

Selected implementation boundary:

1. Add optional full-page raster evidence to `RenderArtifactRecord` when SVG render output can be rasterized locally.
2. Treat `DocumentChangedViewport.clip_rect` as the canonical camera rectangle; before/after cropped artifacts become
   compatibility evidence, not the primary contract.
3. Compact TUI shows `Document viewport diff` with before/after viewport-camera evidence and semantic `-`/`+` lines.
4. Expanded TUI shows `Document expand mode`, full-page render evidence, and a numbered document diff rail that links
   each rail entry to the same `viewport_rect`.
5. No ASCII page canvas is acceptable in the approved path. If a terminal cannot inline images, the TUI must show typed
   resource paths and camera coordinates rather than pretending to render the page as box-drawing text.

Loop 5 pass criteria:

- Backend render records expose full-page PNG raster evidence when local rasterization is available.
- TUI compact output no longer says `Changed page viewport`; it says `Document viewport diff` and shows before/after
  evidence plus semantic changed values.
- TUI expanded output no longer emits `Document page preview` or box-drawing page canvases; it shows full-page render
  evidence and a document diff rail.
- Capture artifacts show compact camera evidence and expanded full-page evidence generated from the same full-page render
  artifact and `viewport_rect`.

Implementation Loop 5 result:

- `RenderArtifactRecord` now carries optional full-page PNG raster artifact refs/paths beside the immutable full-page SVG
  render artifact.
- `DocumentChangedViewport.clip_rect` remains the canonical camera rectangle. Cropped before/after artifacts are retained
  as compatibility/evidence helpers, but compact review is labelled and scored as a viewport-camera diff, not as the
  primary storage contract.
- Compact TUI renders `Document viewport diff` blocks with before/after viewport evidence, semantic `-`/`+` values,
  page number, target path, and `viewport_rect` coordinates.
- Expanded TUI renders `Document expand mode`, full-page render evidence, and a numbered document diff rail. The old
  SVG-to-ASCII page canvas is no longer the promoted expanded path.
- The Codex-visible evidence capture was regenerated from the real 13-week HWPX smoke payload:
  `.evidence/tui-document-render-png/01-compact-viewport-camera.png` and
  `.evidence/tui-document-render-png/02-expand-full-page-camera.png`.

Loop score after implementation:

| Dimension | Target | Current | Notes |
| --- | ---: | ---: | --- |
| Original-form compact/expanded review | 25 | 24 | Compact and expanded captures show real rasterized document evidence. One point remains because non-image terminals still fall back to resource paths. |
| Change locality and clarity | 20 | 20 | Compact shows only changed viewports; expand shows full page plus rail. |
| Typed contract/evidence join | 20 | 20 | Full-page render, full-page raster, viewport rects, before/after artifacts, diff ID, and hashes are joined through the result payload. |
| Terminal compatibility | 15 | 14 | Kitty source-rectangle support is implemented as an optional tier; iTerm2/headless paths remain whole-image/path based. |
| Security/privacy/local-only | 10 | 10 | Rasterization uses only the local `rsvg-convert` executable when present; no remote renderer is introduced. |
| Maintenance/migration cost | 10 | 9 | No required dependency was added, but non-text/style anchors remain follow-up work. |
| **Total** | **100** | **97** | Promotion-worthy for text-run HWPX changes with local raster evidence. Not a universal 99 until style-only/table-cell anchor coverage and terminal image parity improve. |

## Implementation Loop 6: Corrected Full-Page Camera Contract

Status: applied on 2026-06-02 after the capture-vs-runtime mismatch review.

Correction:

- The Loop 5 score over-counted evidence captures as runtime TUI rendering. The Codex `TERM=dumb` frame could only show
  resource paths, while the PNG proof had been composed by the capture script above the Ink frame.
- The promoted contract is not cropped before/after PNG storage. Cropped artifacts may remain compatibility/cache
  evidence, but compact and expand review must be derived from immutable full-page before/after render artifacts plus a
  `viewport_rect` camera.

Implemented contract:

```ts
DocumentViewportCamera {
  source_render_artifact_id: string
  baseline_render_artifact_id: string
  page_index: number
  viewport_rect: { x: number; y: number; width: number; height: number }
  zoom: number
  change_ids: string[]
}
```

Implementation changes:

- Backend render output now writes baseline full-page render artifacts when a diff source artifact is available.
- `DocumentDiff` now carries `baseline_render_artifacts` and `viewport_cameras` beside `render_artifacts` and
  `changed_viewports`.
- Compact TUI now prefers full-page camera evidence: baseline full-page render + source full-page render + shared
  `viewport_rect`.
- Expanded TUI now lists page anchors from the same `viewport_cameras`, and the capture artifact overlays numbered
  anchors on the full page.
- The capture script derives compact minimap/before/after viewport panels from full-page raster images and camera
  rectangles. It no longer needs cropped viewport PNG artifacts for the promoted path.

Updated evidence:

- Compact: `.evidence/tui-document-render-png/01-compact-viewport-camera.png`
- Expand: `.evidence/tui-document-render-png/02-expand-full-page-camera.png`
- Runtime payload: `.evidence/tui-document-render-png/payloads.json` now includes one baseline full-page render artifact
  and six viewport cameras for the 13-week HWPX smoke document.

Revised score:

| Dimension | Target | Current | Notes |
| --- | ---: | ---: | --- |
| Full-page-origin visual evidence | 25 | 25 | Compact and expand are now derived from full-page raster artifacts plus camera rectangles. |
| Change locality and clarity | 20 | 20 | Compact shows minimap, before viewport, after viewport, and semantic `-`/`+` lines. |
| Typed contract/evidence join | 20 | 20 | Baseline render, source render, camera rectangle, diff ID, and change IDs are all typed. |
| Terminal runtime honesty | 15 | 13 | Image-capable terminals can inline images; `TERM=dumb` is explicitly path/evidence mode, not a false visual pass. |
| Security/privacy/local-only | 10 | 10 | All render and raster work remains local. |
| Maintenance/migration cost | 10 | 9 | No required dependency added; style-only/table-cell geometry remains follow-up. |
| **Total** | **100** | **97** | Corrected 97: valid for full-page-camera evidence, with terminal capability and non-text anchors still limiting final promotion. |

## Implementation Loop 7: Visual-Only Final Render Separation

Status: applied on 2026-06-02 after review of the generated final render PNGs.

Correction:

- The final render PNGs still included the raw TUI audit frame below the visual document evidence. That mixed two
  surfaces that must stay separate:
  - visual approval surface: document minimap, before/after viewport, full-page anchors, and diff rail;
  - audit/evidence surface: tool status, workflow, artifact paths, diff ID, and raw structured frame.
- The corrected output keeps the audit frame in the `.txt` artifact and removes it from the default SVG/PNG approval
  render.

Implementation changes:

- `tui/scripts/dump-document-render-png.tsx` now emits visual-only SVG/PNG by default.
- Raw TUI frame text is still written to the sibling `.txt` file for evidence review.
- `UMMAYA_TUI_DOCUMENT_RENDER_INCLUDE_FRAME=1` can be used when an explicit all-in-one debug render is needed.
- `UMMAYA_TUI_DOCUMENT_RENDER_OUT_DIR` lets tests and tools write isolated capture directories.
- Compact visual keeps only the minimap, before viewport, after viewport, and concise `-`/`+` change summaries.
- Expanded visual keeps only the full-page render, numbered anchors, and right-side `Document diff rail`.

Updated visual artifacts:

- `.evidence/tui-document-render-png/01-compact-viewport-camera.png`
- `.evidence/tui-document-render-png/02-expand-full-page-camera.png`

Audit artifacts remain available at:

- `.evidence/tui-document-render-png/01-compact-viewport-camera.txt`
- `.evidence/tui-document-render-png/02-expand-full-page-camera.txt`

## Implementation Loop 8: Compact Selected-Viewport Approval Surface

Status: applied on 2026-06-02 after comparison against the approved compact viewport-camera mock.

Correction:

- The Loop 7 visual-only artifact still stacked multiple changed viewport rows in compact mode. That made compact mode
  look like a capture report instead of the approved review surface.
- The approved compact contract is one selected changed viewport at a time: full-page minimap, before viewport, after
  viewport, and the `-`/`+` semantic change summary for that selected camera.
- Expanded mode remains the multi-anchor full-page review surface with the document diff rail.

Implementation changes:

- `tui/scripts/dump-document-render-png.tsx` now selects one compact viewport camera group by
  `selected_camera_index`, defaulting to the first changed camera.
- Compact summary text is resolved through the selected camera's `change_ids`, so the visible `-`/`+` lines are tied
  to the same `viewport_rect` as the minimap and before/after viewports.
- Compact visual labels now include `Selected change N / M`, while non-selected cameras are not rendered in the
  default compact approval artifact.

Updated evidence:

- Compact: `.evidence/tui-document-render-png/01-compact-viewport-camera.png`
- Expand: `.evidence/tui-document-render-png/02-expand-full-page-camera.png`

Revised score:

| Dimension | Target | Current | Notes |
| --- | ---: | ---: | --- |
| Approved compact visual match | 25 | 25 | Compact now renders one selected minimap/before/after comparison card. |
| Change locality and clarity | 20 | 20 | Only the selected changed region is visible in compact mode, with matching `-`/`+` values. |
| Typed contract/evidence join | 20 | 20 | Selected summary follows `viewport_cameras[].change_ids` and the full-page render camera contract. |
| Terminal runtime honesty | 15 | 13 | Image-capable terminals can inline images; `TERM=dumb` remains path/evidence mode. |
| Security/privacy/local-only | 10 | 10 | All render and raster work remains local. |
| Maintenance/migration cost | 10 | 9 | No required dependency added; style-only/table-cell geometry remains follow-up. |
| **Total** | **100** | **97** | Corrected visual approval surface. Remaining limits are terminal image parity and non-text anchors, not compact layout. |

## Implementation Loop 9: Before/After Diff Color Boxes

Status: applied on 2026-06-02 after visual review found the compact card lacked red/green change boxes.

Correction:

- Compact mode had the selected minimap and before/after viewport camera panels, but only the text summary carried the
  diff colors. The before/after document viewports did not visually encode deletion/addition.
- The corrected compact view keeps the document raster clean and draws only camera-bound review boxes:
  - red box on the `Before` viewport;
  - green box on the `After` viewport.
- This preserves the approved full-page artifact plus `viewport_rect` contract. The boxes are review-layer SVG strokes,
  not mutations of the stored render artifact.

Implementation changes:

- `RasterPanel` now carries a bounded `diffRole` for compact before/after panels.
- `renderRasterPanel` draws `diffRemovedBox` and `diffAddedBox` rectangles inside cropped viewport-camera panels.
- The capture regression test asserts that compact selected-camera SVG contains both red and green diff box classes.

Updated evidence:

- Compact: `.evidence/tui-document-render-png/01-compact-viewport-camera.png`

Revised score:

| Dimension | Target | Current | Notes |
| --- | ---: | ---: | --- |
| Approved compact visual match | 25 | 25 | Compact now shows selected minimap plus red before / green after viewport boxes. |
| Change locality and clarity | 20 | 20 | The visible document area and semantic `-`/`+` text now use matching diff colors. |
| Typed contract/evidence join | 20 | 20 | Diff boxes are generated from the selected `viewport_rect` and panel role. |
| Terminal runtime honesty | 15 | 13 | Image-capable terminals can inline images; `TERM=dumb` remains path/evidence mode. |
| Security/privacy/local-only | 10 | 10 | Review boxes are local SVG evidence only; no remote rendering. |
| Maintenance/migration cost | 10 | 9 | No required dependency added. |
| **Total** | **100** | **97** | Compact visual mismatch corrected. Remaining limits are terminal image parity and non-text anchors. |
