// biome-ignore-all assist/source/organizeImports: ANT-ONLY import markers must not be reordered
import { toolMatchesName, type Tool, type Tools } from './Tool.js'
import { AgentTool } from './tools/AgentTool/AgentTool.js'
import { SkillTool } from './tools/SkillTool/SkillTool.js'
// Epic #1634 P3 FR-001 / Spec 031: active reserved primitives exposed as top-level tools.
import { LookupPrimitive } from './tools/LookupPrimitive/LookupPrimitive.js'
import { ResolveLocationPrimitive } from './tools/ResolveLocationPrimitive/ResolveLocationPrimitive.js'
import { SubmitPrimitive } from './tools/SubmitPrimitive/SubmitPrimitive.js'
import { VerifyPrimitive } from './tools/VerifyPrimitive/VerifyPrimitive.js'
// Epic #1634 P3 FR-018: four new auxiliary tools completing the MVP-7 set.
import { TranslateTool } from './tools/TranslateTool/TranslateTool.js'
import { CalculatorTool } from './tools/CalculatorTool/CalculatorTool.js'
import { DateParserTool } from './tools/DateParserTool/DateParserTool.js'
import { ExportPDFTool } from './tools/ExportPDFTool/ExportPDFTool.js'
// ============================================================================
// SWAP-2-RETAINED-IMPORT-BLOCK (FR-013, Spec 2638 / Initiative #2636)
// ----------------------------------------------------------------------------
// Below imports (BashTool, FileEditTool, FileReadTool, FileWriteTool, GlobTool,
// NotebookEditTool, TaskOutputTool, TaskStopTool, TodoWriteTool,
// ExitPlanModeV2Tool, GrepTool, AskUserQuestionTool, LSPTool, ConfigTool,
// EnterPlanModeTool, EnterWorktreeTool, ExitWorktreeTool, TaskCreateTool,
// TaskGetTool, TaskUpdateTool, TaskListTool, TestingPermissionTool,
// ListMcpResourcesTool, ReadMcpResourceTool, ToolSearchTool, SkillTool,
// BriefTool, WebFetchTool, WebSearchTool — 14+ dev/auxiliary tools) are
// retained at compile-time but NOT registered in getAllBaseTools() (post-P3).
//
// Why: KOSMOS 13-tool citizen-facing surface (Spec 1634 P3 contracts/
// primitive-envelope.md § 1) excludes CC dev tools from LLM visibility.
// However, permissions/sandbox/attachments infrastructure references the
// tool name constants (FR-013 scope correction, #1757) — removing imports
// would break those references and create KOSMOS-only divergence with CC
// (CORE THESIS violation).
//
// Outside-caller counts (measured 2026-05-03, Spec 2638 specify): BashTool 196,
// FileReadTool 91, FileEditTool 69, FileWriteTool 52, GrepTool 36,
// ToolSearchTool 31, GlobTool 28, SkillTool 26, ExitPlanModeV2Tool 24,
// BriefTool 22, WebFetchTool 18, AskUserQuestionTool 17, NotebookEditTool 16,
// TodoWriteTool 15, EnterWorktreeTool 14, TaskStopTool 12, ListMcpResources 10,
// ReadMcpResource 9, TaskOutputTool 8, EnterPlanModeTool 6, TaskCreateTool 6,
// WebSearchTool 6, TaskUpdateTool 5, ScheduleCronTool 4, LSPTool 3,
// TaskGetTool 3, TaskListTool 3, ConfigTool 1, ExitWorktreeTool 1,
// TestingPermissionTool 1. All ≥ 1 — FR-013 confirmed.
//
// CC byte-identical: same imports exist in
// .references/claude-code-sourcemap/restored-src/src/tools.ts (CORE THESIS
// preserves byte-identical default).
// ============================================================================
import { BashTool } from './tools/BashTool/BashTool.js'
import { FileEditTool } from './tools/FileEditTool/FileEditTool.js'
import { FileReadTool } from './tools/FileReadTool/FileReadTool.js'
import { FileWriteTool } from './tools/FileWriteTool/FileWriteTool.js'
import { GlobTool } from './tools/GlobTool/GlobTool.js'
import { NotebookEditTool } from './tools/NotebookEditTool/NotebookEditTool.js'
import { WebFetchTool } from './tools/WebFetchTool/WebFetchTool.js'
import { TaskStopTool } from './tools/TaskStopTool/TaskStopTool.js'
import { BriefTool } from './tools/BriefTool/BriefTool.js'
// Dead code elimination: conditional import for ant-only tools
/* eslint-disable custom-rules/no-process-env-top-level, @typescript-eslint/no-require-imports */
const REPLTool =
  process.env.USER_TYPE === 'ant'
    ? require('./tools/REPLTool/REPLTool.js').REPLTool
    : null
