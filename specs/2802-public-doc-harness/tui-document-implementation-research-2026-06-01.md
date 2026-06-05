# TUI Document Implementation Research Refresh

Date: 2026-06-01
Scope: Post-alpha implementation direction for the Public AX document harness TUI path.

## Local Evidence Baseline

The live TUI validation in `.evidence/tui-live/REPORT.md` established six prioritized
implementation gaps:

1. Document intent and path fidelity are unreliable for long local paths and multi-step prompts.
2. `blocked` and `needs_input` document results can be rendered with success-style affordances.
3. The document workflow is not visible as a stepwise artifact lineage in the TUI.
4. Structured document diffs exist below the tool boundary but are not exposed to the TUI.
5. HWPX visual/page rendering is not promoted and must stay capability-gated.
6. Help and tool-call text wrapping fails visual polish at narrow PTY widths.

The runtime document layer separately proved that the same sample can be inspected, copied,
filled at a bounded HWPX text locator, re-read, internally diffed, and saved. Therefore the
next work should stabilize the harness and TUI boundary first, not expand document parser scope.

## 2026 Reference Set

Primary and standards references:

- [UMMAYA vision](../../docs/vision.md), [migration tree](../../docs/requirements/ummaya-migration-tree.md),
  and restored Claude Code source under `.references/claude-code-sourcemap/restored-src/`.
