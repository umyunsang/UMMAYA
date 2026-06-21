import { findToolByName, type Tool, type ToolUseContext } from '../Tool.js'
import type { AssistantMessage, Message, UserMessage } from '../types/message.js'
import { getAdapterToolByName } from '../tools/AdapterTool/AdapterTool.js'
import {
  repairUmmayaDocumentToolInputForDispatch,
} from '../tools/_shared/toolChoiceRepair.js'
import { deriveLocationQueryFromUserText } from '../tools/_shared/locationInputRepair.js'
import { backfillMojVillageLawyerRegionInput } from '../tools/_shared/publicAdapterInputRepair.js'
import { createUserMessage } from '../utils/messages.js'
import { isUnregisteredRawJsonToolUseId } from '../utils/rawJsonToolCall.js'
import { formatZodValidationError } from '../utils/toolErrors.js'
import {
  latestTextUserMessageIndex,
  messageText,
  type ToolUseBlock,
} from './messageGuards.js'
import { createToolUnavailableErrorPayload } from './toolResultErrors.js'

function serializeToolResult(data: unknown): string {
  if (typeof data === 'string') return data
  if (data === null || data === undefined) return ''
  try {
    return JSON.stringify(data)
  } catch {
    return String(data)
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function parseJsonRecord(value: unknown): Record<string, unknown> | undefined {
  if (isRecord(value)) return value
  if (typeof value !== 'string') return undefined
  try {
    const parsed: unknown = JSON.parse(value)
    return isRecord(parsed) ? parsed : undefined
  } catch {
    return undefined
  }
}

function isStructuredFailureResult(value: unknown): boolean {
  return parseJsonRecord(value)?.ok === false
}

function normalizeToolResultDataForModel(
  toolName: string,
  data: unknown,
): unknown {
  if (toolName !== 'document' || !isRecord(data) || data.ok !== false) {
    return data
  }
  if (isRecord(data.result) && data.result.tool_id === 'document') {
    return data
  }
  const error = isRecord(data.error) ? data.error : undefined
  const message = typeof error?.message === 'string'
    ? error.message
    : 'Document tool failed before producing a document result.'
  return {
    ...data,
    result: {
      tool_id: 'document',
      status: 'failed',
      text_summary: message,
    },
  }
}

function permissionErrorMessage(message: string | undefined): string {
  const trimmed = message?.trim()
  return trimmed
    ? `Permission denied: ${trimmed}`
    : 'Permission denied: tool execution was not approved.'
}

type ToolInput = { readonly [key: string]: unknown }

type SuccessfulToolCall = {
  readonly toolName: string
  readonly input: ToolInput
}

const MAX_SUCCESSFUL_CALLS_PER_EFFECTIVE_TOOL = 2
const HOMETAX_LOOKUP_TOOL_NAME = 'mock_lookup_module_hometax_simplified'
const KMA_METAR_TOOL_NAME = 'kma_apihub_url_air_metar_decoded'
const ROOT_FIND_TOOL_NAME = 'find'
const KAKAO_LOCATION_TOOL_NAMES = new Set([
  'kakao_address_search',
  'kakao_keyword_search',
])
const KMA_ORDINARY_WEATHER_TOOL_NAMES = new Set([
  'kma_apihub_upp_mtly_info_service_get_max_wind',
  'kma_current_observation',
  'kma_forecast_fetch',
  'kma_short_term_forecast',
  'kma_ultra_short_term_forecast',
])
const TAGO_ROUTE_TOOL_NAME = 'tago_bus_route_search'
const MOHW_WELFARE_TOOL_NAME = 'mohw_welfare_eligibility_search'
const PPS_SHOPPING_MALL_PRODUCT_TOOL_NAME = 'pps_shopping_mall_product_lookup'
const NMC_AED_TOOL_NAME = 'nmc_aed_site_locate'
const AED_NEAR_REQUEST_RE =
  /((?:AED|자동심장충격기|제세동기).*(?:근처|주변|인근|가까운|가장\s*가까운)|(?:근처|주변|인근|가까운|가장\s*가까운).*(?:AED|자동심장충격기|제세동기))/iu
const AED_NEAR_TARGET_SPLIT_RE = /근처|주변|인근|가까운|가장\s*가까운/iu
const TAGO_ROUTE_FOLLOWUP_TOOL_NAMES = new Set([
  'tago_bus_arrival_search',
  'tago_bus_location_search',
  'tago_bus_route_station_search',
  'tago_bus_station_search',
])

function stableJson(value: unknown): string {
  if (Array.isArray(value)) {
    return `[${value.map(stableJson).join(',')}]`
  }
  if (isRecord(value)) {
    return `{${Object.keys(value)
      .sort()
      .map(key => `${JSON.stringify(key)}:${stableJson(value[key])}`)
      .join(',')}}`
  }
  const encoded = JSON.stringify(value)
  return encoded === undefined ? String(value) : encoded
}

function toolInputsEquivalent(
  tool: Tool,
  left: ToolInput,
  right: ToolInput,
): boolean {
  return tool.inputsEquivalent?.(left, right) ?? stableJson(left) === stableJson(right)
}

function effectiveToolKey(toolName: string, input: ToolInput): string {
  const concreteToolId = input.tool_id
  if (typeof concreteToolId === 'string' && concreteToolId.trim().length > 0) {
    return `${toolName}:${concreteToolId}`
  }
  return toolName
}

function isCitizenPromptMessage(message: Message): boolean {
  if (message.type !== 'user') return false
  if (message.isMeta === true) return false
  const content = message.message.content
  if (!Array.isArray(content)) return true
  return !content.every(block => block.type === 'tool_result')
}

function latestCitizenPromptIndex(messages: readonly Message[]): number {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index]
    if (message !== undefined && isCitizenPromptMessage(message)) {
      return index
    }
  }
  return -1
}

