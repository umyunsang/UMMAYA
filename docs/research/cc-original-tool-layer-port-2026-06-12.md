# CC Original Tool Layer Port Research Note

Date: 2026-06-12
Status: research note only. No implementation, no spec, no task issues, and no
PR handoff are created by this note.

## Decision Context

UMMAYA is not a document-writing-only system. Document authoring is one
capability inside a broader national AX harness: Claude Code's original
agentic tool loop and TUI, with two sanctioned swaps:

- provider: FriendliAI Serverless + K-EXAONE;
- tool surface: Korean national-infrastructure and citizen-service channels.

The next LazyCodex pipeline should port the full Claude Code original tool
layer into UMMAYA's tool system, then apply UMMAYA exposure policy. This note
records the local source anchors, locked user decisions, trust tiers, and first
execution packages.

## Local Anchors

- `docs/vision.md`: UMMAYA thesis, six-layer harness migration, and the rule
  that Claude Code is the first reference for unclear design decisions.
- `docs/requirements/ummaya-migration-tree.md`: current L1-B/L1-C public-service
  primitive surface and historical C6 helper-tool scope.
- `.references/claude-code-sourcemap/restored-src/src/tools.ts`: CC source of
  truth for built-in tool registration and exposure presets.
- `.references/claude-code-sourcemap/restored-src/src/tools/`: CC source of
  truth for concrete tool implementations.
- `.references/claude-code-sourcemap/restored-src/src/services/tools/`: CC
  streaming tool execution and orchestration layer.
- `.references/claude-code-sourcemap/restored-src/src/services/mcp/`: CC MCP
  connection, auth, normalization, permissions, and server lifecycle layer.
- `tui/src/tools.ts`: current UMMAYA registry shape. It preserves CC registry
  structure but exposes `ToolSearchTool`, the four public-service primitives,
  `DocumentPrimitive`, and workspace adapters as the default catalog.
- `tui/src/tools/WorkspaceToolAdapter/WorkspaceToolAdapter.ts`: current bridge
  for namespaced file/search/shell adapters derived from CC tools.

## CC Restored-Source Status

The CC restored source appears intact for the target tool-layer family:

- Tool interface and registry: `src/Tool.ts`, `src/tools.ts`,
  `src/utils/toolPool.ts`.
- Runtime execution: `src/services/tools/StreamingToolExecutor.ts`,
  `toolExecution.ts`, `toolOrchestration.ts`, `toolHooks.ts`.
- File/search/edit: `FileReadTool`, `FileEditTool`, `FileWriteTool`,
  `GlobTool`, `GrepTool`, `NotebookEditTool`.
- Shell/system: `BashTool`, `PowerShellTool`, `REPLTool`,
  `EnterWorktreeTool`, `ExitWorktreeTool`, `ConfigTool`.
- Web/research/source acquisition: `WebFetchTool`, `WebSearchTool`,
  `AgentTool`, `ToolSearchTool`, `BriefTool`.
- Agent/task orchestration: `AgentTool`, `TaskCreateTool`, `TaskGetTool`,
  `TaskUpdateTool`, `TaskListTool`, `TaskOutputTool`, `TaskStopTool`,
  `TodoWriteTool`, `AskUserQuestionTool`.
- MCP: `MCPTool`, `McpAuthTool`, `ListMcpResourcesTool`,
  `ReadMcpResourceTool`, plus `src/services/mcp/*`.
- Scheduling/remote/skills: `ScheduleCronTool`, `RemoteTriggerTool`,
  `SendMessageTool`, `SkillTool`.

UMMAYA already contains many of these source-shaped tools under `tui/src/tools/`,
but current default exposure intentionally narrows the model-facing catalog to
public-service primitives and workspace adapters. The next work is therefore
not "copy files blindly"; it is source-parity audit, registry recovery, exposure
policy, and runtime verification.

## Locked User Decisions

- Completion target: runtime parity, staged as source parity, registry, runtime,
  and exposure policy.
