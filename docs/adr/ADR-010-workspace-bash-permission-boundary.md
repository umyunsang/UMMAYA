# ADR-010: `workspace_bash` Permission Boundary

**Status**: Accepted
**Date**: 2026-06-02
**Initiative**: #2290
**Affected**:
- `tui/src/tools/WorkspaceToolAdapter/WorkspaceToolAdapter.ts`
- `tui/src/tools.ts`
- `tui/src/tools/_shared/toolChoiceRepair.ts`
- `specs/2803-document-production-hardening/spec.md`

## Context

UMMAYA's active thesis is still `Claude Code harness + K-EXAONE/FriendliAI + Korean public-service tool surface`. The model-facing public-service surface remains `find`, `locate`, `send`, `check`, plus the first-class `document` primitive for public-document authoring. UMMAYA is not becoming a general coding agent.

The public-document harness still needs local workspace accessibility: finding files, inspecting nearby logs, running local render/test/evidence commands, and recovering paths that a citizen names imprecisely. P0 introduced namespaced local workspace adapters for `workspace_glob`, `workspace_grep`, `workspace_read`, `workspace_write`, and `workspace_edit`, all delegating to restored Claude Code local file tools. `workspace_bash` was deferred because shell subprocesses can bypass file-tool deny semantics and can create a broader blast radius than structured file tools.

The restored Claude Code Bash source is intact:

- `.references/claude-code-sourcemap/restored-src/src/tools/BashTool/BashTool.tsx`
- `.references/claude-code-sourcemap/restored-src/src/tools/BashTool/bashPermissions.ts`
- `.references/claude-code-sourcemap/restored-src/src/tools/BashTool/readOnlyValidation.ts`

UMMAYA's corresponding files already match the restored Bash structure closely and should be delegated to rather than reimplemented.

## Current Sources

- Claude Code tools reference states `Bash` executes shell commands and requires permission.
- Claude Code permissions docs describe Bash wildcard matching, compound-command splitting, wrapper handling, and the key limitation: file `Read`/`Edit` deny rules do not cover arbitrary subprocesses. Sandboxing is the OS-level backstop for Bash child processes.
- Claude Code permission modes docs classify risky actions such as `curl | bash`, force push, production deploys, and irreversible file destruction as blocked or review-worthy in auto mode.
- MCP ToolAnnotations define `readOnlyHint`, `destructiveHint`, `idempotentHint`, and `openWorldHint` as hints, not authoritative safety decisions.
- 2026 permission-gate research reports that classifier-based auto approval can under-cover ambiguous state-changing actions; this supports fail-closed wrapper validation for UMMAYA-specific hazards.

## Decision

Add `workspace_bash` as a namespaced workspace adapter, not as a public-service primitive and not as a raw `Bash` tool.

`workspace_bash` delegates execution, rendering, read-only classification, command parsing, compound-command handling, background behavior, and permission prompting to the restored Claude Code `BashTool`.

UMMAYA-specific wrapper restrictions:

1. `workspace_bash` is deferred through `ToolSearch`; it is not always loaded.
2. Raw `Bash` remains absent from the normal model-facing catalog.
3. `dangerouslyDisableSandbox: true` is rejected at `validateInput` before permission evaluation.
4. A non-read-only command that references `.hwp`, `.hwpx`, `.docx`, `.pdf`, `.xlsx`, or `.pptx` is rejected. Document-format mutation must go through the `document` primitive so artifact lineage, render/re-read gates, structured diff, and public-form conformance checks remain intact.
5. Read-only document discovery commands may run under the inherited Bash permission/sandbox model, but the prompt tells the model to use `document` for actual document reading, editing, rendering, diffing, and saving.
6. `workspace_bash` permission rules intentionally preserve the restored Claude Code Bash permission machinery. The model-facing id is namespaced; the shell safety decision remains the CC Bash decision path.

## Rationale

The selected design preserves Claude Code parity where Bash is strongest: parsing, read-only validation, permission prompts, sandbox integration, background task handling, and TUI rendering. It adds only UMMAYA-specific public-document guardrails at the wrapper boundary.

Keeping `workspace_bash` concrete, deferred, and namespaced fits current tool-calling practice better than a single overloaded `workspace` mega tool: each tool has a stable schema, ToolSearch can load it by name, and permission risk remains visible per tool.

The document-format guard is necessary because direct shell writes to HWPX/DOCX/PDF/XLSX/PPTX would bypass the document primitive's evidence contract. This is not a fallback path; it is a fail-closed boundary around formats whose mutation semantics are already owned by the document harness.

## Alternatives Considered

- **Do not add Bash**: safest, but leaves real local evidence and path-recovery workflows dependent on ad hoc terminal operation rather than the harness.
- **Expose raw `Bash` directly**: rejected because it pollutes the UMMAYA model-facing surface and conflicts with the namespaced workspace adapter direction.
- **Reimplement a smaller shell runner**: rejected because it would discard the restored Claude Code permission and sandbox machinery.
- **Allow sandbox override through the wrapper**: rejected because UMMAYA has no separate citizen-facing justification path for disabling Bash sandboxing.

## Consequences

Positive:

- Local evidence, render, test, and file-discovery workflows can be handled by the model through a CC-compatible shell tool.
- Raw Claude Code tool names remain hidden from the normal UMMAYA surface.
- Document mutation stays under the `document` primitive.

Risks:

- Shell commands remain higher blast-radius than structured file tools.
- Some safe document-related helper scripts may need to operate on intermediate text/SVG artifacts rather than the original document binary.
- Permission messages may still follow the restored Bash permission vocabulary internally because the safety machinery is delegated to CC Bash.

Mitigations:

- Deferred loading keeps `workspace_bash` out of the first-turn schema unless the model explicitly searches for it.
- Tests enforce raw-name hiding, ToolSearch discovery, sandbox-override rejection, read-only delegation, and document-format mutation rejection.
- Full `bun run typecheck` and focused TUI tool tests are required for this change.

## Verification

Required focused gates:

```bash
cd tui
bun run typecheck
bun test tests/tools/workspaceToolAdapter.test.ts tests/tools/ummaya-model-facing-tool-surface.test.ts tests/tools/serialization.test.ts --grep "workspace|model-facing tool surface|excludes Read"
```

Implementation result:

- `cd tui && bun run typecheck`: passed.
- `cd tui && bun test tests/tools/workspaceToolAdapter.test.ts tests/tools/_shared/toolChoiceRepair.test.ts tests/tools/ummaya-model-facing-tool-surface.test.ts tests/tools/serialization.test.ts --grep "workspace|glob adapter|model-facing tool surface|assembly shape|excludes Read"`: `97 pass / 0 fail`.

## References

- `docs/vision.md`
- `docs/requirements/ummaya-migration-tree.md`
- `specs/2803-document-production-hardening/spec.md`
- `.references/claude-code-sourcemap/restored-src/src/tools/BashTool/`
- Claude Code tools reference: https://code.claude.com/docs/en/tools-reference
- Claude Code permissions: https://code.claude.com/docs/en/permissions
- Claude Code permission modes: https://code.claude.com/docs/en/permission-modes
- MCP schema reference: https://modelcontextprotocol.io/specification/2025-11-25/schema
- Measuring the Permission Gate: https://arxiv.org/abs/2604.04978
- Dive into Claude Code: https://arxiv.org/abs/2604.14228
