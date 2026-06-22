import { z } from 'zod/v4'
import type { Tool } from '../../../Tool.js'
import type {
  OpenAITool,
  ProviderOptions,
  ProviderRequest,
  QueryModelParams,
} from './types.js'
import { latestUserText, transcriptToOpenAIMessages } from './messages.js'
import {
  selectProviderToolChoiceName,
  selectProviderTools,
} from './toolSelection.js'
import { isAdapterToolName } from '../../../tools/AdapterTool/AdapterTool.js'
import type { ProviderTurnEvidenceContext } from './evidence.js'
import {
  hasCurrentTurnLocationContext,
  selectionTextWithPriorLocationContext,
} from './selectionContext.js'
import {
  providerReasoningRequestPayload,
  resolveProviderReasoningPolicy,
} from './reasoning.js'
import type { ResolvedReasoningPolicy } from '../../../utils/kExaoneReasoning.js'

function forcedToolChoiceSystemInstruction(toolName: string): string {
  if (toolName === 'workspace_bash') {
    return [
      `Mandatory tool call: the host selected ${toolName} for this turn.`,
      "Before the tool call, emit exactly one brief user-visible prelude in the user's language that states the next check.",
      'Do not ask a follow-up question, do not choose another tool, and do not provide the final answer before the tool result.',
      `Emit exactly one ${toolName} tool call with valid JSON arguments.`,
      'For sequenced shell requests, emit the next concrete shell command requested by the user rather than a status summary.',
      'If the user asks to attempt a destructive command and says they will deny the permission prompt, still emit that destructive command so the host permission gate can prompt and enforce the denial.',
      'Do not replace a requested delete command with ls/find/path-existence prose, and preserve leading dots in hidden paths such as .omo/...',
    ].join(' ')
  }
  return [
    `Mandatory tool call: the host selected ${toolName} for this turn.`,
    "Before the tool call, emit exactly one brief user-visible prelude in the user's language that states the next check.",
    'Do not ask a follow-up question, do not choose another tool, and do not provide the final answer before the tool result.',
    `Emit exactly one ${toolName} tool call with valid JSON arguments.`,
  ].join(' ')
}

function reasoningSystemInstruction(
  policy: ResolvedReasoningPolicy,
): string | undefined {
  if (!policy.enableThinking) return undefined
  return [
    'Provider thinking is enabled for this turn.',
    'Keep hidden reasoning concise for simple answer-only requests and move to the final answer as soon as enough evidence is available.',
    'Use extended reasoning only when it materially improves correctness for multi-step calculations, tool planning, code, or public-service workflows.',
    'Do not spend the whole completion budget on thinking; preserve budget for visible final answer text.',
  ].join(' ')
}

function extraSystemInstruction(params: {
  readonly activeToolChoiceName?: string
  readonly reasoningPolicy: ResolvedReasoningPolicy
}): string | undefined {
  const parts = [
    params.activeToolChoiceName
      ? forcedToolChoiceSystemInstruction(params.activeToolChoiceName)
      : undefined,
    reasoningSystemInstruction(params.reasoningPolicy),
  ].filter((part): part is string => part !== undefined)
  return parts.length > 0 ? parts.join(' ') : undefined
}

function schemaForTool(tool: Tool): Record<string, unknown> {
  if (tool.inputJSONSchema) {
    return normalizeProviderParameterSchema(tool.inputJSONSchema)
  }
  const generatedSchema = z.toJSONSchema(tool.inputSchema)
  return normalizeProviderParameterSchema(
    isJsonObject(generatedSchema) ? generatedSchema : {},
  )
}

function normalizeProviderParameterSchema(
  schema: Record<string, unknown>,
): Record<string, unknown> {
  const normalized = normalizeSchemaNode(schema, schema, new Set<string>())
  if (isJsonObject(normalized)) return normalized
  return providerSafeUnresolvedRefSchema()
}

function normalizeSchemaNode(
  value: unknown,
  root: Record<string, unknown>,
  refStack: ReadonlySet<string>,
): unknown {
  if (Array.isArray(value)) {
    return value.map(item => normalizeSchemaNode(item, root, refStack))
  }
  if (!isJsonObject(value)) return value

  const ref = typeof value.$ref === 'string' ? value.$ref : undefined
  if (ref !== undefined) {
    const inlined = inlineLocalSchemaRef(ref, value, root, refStack)
    if (inlined !== undefined) return inlined
    return providerSafeUnresolvedRefSchema()
  }

  const normalized: Record<string, unknown> = {}
  for (const [key, child] of Object.entries(value)) {
    if (key === '$defs' || key === 'definitions') continue
    normalized[key] = normalizeSchemaNode(child, root, refStack)
  }
  return normalized
}

function inlineLocalSchemaRef(
  ref: string,
  schemaWithRef: Record<string, unknown>,
  root: Record<string, unknown>,
  refStack: ReadonlySet<string>,
): unknown | undefined {
  if (refStack.has(ref)) return undefined
  const resolved = resolveLocalSchemaRef(root, ref)
  if (resolved === undefined) return undefined
  const nextStack = new Set(refStack)
  nextStack.add(ref)
  const normalizedResolved = normalizeSchemaNode(resolved, root, nextStack)
  if (!isJsonObject(normalizedResolved)) return normalizedResolved

  const normalizedSiblings: Record<string, unknown> = {}
  for (const [key, child] of Object.entries(schemaWithRef)) {
    if (key === '$ref' || key === '$defs' || key === 'definitions') continue
    normalizedSiblings[key] = normalizeSchemaNode(child, root, nextStack)
  }
  return {
    ...normalizedResolved,
    ...normalizedSiblings,
  }
}