function latestCitizenPromptText(messages: readonly Message[]): string {
  const index = latestTextUserMessageIndex(messages)
  const message = index >= 0 ? messages[index] : undefined
  return message ? messageText(message) : ''
}

function successfulToolResultIdsSinceLatestPrompt(
  messages: readonly Message[],
): ReadonlySet<string> {
  const startIndex = latestCitizenPromptIndex(messages)
  const ids = new Set<string>()
  for (const message of messages.slice(startIndex + 1)) {
    if (message.type !== 'user' || !Array.isArray(message.message.content)) {
      continue
    }
    for (const block of message.message.content) {
      if (
        block.type === 'tool_result' &&
        block.is_error !== true &&
        !isStructuredFailureResult(block.content)
      ) {
        ids.add(block.tool_use_id)
      }
    }
  }
  return ids
}

function successfulToolCallsSinceLatestPrompt(
  messages: readonly Message[],
): readonly SuccessfulToolCall[] {
  const startIndex = latestCitizenPromptIndex(messages)
  const successfulResultIds = successfulToolResultIdsSinceLatestPrompt(messages)
  const calls: SuccessfulToolCall[] = []
  for (const message of messages.slice(startIndex + 1)) {
    if (message.type !== 'assistant') continue
    for (const block of message.message.content) {
      if (
        block.type === 'tool_use' &&
        successfulResultIds.has(block.id) &&
        isRecord(block.input)
      ) {
        calls.push({
          toolName: block.name,
          input: repairDirectLocationToolInputForValidation({
            toolName: block.name,
            input: block.input,
            messages,
          }),
        })
      }
    }
  }
  return calls
}

type PriorToolResult = {
  readonly toolName: string
  readonly input: ToolInput | undefined
  readonly content: unknown
  readonly isError: boolean
  readonly isStructuredFailure: boolean
}

function toolResultsSinceLatestPrompt(
  messages: readonly Message[],
): readonly PriorToolResult[] {
  const startIndex = latestCitizenPromptIndex(messages)
  const toolCallsByUseId = new Map<
    string,
    { readonly toolName: string; readonly input: ToolInput | undefined }
  >()
  const results: PriorToolResult[] = []
  for (const message of messages.slice(startIndex + 1)) {
    if (message.type === 'assistant') {
      for (const block of message.message.content) {
        if (block.type === 'tool_use') {
          toolCallsByUseId.set(block.id, {
            toolName: block.name,
            input: isRecord(block.input) ? block.input : undefined,
          })
        }
      }
      continue
    }
    if (message.type !== 'user' || !Array.isArray(message.message.content)) {
      continue
    }
    for (const block of message.message.content) {
      if (block.type !== 'tool_result') continue
      const toolCall = toolCallsByUseId.get(block.tool_use_id)
      if (toolCall === undefined) continue
      results.push({
        toolName: toolCall.toolName,
        input: toolCall.input,
        content: block.content,
        isError: block.is_error === true,
        isStructuredFailure: isStructuredFailureResult(block.content),
      })
    }
  }
  return results
}

function repeatedToolUseMessage(toolName: string): string {
  return `<tool_use_error>RepeatedToolUseError: Tool '${toolName}' already returned a successful result for the same effective inputs in this query loop. Use the prior tool result, or call with different parameters only if the citizen goal requires a broader follow-up.</tool_use_error>`
}

function hometaxProgressionMessage(): string {
  return [
    'Hometax lookup already returned a usable simplified-tax lookup result for this citizen request.',
    'Do not repeat the same lookup before the required 본인확인, 위임, and 동의 progression.',
    'Next valid step: call the verify tool for 본인확인/위임 동의, or write a Korean needs-input answer asking for that approval.',
  ].join(' ')
}

function kmaAviationRepeatMessage(kind: 'usable' | 'blocked'): string {
  return kind === 'usable'
    ? [
        'KMA aviation lookup already returned usable METAR evidence for this airport request.',
        'Do not repeat the decoded METAR tool in the same query loop.',
        'Use the prior aviation tool_result to answer the delay-risk question and state any remaining manual notification limitation.',
      ].join(' ')
    : [
        'KMA aviation lookup already returned a blocked result for this airport request.',
        'Do not retry the decoded METAR tool without new credential/configuration evidence.',
        'Write a Korean handoff answer that names the aviation weather credential limitation.',
      ].join(' ')
}

function kmaOrdinaryFallbackMessage(toolName: string): string {
  return [
    `Do not call ${toolName} as a fallback for airport aviation weather after aviation METAR evidence exists.`,
    'Do not ask the user for KMA nx/ny grid coordinates for an airport-flight risk question.',
    'Use the aviation weather evidence already returned, or give a Korean handoff answer for official airline/airport status checks.',
  ].join(' ')
}

