# Terminal Render Direction Reset

Date: 2026-06-02

Scope: Public AX document review surfaces after rejecting terminal inline-image
protocols for document rendering.

## Decision

Terminal inline-image protocols are retired from the Public AX document harness
render contract. They are not downgraded to an optional tier. They are removed
from the promoted document-render path because terminal graphics support is
terminal-emulator-specific, not a property of the shell, the UMMAYA harness, or
the document renderer.

The selected replacement direction is:

1. Keep the TUI as the Claude Code-style control plane for tool calls, workflow
   status, approval, and focus/navigation commands.
2. Render original-form document pages in a local viewer bridge backed by
   immutable full-page render artifacts, `viewport_rect` cameras, and
   document-diff anchors.
3. Use compact mode to render the changed region as an original-form document
   viewport in the viewer surface. The user-facing compact view must look like
   a document excerpt, not an artifact log, file manifest, or metadata card.
4. Use expand mode to render the full original-form document page in the same
   viewer surface, with anchor rail and before/after viewport cameras.
5. Treat the render proof as successful only when the local viewer artifact is
   openable and screenshot-verifiable through the real pipeline.

## Local Anchors

- UMMAYA thesis: `docs/vision.md` and
  `docs/requirements/ummaya-migration-tree.md` keep the Claude Code-style tool
  loop as the harness foundation. Document rendering is a public-service
  evidence surface, not a new root primitive.
- Active feature: `specs/2802-public-doc-harness/spec.md` requires render
  evidence, re-read validation, structured diffs, and public-form conformance
  gates for HWPX, HWP, DOCX, PDF, XLSX, and PPTX.
- Prior viewport-camera note:
  `specs/2802-public-doc-harness/document-viewport-diff-research-2026-06-01.md`
  selected `full-page render artifact + viewport_rect + change_ids`, but still
  left inline image protocols as a possible terminal tier. That optional tier is
  now superseded.

## Claude Code Restored-Source Check

Status: no direct public-document page renderer exists in restored Claude Code.

Closest intact analogs:

- `.references/claude-code-sourcemap/restored-src/src/tools/FileReadTool/UI.tsx`
  renders image/PDF read results as concise textual tool-result cards such as
  `Read image (...)` and `Read PDF (...)`; it does not draw image bytes inside
  the terminal.
- `.references/claude-code-sourcemap/restored-src/src/components/messages/UserImageMessage.tsx`
  renders image attachments as labels or file hyperlinks when hyperlink support
  exists; it does not use iTerm2, Kitty, Sixel, or other inline graphics.
- `.references/claude-code-sourcemap/restored-src/src/components/StructuredDiff/Fallback.tsx`
  keeps diffs terminal-native with `+`/`-`, color, wrapping, and word-level
  highlighting.
- Claude Code Desktop documentation describes a separate preview pane for HTML,
  PDF, image, and video paths and a separate diff viewer for code review.

Conclusion: the CC-shaped migration is not "draw document pages in the
terminal." It is "keep terminal message/diff/tool surfaces compact and open
rich visual artifacts in a first-class preview/viewer surface."

## 2026-Current Sources

- Claude Code terminal configuration: terminal theming is delegated to the
  terminal application, and file-based workflows are preferred for large
  content. Applicability: terminal rendering should not become the document
  fidelity contract.
  https://code.claude.com/docs/en/terminal-config
- Claude Code Desktop: HTML, PDF, image, and video paths open in the preview
  pane; code changes use a diff viewer. Applicability: rich visual artifacts
  belong in a viewer surface, while the terminal/chat remains the control plane.
  https://code.claude.com/docs/en/desktop
- iTerm2 inline images: the protocol is proprietary OSC 1337 file transfer and
  inline display. Applicability: rejected because it is terminal-specific and
  not a portable harness contract.
  https://iterm2.com/3.3/documentation-images.html
- Kitty graphics protocol: powerful raster graphics with source rectangles and
  placement, but it is still a terminal-emulator protocol with multiplexer and
  implementation variability. Applicability: rejected for the promoted
  document-review path despite strong capabilities.
  https://sw.kovidgoyal.net/kitty/graphics-protocol/
  https://sw.kovidgoyal.net/kitty/kittens/icat/
- WezTerm image protocol: implements iTerm2 image support but documents version
  and multiplexer limitations. Applicability: confirms portability risk.
  https://wezterm.org/imgcat.html
- PDF.js: web-standards PDF renderer with browser viewer and Canvas/Web Worker
  architecture. Applicability: selected reference for PDF viewer surfaces and
  browser-compatible page rendering where PDF artifacts are in scope.
  https://github.com/mozilla/pdf.js
- MDN blob URLs and secure local origins: local `localhost` and `file://` are
  generally trustworthy contexts; blob URLs can attach generated image/canvas
  data to viewer DOM surfaces. Applicability: use local-only viewer artifacts
  without remote upload.
  https://developer.mozilla.org/en-US/docs/Web/URI/Reference/Schemes/blob
  https://github.com/mdn/content/blob/main/files/en-us/web/security/defenses/secure_contexts/index.md
