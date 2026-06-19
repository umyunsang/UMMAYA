import { createRequire } from 'node:module'
import { buildTool, type ToolDef } from 'src/Tool.js'
import type * as AgentToolUI from './UI.js'
import { checkAgentToolPermissions } from './permissions.js'
import { mapAgentToolResultToToolResultBlockParam } from './resultMapping.js'
import {
  inputSchema,
  outputSchema,
  type AgentToolInput,
  type AgentToolOutput,
  type InputSchema,
  type OutputSchema,
  type Progress,
  type RemoteLaunchedOutput,
} from './schemas.js'
import {
  AGENT_TOOL_NAME,
  LEGACY_AGENT_TOOL_NAME,
} from './constants.js'

export { inputSchema, outputSchema }
export type { RemoteLaunchedOutput }

const requireUi = createRequire(import.meta.url)
let uiModule: typeof AgentToolUI | undefined

function getUi(): typeof AgentToolUI {
  if (uiModule === undefined) {
    const loaded: typeof AgentToolUI = requireUi('./UI.js')
    uiModule = loaded
  }
  return uiModule
}

function toAgentAutoClassifierInput(input: Partial<AgentToolInput>): string {
  const tags = [
    input.subagent_type,
    input.mode ? `mode=${input.mode}` : undefined,
  ].filter((tag): tag is string => tag !== undefined)
  const prefix = tags.length > 0 ? `(${tags.join(', ')}): ` : ': '
  return `${prefix}${input.prompt ?? ''}`
}

export const AgentTool = buildTool({
  async prompt(options) {
    const { buildAgentToolPrompt } = await import('./launchRouting.js')
    return buildAgentToolPrompt(options)
  },
  name: AGENT_TOOL_NAME,
  searchHint: 'delegate work to a subagent',
  aliases: [LEGACY_AGENT_TOOL_NAME],
  maxResultSizeChars: 100_000,
  async description() {
    return 'Launch a new agent'
  },
  get inputSchema(): InputSchema {
    return inputSchema()
  },
  get outputSchema(): OutputSchema {
    return outputSchema()
  },
  async call(input, toolUseContext, canUseTool, assistantMessage, onProgress) {
    const { callAgentTool } = await import('./lifecycle.js')
    return callAgentTool(
      input,
      toolUseContext,
      canUseTool,
      assistantMessage,
      onProgress,
    )
  },
  isReadOnly() {
    return true
  },
  toAutoClassifierInput: toAgentAutoClassifierInput,
  isConcurrencySafe() {
    return true
  },
  userFacingName(input) {
    return getUi().userFacingName(input)
  },
  userFacingNameBackgroundColor(input) {
    return getUi().userFacingNameBackgroundColor(input)
  },
  getActivityDescription(input) {
    return input?.description ?? 'Running task'
  },
  checkPermissions: checkAgentToolPermissions,
  mapToolResultToToolResultBlockParam: mapAgentToolResultToToolResultBlockParam,
  renderToolResultMessage(...args) {
    return getUi().renderToolResultMessage(...args)
  },
  renderToolUseMessage(...args) {
    return getUi().renderToolUseMessage(...args)
  },
  renderToolUseTag(input) {
    return getUi().renderToolUseTag(input)
  },
  renderToolUseProgressMessage(...args) {
    return getUi().renderToolUseProgressMessage(...args)
  },
  renderToolUseRejectedMessage(...args) {
    return getUi().renderToolUseRejectedMessage(...args)
  },
  renderToolUseErrorMessage(...args) {
    return getUi().renderToolUseErrorMessage(...args)
  },
  renderGroupedToolUse(...args) {
    return getUi().renderGroupedAgentToolUse(...args)
  },
} satisfies ToolDef<InputSchema, AgentToolOutput, Progress>)