function kmaGridRepeatMessage(toolName: string): string {
  return [
    'Do not repeat ordinary KMA current or forecast tools after a missing-grid or invalid-grid result.',
    `Tool ${toolName} already failed for this route/weather turn without required grid parameters.`,
    'Answer from the existing location evidence and ask for a precise district/date-time only if more weather detail is required.',
  ].join(' ')
}

function locationRepeatMessage(toolName: string, query: string): string {
  return [
    `Location lookup ${toolName} already returned usable Kakao coordinates for "${query}" in this query loop.`,
    'Do not repeat the same location lookup.',
    'Use the prior location evidence, or call the same adapter with a different origin, destination, radius, or refined query when the citizen goal requires it.',
  ].join(' ')
}

function shouldUseGenericRepeatGuard(tool: Tool, toolName: string): boolean {
  return tool.inputsEquivalent !== undefined || toolName === ROOT_FIND_TOOL_NAME
}

function priorKmaAviationResultKind(
  priorResults: readonly PriorToolResult[],
): 'usable' | 'blocked' | undefined {
  const aviationResult = priorResults.find(
    result => result.toolName === KMA_METAR_TOOL_NAME,
  )
  if (aviationResult === undefined) return undefined
  return aviationResult.isStructuredFailure || aviationResult.isError
    ? 'blocked'
    : 'usable'
}

function isKmaGridFailureResult(result: PriorToolResult): boolean {
  if (!KMA_ORDINARY_WEATHER_TOOL_NAMES.has(result.toolName)) return false
  const text = serializeToolResult(result.content)
  return (
    /Missing or invalid fields|LOCATE FIRST|nx\/ny/iu.test(text) ||
    /(?:missing|required|invalid)[^.\n]*(?:base_date|base_time)/iu.test(text) ||
    /(?:base_date|base_time)[^.\n]*(?:missing|required|invalid)/iu.test(text)
  )
}

function createGuardToolResult(
  block: ToolUseBlock,
  assistantMessage: AssistantMessage,
  message: string,
): UserMessage {
  return createUserMessage({
    content: [
      {
        type: 'tool_result',
        tool_use_id: block.id,
        content: message,
        is_error: true,
      },
    ],
    toolUseResult: `Error: ${message}`,
    sourceToolAssistantUUID: assistantMessage.uuid,
  })
}

function createTerminalGuardToolResult(
  block: ToolUseBlock,
  assistantMessage: AssistantMessage,
  message: string,
): UserMessage {
  const payload = {
    ok: true,
    result: {
      kind: 'terminal_limitation',
      message,
    },
  }
  return createUserMessage({
    content: [
      {
        type: 'tool_result',
        tool_use_id: block.id,
        content: JSON.stringify(payload),
      },
    ],
    toolUseResult: payload,
    sourceToolAssistantUUID: assistantMessage.uuid,
  })
}

function recordHasZeroCollectionCount(value: unknown): boolean {
  if (!isRecord(value)) return false
  const kind = value.kind
  const items = value.items
  const totalCount = value.total_count ?? value.totalCount
  const totalIsZero =
    totalCount === 0 ||
    totalCount === '0' ||
    totalCount === null ||
    totalCount === undefined
  if (
    (kind === 'collection' || Array.isArray(items)) &&
    Array.isArray(items) &&
    items.length === 0 &&
    totalIsZero
  ) {
    return true
  }
  return ['data', 'result', 'payload'].some(key =>
    recordHasZeroCollectionCount(value[key]),
  )
}

function isZeroCollectionToolResult(content: unknown): boolean {
  if (recordHasZeroCollectionCount(content)) return true
  const parsed = parseJsonRecord(content)
  return parsed !== undefined && recordHasZeroCollectionCount(parsed)
}