// KOSMOS Spec 1633 / Epic #2293 — SuggestBackgroundPRTool deleted (claude-code dev workflow tool).
const SuggestBackgroundPRTool = null
const SleepTool =
  feature('PROACTIVE') || feature('KAIROS')
    ? require('./tools/SleepTool/SleepTool.js').SleepTool
    : null
const cronTools = feature('AGENT_TRIGGERS')
  ? [
      require('./tools/ScheduleCronTool/CronCreateTool.js').CronCreateTool,
      require('./tools/ScheduleCronTool/CronDeleteTool.js').CronDeleteTool,
      require('./tools/ScheduleCronTool/CronListTool.js').CronListTool,
    ]
  : []
const RemoteTriggerTool = feature('AGENT_TRIGGERS_REMOTE')
  ? require('./tools/RemoteTriggerTool/RemoteTriggerTool.js').RemoteTriggerTool
  : null
// KOSMOS Spec 1633 / Epic #2293 — MonitorTool deleted (claude-code dev workflow tool).
const MonitorTool = null
const SendUserFileTool = feature('KAIROS')
  ? require('./tools/SendUserFileTool/SendUserFileTool.js').SendUserFileTool
  : null
const PushNotificationTool =
  feature('KAIROS') || feature('KAIROS_PUSH_NOTIFICATION')
    ? require('./tools/PushNotificationTool/PushNotificationTool.js')
        .PushNotificationTool
    : null
const SubscribePRTool = feature('KAIROS_GITHUB_WEBHOOKS')
  ? require('./tools/SubscribePRTool/SubscribePRTool.js').SubscribePRTool
  : null
/* eslint-enable custom-rules/no-process-env-top-level, @typescript-eslint/no-require-imports */
import { TaskOutputTool } from './tools/TaskOutputTool/TaskOutputTool.js'
import { WebSearchTool } from './tools/WebSearchTool/WebSearchTool.js'
import { TodoWriteTool } from './tools/TodoWriteTool/TodoWriteTool.js'
import { ExitPlanModeV2Tool } from './tools/ExitPlanModeTool/ExitPlanModeV2Tool.js'
import { TestingPermissionTool } from './tools/testing/TestingPermissionTool.js'
import { GrepTool } from './tools/GrepTool/GrepTool.js'
// KOSMOS Spec 1633 / Epic #2293 — TungstenTool deleted (claude-code internal tool).
const TungstenTool = null
// Lazy require to break circular dependency: tools.ts -> TeamCreateTool/TeamDeleteTool -> ... -> tools.ts
/* eslint-disable @typescript-eslint/no-require-imports */
const getTeamCreateTool = () =>
  require('./tools/TeamCreateTool/TeamCreateTool.js')
    .TeamCreateTool as typeof import('./tools/TeamCreateTool/TeamCreateTool.js').TeamCreateTool
const getTeamDeleteTool = () =>
  require('./tools/TeamDeleteTool/TeamDeleteTool.js')
    .TeamDeleteTool as typeof import('./tools/TeamDeleteTool/TeamDeleteTool.js').TeamDeleteTool
