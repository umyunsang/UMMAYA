# Document Viewer Bridge Method Research

Date: 2026-06-02

Scope: Find the best implementation method for compact and expanded Public AX
document rendering after retiring terminal inline-image protocols.

## Deep Research Migration Note

- Local anchors:
  - `docs/vision.md`
  - `docs/requirements/ummaya-migration-tree.md`
  - `specs/2802-public-doc-harness/spec.md`
  - `specs/2802-public-doc-harness/terminal-render-reset-2026-06-02.md`
  - `specs/2802-public-doc-harness/document-viewport-diff-research-2026-06-01.md`
- CC restored-source status:
  - No direct public-document page renderer exists in restored Claude Code.
  - Closest intact sources are file-read result cards, image attachment links,
    structured diff rendering, and separate desktop preview/diff surfaces.
- Selected approach:
  - Build an artifact-scoped local document review viewer as the promoted
    document render surface.
  - The TUI controls tool flow and viewer focus, but the user-facing compact
    and expand surfaces are rendered as document-shaped browser/WebView pages,
    not terminal metadata.

## Current Sources

- Claude Code Desktop preview pane: HTML, PDF, image, and video paths open in a
  preview pane, and code changes use a separate diff viewer. This supports the
  split between terminal control plane and rich visual review surface.
  https://code.claude.com/docs/en/desktop
- Claude Code terminal configuration: terminal behavior is delegated to the
  terminal app. This reinforces that document fidelity cannot depend on a
  terminal emulator.
  https://code.claude.com/docs/en/terminal-config
- Playwright screenshots: supports full-page and locator/region screenshots,
  which maps directly to the viewer proof gate for compact and expanded
  document review.
  https://playwright.dev/docs/screenshots
- PDF.js: browser PDF renderer and viewer reference. It is the right reference
  for PDF-native viewing when PDF artifacts are in scope; for HWPX and OOXML
  artifacts UMMAYA can still render page evidence to SVG/PNG first.
  https://github.com/mozilla/pdf.js
- MDN blob URLs: browser-native local object URLs can represent generated page
  assets without remote upload.
  https://developer.mozilla.org/en-US/docs/Web/URI/Reference/Schemes/blob
- Tauri v2 security: viable future native WebView shell, but requires an ADR for
  CSP, command scopes, artifact size, and packaging impact.
  https://v2.tauri.app/security/
- Electron security: useful comparison for desktop shells, but heavier than
  required for the first viewer bridge.
  https://www.electronjs.org/docs/latest/tutorial/security
- OpenSeadragon: mature browser image viewer for pan/zoom, navigator, viewport
  control, and overlays. Strong candidate if UMMAYA needs a package-backed
  viewport engine for large or multi-page documents.
  https://openseadragon.github.io/

## Evaluation Criteria

| Criterion | Weight |
| --- | ---: |
| User-visible original-form document rendering | 25 |
| Compact changed-region clarity | 15 |
| Expanded full-page review quality | 15 |
| CC harness fit | 15 |
| Local-only privacy/security | 10 |
| Evidence Fabric and Playwright testability | 10 |
| Dependency and packaging risk | 10 |

Hard gates:

- No iTerm2, Kitty, Sixel, or terminal image escape sequences.
- No ASCII, Unicode canvas, path-only, artifact-ID-only, hash-only, or raw
  metadata display as the promoted document review surface.
- No remote document rendering or external asset fetch.
- Compact and expand must both render document-shaped pages.
- Metadata is allowed only in evidence/debug records, not in the primary user
  surface.

## Candidate Scorecard

