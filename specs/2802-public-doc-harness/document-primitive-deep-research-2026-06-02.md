# Document Primitive Deep Research Migration Note

Date: 2026-06-02

## Local Anchors

- `docs/vision.md`: UMMAYA migrates the Claude Code harness and measures success by citizen experience parity with Claude Code tool work.
- `docs/requirements/ummaya-migration-tree.md`: The prior active root surface was `find`, `locate`, `send`, and `check`; the public-document harness now needs an explicit spec amendment because document editing is not a public-data adapter.
- `specs/2802-public-doc-harness/spec.md`: FR-019, FR-040, and SC-009 are superseded from stage-visible document tools to a single `document` primitive with internal workflow evidence.
- `src/ummaya/tools/documents/`: Current runtime already has inspect, copy, fill/style, render, validate, and save stages. The defect is the model-facing boundary, not the engine stages.

## Claude Code Restored-Source Status

- Restored source status: intact.
- Reference files:
  - `.references/claude-code-sourcemap/restored-src/src/tools/FileEditTool/FileEditTool.ts`
  - `.references/claude-code-sourcemap/restored-src/src/tools/FileEditTool/UI.tsx`
  - `.references/claude-code-sourcemap/restored-src/src/components/FileEditToolUpdatedMessage.tsx`
  - `.references/claude-code-sourcemap/restored-src/src/components/StructuredDiffList.tsx`
- Adopted insight: Claude Code exposes one Edit tool to the model and renders the structured patch from that tool result. It does not expose read, patch, and diff-render as separate normal model-facing tools.
- Inference boundary: UMMAYA document files are richer than source-code text files, so the primitive owns a multi-stage internal workflow. The model-facing unit remains one edit/review primitive.

## 2026-Current Sources

- Anthropic tool-use docs, "How tool use works": tool use is a schema contract; client-executed tools are selected by the model and executed by the application in an agentic loop. Adopted for the single `document` tool boundary.
- OpenAI function calling help, updated 2026 crawl: structured outputs with strict schemas reduce argument drift, but app-side validation remains required. Adopted for keeping Pydantic validation and typed blocked/needs-input outcomes.
- MCP 2025-11-25 schema: tools have `inputSchema`, optional `outputSchema`, and annotations; annotations are hints, not permission guarantees. Adopted for keeping permission/audit logic outside descriptive hints.
- MCP 2026 tool-annotations post: read-only/destructive/idempotent/open-world hints are useful risk vocabulary but context-sensitive. Adopted as a risk signal: document writes need a real gate, not a descriptive stage name.
- BFCL ICML 2025: function-calling accuracy is an agentic evaluation axis across single, multi-tool, and multi-turn settings. Adopted for evaluating natural HWPX requests through real tool selection, not only unit tests.
- revdiff 2026 docs/site: review UI is focused on changed content, line annotation, and structured stdout, with no decorative card shell. Adopted for TUI compact diff style.
- Difftastic current docs: structural diff improves human readability by comparing meaningful structure, not raw line text. Adopted as a document-IR diff analogy: field/table paths are the review anchors.

## Candidate Scorecard

Weights: CC parity 20, tool-selection correctness 20, user-visible review quality 20, security/permission clarity 15, migration cost 10, testability 10, spec consistency 5.

| Candidate | Score | Decision | Rationale |
|---|---:|---|---|
| Keep nine visible document tools and improve prompts | 43 | Reject | Still asks the model to choose internal stages and keeps `locate` confusion alive. |
| Keep nine tools but add a client-side forced workflow router | 58 | Reject | Hides the same model-surface problem behind recovery code and violates root-cause-first rules. |
| Register one `document` primitive backed by internal format adapters | 94 | Adopt | Matches Claude Code Edit shape, reduces tool-selection ambiguity, and preserves existing engine stages as internal evidence. |
| Replace the document harness with a browser/editor app | 49 | Reject | Over-expands scope and breaks TUI-first CC harness parity. |

## Selected Approach

Register a single model-facing `document` tool with `primitive="document"`.

The tool accepts:

- `document`: local path or known artifact id.
- `operation`: requested document operation class.
- `instruction`: natural-language edit/review intent.
- `patches` and `styles`: optional explicit field/style operations when the model can provide them.
- `template_id` and `destination_display_name`: optional validation/export requests.

The runtime executes internal stages:

1. Inspect/source intake.
2. Schema/extraction.
3. Working copy.
4. Fill/style mutation.
5. Structured diff creation.
6. Render evidence with compact diff data.
7. Optional validation/save.

The result is a single `DocumentToolResult` with `tool_id="document"`, workflow evidence, `diff`, render artifacts, and the same compact TUI renderer used for document diffs. The user must not ask a separate "show changes" request after an edit.

## Migration Boundary

- Keep existing `DocumentToolRuntime` stage methods as internal implementation and direct unit-test seams.
- Stop registering stage ids as model-facing tools in normal `register_document_tools()`.
- Update the contract catalog from nine tool entries to one `document` entry.
- Extend primitive metadata to include `document`.
- Update search/tool-choice repair from `select:document_inspect,...` to `select:document`.
- TUI recognizes `tool_id="document"` as a document result.

## Tests and Evidence

RED tests introduced:

- `tests/tools/documents/test_tool_registry_document_tools.py`: model-facing registry exposes only `document`.
- `tests/tools/documents/test_document_tool_flow.py`: one `document` call edits and returns rendered diff evidence.

Verification gates after implementation:

- `uv run pytest tests/tools/documents/test_tool_registry_document_tools.py tests/tools/documents/test_document_tool_flow.py -q`
- `uv run pytest tests/engine/test_engine.py::test_available_adapters_context_prioritizes_document_path_intake -q`
- `cd tui && bun run test -- tests/tools/_shared/toolChoiceRepair.test.ts tests/primitive/dispatcher.test.tsx`
- Real `bun run tui` alpha with a natural Korean document-edit request.

2026-06-02 final boundary correction:

- `src/ummaya/ipc/stdio.py` now treats `document({...})` as a concrete document adapter call by normalizing it to `{tool_id:"document", params:...}` at dispatch, preventing the direct primitive marker from swallowing real document execution.
- The final-answer gate now requires one successful `document` result after the latest user document request instead of enforcing exposed `document_inspect -> copy -> fill -> render` stage calls.
- TUI tool-choice repair now uses `select:document` and never synthesizes incomplete document arguments client-side. The model must fill the schema; the client only narrows tool exposure.
- IPC and adapter-manifest schemas now include `document` as an allowed primitive.
- Verification:
  - `uv run pytest ... -q` focused backend contract/routing/IPC set: 39 passed.
  - `cd tui && bun run typecheck`: passed.
  - `cd tui && bun run test -- tests/tools/_shared/toolChoiceRepair.test.ts tests/primitive/dispatcher.test.tsx tests/ipc/handlers.test.ts tests/ipc/bridge.test.ts`: 350 passed, 1 skipped, 2 todo.

## Remaining Gates

- Real `bun run tui` alpha with a natural Korean document-edit request remains the next user-visible proof gate.
- Natural-prompt field inference for arbitrary HWPX forms remains adapter-specific. This note only fixes the model-facing primitive boundary and automatic review result.