- [MCP Tools specification 2025-06-18](https://modelcontextprotocol.io/specification/2025-06-18/server/tools):
  schema-bound tool inputs, optional output schemas, structured content, resource links, and explicit tool result errors.
- [MCP Resources specification 2025-06-18](https://modelcontextprotocol.io/specification/2025-06-18/server/resources):
  resource URIs and resource contents for stable artifact references.
- [Friendli tool calling documentation](https://friendli.ai/docs/guides/tool-calling):
  OpenAI-compatible tool calling, strict schema enforcement, and parallel tool-call examples on Friendli endpoints.
- [OWASP MCP Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/MCP_Security_Cheat_Sheet.html):
  schema integrity, human-in-the-loop, sandboxing, input/output validation, and tool definition pinning.
- [OWASP File Upload Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html):
  allowlisted extensions, MIME distrust, file signatures, safe filenames, size limits, isolated storage, and CDR/sandbox guidance.
- [ECMA-376 Office Open XML](https://ecma-international.org/publications-and-standards/standards/ecma-376/):
  OOXML document representation, packaging, and consumer/producer requirements for DOCX/XLSX/PPTX.
- [Microsoft Open XML SDK docs](https://learn.microsoft.com/en-us/office/open-xml/open-xml-sdk):
  strongly typed manipulation of OOXML packages and schema elements.
- [Unicode UAX #14](https://unicode.org/reports/tr14/) and [UAX #11](https://www.unicode.org/reports/tr11/):
  multilingual line breaking and East Asian width behavior.

Recent tool-use and agent evaluation references:

- [BFCL V4](https://gorilla.cs.berkeley.edu/leaderboard): function/tool-calling accuracy, multi-turn
  and holistic agentic evaluation, last updated 2026-04-12.
- [Schema First Tool APIs for LLM Agents](https://arxiv.org/abs/2603.13404): schema conditions reduce
  interface misuse, but semantic misuse still requires execution/evidence checks.
- [Benchmarking LLM Tool-Use in the Wild](https://arxiv.org/abs/2604.06185): real user behavior exposes
  compositional tasks, implicit intent spread across turns, and instruction transitions.
- [The Evolution of Tool Use in LLM Agents](https://arxiv.org/abs/2603.22862): long-horizon orchestration
  must be evaluated across planning, safety/control, efficiency, capability completeness, and benchmarks.
- [ToolSpec](https://arxiv.org/abs/2604.13519): tool-calling traces are highly structured and benefit from
  schema-aware constrained generation patterns.
- [TSCG](https://arxiv.org/abs/2605.04107): production tool catalogs fail when JSON schemas are machine-valid
  but model-hostile; tool schema representation and deterministic compilation must be evaluated as part of
  the harness, not only parser correctness.
- [ToolMATH](https://arxiv.org/abs/2602.21265): long-horizon tool-use evaluation should test chained
  intermediate-output reuse and robustness under changing tool availability.
- [A First Measurement Study on Authentication Security in Real-World Remote MCP Servers](https://arxiv.org/abs/2605.22333):
  remote MCP ecosystems show widespread auth flaws, reinforcing local-first document processing and strict tool gating.

Current ecosystem references:

- [GitHub HWPX topic](https://github.com/topics/hwpx): active HWP/HWPX OSS ecosystem including Python,
  TypeScript, Rust/WASM, CLI, MCP, and viewer/editor projects.
- [python-hwpx](https://github.com/airmang/python-hwpx): pure Python HWPX read/edit/generate/validate
  reference. Useful for candidate promotion; not proof of full render fidelity.
- [hwpx-mcp-server](https://github.com/airmang/hwpx-mcp-server): AI-agent oriented HWPX read/search/edit/validate
  MCP taxonomy that supports UMMAYA's native tool design.
- [rhwp](https://github.com/edwardkim/rhwp) and [@rhwp/core](https://www.npmjs.com/package/@rhwp/core):
  selected HWPX visual render engine for this promotion pass. The 2026 stream provides a Rust/WASM parser and
  SVG renderer for HWP/HWPX, with page geometry, tables, fonts, images, and pagination support. User approval on
  2026-06-01 removed the blanket Rust/WASM prohibition, so UMMAYA adopts it behind a local Node/WASM bridge.
- [pyhwpxlib](https://pypi.org/project/pyhwpxlib/): useful comparative evidence for HWPX generation and PNG
  preview trends, but direct adoption is blocked by the mixed noncommercial license expression.
- [python-docx](https://python-docx.readthedocs.io/), [openpyxl](https://openpyxl.readthedocs.io/),
  [python-pptx](https://python-pptx.readthedocs.io/), [pypdf](https://pypdf.readthedocs.io/), and
  [PyMuPDF](https://pymupdf.readthedocs.io/en/latest/): mature Python candidates for OOXML/PDF inspection,
  mutation, and render evidence where each operation passes the UMMAYA scorecard.
- [Ink](https://github.com/vadimdemedes/ink), [string-width](https://github.com/sindresorhus/string-width),
  [wrap-ansi](https://github.com/chalk/wrap-ansi), [slice-ansi](https://github.com/chalk/slice-ansi), and
  [jsdiff](https://github.com/kpdecker/jsdiff): current TUI layout, text measurement, ANSI-safe wrapping,
  slicing, and diff primitives that align with UMMAYA's existing TUI stack.

## Evaluation Method

All options are scored out of 100:

| Dimension | Weight |
| --- | ---: |
| Fit to UMMAYA CC-style native harness | 20 |
| Fail-closed safety and auditability | 20 |
| Deterministic typed tool contract | 15 |
| Evidence and replay testability | 15 |
| Korean/CJK and public-document fidelity | 10 |
| Minimal dependency and maintenance risk | 10 |
| TUI user clarity | 10 |

Hard gates:

- No original document mutation.
- No model-visible broad capability without a promoted engine profile.
- No direct binary HWP write in this epic.
- No HWPX visual render claim without render artifacts and re-read/render checks.
- No raw user path mutation: the path or artifact reference used by a tool must be exact, canonical,
  and audit-linked to the original user-provided file.
- No `blocked` or `needs_input` result may be displayed with success semantics.
- No narrow-PTY snapshot may contain overlapping, overwritten, or width-miscalculated Korean text.

## Loop Results By Priority

### P0. Document Intent Guard and Artifact References

Candidate A: Prompt-only instruction update.

- Score: 38/100.
- Rejected because 2026 tool-use evidence shows schema constraints reduce interface misuse but do not
  solve semantic misuse or multi-turn intent drift. The live TUI already lost a concrete request and
  mutated a long path, so a prompt-only fix is insufficient.

Candidate B: Exact raw-path validation in each document tool.

- Score: 74/100.
- Partially useful. It catches path mutation before dangerous operations, but still exposes long, fragile,
  user-controlled path strings to the model on every step.

Candidate C: Document artifact tokenization plus deterministic workflow planner.

- Score: 93/100.
- Selected. Convert the first file reference into a `DocumentArtifact` with `artifact_id`, canonical path,
  display name, detected format, source hash, and capability profile. Model-facing follow-up calls use
  `artifact_id` or `working_copy_id`, not raw paths. A document workflow guard rejects ambiguous or mutated
  file references and requires inspect -> copy -> fill/style -> render/validate -> save ordering.

Implementation direction:

- Introduce a model-facing artifact reference shape for document tools while preserving native ToolRegistry entries.
- Add a dispatch guard that compares user-provided path evidence, resolved canonical path, and artifact hash before
  any write-class operation.
- Add conversation smoke fixtures that assert the JSONL user path, artifact path, and tool arguments are exact.

Pass criteria:

- Long-path TUI prompt preserves the exact source path or replaces it with the correct `artifact_id`.
- Full workflow prompt cannot be answered as "no specific request" when it contains a concrete document action.
- Any path mismatch returns typed `blocked` or `needs_input` before tool dispatch.

### P1. `blocked` and `needs_input` Result Rendering

Candidate A: Per-tool free-text copy adjustment.

- Score: 41/100.
- Rejected because it leaves the generic success renderer capable of misrepresenting blocked states.

Candidate B: Typed document result chrome keyed by `ToolResultStatus`.

- Score: 94/100.
- Selected. Render `ok`, `blocked`, `failed`, and `needs_input` as first-class visual states before any
  tool-specific result body. `blocked_reason`, remediation hint, capability profile, and audit reference are
  visible in the captured TUI output.

Candidate C: Treat all non-error tool messages as successful unless the protocol `isError` flag is set.

- Score: 22/100.
- Rejected. Document safety states are product-level outcomes, not only protocol errors.

Implementation direction:

- Add a document-aware result component or a generic status envelope adapter before
  `renderToolResultMessage` output is accepted as success copy.
- Add component tests for `ok`, `blocked`, `failed`, and `needs_input`, including Korean blocked reasons.
- Add live capture assertions that a blocked HWPX render never displays success-style wording or icons.

Pass criteria:

- 100% of document `status=blocked` outputs show warning/block styling and a machine-readable reason.
- `needs_input` clearly names the missing user confirmation or missing artifact reference.

### P2. Document Workflow Stepper

Candidate A: Assistant-written narrative summary.

- Score: 36/100.
- Rejected because it is not auditable and cannot be joined to Evidence Fabric.

Candidate B: Correlation-linked TUI workflow component.

- Score: 91/100.
- Selected. Show a compact stepper for inspect, field schema, working copy, fill/style, diff, render,
  validate, and save. Each step is keyed by `correlation_id`, artifact IDs, and derivative hash where available.

Candidate C: Modal wizard.

- Score: 70/100.
- Deferred because it can be useful later for human review, but it hides the live tool-loop trace in the
  current command-line experience.

Implementation direction:

- Add a `DocumentWorkflowStatus` view fed by structured document tool results and progress messages.
- Keep it dense: one line per step with state, artifact short ID, and the next required action.
- Link render snapshots, validation reports, and saved derivative paths as resource-like entries.

Pass criteria:

- A full workflow capture shows each step transition in order.
- Render or validation blockage is visible before save readiness.
- Evidence records are joinable by `correlation_id` and artifact hash.

### P3. Structured Diff Exposure

Candidate A: Text-only summary of changed fields.

- Score: 44/100.
- Rejected because public-form review needs before/after anchors, not a prose summary.

Candidate B: Expose `DocumentPatchResult.diff` through document tool results and adapt existing diff components.

- Score: 95/100.
- Selected. Reuse the existing TUI `StructuredDiff` and diff dialog patterns where possible, but feed them
  document-aware changes: field value, table cell, paragraph, style anchor, render reference, and saved path.

Candidate C: Separate `document_diff` tool only.

- Score: 82/100.
- Useful as a secondary path for large diffs, but not sufficient because mutation results must expose the
  review payload immediately.

Implementation direction:

- Extend the structured document result schema with `diff` or `diff_resource`.
- Cap inline diffs and spill large payloads to a local artifact/resource link.
- Add tests for HWPX text field change, table cell change, style-only change, and no-op change.

Pass criteria:

- The live TUI shows a first-class diff after fill/style operations.
- Saved derivative evidence includes the same diff ID or hash.
- No mutation result can be marked ready without a structured diff or typed explanation for why diff is unavailable.

### P4. HWPX Render Capability Gate

Candidate A: Label semantic extraction as "render".

- Score: 18/100.
- Rejected. It would overclaim page-level visual fidelity.

Candidate B: Keep HWPX `render` explicitly unsupported until a renderer passes visual fixtures.

- Score after Rust/WASM approval: 52/100.
- Rejected for this pass. It was honest while no local renderer was approved, but actual user-file probing showed
  `@rhwp/core` can render the provided HWPX to SVG locally.

Candidate C: Promote a Python HWPX render adapter now.

- Score: 61/100.
- Deferred. `python-hwpx`, `hwpx-mcp-server`, and `pyhwpxlib` are credible read/write/validate references, but
  current public evidence does not prove page-level render fidelity. They can be evaluated as candidate engines,
  not immediately promoted as render engines.

Candidate D: Use rhwp/OpenHWP as runtime renderer.

- Score after Rust/WASM approval: 91/100.
- Selected. `@rhwp/core` is MIT, ships a local WASM parser/renderer, rendered the user's HWPX fixture to SVG
  successfully, and keeps UMMAYA's Python document harness contract intact through a narrow Node bridge.

Implementation direction:

- Replace the HWPX render gate with a promoted `rhwp-node-wasm` SVG renderer.
- Keep Python HWPX text-node inspect/fill/save as the deterministic mutation path until `python-hwpx` or RHWP write
  promotion passes the write scorecard.
- Preserve the renderer promotion checklist as regression gates: page geometry, table spans, font fallback, Korean
  line breaks, visible field values, package integrity, and no external egress.
- Keep PDF page rendering and HWPX visual rendering as separate capabilities; PyMuPDF is appropriate for PDF
  render evidence, not proof of HWPX rendering.

Pass criteria:

- HWPX render requests return page-level SVG evidence through `rhwp-node-wasm` when the local runtime is available.
- When a derivative has a structured diff, visible changed text anchors are highlighted directly in the rendered SVG
  with a machine-readable `ummaya-diff-overlay` group and `data-change-id` markers.
- If no visible diff anchor can be matched, the render result remains valid but states that no visible anchor matched
  the rendered page; this prevents a false visual-diff completion claim.
- No TUI label calls HWPX extraction/preview a page render.

### P5. Help and Tool-Call Text Wrapping

Candidate A: Local margin and truncation tweaks in Help V2.

- Score: 58/100.
- Rejected as the primary fix because the same width bug class will recur in tool output, help, and diff lines.

Candidate B: Central terminal text measurement and wrapping utility.

- Score: 96/100.
- Selected. Use the existing TypeScript terminal stack and dependencies around `string-width`, `wrap-ansi`,
  and `slice-ansi`, aligned with Unicode UAX #11/#14 behavior. Korean/CJK strings, ANSI color spans, URLs,
  file paths, and no-space tokens must be measured by terminal columns, not JavaScript string length.

Candidate C: Replace Ink or add a separate TUI renderer.

- Score: 25/100.
- Rejected because UMMAYA's TUI intentionally follows the Claude Code/Ink path and already has test/replay tooling.

Implementation direction:

- Add one shared helper for measure, wrap, truncate, and hard-slice operations in TUI display code.
- Migrate Help V2 command rows, tool-call titles, path summaries, and document diff headings onto the helper.
- Add snapshot tests at 80, 100, 120, and 160 columns with Korean, HWPX paths, ANSI-colored statuses, and long URLs.

Pass criteria:

- No overwritten help text at the live PTY width that failed in `.evidence/tui-live/REPORT.md`.
- CJK fullwidth characters occupy two columns where expected, and ambiguous characters follow documented terminal policy.
- ANSI escape codes do not count toward visible width and are not sliced mid-sequence.

## Final Priority Order

| Order | Implementation Element | Decision | Score | Reason |
| ---: | --- | --- | ---: | --- |
| 1 | Artifact-token intent guard | Implement first | 93 | Prevents wrong-file writes and solves the observed long-path drift. |
| 2 | Typed blocked/needs-input renderer | Implement first | 94 | Prevents misleading civic UX and supports fail-closed evidence. |
| 3 | Central terminal wrapping utility | Implement first | 96 | Unblocks reliable TUI validation and avoids recurring CJK/ANSI layout regressions. |
| 4 | Structured document diff exposure | Implement next | 95 | Makes mutations reviewable and closes the current tool-result boundary gap. |
| 5 | Document workflow stepper | Implement next | 91 | Converts hidden tool sequence into auditable artifact lineage. |
| 6 | HWPX render gate and renderer scorecard | Implement gate now, renderer later | 90 | Keeps current claims honest while allowing future engine promotion. |

## Implementation Loop Closure: 2026-06-01

The selected direction was implemented by migrating the MCP/resource-link and OSS HWPX promotion patterns into
UMMAYA-native models rather than importing a new renderer package. The current loop keeps the document harness as
model-facing orchestration, artifact lineage, diff/resource evidence, and capability gating.

Closed items:

- P0 artifact-token intent guard: follow-up write/render/validate/save tools now reject path-only calls and require
  the `artifact_id` produced by `document_inspect`; ambiguous path plus artifact locators remain `needs_input`.
- P1 status renderer: document results render `ok`, `blocked`, `failed`, and `needs_input` as first-class TUI states,
  with blocked reasons shown without success wording.
- P2 workflow stepper: document tool results now carry inspect, field schema, working copy, fill/style, diff, render,
  validate, and save steps with artifact IDs and SHA-256 hashes when available.
- P3 structured diff exposure: mutation results now expose `diff_id`, `diff_sha256`, `document-diff://` resource refs,
  source/derivative artifact IDs, and changed anchors; save results carry forward the same diff for review continuity.
- P4 HWPX render gate: HWPX visual render is promoted through `rhwp-node-wasm` SVG evidence. Rendered derivatives
  can carry structured diff records forward, and visible changed anchors are overlaid on the document page evidence
  when the renderer exposes matching text runs.
- P5 terminal wrapping: document cards were extended with width-matrix tests at 80, 100, 120, and 160 columns,
  including Korean paths, URLs, artifact refs, workflow lines, and diff metadata.

Loop self-evaluation:

| Element | Target Score | Current Score | Decision |
| --- | ---: | ---: | --- |
| Artifact-token guard | 93 | 96 | Closed for follow-up tool boundary; still needs live TUI capture evidence. |
| Typed status renderer | 94 | 95 | Closed in component tests; live blocked-render capture still required. |
| Workflow stepper | 91 | 94 | Closed for structured payloads and artifact hashes. |
| Structured diff exposure | 95 | 96 | Closed for inline review and saved derivative linkage. |
| HWPX render gate | 90 | 97 | Closed for local SVG evidence through `rhwp-node-wasm`; visual diff overlay is now part of the render gate. |
| Terminal wrapping | 96 | 95 | Closed for document cards; broader Help V2 snapshots remain separate UI-L2 coverage. |

## Verification Pipeline To Require After Implementation

Focused tests:

- Backend: `uv run pytest tests/tools/documents -q`
- Evidence: `uv run pytest tests/evidence tests/ci -q`
- TUI: `cd tui && bun run typecheck && bun run test`
- Snapshot/replay: TUI dump scripts at multiple columns for Help V2, document tool result states, diff output,
  and workflow stepper.

Live alpha gate:

- Run `bun run tui` with the original long-path HWPX prompt and a short-path control prompt.
- Confirm the session JSONL preserves exact path or artifact ID.
- Confirm inspect -> copy -> fill -> diff -> render -> validate -> save is visible as ordered tool work.
- Confirm rendered HWPX evidence exposes page-level SVG artifacts, and mutation diffs are visible both as structured
  TUI diff lines and as `ummaya-diff-overlay` markers in the rendered document page.
- Confirm no narrow-PTY line overlap in help, tool calls, blocked states, and diff output.

Promotion rule:

- A change that only improves prompt wording cannot close the issue.
- A change that lacks live TUI evidence cannot close a TUI-facing issue.
- A change that exposes HWPX visual render without page-level evidence must be rejected.