const getSendMessageTool = () =>
  require('./tools/SendMessageTool/SendMessageTool.js')
    .SendMessageTool as typeof import('./tools/SendMessageTool/SendMessageTool.js').SendMessageTool
/* eslint-enable @typescript-eslint/no-require-imports */
import { AskUserQuestionTool } from './tools/AskUserQuestionTool/AskUserQuestionTool.js'
import { LSPTool } from './tools/LSPTool/LSPTool.js'
import { ListMcpResourcesTool } from './tools/ListMcpResourcesTool/ListMcpResourcesTool.js'
import { ReadMcpResourceTool } from './tools/ReadMcpResourceTool/ReadMcpResourceTool.js'
import { ToolSearchTool } from './tools/ToolSearchTool/ToolSearchTool.js'
import { EnterPlanModeTool } from './tools/EnterPlanModeTool/EnterPlanModeTool.js'
import { EnterWorktreeTool } from './tools/EnterWorktreeTool/EnterWorktreeTool.js'
import { ExitWorktreeTool } from './tools/ExitWorktreeTool/ExitWorktreeTool.js'
import { ConfigTool } from './tools/ConfigTool/ConfigTool.js'
import { TaskCreateTool } from './tools/TaskCreateTool/TaskCreateTool.js'
import { TaskGetTool } from './tools/TaskGetTool/TaskGetTool.js'
import { TaskUpdateTool } from './tools/TaskUpdateTool/TaskUpdateTool.js'
import { TaskListTool } from './tools/TaskListTool/TaskListTool.js'
import uniqBy from 'lodash-es/uniqBy.js'
import { isToolSearchEnabledOptimistic } from './utils/toolSearch.js'
import { isTodoV2Enabled } from './utils/tasks.js'
// Dead code elimination: conditional import for CLAUDE_CODE_VERIFY_PLAN
/* eslint-disable custom-rules/no-process-env-top-level, @typescript-eslint/no-require-imports */
// KOSMOS Spec 1633 / Epic #2293 — VerifyPlanExecutionTool deleted (claude-code dev workflow tool).
const VerifyPlanExecutionTool = null
/* eslint-enable custom-rules/no-process-env-top-level, @typescript-eslint/no-require-imports */
import { SYNTHETIC_OUTPUT_TOOL_NAME } from './tools/SyntheticOutputTool/SyntheticOutputTool.js'
export {
  ALL_AGENT_DISALLOWED_TOOLS,
  CUSTOM_AGENT_DISALLOWED_TOOLS,
  ASYNC_AGENT_ALLOWED_TOOLS,
  COORDINATOR_MODE_ALLOWED_TOOLS,
} from './constants/tools.js'
import { feature } from 'bun:bundle'
// Dead code elimination: conditional import for OVERFLOW_TEST_TOOL
/* eslint-disable custom-rules/no-process-env-top-level, @typescript-eslint/no-require-imports */
const OverflowTestTool = feature('OVERFLOW_TEST_TOOL')
  ? require('./tools/OverflowTestTool/OverflowTestTool.js').OverflowTestTool
  : null
const CtxInspectTool = feature('CONTEXT_COLLAPSE')
  ? require('./tools/CtxInspectTool/CtxInspectTool.js').CtxInspectTool
  : null
const TerminalCaptureTool = feature('TERMINAL_PANEL')
  ? require('./tools/TerminalCaptureTool/TerminalCaptureTool.js')
      .TerminalCaptureTool
  : null
const WebBrowserTool = feature('WEB_BROWSER_TOOL')
  ? require('./tools/WebBrowserTool/WebBrowserTool.js').WebBrowserTool
  : null
const coordinatorModeModule = feature('COORDINATOR_MODE')
  ? (require('./coordinator/coordinatorMode.js') as typeof import('./coordinator/coordinatorMode.js'))
  : null
const SnipTool = feature('HISTORY_SNIP')
  ? require('./tools/SnipTool/SnipTool.js').SnipTool
  : null