- Classification: hybrid of CC function group inventory and AX trust-boundary
  tier.
- First execution scope: inventory/tier table plus recovery of inactive or
  incomplete registry entries.
- First-wave domains: research/source verification, harness orchestration, and
  file-work all stay in wave one.
- File-work exposure: read/search default; write/edit/notebook mutation only
  behind permission gauntlet and explicit user approval.
- Shell/system exposure: default exposure is allowed only through the permission
  gauntlet.
- MCP exposure: CC-parity default exposure, with server-specific permission
  gauntlet and policy.
- UMMAYA primitives: `find`, `locate`, `send`, and `check` remain national AX
  main verbs. CC tools are the support/runtime substrate, not replacements for
  those verbs.
- Artifact shape: make a dated `docs/research/` note first. Later work may open
  a separate spec/epic through LazyCodex.
- 2803 order: document-production-hardening PR #3141 must be merged and cleaned
  before this note. That is complete.

## Scope Reconciliation

`docs/requirements/ummaya-migration-tree.md` still records an earlier helper
tool decision that excluded `Read`, `Write`, `Edit`, `Bash`, `Glob`, `Grep`, and
`NotebookEdit` from the citizen-facing helper surface. The user's current
direction expands scope to port all CC original tools into the UMMAYA tool
system.

LazyCodex should treat this note as the start of a new scope-change lane. Before
implementation, the pipeline must update the relevant spec or requirements
artifact to distinguish:

- registered runtime capability;
- model-facing default exposure;
- permission-gated exposure;
- national AX primitive surface.

This prevents "all tools exist" from being confused with "all tools are always
safe to call."

## Trust-Boundary Tiers

| Tier | Category | Default posture | Examples |
|---|---|---|---|
| 0 | Read-only local context | Expose by default when bounded to workspace and transcript policy | `FileReadTool`, `GlobTool`, `GrepTool`, readonly workspace discovery |
| 1 | Local mutation | Permission gauntlet and user approval required | `FileEditTool`, `FileWriteTool`, `NotebookEditTool`, document derivative writes |
| 2 | Shell/system execution | Permission gauntlet, command analysis, sandbox/cwd policy, destructive-command review | `BashTool`, `PowerShellTool`, `REPLTool`, worktree tools |
| 3 | External network/source acquisition | Permission gauntlet or approved source policy; source logging and citation evidence | `WebFetchTool`, `WebSearchTool`, MCP read tools |
| 4 | Agent/research orchestration | Bounded delegation, progress visibility, cancellation, transcript join keys | `AgentTool`, task tools, `TodoWriteTool`, `ToolSearchTool` |
| 5 | Protected national AX actions | Identity/consent/delegation and agency policy citation required | `check`, `send`, payment, certificate, Government24/Hometax-class adapters |

Tiers are cumulative. A tool that both mutates files and calls the network uses
the stricter policy.

## AX Infrastructure Direction

Porting CC's full tool layer strengthens UMMAYA as national AX infrastructure in
four ways:

1. It separates the citizen's intent surface from the runtime substrate. Citizens
   still ask for outcomes through `find`, `locate`, `send`, and `check`, while
   the harness can use file, web, agent, MCP, and shell tools to gather evidence
   and execute safely.
2. It makes source verification a first-class capability. Document work,
   welfare eligibility, tax guidance, school assignments, research papers, and
   policy-sensitive answers can call `WebFetch`, `WebSearch`, MCP resources, or
   agent research when user-provided evidence is insufficient.
3. It preserves CC's permission gauntlet discipline for non-citizen-service
   tools. Local file writes, shell commands, notebooks, MCP servers, and web
   fetches become auditable support operations rather than hidden fallbacks.
4. It lets agency and public-infrastructure adapters stay focused. National AX
   adapters wrap official channels; CC support tools provide research,
   workspace, orchestration, and verification around those channels.