| Candidate | Score | Decision | Rationale |
| --- | ---: | --- | --- |
| A. Terminal-native structured text only | 58 | Reject as review surface | Good CC fit, but not original-form document rendering. May remain as hidden debug or emergency textual explanation. |
| B. Static artifact links opened manually | 67 | Reject as primary | Honest and low risk, but the user still sees links/paths instead of the document surface. |
| C. Artifact-scoped local HTML viewer generated per render | 94 | Select P0 | No new runtime dependency, local-only, browser-compatible, can render full-page SVG/PNG evidence, supports compact and expand routes, and is easy to screenshot with Playwright. |
| D. Localhost viewer server with route/state API | 91 | Select as P0 extension | Better focus/update behavior than static files, but has server lifecycle complexity. Use only if static hash routes are insufficient. |
| E. OpenSeadragon-backed local viewer | 90 | P1 package candidate | Strong pan/zoom/navigator/overlay primitives, but needs dependency approval. Use when large-page or multi-page navigation outgrows vanilla viewer code. |
| F. PDF.js-native viewer as universal viewer | 78 | Partial, format-specific | Strong for PDF, but HWPX/DOCX/PPTX/XLSX need page render artifacts first. Use PDF.js only for PDF-native paths. |
| G. Tauri native WebView viewer | 86 | P1 shell candidate | Strong desktop fit and local-only posture, but requires ADR and packaging work. |
| H. Electron native viewer | 74 | Reject for now | Capable but heavier security and packaging burden than Tauri or local browser viewer. |

## Selected Method

The most congruent implementation method is:

```text
Document tool result
  -> immutable full-page render artifacts
  -> DocumentViewerArtifact manifest
  -> generated local viewer HTML/CSS/JS
  -> TUI opens/focuses compact or expand viewer state
  -> Playwright captures viewer screenshot evidence
  -> Evidence Fabric stores hidden metadata and screenshot joins
```

This method keeps the Claude Code-style TUI as the tool-loop control plane while
moving original-form visual review into a real browser/WebView document surface.

## User-Facing Viewer Contract

Compact viewer:

- First visible screen is the changed document region.
- Layout:
  - left: page minimap in original document shape;
  - middle: before viewport in original document shape;
  - right: after viewport in original document shape;
  - rail: concise `- before` / `+ after` labels attached to the viewport
    review, not raw metadata.
- Red/green state is communicated by before/after pane framing and the diff
  rail, not by SVG boxes drawn over the document image.
- No artifact ID, hash, file path, raw `viewport_rect`, or JSON-like payload is
  visible by default.

Expanded viewer:

- First visible screen is the full document page in original form.
- Changed anchors are represented in the diff rail and hidden manifest, not as
  overlay marks drawn on top of the full-page document.
- Diff rail lists anchors in human labels.
- Future focus/navigation uses the hidden `viewport_rect` manifest contract;
  P0 does not draw focus marks over the full-page document.
- Before/after comparison is available without leaving the document-shaped
  viewer.
- Metadata remains hidden behind debug/evidence output.

## Runtime Boundary

P0 implementation boundary:

- Generate a self-contained viewer directory per document render result.
- Store:
  - `viewer.html`
  - `viewer.css`
  - `viewer.js`
  - `viewer-manifest.json`
  - full-page SVG/PNG render assets
  - optional before/after page assets
- Use hash or query routing:
  - `viewer.html#compact:change-01`
  - `viewer.html#expand:page-1`
- Open the viewer with the existing `openPath()` path opener for local files.
- For verification, use Playwright against the `file://` URL when assets are
  same-directory and against a loopback server only when browser restrictions or
  PDF.js require HTTP.

P0 extension:

- Add an ephemeral localhost viewer server only if the static viewer cannot
  reliably focus/update open viewer windows.
- Bind to `127.0.0.1`, never `0.0.0.0`.
- Serve only artifact-store viewer directories.
- No external network fetches.

P1 candidates:

- OpenSeadragon: add only if large/multi-page zoom, minimap, and overlay
  behavior becomes too complex for a small vanilla viewer module.
- Tauri: add only after ADR covering Rust boundary, local-only execution,
  license, artifact size, CSP, command scopes, and packaging impact.

## Test And Evidence Gates

Focused tests:

- TUI/document render path must not emit iTerm2, Kitty, or Sixel escape
  sequences.
- Compact and expand tool-result rendering must not show artifact IDs, hashes,
  raw file paths, or raw `viewport_rect` as the primary user-facing result.
- Viewer manifest must include render artifact IDs, diff IDs, page indexes, and
  `viewport_rect` values as hidden evidence data.
- Generated compact viewer must contain document-shaped before/after panes,
  red/green pane framing, and no `change-box`/`anchor-group` overlay markup.
- Generated expanded viewer must contain a full-page document surface and anchor
  rail.

Visual verification:

- Playwright screenshot of compact viewer.
- Playwright screenshot of expanded viewer.
- Pixel or DOM assertions:
  - document page is nonblank;
  - before/after panes exist;
  - diff rail and pane framing communicate before/after state;
  - no `change-box` or `anchor-group` overlay nodes are present;
  - hidden metadata is not primary visible text;
  - hidden manifest preserves the viewport focus contract.

Live TUI proof:

- Run `bun run tui` with ordinary user phrasing.
- Verify the model selects document tools.
- Verify the TUI opens/focuses viewer mode.
- Verify the user-facing visible review is a document-shaped compact or expand
  viewer, not a metadata card.

## Implementation Order

1. Remove document-path inline image protocol code and success tests.
2. Add failing tests for "no terminal image escape" and "no metadata-only
   compact/expand review".
3. Add `DocumentViewerArtifact` and viewer manifest types.
4. Generate artifact-scoped viewer HTML/CSS/JS from current render result.
5. Wire document render tool result to open compact/expand viewer states.
6. Add Playwright visual evidence capture.
7. Run focused TUI tests and live `bun run tui` proof.

## 2026-06-02 Implementation Loop Result

- Completed:
  - Removed the terminal image protocol success path from document render
    gating.
  - Added a local viewer bridge for compact and expanded document review.
  - Ensured successful compact/expanded TUI output hides artifact IDs, paths,
    engine IDs, MIME types, raw `viewport_rect`, and diff target paths.
  - Preserved fail-closed behavior when the tool result has no readable
    full-page render asset.
  - Promoted SVG full-page render artifacts as valid viewer inputs; PNG remains
    valid when present.
  - Added compact viewer checks for minimap, before viewport, after viewport,
    and red/green pane framing without document-image overlay boxes.
  - Added expanded viewer checks for full-page document surface, numbered
    diff rail items, and no full-page document overlay anchors.
- Verified:
  - `cd tui && bun test tests/tools/_shared/documentToolResultRender.test.ts tests/primitive/dispatcher.test.tsx --timeout 30000`
  - `cd tui && bun run typecheck`
  - `cd tui && bun run test`
  - Real non-verbose `bun run tui` user query:
    `정확한 파일은 /Users/um-yunsang/Downloads/SW중심대학사업 현장미러형연계프로젝트 주간활동일지(학과_팀명).hwpx 이야. 이 파일을 13주차로 작성하고 변경사항은 compact document viewer로 보여줘`
  - Live TUI result: the model selected the document tool flow and rendered a
    single compact `Document viewer` status, not repeated workflow/log text.
  - Generated viewer artifact:
    `.evidence/tui-document-viewer-live/document-viewer-cb5d556e6455c1d3/viewer.html`
  - Viewer artifact contains compact mode, Minimap, Before viewport, After
    viewport, red/green pane framing, and no document-image overlay boxes.
- Remaining gate:
  - Capture the generated viewer with Playwright as a PNG UX artifact in the
    next visual-evidence loop.

## Final Recommendation

Select Candidate C as P0:

**artifact-scoped local HTML document viewer generated from immutable render
artifacts, controlled by the TUI, verified by Playwright screenshots.**

Do not adopt OpenSeadragon, Tauri, or Electron in the first implementation
loop. They remain scored candidates for later escalation only after the vanilla
viewer fails a concrete large-document, multi-page, focus, or packaging gate.
