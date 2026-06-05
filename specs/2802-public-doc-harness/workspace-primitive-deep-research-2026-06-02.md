# Workspace Primitive Migration Deep Research — 2026-06-02

## Final Direction

UMMAYA should not expose one model-facing mega tool such as `workspace({ tool_id, params })`.
The final direction is an internal `workspace` primitive family with concrete namespaced adapters:

- `workspace_glob`
- `workspace_grep`
- `workspace_read`
- `workspace_write`
- `workspace_edit`
- `workspace_bash`

The adapters delegate to the restored Claude Code local workspace tools while preserving UMMAYA's public-service primitive surface. Raw Claude Code tool names (`Glob`, `Grep`, `Read`, `Write`, `Edit`, `Bash`) remain absent from the model-facing catalog.

## Local Reference Anchors

- `docs/vision.md`: UMMAYA keeps the Claude Code harness and swaps only the LLM and tool surface.
- `docs/requirements/ummaya-migration-tree.md`: CC tool loop and TUI behavior are canonical migration anchors.
- `.references/claude-code-sourcemap/restored-src/src/tools/`: byte-identical Claude Code tool source for local file access.
- `specs/2802-public-doc-harness/spec.md`: `document` is a first-class primitive; format-specific engines live below it.

## 2026-Current Research Inputs

- OpenAI function calling docs describe tool calling as concrete tool definitions with JSON Schema and note that large tool sets should use tool search to defer rarely used schemas.
- MCP tools specification defines tools by unique `name`, `inputSchema`, optional `outputSchema`, structured content, and client-side validation expectations.
- Claude Code tools reference keeps local workspace operations as separate concrete tools (`Glob`, `Grep`, `Read`, `Write`, `Edit`) with permission boundaries.
- BFCL ICML 2025 frames function calling as selecting the correct external function/API in multi-turn agentic workflows; this supports fine-grained tool identity instead of an overloaded single function.
- Current local-first search ecosystem continues to converge on typed search surfaces: ripgrep for regex search; newer semantic search tools such as ogrep use MCP-native structured tools while keeping the agent as orchestrator.

## Candidate Scorecard

| Candidate | Fit | Score | Decision |
| --- | --- | ---: | --- |
| Single visible `workspace` mega tool | Hides concrete permissions and schemas; increases argument confusion; weak ToolSearch fit. | 58/100 | Rejected |
| Re-enable raw CC names directly | Preserves CC behavior but pollutes UMMAYA's public-service surface and conflicts with existing tests. | 72/100 | Rejected |
| Internal `workspace` family + concrete `workspace_*` adapters | Preserves CC implementation, concrete schemas, ToolSearch discovery, and UMMAYA namespace. | 94/100 | Selected |
| Keep document path repair only | Fixes one HWPX symptom but does not provide general file/folder accessibility. | 64/100 | Rejected |

## Migration Boundary

Implemented P0 adapters:

- `workspace_glob`: always loaded because path discovery must work on turn one.
- `workspace_grep`, `workspace_read`, `workspace_write`, `workspace_edit`, `workspace_bash`: deferred through ToolSearch.

Explicit guard:

- `workspace_write` and `workspace_edit` reject direct writes to `.hwp`, `.hwpx`, `.docx`, `.pdf`, `.xlsx`, and `.pptx`.
- `workspace_bash` rejects sandbox override and rejects non-read-only commands that reference `.hwp`, `.hwpx`, `.docx`, `.pdf`, `.xlsx`, or `.pptx`.
- Document formats must be edited through the `document` primitive so structured document engines own parsing, patching, rendering, diff, and save semantics.

Governed by ADR:

- `workspace_bash`: introduced only after `docs/adr/ADR-010-workspace-bash-permission-boundary.md`, because shell subprocesses can bypass file-tool read/write intent boundaries.

Deferred:

- `NotebookEdit`, `WebFetch`, team/task tools: outside the public-document file accessibility scope.

## Evaluation Criteria

1. Concrete tool identity: each adapter has a stable tool name and schema.
2. CC parity: local file behavior delegates to restored Claude Code tools.
3. UMMAYA namespace: raw CC developer tool names are not exposed.
4. ToolSearch fit: only path discovery is always loaded; heavier tools are deferred.
5. Document safety: binary/document formats cannot be modified by text file tools.
6. TUI routing: ambiguous document folder/name requests use `workspace_glob` before `document`; exact document paths go directly to `document`.

## Verification

- `cd tui && bun run typecheck`
- `cd tui && bun test tests/tools/workspaceToolAdapter.test.ts tests/tools/_shared/toolChoiceRepair.test.ts tests/tools/ummaya-model-facing-tool-surface.test.ts tests/tools/serialization.test.ts --grep "workspace|glob adapter|model-facing tool surface|assembly shape|excludes Read"`
- Result: `97 pass / 0 fail`

## Source Links

- OpenAI function calling guide: https://developers.openai.com/api/docs/guides/function-calling
- OpenAI function calling help article: https://help.openai.com/en/articles/8555517-function-calling-updates
- MCP tools specification: https://modelcontextprotocol.io/specification/2025-06-18/server/tools
- MCP specification repository: https://github.com/modelcontextprotocol/modelcontextprotocol
- BFCL ICML 2025 paper page: https://proceedings.mlr.press/v267/patil25a.html
- Claude Code tools reference: https://code.claude.com/docs/en/tools-reference
- ripgrep project: https://github.com/BurntSushi/ripgrep
- ogrep local-first semantic search: https://ogrep.be/