function isMohwNoDataResult(result: PriorToolResult): boolean {
  if (result.toolName !== MOHW_WELFARE_TOOL_NAME) return false
  const text = serializeToolResult(result.content)
  return /resultCode=['"]?40|NO DATA FOUND/iu.test(text)
}

function hasZeroTotalCount(value: unknown): boolean {
  if (Array.isArray(value)) return value.some(hasZeroTotalCount)
  if (!isRecord(value)) return false
  const totalCount = value.total_count ?? value.totalCount
  if (totalCount === 0 || totalCount === '0') return true
  return Object.values(value).some(hasZeroTotalCount)
}

function isPpsZeroProductResult(result: PriorToolResult): boolean {
  if (result.toolName !== PPS_SHOPPING_MALL_PRODUCT_TOOL_NAME) return false
  const parsed = parseJsonRecord(result.content)
  const value = parsed ?? result.content
  return hasZeroTotalCount(value)
}

function isPpsProductResult(result: PriorToolResult): boolean {
  return result.toolName === PPS_SHOPPING_MALL_PRODUCT_TOOL_NAME &&
    !result.isError &&
    !result.isStructuredFailure
}

function tagoNoRouteEvidenceMessage(result: PriorToolResult): string {
  const input = result.input ?? {}
  const routeNo = typeof input.route_no === 'string' ? input.route_no.trim() : ''
  const cityCode = typeof input.city_code === 'string' ? input.city_code.trim() : ''
  const target = [
    routeNo ? `route_no=${routeNo}` : undefined,
    cityCode ? `city_code=${cityCode}` : undefined,
  ].filter(Boolean).join(', ')
  return [
    `TAGO route lookup already returned zero official rows${target ? ` for ${target}` : ''}.`,
    'This is city-bus route evidence, not Seoul-to-Daejeon intercity transport evidence.',
    'Do not substitute another route, city, stop, route_id, or arrival lookup without citizen confirmation.',
    'Answer in Korean that TAGO express-bus and intercity-bus public-data channels are separate unregistered adapter surfaces in this UMMAYA build, then hand off to official rail or express/intercity bus channels.',
  ].join(' ')
}

function tagoRouteZeroResult(
  priorResults: readonly PriorToolResult[],
): PriorToolResult | undefined {
  for (let index = priorResults.length - 1; index >= 0; index -= 1) {
    const result = priorResults[index]
    if (
      result !== undefined &&
      result.toolName === TAGO_ROUTE_TOOL_NAME &&
      isZeroCollectionToolResult(result.content)
    ) {
      return result
    }
  }
  return undefined
}

function mohwNoDataEvidenceMessage(): string {
  return [
    'MOHW/SSIS welfare lookup already returned NO DATA FOUND for two official query attempts in this request.',
    'Do not broaden to unrelated life stages, benefit categories, or pregnancy/childcare scopes without citizen confirmation.',
    'Answer in Korean that mohw_welfare_eligibility_search returned no official rows, do not invent local benefit names or phone numbers, and hand off only to Bokjiro service search or the official 129 welfare counseling boundary.',
  ].join(' ')
}

function ppsZeroProductEvidenceMessage(): string {
  return [
    'PPS shopping mall product lookup already returned an official successful response with totalCount=0 in this request.',
    'This is not an agency API failure; do not broaden to unrelated procurement product names without citizen confirmation.',
    'Answer in Korean that pps_shopping_mall_product_lookup returned zero official product rows, name the agency API, and ask whether to retry with a different search term.',
  ].join(' ')
}

function ppsProductAlreadyReturnedMessage(): string {
  return [
    'PPS shopping mall product lookup already returned official product rows in this request.',
    'Do not repeat the same procurement product lookup or relabel the successful API response as a failure.',
    'Answer in Korean from the prior pps_shopping_mall_product_lookup tool_result only.',
  ].join(' ')
}

function isTagoRouteContinuationTool(toolName: string): boolean {
  return toolName === TAGO_ROUTE_TOOL_NAME || TAGO_ROUTE_FOLLOWUP_TOOL_NAMES.has(toolName)
}

type DomainRepeatGuardResult = {
  readonly message: string
  readonly terminal: boolean
}

function domainRepeatGuardMessage(params: {
  readonly block: ToolUseBlock
  readonly input: ToolInput
  readonly priorResults: readonly PriorToolResult[]
  readonly successfulCalls: readonly SuccessfulToolCall[]
}): DomainRepeatGuardResult | undefined {
  if (isTagoRouteContinuationTool(params.block.name)) {
    const zeroRouteResult = tagoRouteZeroResult(params.priorResults)
    if (zeroRouteResult !== undefined) {
      return {
        message: tagoNoRouteEvidenceMessage(zeroRouteResult),
        terminal: true,
      }
    }
  }

  if (
    params.block.name === MOHW_WELFARE_TOOL_NAME &&
    params.priorResults.filter(isMohwNoDataResult).length >= 2
  ) {
    return {
      message: mohwNoDataEvidenceMessage(),
      terminal: true,
    }
  }

  if (
    params.block.name === PPS_SHOPPING_MALL_PRODUCT_TOOL_NAME &&
    params.priorResults.some(isPpsZeroProductResult)
  ) {
    return {
      message: ppsZeroProductEvidenceMessage(),
      terminal: true,
    }
  }

  if (
    params.block.name === PPS_SHOPPING_MALL_PRODUCT_TOOL_NAME &&
    params.priorResults.some(isPpsProductResult)
  ) {
    return {
      message: ppsProductAlreadyReturnedMessage(),
      terminal: true,
    }
  }

  if (KAKAO_LOCATION_TOOL_NAMES.has(params.block.name)) {
    const query = typeof params.input.query === 'string'
      ? params.input.query.trim()
      : ''
    if (
      query.length > 0 &&
      params.successfulCalls.some(call =>
        KAKAO_LOCATION_TOOL_NAMES.has(call.toolName) &&
        typeof call.input.query === 'string' &&
        call.input.query.trim() === query
      )
    ) {
      return {
        message: locationRepeatMessage(params.block.name, query),
        terminal: false,
      }
    }
  }

  if (
    params.block.name === HOMETAX_LOOKUP_TOOL_NAME &&
    params.successfulCalls.some(call => call.toolName === HOMETAX_LOOKUP_TOOL_NAME)
  ) {
    return {
      message: hometaxProgressionMessage(),
      terminal: false,
    }
  }

  if (params.block.name === KMA_METAR_TOOL_NAME) {
    const kind = priorKmaAviationResultKind(params.priorResults)
    return kind
      ? {
          message: kmaAviationRepeatMessage(kind),
          terminal: false,
        }
      : undefined
  }

  const aviationKind = priorKmaAviationResultKind(params.priorResults)
  if (aviationKind !== undefined) {
    if (KMA_ORDINARY_WEATHER_TOOL_NAMES.has(params.block.name)) {
      return {
        message: kmaOrdinaryFallbackMessage(params.block.name),
        terminal: false,
      }
    }
    if (
      params.block.name === ROOT_FIND_TOOL_NAME &&
      typeof params.block.input.tool_id === 'string' &&
      KMA_ORDINARY_WEATHER_TOOL_NAMES.has(params.block.input.tool_id)
    ) {
      return {
        message: kmaOrdinaryFallbackMessage(params.block.input.tool_id),
        terminal: false,
      }
    }
  }

  if (
    KMA_ORDINARY_WEATHER_TOOL_NAMES.has(params.block.name) &&
    params.priorResults.some(
      result =>
        result.toolName === params.block.name && isKmaGridFailureResult(result),
    )
  ) {
    return {
      message: kmaGridRepeatMessage(params.block.name),
      terminal: false,
    }
  }

  return undefined
}

function repairDirectLocationToolInputForValidation(params: {
  readonly toolName: string
  readonly input: ToolInput
  readonly messages: readonly Message[]
}): ToolInput {
  if (
    !KAKAO_LOCATION_TOOL_NAMES.has(params.toolName) ||
    (typeof params.input.query === 'string' &&
      params.input.query.trim().length > 0)
  ) {
    return params.input
  }
  const query = deriveLocationQueryFromUserText(
    latestCitizenPromptText(params.messages),
  )
  return query === undefined ? params.input : { ...params.input, query }
}

function finiteCoordinate(value: unknown): number | undefined {
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : undefined
  }
  if (typeof value !== 'string') return undefined
  const parsed = Number(value.trim())
  return Number.isFinite(parsed) ? parsed : undefined
}