const ListPeersTool = feature('UDS_INBOX')
  ? require('./tools/ListPeersTool/ListPeersTool.js').ListPeersTool
  : null
// KOSMOS Spec 1633 / Epic #2293 — WorkflowTool deleted (claude-code multi-step
// workflow tool; KOSMOS uses primitive chains via system prompt).
const WorkflowTool = null
/* eslint-enable custom-rules/no-process-env-top-level, @typescript-eslint/no-require-imports */
import type { ToolPermissionContext } from './Tool.js'
import { getDenyRuleForTool } from './utils/permissions/permissions.js'
import { hasEmbeddedSearchTools } from './utils/embeddedTools.js'
import { isEnvTruthy } from './utils/envUtils.js'
import { isPowerShellToolEnabled } from './utils/shell/shellToolUtils.js'
import { isAgentSwarmsEnabled } from './utils/agentSwarmsEnabled.js'
import { isWorktreeModeEnabled } from './utils/worktreeModeEnabled.js'
import {
  REPL_TOOL_NAME,
  REPL_ONLY_TOOLS,
  isReplModeEnabled,
} from './tools/REPLTool/constants.js'
export { REPL_ONLY_TOOLS }
/* eslint-disable @typescript-eslint/no-require-imports */
const getPowerShellTool = () => {
  if (!isPowerShellToolEnabled()) return null
  return (
    require('./tools/PowerShellTool/PowerShellTool.js') as typeof import('./tools/PowerShellTool/PowerShellTool.js')
  ).PowerShellTool
}
/* eslint-enable @typescript-eslint/no-require-imports */

/**
 * Predefined tool presets that can be used with --tools flag
 */
export const TOOL_PRESETS = ['default'] as const

export type ToolPreset = (typeof TOOL_PRESETS)[number]

export function parseToolPreset(preset: string): ToolPreset | null {
  const presetString = preset.toLowerCase()
  if (!TOOL_PRESETS.includes(presetString as ToolPreset)) {
    return null
  }
  return presetString as ToolPreset
}

/**
 * Get the list of tool names for a given preset
 * Filters out tools that are disabled via isEnabled() check
 * @param preset The preset name
 * @returns Array of tool names
 */
export function getToolsForDefaultPreset(): string[] {
  const tools = getAllBaseTools()
  const isEnabled = tools.map(tool => tool.isEnabled())
  return tools.filter((_, i) => isEnabled[i]).map(tool => tool.name)
}

/**
 * Get the complete exhaustive list of all tools that could be available
 * in the current environment.
 *
 * **Epic #1634 P3 — closed 13-tool citizen-facing surface** (contracts/primitive-envelope.md § 1):
 *
 *   Active primitives (4):     lookup, resolve_location, submit, verify
 *   Retained CC auxiliary (2): WebFetch, WebSearch
 *   New auxiliary (4):         Translate, Calculator, DateParser, ExportPDF
 *   Task primitive backing:    AgentTool (rewired per T027)
 *   Citizen document:          Brief
 *   External MCP passthrough:  ListMcpResources, ReadMcpResource (paired for MCP semantics)
 *
 * Any tool outside this set is a regression caught by the CI tool-list closure
 * snapshot test (T035; contracts/routing-consistency.md § 3 check 7).
 *
 * The 14 "undecided" CC tools (TodoWrite / ToolSearch / AskUserQuestion /
 * Sleep / Monitor / Workflow / ScheduleCron / Task-* × 5 / Team-* × 2) were
 * resolved per T027a: 9 defer-to-P4 (#1635), 5 delete-in-followup (#1757).
 * None are registered here. See
 * ``specs/1634-tool-system-wiring/decisions/undecided-tools.md``.
 *
 * The 15 CC dev tools (Bash, FileEdit, FileRead, FileWrite, Glob, Grep,
 * NotebookEdit, PowerShell, LSP, REPL, Config, EnterWorktree, ExitWorktree,
 * EnterPlanMode, ExitPlanMode) remain imported at compile time because their
 * name constants are consumed by the permissions / sandbox / attachments
 * infrastructure (FR-013 scope correction, #1757). They are NOT registered
 * here and therefore NOT LLM-visible.
 */