For document authoring specifically, the rule remains fail-closed: write only
fields supported by user-provided or source-verified evidence; leave unsupported
fields blank or in question-waiting state; do not invent content even when the
user asks for a plausible draft.

## First LazyCodex Execution Packages

1. Inventory and tier map
   - Generate a source inventory from `.references/.../src/tools.ts`,
     `.references/.../src/tools/`, and `tui/src/tools/`.
   - Classify every CC tool into the trust tiers above.
   - Mark each UMMAYA copy as `source-parity`, `modified`, `inactive`,
     `registry-hidden`, `unsupported`, or `missing`.

2. Registry recovery
   - Recover inactive or incomplete tools without changing UMMAYA's main verbs.
   - Keep `tui/src/tools.ts` as the registry contract; do not create a parallel
     registry.
   - Preserve `ToolSearchTool` and deferred loading so schemas do not flood the
     model context.

3. Web research and source verification
   - Wire `WebFetchTool`, `WebSearchTool`, and `AgentTool` as support tools for
     document writing, policy research, school assignments, papers, and public
     service evidence gathering.
   - Require source logging, citation evidence, and user approval before using
     gathered facts in mutable document output.
   - If research cannot verify a claim, the document/planner must ask the user
     or leave the slot blank.

4. File and workspace work
   - Make read/search default visible under the workspace adapter policy.
   - Gate write/edit/notebook operations through CC permission components and
     UMMAYA document-safety restrictions.
   - Keep document binary mutation routed through `DocumentPrimitive` and
     promoted engines, not raw `FileWriteTool`.

5. Shell/system/MCP exposure
   - Expose shell and MCP with CC permission UX and UMMAYA policy text.
   - Require server-specific MCP trust prompts and no silent server execution.
   - Keep shell output, cwd changes, long-running jobs, cancellation, and
     destructive-command warnings observable.

6. Agent/task orchestration
   - Restore `AgentTool`, task tools, and todo semantics as harness support.
   - Preserve progress visibility, cancellation/resume, and evidence join keys.
   - Use this for deep research and multi-step verification, not as an opaque
     bypass around the user's approval requirements.

## Acceptance Criteria For The Later Implementation

- Source-parity diff exists for every CC tool subtree that is ported or
  intentionally diverged.
- `tui/src/tools.ts` exposes a deterministic model-facing catalog that separates
  default, deferred, permission-gated, and hidden tools.
- Web/research tools can be called during document work, but unsupported facts
  remain blank or question-waiting.
- Permission prompts render through existing CC-shaped permission components for
  file mutation, notebook mutation, shell/system execution, MCP, and web fetch.
- Evidence Fabric records tool selection, permission decisions, source URLs,
  document field provenance, render/re-read outcomes, and blocked states.
- TUI real-use scenarios show progress, tool call, tool result, post-tool
  synthesis, and final answer in order.
- No raw CC developer tool silently bypasses UMMAYA national AX primitives or
  protected-domain `check`/`send` consent boundaries.

## Rejected Shortcuts

- Do not add prompt-only lists of tool names as a substitute for registry
  recovery.
- Do not expose raw file-write or shell tools by default without permission
  gauntlet.
- Do not make document authoring "plausible" by default; evidence remains
  mandatory.
- Do not create a second UMMAYA-specific tool loop when CC's restored tool loop
  is intact.
- Do not implement this note directly outside the LazyCodex pipeline.

## Open Items For LazyCodex

- Decide whether the scope-change artifact should be a new spec, an epic, or
  both.
- Update the historical C6 helper-tool requirements so they no longer conflict
  with the full CC tool-layer port.
- Add current primary-source research only where the later implementation
  touches unstable external contracts: FriendliAI/K-EXAONE tool calling,
  MCP specification changes, web-search provider APIs, browser/computer-use
  tools, and package/runtime dependencies.
- Define the first manual QA script before code: one Korean natural-user document
  request that requires web/source verification, one file read/search request,
  one permission-gated write request, one shell request, one MCP request, and one
  agent research request.
