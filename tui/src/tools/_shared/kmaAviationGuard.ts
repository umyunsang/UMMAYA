import type { ToolUseContext, ValidationResult } from '../../Tool.js'
import { listAdapters } from '../../services/api/adapterManifest.js'
import { textFromContent } from './nmcAedGuard.js'
import { isNonSyntheticUserMessageText } from './citizenUserText.js'

const KMA_AIR_TOOL_NAMES = new Set([
  'kma_apihub_url_air_amos_minute',
  'kma_apihub_url_air_metar_decoded',
])
const ORDINARY_WEATHER_TOOL_NAMES = new Set([
  'kma_current_observation',
  'kma_ultra_short_term_forecast',
  'kma_short_term_forecast',
])
const LOCATION_TOOL_NAMES = new Set([
  'kakao_keyword_search',
  'kakao_address_search',
  'kakao_coord_to_region',
])
const AIRPORT_PLACE_RE =
  /(김해|김포|김해공항|김포공항|gimhae|gimpo|rkpk|rkss|\bairport\b|공항)/iu
const AIRPORT_AVIATION_RE =
  /(비행기|항공편|비행편|운항|이륙|착륙|결항|지연|뜰\s*만|뜨나|뜰\s*수|flight|take\s*off|landing|delay|cancel|metar|speci|amos|rvr|활주로|시정|visibility|공항기상|항공기상)/iu

function latestUserText(context: ToolUseContext): string {
  const messages = Array.isArray(context.messages) ? context.messages : []
  for (let idx = messages.length - 1; idx >= 0; idx -= 1) {
    const message = messages[idx] as Record<string, unknown>
    const inner = message.message as Record<string, unknown> | undefined
    const role =
      typeof inner?.role === 'string'
        ? inner.role
        : typeof message.role === 'string'
          ? message.role
          : message.type
    if (role !== 'user') continue
    const text = textFromContent(inner?.content ?? message.content)
    if (isNonSyntheticUserMessageText(message, text)) return text
  }
  return ''
}

function isAirportAviationQuery(text: string): boolean {
  return AIRPORT_PLACE_RE.test(text) && AIRPORT_AVIATION_RE.test(text)
}

function hasAviationAdapter(): boolean {
  return listAdapters().some(entry => KMA_AIR_TOOL_NAMES.has(entry.tool_id))
}

export function validateKmaAviationToolChoice(
  toolId: string,
  context: ToolUseContext,
): ValidationResult | undefined {
  if (KMA_AIR_TOOL_NAMES.has(toolId)) return undefined
  if (!LOCATION_TOOL_NAMES.has(toolId) && !ORDINARY_WEATHER_TOOL_NAMES.has(toolId)) {
    return undefined
  }
  const userText = latestUserText(context)
  if (!isAirportAviationQuery(userText)) return undefined
  if (!hasAviationAdapter()) return undefined
  return {
    result: false,
    message:
      'KMA aviation tool-choice mismatch: the latest citizen request asks for airport METAR/AMOS aviation evidence such as flight operation, wind, runway, RVR, or visibility. ' +
      'Call kma_apihub_url_air_metar_decoded for airport METAR/시정/풍향/풍속 evidence, or kma_apihub_url_air_amos_minute for AMOS runway-minute evidence when that airport/station is documented. ' +
      'Do not call locate or ordinary KMA current-observation tools first because they do not provide airport METAR/AMOS visibility evidence.',
    errorCode: 1,
  }
}