function coordinatesFromRecord(
  value: unknown,
): { readonly lat: number; readonly lon: number } | undefined {
  if (!isRecord(value)) return undefined
  const lat =
    finiteCoordinate(value.lat) ??
    finiteCoordinate(value.latitude) ??
    finiteCoordinate(value.y) ??
    finiteCoordinate(value.yPos)
  const lon =
    finiteCoordinate(value.lon) ??
    finiteCoordinate(value.lng) ??
    finiteCoordinate(value.longitude) ??
    finiteCoordinate(value.x) ??
    finiteCoordinate(value.xPos)
  if (lat !== undefined && lon !== undefined) {
    return { lat, lon }
  }
  return (
    coordinatesFromRecord(value.result) ??
    coordinatesFromRecord(value.data) ??
    coordinatesFromRecord(value.coords) ??
    coordinatesFromRecord(value.poi)
  )
}

function normalizeLocationText(value: string): string {
  return value.normalize('NFKC').replace(/\s+/gu, '').toLowerCase()
}

function nmcAedNearTargetFromUserText(text: string): string | undefined {
  if (!AED_NEAR_REQUEST_RE.test(text)) return undefined
  const [beforeNear] = text.split(AED_NEAR_TARGET_SPLIT_RE)
  const target = beforeNear
    ?.split(/[.!?。！？,\n]/u)
    .at(-1)
    ?.replace(/^\s*(?:오늘|현재|지금)\s*/u, '')
    .replace(/\s*(?:에서|의|를|을)?\s*$/u, '')
    .trim()
  return target && target.length > 0 ? target : undefined
}

function kakaoResultMatchesTarget(params: {
  readonly result: PriorToolResult
  readonly parsed: Record<string, unknown> | undefined
  readonly target: string | undefined
}): boolean {
  if (params.target === undefined) return true
  const target = normalizeLocationText(params.target)
  const query = typeof params.result.input?.query === 'string'
    ? normalizeLocationText(params.result.input.query)
    : ''
  if (query.includes(target)) return true
  const text = normalizeLocationText(serializeToolResult(params.parsed ?? params.result.content))
  return text.includes(target)
}

function latestKakaoLocateOrigin(
  messages: readonly Message[],
): { readonly lat: number; readonly lon: number } | undefined {
  const results = toolResultsSinceLatestPrompt(messages)
  const target = nmcAedNearTargetFromUserText(latestCitizenPromptText(messages))
  for (let index = results.length - 1; index >= 0; index -= 1) {
    const result = results[index]
    if (
      result === undefined ||
      result.isError ||
      result.isStructuredFailure ||
      !KAKAO_LOCATION_TOOL_NAMES.has(result.toolName)
    ) {
      continue
    }
    const parsed = parseJsonRecord(result.content)
    if (!kakaoResultMatchesTarget({ result, parsed, target })) continue
    const origin = coordinatesFromRecord(parsed ?? result.content)
    if (origin !== undefined) return origin
  }
  return undefined
}

function nmcAedMissingPreciseOriginMessage(messages: readonly Message[]): string | undefined {
  const target = nmcAedNearTargetFromUserText(latestCitizenPromptText(messages))
  if (target === undefined || latestKakaoLocateOrigin(messages) !== undefined) {
    return undefined
  }
  return [
    '<tool_use_error>MissingPreciseOrigin:',
    `For AED near-distance requests, first call kakao_keyword_search with the exact place name "${target}".`,
    'Then call nmc_aed_site_locate with origin_lat/origin_lon from that Kakao result.',
    'Do not use generic district or "AED" keyword coordinates as the distance origin.',
    '</tool_use_error>',
  ].join(' ')
}