export function getAllBaseTools(): Tools {
  return [
    // Active reserved primitives — FR-001 / Spec 031.
    // subscribe is intentionally not LLM-visible until KOSMOS has an app/push
    // notification surface that matches the real national-service model.
    LookupPrimitive,
    ResolveLocationPrimitive,
    SubmitPrimitive,
    VerifyPrimitive,

    // Retained CC auxiliary — FR-015 + FR-016
    WebFetchTool,
    WebSearchTool,

    // New auxiliary (MVP-7 completion) — FR-018
    TranslateTool,
    CalculatorTool,
    DateParserTool,
    ExportPDFTool,

    // AgentTool repurposed as Task primitive backing — FR-017
    AgentTool,

    // Citizen document surface — FR-016
    BriefTool,

    // External MCP passthrough — FR-016 (listed as single logical "MCP" in contract § 1;
    // CC splits list + read into two tools, both kept as-is for CC parity)
    ListMcpResourcesTool,
    ReadMcpResourceTool,
  ]
}

/**
 * Filters out tools that are blanket-denied by the permission context.
 * A tool is filtered out if there's a deny rule matching its name with no
 * ruleContent (i.e., a blanket deny for that tool).
 *
 * Uses the same matcher as the runtime permission check (step 1a), so MCP
 * server-prefix rules like `mcp__server` strip all tools from that server
 * before the model sees them — not just at call time.
 */
export function filterToolsByDenyRules<
  T extends {
    name: string
    mcpInfo?: { serverName: string; toolName: string }
  },
>(tools: readonly T[], permissionContext: ToolPermissionContext): T[] {
  return tools.filter(tool => !getDenyRuleForTool(permissionContext, tool))
}

export const getTools = (permissionContext: ToolPermissionContext): Tools => {
  // Simple mode: only Bash, Read, and Edit tools
  if (isEnvTruthy(process.env.CLAUDE_CODE_SIMPLE)) {
    // --bare + REPL mode: REPL wraps Bash/Read/Edit/etc inside the VM, so
    // return REPL instead of the raw primitives. Matches the non-bare path
    // below which also hides REPL_ONLY_TOOLS when REPL is enabled.
    // SWAP-2-PRESERVE: byte-identical with CC tools.ts:277. The `&& REPLTool` guard
    // makes this branch provably dead in KOSMOS (REPLTool=null per Spec 1633 / Epic #2293)
    // even when isReplModeEnabled() is true via CLAUDE_REPL_MODE or USER_TYPE=ant.
    // Branch preserved for CC parity (CORE THESIS: byte-identical default).
    if (isReplModeEnabled() && REPLTool) {
      const replSimple: Tool[] = [REPLTool]
      if (
        feature('COORDINATOR_MODE') &&
        coordinatorModeModule?.isCoordinatorMode()
      ) {
        replSimple.push(TaskStopTool, getSendMessageTool())
      }
      return filterToolsByDenyRules(replSimple, permissionContext)
    }
    const simpleTools: Tool[] = [BashTool, FileReadTool, FileEditTool]
    // When coordinator mode is also active, include AgentTool and TaskStopTool
    // so the coordinator gets Task+TaskStop (via useMergedTools filtering) and
    // workers get Bash/Read/Edit (via filterToolsForAgent filtering).
    if (
      feature('COORDINATOR_MODE') &&
      coordinatorModeModule?.isCoordinatorMode()
    ) {
      simpleTools.push(AgentTool, TaskStopTool, getSendMessageTool())
    }
    return filterToolsByDenyRules(simpleTools, permissionContext)
  }

  // Get all base tools and filter out special tools that get added conditionally
  const specialTools = new Set([
    ListMcpResourcesTool.name,
    ReadMcpResourceTool.name,
    SYNTHETIC_OUTPUT_TOOL_NAME,
  ])

  const tools = getAllBaseTools().filter(tool => !specialTools.has(tool.name))

  // Filter out tools that are denied by the deny rules
  let allowedTools = filterToolsByDenyRules(tools, permissionContext)

  // When REPL mode is enabled, hide primitive tools from direct use.
  // They're still accessible inside REPL via the VM context.
  // SWAP-2-PRESERVE: byte-identical with CC tools.ts:314. isReplModeEnabled() is
  // env-gated (CLAUDE_REPL_MODE or USER_TYPE=ant + CLAUDE_CODE_ENTRYPOINT=cli) and
  // CAN run in those cases. With REPLTool=null (Spec 1633 / Epic #2293), no
  // REPL_TOOL_NAME tool exists in `allowedTools`, so `replEnabled` evaluates to
  // false and the REPL_ONLY_TOOLS filter step is a no-op. Branch preserved for
  // CC parity (CORE THESIS: byte-identical default).
  if (isReplModeEnabled()) {
    const replEnabled = allowedTools.some(tool =>
      toolMatchesName(tool, REPL_TOOL_NAME),
    )
    if (replEnabled) {
      allowedTools = allowedTools.filter(
        tool => !REPL_ONLY_TOOLS.has(tool.name),
      )
    }
  }

  const isEnabled = allowedTools.map(_ => _.isEnabled())
  return allowedTools.filter((_, i) => isEnabled[i])
}