function resolveLocalSchemaRef(
  root: Record<string, unknown>,
  ref: string,
): unknown | undefined {
  if (ref === '#') return root
  if (!ref.startsWith('#/')) return undefined

  let current: unknown = root
  for (const segment of ref.slice(2).split('/').map(decodeJsonPointerSegment)) {
    if (!isJsonObject(current)) return undefined
    current = current[segment]
  }
  return current
}

function decodeJsonPointerSegment(segment: string): string {
  return segment.replace(/~1/g, '/').replace(/~0/g, '~')
}

function providerSafeUnresolvedRefSchema(): Record<string, unknown> {
  return {
    type: 'object',
    description:
      'Provider-safe open object for an unresolved local schema reference.',
    properties: {},
    additionalProperties: true,
  }
}

function isJsonObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function parseJsonObject(value: unknown): Record<string, unknown> | undefined {
  if (isJsonObject(value)) return value
  if (typeof value !== 'string') return undefined
  try {
    const parsed: unknown = JSON.parse(value)
    return isJsonObject(parsed) ? parsed : undefined
  } catch {
    return undefined
  }
}

function messageEnvelope(message: unknown): Record<string, unknown> | undefined {
  if (!isJsonObject(message)) return undefined
  return isJsonObject(message.message) ? message.message : undefined
}

function messageContentBlocks(message: unknown): readonly Record<string, unknown>[] {
  const content = messageEnvelope(message)?.content
  return Array.isArray(content) ? content.filter(isJsonObject) : []
}

function isToolResultBlock(block: Record<string, unknown>): boolean {
  return block.type === 'tool_result'
}

function isStructuredFailureResult(value: unknown): boolean {
  return parseJsonObject(value)?.ok === false
}

function isCitizenPromptMessage(message: unknown): boolean {
  if (!isJsonObject(message) || message.type !== 'user') return false
  const content = messageEnvelope(message)?.content
  if (!Array.isArray(content)) return true
  const blocks = content.filter(isJsonObject)
  return !blocks.every(isToolResultBlock)
}

function latestCitizenPromptIndex(messages: readonly unknown[]): number {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (isCitizenPromptMessage(messages[index])) return index
  }
  return -1
}

function successfulToolNamesSinceLatestPrompt(
  messages: readonly unknown[],
): ReadonlySet<string> {
  const startIndex = latestCitizenPromptIndex(messages)
  const toolNamesByUseId = new Map<string, string>()
  const successfulResultIds = new Set<string>()
  for (const message of messages.slice(startIndex + 1)) {
    if (!isJsonObject(message)) continue
    for (const block of messageContentBlocks(message)) {
      if (
        message.type === 'assistant' &&
        block.type === 'tool_use' &&
        typeof block.id === 'string' &&
        typeof block.name === 'string'
      ) {
        toolNamesByUseId.set(block.id, block.name)
      }
      if (
        message.type === 'user' &&
        block.type === 'tool_result' &&
        block.is_error !== true &&
        typeof block.tool_use_id === 'string' &&
        !isStructuredFailureResult(block.content)
      ) {
        successfulResultIds.add(block.tool_use_id)
      }
    }
  }
  const names = new Set<string>()
  for (const id of successfulResultIds) {
    const name = toolNamesByUseId.get(id)
    if (name !== undefined) names.add(name)
  }
  return names
}

function toolToOpenAI(tool: Tool): OpenAITool {
  return {
    type: 'function',
    function: {
      name: tool.name,
      description: tool.searchHint ?? tool.name,
      parameters: schemaForTool(tool),
    },
  }
}

function toolChoiceFor(
  toolName: string | undefined,
): ProviderRequest['tool_choice'] {
  if (toolName === undefined) return undefined
  return {
    type: 'function',
    function: { name: toolName },
  }
}

function firstUnresolvedAdapterToolName(
  tools: readonly Tool[],
  messages: QueryModelParams['messages'],
): string | undefined {
  const successfulToolNames = successfulToolNamesSinceLatestPrompt(messages)
  return tools.find(
    tool => isAdapterToolName(tool.name) && !successfulToolNames.has(tool.name),
  )?.name
}

export function buildProviderRequest(
  params: QueryModelParams,
  evidenceContext?: ProviderTurnEvidenceContext,
): ProviderRequest {
  const forcedToolName =
    params.options.toolChoice?.type === 'tool'
      ? params.options.toolChoice.name
      : undefined
  const userText = selectionTextWithPriorLocationContext(params.messages)
  const selectedToolChoiceName = selectProviderToolChoiceName({
    tools: params.tools,
    userText,
    forcedToolName,
  })
  const tools = selectProviderTools({
    tools: params.tools,
    userText,
    forcedToolName: selectedToolChoiceName,
    disabledToolNames: params.options.disabledProviderToolNames ?? [],
    querySource: params.options.querySource,
    hasCurrentTurnLocationContext: hasCurrentTurnLocationContext(params.messages),
    evidenceContext,
  })
  const activeToolChoiceName =
    selectedToolChoiceName ?? firstUnresolvedAdapterToolName(tools, params.messages)
  const toolChoice = toolChoiceFor(activeToolChoiceName)
  const toolPayload = tools.map(toolToOpenAI)
  const reasoningPolicy = resolveProviderReasoningPolicy()
  return {
    model: params.options.model,
    stream: true,
    ...providerReasoningRequestPayload(reasoningPolicy),
    messages: transcriptToOpenAIMessages(
      params.messages,
      params.systemPrompt,
      extraSystemInstruction({ activeToolChoiceName, reasoningPolicy }),
    ),
    ...(toolPayload.length > 0 ? { tools: toolPayload } : {}),
    ...(toolChoice ? { tool_choice: toolChoice } : {}),
  }
}

export function getAPIMetadata(): Record<string, string> {
  return { user_id: 'ummaya-local' }
}