function aedOriginFromInput(
  input: ToolInput,
): { readonly lat: number; readonly lon: number } | undefined {
  const lat = finiteCoordinate(input.origin_lat)
  const lon = finiteCoordinate(input.origin_lon)
  return lat === undefined || lon === undefined ? undefined : { lat, lon }
}

function sameAedOrigin(
  left: { readonly lat: number; readonly lon: number },
  right: { readonly lat: number; readonly lon: number },
): boolean {
  return (
    Math.abs(left.lat - right.lat) <= 0.0005 &&
    Math.abs(left.lon - right.lon) <= 0.0005
  )
}

function repairNmcAedOriginToolInput(params: {
  readonly toolName: string
  readonly input: ToolInput
  readonly messages: readonly Message[]
}): ToolInput {
  if (params.toolName !== NMC_AED_TOOL_NAME) {
    return params.input
  }
  const origin = latestKakaoLocateOrigin(params.messages)
  const existingOrigin = aedOriginFromInput(params.input)
  return origin === undefined ||
    (existingOrigin !== undefined && sameAedOrigin(existingOrigin, origin))
    ? params.input
    : {
        ...params.input,
        origin_lat: origin.lat,
        origin_lon: origin.lon,
      }
}

type NmcAedOriginResolution =
  | { readonly kind: 'input'; readonly input: ToolInput }
  | { readonly kind: 'blocked'; readonly message: string }

async function resolveNmcAedOriginToolInput(params: {
  readonly toolName: string
  readonly input: ToolInput
  readonly messages: readonly Message[]
  readonly toolUseContext: ToolUseContext
  readonly canUseTool: Parameters<Tool['call']>[2]
  readonly assistantMessage: AssistantMessage
  readonly toolUseId: string
}): Promise<NmcAedOriginResolution> {
  if (params.toolName !== NMC_AED_TOOL_NAME) {
    return { kind: 'input', input: params.input }
  }
  const missingOriginMessage = nmcAedMissingPreciseOriginMessage(params.messages)
  if (missingOriginMessage === undefined) {
    return { kind: 'input', input: params.input }
  }
  const target = nmcAedNearTargetFromUserText(
    latestCitizenPromptText(params.messages),
  )
  if (target === undefined) {
    return { kind: 'blocked', message: missingOriginMessage }
  }
  const originTool = findToolByName(
    params.toolUseContext.options.tools,
    'kakao_keyword_search',
  ) ?? getAdapterToolByName('kakao_keyword_search')
  if (originTool === undefined) {
    return { kind: 'blocked', message: missingOriginMessage }
  }

  const originInput: ToolInput = { query: target }
  const parsedOriginInput = originTool.inputSchema.safeParse(originInput)
  if (!parsedOriginInput.success || !isRecord(parsedOriginInput.data)) {
    return { kind: 'blocked', message: missingOriginMessage }
  }
  const originPermission = await params.canUseTool(
    originTool,
    parsedOriginInput.data,
    params.toolUseContext,
    params.assistantMessage,
    `${params.toolUseId}:origin`,
  )
  if (originPermission.behavior !== 'allow') {
    return { kind: 'blocked', message: missingOriginMessage }
  }
  const originCallInput = isRecord(originPermission.updatedInput)
    ? originPermission.updatedInput
    : parsedOriginInput.data
  const originResult = await originTool.call(
    originCallInput,
    {
      ...params.toolUseContext,
      toolUseId: `${params.toolUseId}:origin`,
      userModified: originPermission.userModified ?? false,
    },
    params.canUseTool,
    params.assistantMessage,
  )
  const originData = normalizeToolResultDataForModel(
    'kakao_keyword_search',
    originResult.data,
  )
  if (isStructuredFailureResult(originData)) {
    return { kind: 'blocked', message: missingOriginMessage }
  }
  const parsedOriginData = parseJsonRecord(originData)
  if (
    !kakaoResultMatchesTarget({
      result: {
        toolName: 'kakao_keyword_search',
        input: originInput,
        content: originData,
        isError: false,
        isStructuredFailure: false,
      },
      parsed: parsedOriginData,
      target,
    })
  ) {
    return { kind: 'blocked', message: missingOriginMessage }
  }
  const origin = coordinatesFromRecord(parsedOriginData ?? originData)
  return origin === undefined
    ? { kind: 'blocked', message: missingOriginMessage }
    : {
        kind: 'input',
        input: {
          ...params.input,
          origin_lat: origin.lat,
          origin_lon: origin.lon,
        },
      }
}

function derivePpsProductQueryFromUserText(text: string): string | undefined {
  const normalized = text.normalize('NFKC')
  const keywordMatch = /(노트북|랩탑|휴대용\s*컴퓨터|컴퓨터|PC|전산장비|프린터|모니터|복사기)/iu.exec(normalized)
  if (keywordMatch?.[1]) return keywordMatch[1].replace(/\s+/gu, ' ').trim()
  const productMatch = /([가-힣A-Za-z0-9+\-\s]{2,24})(?:\s*관련)?\s*(?:물품|제품|상품)/u.exec(normalized)
  const product = productMatch?.[1]?.trim()
  return product && product.length > 0 ? product : undefined
}