- Tauri v2 security: Tauri relies on OS WebViews and emphasizes trust-boundary
  and CSP design. Applicability: viable future packaged viewer bridge when a
  native desktop shell is justified, but not required for the first reset.
  https://v2.tauri.app/security/
- Electron security: BrowserWindow can sandbox renderers and isolate contexts,
  but Electron adds heavier runtime and security configuration burden.
  Applicability: rejected for the first reset unless a later desktop shell ADR
  justifies it.
  https://www.electronjs.org/docs/latest/tutorial/security

## Scorecard

Weights:

| Criterion | Weight |
| --- | ---: |
| Original-form visual fidelity | 25 |
| Environment portability | 20 |
| Claude Code harness fit | 20 |
| Evidence Fabric joinability | 15 |
| Security/privacy/local-only posture | 10 |
| Migration cost and dependency risk | 10 |

Candidates:

| Candidate | Score | Decision | Rationale |
| --- | ---: | --- | --- |
| Terminal inline-image protocols | 48 | Retire | High fidelity only in selected terminal emulators. Fails portability, CI/Codex PTY proof, and CC source parity. |
| ASCII/Unicode/Sixel page canvas | 35 | Reject | Terminal-compatible but not original-form document rendering. User explicitly rejected ASCII/canvas-like output. |
| Text-only structured document diff | 61 | Keep for compact summary only | CC-like and robust, but insufficient for visual public-form review. |
| Local artifact links only | 70 | Keep as degraded control-plane state | Honest and portable, but too weak as the promoted review experience. |
| Local browser/static viewer bridge | 92 | Select P0 | Uses full-page artifacts, `viewport_rect`, anchors, and screenshots. Minimal runtime burden and strong portability through ordinary browsers/localhost. |
| Tauri native viewer bridge | 86 | Select P1 candidate | Strong local desktop fit and Rust boundary, but requires ADR/dependency justification and packaging work. |
| Electron native viewer bridge | 76 | Reject for now | Good rendering but heavier runtime and security overhead than needed. |

## Selected Contract

Runtime payload:

```ts
type DocumentViewerArtifact = {
  viewer_artifact_id: string
  viewer_url: string
  mode: 'compact' | 'expand'
  page_index: number
  source_render_artifact_id: string
  baseline_render_artifact_id?: string
  viewport_rect?: { x: number; y: number; width: number; height: number }
  change_ids: string[]
  document_diff_id: string
  local_only: true
}
```

TUI compact mode:

- Opens or focuses a local viewer route in compact mode.
- The visible surface renders a before/after document viewport using the
  original page render and `viewport_rect`.
- The changed region is marked inside the document-shaped viewport with
  red/green change boxes and accessible non-color labels.
- The TUI may show a short human command status such as `Document viewer
  opened`, but it must not show artifact IDs, render paths, hashes, raw
  `viewport_rect`, or resource metadata as the primary user-facing result.
- Does not emit terminal image escape sequences.
- Does not mark visual render success unless viewer artifact validation passes.

TUI expand mode:

- Opens or focuses the local viewer bridge route.
- Viewer shows the full page in original form.
- Viewer displays a diff rail with anchors.
- Selecting an anchor applies the same `viewport_rect` camera to before/after
  panes.
- Metadata such as viewer artifact ID, route, render hash, screenshot path, and
  Evidence Fabric join keys is recorded in evidence/debug output only. It is not
  rendered as the primary user-facing document review surface.

Viewer bridge:

- P0: local static HTML or localhost route generated from artifact store output.
- P1: Tauri WebView wrapper only after ADR covers license, artifact size,
  platform behavior, CSP, and local-only execution.
- Never remote-render public documents.

## Implementation Reset

Remove from the document harness path:

- `UMMAYA_TUI_INLINE_IMAGE_PROTOCOL`
- `detectGraphicsSupport()` for document page preview
- `emitKittyImage()`
- `emitIterm2Image()`
- tests that assert OSC 1337 or Kitty APC image output as document-render
  success
- success gates that treat terminal graphics as proof

Replace with:

- `DocumentViewerBridge` payload and component boundary
- viewer artifact generation from the existing full-page render artifacts
- compact/expand viewer routes that render document-shaped UI, not metadata
  cards
- Playwright/browser screenshot evidence for visual proof
- tests that fail when TUI emits inline-image escape sequences in the document
  path
- tests that fail when compact or expand document review renders only artifact
  IDs, file paths, hashes, raw `viewport_rect`, or other log-like metadata in
  place of the document-shaped viewer

## Exit Criteria

1. No document renderer code writes iTerm2, Kitty, or Sixel image escape
   sequences.
2. Compact mode presents an original-form before/after document viewport for
   the changed region. Log-like artifact metadata is absent from the primary
   user-facing surface.
3. Expand mode presents the original-form full page with document anchors and
   diff rail. Log-like artifact metadata is absent from the primary
   user-facing surface.
4. Playwright or equivalent local browser verification captures the viewer with
   before/after viewports and full-page anchors.
5. Evidence Fabric records the viewer artifact, screenshot path, document diff
   ID, render artifact IDs, and `viewport_rect` values.
6. A live `bun run tui` path proves the model selects the document tools and
   that the user-facing result is the viewer bridge, not terminal image output.