/**
 * Assemble the full tool pool for a given permission context and MCP tools.
 *
 * This is the single source of truth for combining built-in tools with MCP tools.
 * Both REPL.tsx (via useMergedTools hook) and runAgent.ts (for coordinator workers)
 * use this function to ensure consistent tool pool assembly.
 *
 * The function:
 * 1. Gets built-in tools via getTools() (respects mode filtering)
 * 2. Filters MCP tools by deny rules
 * 3. Deduplicates by tool name (built-in tools take precedence)
 *
 * @param permissionContext - Permission context for filtering built-in tools
 * @param mcpTools - MCP tools from appState.mcp.tools
 * @returns Combined, deduplicated array of built-in and MCP tools
 */
export function assembleToolPool(
  permissionContext: ToolPermissionContext,
  mcpTools: Tools,
): Tools {
  const builtInTools = getTools(permissionContext)

  // Filter out MCP tools that are in the deny list
  const allowedMcpTools = filterToolsByDenyRules(mcpTools, permissionContext)

  // Sort each partition for prompt-cache stability, keeping built-ins as a
  // contiguous prefix. The server's claude_code_system_cache_policy places a
  // global cache breakpoint after the last prefix-matched built-in tool; a flat
  // sort would interleave MCP tools into built-ins and invalidate all downstream
  // cache keys whenever an MCP tool sorts between existing built-ins. uniqBy
  // preserves insertion order, so built-ins win on name conflict.
  // Avoid Array.toSorted (Node 20+) — we support Node 18. builtInTools is
  // readonly so copy-then-sort; allowedMcpTools is a fresh .filter() result.
  const byName = (a: Tool, b: Tool) => a.name.localeCompare(b.name)
  return uniqBy(
    [...builtInTools].sort(byName).concat(allowedMcpTools.sort(byName)),
    'name',
  )
}

/**
 * Get all tools including both built-in tools and MCP tools.
 *
 * This is the preferred function when you need the complete tools list for:
 * - Tool search threshold calculations (isToolSearchEnabled)
 * - Token counting that includes MCP tools
 * - Any context where MCP tools should be considered
 *
 * Use getTools() only when you specifically need just built-in tools.
 *
 * @param permissionContext - Permission context for filtering built-in tools
 * @param mcpTools - MCP tools from appState.mcp.tools
 * @returns Combined array of built-in and MCP tools
 */
export function getMergedTools(
  permissionContext: ToolPermissionContext,
  mcpTools: Tools,
): Tools {
  const builtInTools = getTools(permissionContext)
  return [...builtInTools, ...mcpTools]
}