function repairPpsProductToolInput(params: {
  readonly toolName: string
  readonly input: ToolInput
  readonly messages: readonly Message[]
}): ToolInput {
  if (params.toolName !== PPS_SHOPPING_MALL_PRODUCT_TOOL_NAME) {
    return params.input
  }
  if (
    typeof params.input.prdct_clsfc_no_nm === 'string' &&
    params.input.prdct_clsfc_no_nm.trim().length > 0
  ) {
    return params.input
  }
  const query = derivePpsProductQueryFromUserText(
    latestCitizenPromptText(params.messages),
  )
  return query === undefined
    ? params.input
    : { ...params.input, prdct_clsfc_no_nm: query }
}

function unexplainedRepeatedToolMessage(toolName: string): string {
  return `<tool_use_error>RepeatedToolUseError: Tool '${toolName}' already returned a successful result in this query loop. Before calling the same tool again with different inputs, write a visible progress sentence explaining which parameter, radius, source, or scope is changing; otherwise answer from the prior tool_result.</tool_use_error>`
}

function excessiveRepeatedToolMessage(toolName: string): string {
  return `<tool_use_error>RepeatedToolUseError: Tool '${toolName}' already returned multiple successful results in this query loop. Stop calling the same effective tool again; answer from the prior tool_result set or state the remaining limitation.</tool_use_error>`
}

function hasVisibleAssistantText(message: AssistantMessage): boolean {
  return message.message.content.some(
    block => block.type === 'text' && block.text.trim().length > 0,
  )
}

export async function runToolUseBlocks(params: {
  readonly blocks: readonly ToolUseBlock[]
  readonly assistantMessage: AssistantMessage
  readonly messages: readonly Message[]
  readonly toolUseContext: ToolUseContext
  readonly canUseTool: Parameters<
    ToolUseContext['options']['tools'][number]['call']
  >[2]
}): Promise<readonly UserMessage[]> {
  const results: UserMessage[] = []
  const successfulCalls: SuccessfulToolCall[] = [
    ...successfulToolCallsSinceLatestPrompt(params.messages),
  ]
  for (const block of params.blocks) {
    const localTool = findToolByName(params.toolUseContext.options.tools, block.name)
    const tool = isUnregisteredRawJsonToolUseId(block.id)
      ? undefined
      : localTool ?? getAdapterToolByName(block.name)
    if (!tool) {
      const errorPayload = createToolUnavailableErrorPayload(block.name)
      const errorContent = serializeToolResult(errorPayload)
      results.push(
        createUserMessage({
          content: [
            {
              type: 'tool_result',
              tool_use_id: block.id,
              content: errorContent,
              is_error: true,
            },
          ],
          toolUseResult: errorPayload,
          sourceToolAssistantUUID: params.assistantMessage.uuid,
        }),
      )
      continue
    }

    const documentRepair = repairUmmayaDocumentToolInputForDispatch({
      toolName: block.name,
      input: block.input,
      messages: params.messages,
    })
    if (documentRepair.kind === 'blocked') {
      results.push(
        createUserMessage({
          content: [
            {
              type: 'tool_result',
              tool_use_id: block.id,
              content: documentRepair.message,
              is_error: true,
            },
          ],
          toolUseResult: documentRepair.message,
          sourceToolAssistantUUID: params.assistantMessage.uuid,
        }),
      )
      continue
    }
    const toolUseContext = {
      ...params.toolUseContext,
      messages: params.messages,
    }
    const publicAdapterInput = backfillMojVillageLawyerRegionInput(
      block.name,
      documentRepair.input,
      latestCitizenPromptText(params.messages),
    )
    const aedOriginInput = repairNmcAedOriginToolInput({
      toolName: block.name,
      input: publicAdapterInput,
      messages: params.messages,
    })
    const aedOriginResolution = await resolveNmcAedOriginToolInput({
      toolName: block.name,
      input: aedOriginInput,
      messages: params.messages,
      toolUseContext,
      canUseTool: params.canUseTool,
      assistantMessage: params.assistantMessage,
      toolUseId: block.id,
    })
    if (aedOriginResolution.kind === 'blocked') {
      results.push(
        createUserMessage({
          content: [
            {
              type: 'tool_result',
              tool_use_id: block.id,
              content: aedOriginResolution.message,
              is_error: true,
            },
          ],
          toolUseResult: aedOriginResolution.message,
          sourceToolAssistantUUID: params.assistantMessage.uuid,
        }),
      )
      continue
    }
    const ppsProductInput = repairPpsProductToolInput({
      toolName: block.name,
      input: aedOriginResolution.input,
      messages: params.messages,
    })
    const inputForValidation = localTool === undefined
      ? ppsProductInput
      : repairDirectLocationToolInputForValidation({
          toolName: block.name,
          input: ppsProductInput,
          messages: params.messages,
        })
    const parsedInput = tool.inputSchema.safeParse(inputForValidation)
    if (!parsedInput.success) {
      const errorContent = formatZodValidationError(
        block.name,
        parsedInput.error,
      )
      results.push(
        createUserMessage({
          content: [
            {
              type: 'tool_result',
              tool_use_id: block.id,
              content: `<tool_use_error>InputValidationError: ${errorContent}</tool_use_error>`,
              is_error: true,
            },
          ],
          toolUseResult: `InputValidationError: ${parsedInput.error.message}`,
          sourceToolAssistantUUID: params.assistantMessage.uuid,
        }),
      )
      continue
    }
    const priorResults = toolResultsSinceLatestPrompt(params.messages)
    const domainGuardMessage = domainRepeatGuardMessage({
      block,
      input: parsedInput.data,
      priorResults,
      successfulCalls,
    })
    if (domainGuardMessage !== undefined) {
      results.push(
        domainGuardMessage.terminal
          ? createTerminalGuardToolResult(
              block,
              params.assistantMessage,
              domainGuardMessage.message,
            )
          : createGuardToolResult(
              block,
              params.assistantMessage,
              domainGuardMessage.message,
            ),
      )
      continue
    }
    const repeatedSuccessfulCall = successfulCalls.some(
      call =>
        effectiveToolKey(call.toolName, call.input) ===
          effectiveToolKey(block.name, parsedInput.data) &&
        toolInputsEquivalent(tool, parsedInput.data, call.input),
    )
    if (repeatedSuccessfulCall && shouldUseGenericRepeatGuard(tool, block.name)) {
      const errorContent = repeatedToolUseMessage(block.name)
      results.push(
        createUserMessage({
          content: [
            {
              type: 'tool_result',
              tool_use_id: block.id,
              content: errorContent,
              is_error: true,
            },
          ],
          toolUseResult: `Error: ${errorContent}`,
          sourceToolAssistantUUID: params.assistantMessage.uuid,
        }),
      )
      continue
    }
    const successfulCallCountForEffectiveTool = successfulCalls.filter(
      call =>
        effectiveToolKey(call.toolName, call.input) ===
          effectiveToolKey(block.name, parsedInput.data),
    ).length
    if (
      successfulCallCountForEffectiveTool >=
      MAX_SUCCESSFUL_CALLS_PER_EFFECTIVE_TOOL &&
      shouldUseGenericRepeatGuard(tool, block.name)
    ) {
      const errorContent = excessiveRepeatedToolMessage(block.name)
      results.push(
        createUserMessage({
          content: [
            {
              type: 'tool_result',
              tool_use_id: block.id,
              content: errorContent,
              is_error: true,
            },
          ],
          toolUseResult: `Error: ${errorContent}`,
          sourceToolAssistantUUID: params.assistantMessage.uuid,
        }),
      )
      continue
    }
    const sameToolAlreadySucceeded = successfulCallCountForEffectiveTool > 0
    if (
      sameToolAlreadySucceeded &&
      shouldUseGenericRepeatGuard(tool, block.name) &&
      !hasVisibleAssistantText(params.assistantMessage)
    ) {
      const errorContent = unexplainedRepeatedToolMessage(block.name)
      results.push(
        createUserMessage({
          content: [
            {
              type: 'tool_result',
              tool_use_id: block.id,
              content: errorContent,
              is_error: true,
            },
          ],
          toolUseResult: `Error: ${errorContent}`,
          sourceToolAssistantUUID: params.assistantMessage.uuid,
        }),
      )
      continue
    }
    const isValidCall = await tool.validateInput?.(
      parsedInput.data,
      toolUseContext,
    )
    if (isValidCall?.result === false) {
      results.push(
        createUserMessage({
          content: [
            {
              type: 'tool_result',
              tool_use_id: block.id,
              content: `<tool_use_error>${isValidCall.message}</tool_use_error>`,
              is_error: true,
            },
          ],
          toolUseResult: `Error: ${isValidCall.message}`,
          sourceToolAssistantUUID: params.assistantMessage.uuid,
        }),
      )
      continue
    }
    const permissionDecision = await params.canUseTool(
      tool,
      parsedInput.data,
      toolUseContext,
      params.assistantMessage,
      block.id,
    )
    if (permissionDecision.behavior !== 'allow') {
      const errorContent = permissionErrorMessage(permissionDecision.message)
      results.push(
        createUserMessage({
          content: [
            {
              type: 'tool_result',
              tool_use_id: block.id,
              content: errorContent,
              is_error: true,
            },
          ],
          toolUseResult: `Error: ${errorContent}`,
          sourceToolAssistantUUID: params.assistantMessage.uuid,
        }),
      )
      continue
    }
    const callInput = permissionDecision.updatedInput ?? parsedInput.data
    const result = await tool.call(
      callInput,
      {
        ...toolUseContext,
        toolUseId: block.id,
        userModified: permissionDecision.userModified ?? false,
      },
      params.canUseTool,
      params.assistantMessage,
    )
    const modelData = normalizeToolResultDataForModel(block.name, result.data)
    const isStructuredFailure = isStructuredFailureResult(modelData)
    results.push(
      createUserMessage({
        content: [
          {
            type: 'tool_result',
            tool_use_id: block.id,
            content: serializeToolResult(modelData),
            ...(isStructuredFailure ? { is_error: true as const } : {}),
          },
        ],
        toolUseResult: modelData,
        sourceToolAssistantUUID: params.assistantMessage.uuid,
      }),
    )
    if (!isStructuredFailure) {
      successfulCalls.push({ toolName: block.name, input: parsedInput.data })
    }
  }
  return results
}
