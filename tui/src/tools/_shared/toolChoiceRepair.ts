import type { BetaToolChoiceTool } from '../../sdk-compat.js'
import type { Tools } from '../../Tool.js'
import type { Message } from '../../types/message.js'
import {
  buildNmcAedFollowupPromptIfNeeded,
  textFromContent,
} from './nmcAedGuard.js'
import { resolveAdapter } from '../../services/api/adapterManifest.js'
import {
  isKmaAnalysisMapText,
  KMA_ANALYSIS_CHART_TOOL_NAME,
} from './kmaAnalysisGuard.js'
import { isNonSyntheticUserMessageText } from './citizenUserText.js'

const KMA_AIR_TOOLS = [
  'kma_apihub_url_air_metar_decoded',
  'kma_apihub_url_air_amos_minute',
] as const
const NMC_EMERGENCY_TOOL_NAME = 'nmc_emergency_search'
const NMC_AED_TOOL_NAME = 'nmc_aed_site_locate'
const KAKAO_COORD_TO_REGION_TOOL_NAME = 'kakao_coord_to_region'
const TAGO_STATION_TOOL_NAME = 'tago_bus_station_search'
const TAGO_ROUTE_TOOL_NAME = 'tago_bus_route_search'
const TAGO_ROUTE_STATION_TOOL_NAME = 'tago_bus_route_station_search'
const TAGO_ARRIVAL_TOOL_NAME = 'tago_bus_arrival_search'
const PPS_BID_TOOL_NAME = 'pps_bid_public_info'
const AIRKOREA_TOOL_NAME = 'airkorea_ctprvn_air_quality'
const PROTECTED_CHECK_TOOLS = [
  'mock_verify_module_simple_auth',
  'mock_verify_ganpyeon_injeung',
  'mock_verify_mobile_id',
  'mock_verify_mydata',
] as const

const AIRPORT_PLACE_RE =
  /(김해|김포|김해공항|김포공항|gimhae|gimpo|rkpk|rkss|\bairport\b|공항)/iu
const AIRPORT_AVIATION_RE =
  /(비행기|항공편|비행편|운항|이륙|착륙|결항|지연|뜰\s*만|뜨나|뜰\s*수|flight|take\s*off|landing|delay|cancel|metar|speci|amos|rvr|활주로|시정|visibility|공항기상|항공기상)/iu
const AMOS_PREFERENCE_RE = /(amos|rvr|활주로|runway)/iu
const GIMPO_RE = /(김포|김포공항|gimpo|rkss)/iu
const PROTECTED_QUERY_RE =
  /(본인확인|인증|간편인증|모바일\s*(?:신분증|id)|mobile\s*id|마이데이터|mydata|증명원|소득금액증명|소득금액증명원|주민등록등본|민원|발급)/iu
const MOBILE_ID_RE = /(mobile\s*id|모바일\s*(?:신분증|id)|mobile_id)/iu
const SIMPLE_AUTH_RE =
  /(simple_auth|간편인증|ganpyeon|소득금액증명|증명원|민원|발급)/iu
const MYDATA_RE = /(mydata|마이데이터)/iu
const MEDICAL_COLLAPSE_RE =
  /(사람이\s*쓰러|쓰러졌|쓰러짐|쓰러져|의식[을이가은는\s]*(없|잃|불명)|무의식|심정지|심폐소생|cpr|호흡\s*(없|곤란)|숨\s*(안|못)|collapse|collapsed|unconscious|cardiac\s*arrest|not\s*breathing|aed|자동심장|심장충격|제세동)/iu
const MEDICAL_COLLAPSE_OR_ER_RE =
  /(사람이\s*쓰러|쓰러졌|쓰러짐|쓰러져|의식[을이가은는\s]*(없|잃|불명)|무의식|심정지|심폐소생|cpr|호흡\s*(없|곤란)|숨\s*(안|못)|collapse|collapsed|unconscious|cardiac\s*arrest|not\s*breathing|응급실|응급의료기관|응급의료센터|emergency\s*room|\ber\b)/iu
const NON_MEDICAL_EMERGENCY_RE =
  /(비상벨|안심벨|emergency\s*(call\s*)?box|call\s*box)/iu
const TAGO_BUS_RE =
  /(버스|시내버스|정류장|정류소|노선|도착|언제\s*와|몇\s*분|bus|route|arrival|station)/iu
const TAGO_ROUTE_NO_RE = /(?:^|[^\d])(\d{1,4}(?:-\d)?)\s*번/u
const TAGO_PLACE_RE = /([가-힣A-Za-z0-9().·\s]+?)(?:에서|근처|앞|인근)/u
const PPS_BID_RE = /(입찰|나라장터|조달청|공고|공사조회|전기공사|bid|procurement)/iu
const AIRKOREA_RE =
  /(미세먼지|초미세먼지|대기질|대기오염|마스크|pm\s*2\.?5|pm\s*10|air\s*korea|airkorea)/iu
const PUBLIC_DATA_MISMATCH_CALL_RE =
  /Public-data tool-choice mismatch:[\s\S]*?\bCall\s+([a-z][a-z0-9_]*)\s+/iu
const TAGO_BUS_COMPLETION_PROMPT =
  'TAGO bus arrival evidence chain complete: the route search, route passing-stop lookup, and arrival lookup have already been attempted for this bus-arrival request. Do not call another location, public-data, or TAGO bus tool in this turn. Write the final Korean answer now from the actual TAGO results only. If the arrival result has zero items, say that no current matching arrival is shown for the checked stop/direction, and include the route/stop evidence that was found.'
const TAGO_BUS_REPAIR_PROMPT =
  'TAGO bus final answer repair: the previous answer still promised another stop/route lookup after TAGO arrival evidence was already attempted. Rewrite the final Korean answer now from the actual TAGO tool_result only. Do not say 확인하겠습니다, 확인해보겠습니다, 검색해 보겠습니다, 다시 조회, or that you will check another stop. If the arrival result has zero items, say no current arrival is shown for the checked 부산역 stop and ask the citizen for a specific route number or exact stop only as a next-step option.'
const AIRKOREA_COMPLETION_PROMPT =
  'AirKorea air-quality evidence complete: airkorea_ctprvn_air_quality has already returned the official result for this 미세먼지/초미세먼지 request. Do not call another location, weather, public-data, or AirKorea tool in this turn. Write the final Korean answer now from the actual tool_result only. Include stationName, dataTime, PM10 value and pm10GradeLabelKo, PM2.5 value and pm25GradeLabelKo, and CAI/khaiValue with khaiGradeLabelKo when present. This adapter returns city/province measurement rows, not a geocoded nearest-station result: say it is city/province station data, use only exact stationName rows present in tool_result, and do not infer the citizen place district, distance, nearest station, station groups, or value ranges unless those exact fields exist in tool_result. If totalCount is 0 or items are empty, say the official AirKorea API returned no rows for the checked sidoName and do not say you are still checking.'
const AIRKOREA_REPAIR_PROMPT =
  'AirKorea final answer repair: the previous answer inferred nearest/direction/distance, average/range values, district groups, or changed raw values beyond the official tool_result. Rewrite the final Korean answer using only the exact AirKorea rows listed below. Do not say 가장 가까운, 인근, 동쪽, 서쪽, 남쪽, 북쪽, distance, nearest, 평균, 범위, 대부분, 해운대구 지역, or average unless those exact fields exist in tool_result. Copy PM10, PM2.5, CAI, stationName, dataTime, and grade labels literally. If the citizen named a place but the tool returned only city/province rows, say this is city/province station data rather than a nearest-station answer.'
const AIRKOREA_UNSUPPORTED_LOCATION_CLAIM_RE =
  /(가장\s*가까운|인근|동쪽|서쪽|남쪽|북쪽|거리|평균|범위|대부분|전체적으로|해운대구\s*지역|명확한\s*측정소|지역에\s*해당|nearest|distance|average|range)/iu
const TAGO_BUS_PENDING_FINAL_RE =
  /(확인해\s*보겠습니다|확인하겠습니다|검색해\s*보겠습니다|검색하겠습니다|다른\s*정류장|다시\s*(?:조회|확인|검색)|조회하겠습니다|will\s+check|will\s+search|will\s+look\s+up)/iu
const GENERIC_PENDING_FINAL_RE =
  /(답변을?\s*제공하겠습니다|제공하겠습니다|확인해\s*보겠습니다|확인하겠습니다|조회하겠습니다|찾아보겠습니다|검색해\s*보겠습니다|검색하겠습니다|최종\s*답변은|final answer should|will\s+(?:answer|provide|check|search|look\s+up))/iu
const GENERIC_PENDING_FINAL_REPAIR_PROMPT =
  'Final answer repair: successful tool_result evidence already exists, but the previous assistant message was still a plan or promise to answer later. Write the final Korean answer now from the actual tool_result values only. Do not say 제공하겠습니다, 확인하겠습니다, 조회하겠습니다, 찾아보겠습니다, 검색해 보겠습니다, or describe what you will answer next.'

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return typeof value === 'object' && value !== null
    ? (value as Record<string, unknown>)
    : undefined
}

function messageRecord(message: unknown): Record<string, unknown> | undefined {
  return asRecord(asRecord(message)?.message)
}

function messageRole(message: unknown): string | undefined {
  const outer = asRecord(message)
  const inner = messageRecord(message)
  if (typeof inner?.role === 'string') return inner.role
  if (typeof outer?.role === 'string') return outer.role
  return typeof outer?.type === 'string' ? outer.type : undefined
}

function messageContent(message: unknown): unknown {
  return messageRecord(message)?.content ?? asRecord(message)?.content
}

function latestUserText(messages: readonly unknown[]): string {
  for (let idx = messages.length - 1; idx >= 0; idx -= 1) {
    const message = messages[idx]
    if (messageRole(message) !== 'user') continue
    const text = textFromContent(messageContent(message))
    if (isNonSyntheticUserMessageText(message, text)) return text
  }
  return ''
}

function toolUseNames(messages: readonly unknown[]): Set<string> {
  const names = new Set<string>()
  for (const message of messages) {
    const content = messageContent(message)
    if (!Array.isArray(content)) continue
    for (const block of content) {
      const record = asRecord(block)
      if (record?.type === 'tool_use') {
        const input = asRecord(record.input)
        const nestedToolName =
          typeof input?.tool_id === 'string' ? input.tool_id : undefined
        if (nestedToolName) names.add(nestedToolName)
        else if (typeof record.name === 'string') names.add(record.name)
        continue
      }
      if (record?.type !== 'tool_result') continue
      if (typeof record.content !== 'string') continue
      const parsed = parseJsonRecord(record.content)
      const source = asRecord(asRecord(parsed?.result)?.meta)?.source
      if (typeof source === 'string') names.add(source)
    }
  }
  return names
}

function latestToolResultText(messages: readonly unknown[]): string {
  for (let idx = messages.length - 1; idx >= 0; idx -= 1) {
    const content = messageContent(messages[idx])
    if (!Array.isArray(content)) continue
    const parts: string[] = []
    for (const block of content) {
      const record = asRecord(block)
      if (record?.type !== 'tool_result') continue
      if (typeof record.content === 'string') {
        parts.push(record.content)
      } else {
        const text = textFromContent(record.content)
        if (text.trim()) parts.push(text)
      }
    }
    if (parts.length > 0) return parts.join('\n')
  }
  return ''
}

function latestAssistantText(messages: readonly unknown[]): string {
  for (let idx = messages.length - 1; idx >= 0; idx -= 1) {
    if (messageRole(messages[idx]) !== 'assistant') continue
    const text = textFromContent(messageContent(messages[idx]))
    if (text.trim()) return text
  }
  return ''
}

function hasAirKoreaRepairPrompt(messages: readonly unknown[]): boolean {
  return messages.some(message => textFromContent(messageContent(message)).includes('AirKorea final answer repair'))
}

function hasTagoBusRepairPrompt(messages: readonly unknown[]): boolean {
  return messages.some(message => textFromContent(messageContent(message)).includes('TAGO bus final answer repair'))
}

function hasGenericPendingFinalRepairPrompt(messages: readonly unknown[]): boolean {
  return messages.some(message => textFromContent(messageContent(message)).includes('Final answer repair: successful tool_result'))
}

function hasToolResult(messages: readonly unknown[]): boolean {
  return messages.some(message => {
    const content = messageContent(message)
    if (!Array.isArray(content)) return false
    return content.some(block => asRecord(block)?.type === 'tool_result')
  })
}

function toolResultTextsFor(
  messages: readonly unknown[],
  toolName: string,
): string[] {
  const idToName = toolUseById(messages)
  const texts: string[] = []
  for (const message of messages) {
    const content = messageContent(message)
    if (!Array.isArray(content)) continue
    for (const block of content) {
      const record = asRecord(block)
      if (record?.type !== 'tool_result') continue
      if (typeof record.tool_use_id !== 'string') continue
      const mappedToolName = idToName.get(record.tool_use_id)
      if (mappedToolName === toolName) {
        if (typeof record.content === 'string') texts.push(record.content)
        continue
      }
      if (typeof record.content !== 'string') continue
      const parsed = parseJsonRecord(record.content)
      const source = asRecord(asRecord(parsed?.result)?.meta)?.source
      if (source === toolName) texts.push(record.content)
    }
  }
  return texts
}

function toolUseById(messages: readonly unknown[]): Map<string, string> {
  const ids = new Map<string, string>()
  for (const message of messages) {
    const content = messageContent(message)
    if (!Array.isArray(content)) continue
    for (const block of content) {
      const record = asRecord(block)
      if (record?.type !== 'tool_use') continue
      if (typeof record.id !== 'string' || typeof record.name !== 'string') {
        continue
      }
      const input = asRecord(record.input)
      const nestedToolName =
        typeof input?.tool_id === 'string' ? input.tool_id : undefined
      ids.set(record.id, nestedToolName ?? record.name)
    }
  }
  return ids
}

function parseJsonRecord(value: string): Record<string, unknown> | undefined {
  try {
    return asRecord(JSON.parse(value))
  } catch {
    return undefined
  }
}

function stringField(record: Record<string, unknown>, key: string): string | undefined {
  const value = record[key]
  if (value === null || value === undefined) return undefined
  const text = String(value).trim()
  return text === '' ? undefined : text
}

function airKoreaExactRowsSummary(messages: readonly unknown[]): string | undefined {
  const rows: string[] = []
  for (const text of toolResultTextsFor(messages, AIRKOREA_TOOL_NAME)) {
    const parsed = parseJsonRecord(text)
    const result = asRecord(parsed?.result)
    const items = Array.isArray(result?.items) ? result.items : []
    for (const item of items) {
      const record = asRecord(asRecord(item)?.record)
      if (!record) continue
      const stationName = stringField(record, 'stationName')
      const dataTime = stringField(record, 'dataTime')
      const pm10Value = stringField(record, 'pm10Value')
      const pm10Grade = stringField(record, 'pm10GradeLabelKo')
      const pm25Value = stringField(record, 'pm25Value')
      const pm25Grade = stringField(record, 'pm25GradeLabelKo')
      const khaiValue = stringField(record, 'khaiValue')
      const khaiGrade = stringField(record, 'khaiGradeLabelKo')
      if (!stationName) continue
      rows.push(
        `- ${stationName}: dataTime=${dataTime ?? '없음'}, PM10=${pm10Value ?? '없음'}${pm10Grade ? `(${pm10Grade})` : ''}, PM2.5=${pm25Value ?? '없음'}${pm25Grade ? `(${pm25Grade})` : ''}, CAI=${khaiValue ?? '없음'}${khaiGrade ? `(${khaiGrade})` : ''}`,
      )
      if (rows.length >= 8) break
    }
    if (rows.length >= 8) break
  }
  if (rows.length === 0) return undefined
  return `\n\nExact AirKorea rows you may cite verbatim:\n${rows.join('\n')}`
}

function hasSuccessfulRegionLocateResult(messages: readonly unknown[]): boolean {
  const idToName = toolUseById(messages)
  for (const message of messages) {
    const content = messageContent(message)
    if (!Array.isArray(content)) continue
    for (const block of content) {
      const record = asRecord(block)
      if (record?.type !== 'tool_result') continue
      if (record.is_error === true) continue
      if (typeof record.tool_use_id !== 'string') continue
      const toolName = idToName.get(record.tool_use_id)
      if (toolName !== 'locate' && !toolName?.startsWith('kakao_')) continue
      if (typeof record.content !== 'string') continue
      const parsed = parseJsonRecord(record.content)
      if (parsed?.ok === false) continue
      const result = asRecord(parsed?.result ?? parsed)
      if (result?.kind !== 'region') continue
      if (
        typeof result.region_1depth_name === 'string' &&
        typeof result.region_2depth_name === 'string'
      ) {
        return true
      }
    }
  }
  return false
}

function hasSuccessfulPoiLocateResult(messages: readonly unknown[]): boolean {
  const idToName = toolUseById(messages)
  for (const message of messages) {
    const content = messageContent(message)
    if (!Array.isArray(content)) continue
    for (const block of content) {
      const record = asRecord(block)
      if (record?.type !== 'tool_result') continue
      if (record.is_error === true) continue
      if (typeof record.tool_use_id !== 'string') continue
      const toolName = idToName.get(record.tool_use_id)
      if (toolName !== 'locate' && !toolName?.startsWith('kakao_')) continue
      if (typeof record.content !== 'string') continue
      const parsed = parseJsonRecord(record.content)
      if (parsed?.ok === false) continue
      const result = asRecord(parsed?.result ?? parsed)
      if (result?.kind !== 'poi') continue
      if (typeof result.lat === 'number' && typeof result.lon === 'number') {
        return true
      }
    }
  }
  return false
}

function availableToolNamesFromTools(tools: Tools): Set<string> {
  return new Set(tools.map(tool => tool.name))
}

function isAvailableOrSyncedAdapter(
  available: Set<string>,
  toolName: string,
): boolean {
  return available.has(toolName) || resolveAdapter(toolName) !== undefined
}

function chooseAvailableOrSyncedAdapter(
  available: Set<string>,
  candidates: readonly string[],
): string | undefined {
  return candidates.find(candidate => isAvailableOrSyncedAdapter(available, candidate))
}

function isAirportAviationQuery(text: string): boolean {
  return AIRPORT_PLACE_RE.test(text) && AIRPORT_AVIATION_RE.test(text)
}

function isMedicalCollapseQuery(text: string): boolean {
  return MEDICAL_COLLAPSE_RE.test(text) && !NON_MEDICAL_EMERGENCY_RE.test(text)
}

function routeNoFromUserText(text: string): string | undefined {
  return TAGO_ROUTE_NO_RE.exec(text)?.[1]
}

function placeNameFromUserText(text: string): string | undefined {
  const match = TAGO_PLACE_RE.exec(text)
  const place = match?.[1]?.trim()
  if (!place) return undefined
  return place.replace(/\s+/gu, ' ')
}

function isTagoRoutePlaceQuery(text: string): boolean {
  return TAGO_BUS_RE.test(text) && routeNoFromUserText(text) !== undefined
}

function isTagoBusQuery(text: string): boolean {
  return TAGO_BUS_RE.test(text)
}

function isTagoBusOriginDestinationQuery(text: string): boolean {
  if (!isTagoBusQuery(text) || routeNoFromUserText(text) !== undefined) return false
  return /에서[\s\S]{1,50}(?:까지|으로|로|가는|가려고|가야|가려면|이동|방향|행)/u.test(
    text,
  )
}

function hasSuccessfulStationSearch(messages: readonly unknown[]): boolean {
  return toolResultTextsFor(messages, TAGO_STATION_TOOL_NAME).some(
    text => text.includes('"ok":true') && text.includes('"nodeid"'),
  )
}

function hasSuccessfulRouteSearch(messages: readonly unknown[]): boolean {
  return toolResultTextsFor(messages, TAGO_ROUTE_TOOL_NAME).some(
    text => text.includes('"ok":true') && text.includes('"routeid"'),
  )
}

function hasSuccessfulRouteStationSearch(messages: readonly unknown[]): boolean {
  return toolResultTextsFor(messages, TAGO_ROUTE_STATION_TOOL_NAME).some(
    text => text.includes('"ok":true') && text.includes('"nodeid"'),
  )
}

function selectTagoBusToolChoice(
  userText: string,
  available: Set<string>,
  usedToolNames: Set<string>,
  messages: readonly unknown[],
): string | undefined {
  if (!isTagoBusQuery(userText)) return undefined
  if (routeNoFromUserText(userText) === undefined) {
    if (
      !usedToolNames.has(TAGO_STATION_TOOL_NAME) &&
      isAvailableOrSyncedAdapter(available, TAGO_STATION_TOOL_NAME)
    ) {
      return TAGO_STATION_TOOL_NAME
    }
    if (isTagoBusOriginDestinationQuery(userText)) {
      return undefined
    }
    if (
      hasSuccessfulStationSearch(messages) &&
      !usedToolNames.has(TAGO_ARRIVAL_TOOL_NAME) &&
      isAvailableOrSyncedAdapter(available, TAGO_ARRIVAL_TOOL_NAME)
    ) {
      return TAGO_ARRIVAL_TOOL_NAME
    }
    return undefined
  }
  if (
    !usedToolNames.has(TAGO_ROUTE_TOOL_NAME) &&
    isAvailableOrSyncedAdapter(available, TAGO_ROUTE_TOOL_NAME)
  ) {
    return TAGO_ROUTE_TOOL_NAME
  }
  if (
    hasSuccessfulRouteSearch(messages) &&
    !usedToolNames.has(TAGO_ROUTE_STATION_TOOL_NAME) &&
    isAvailableOrSyncedAdapter(available, TAGO_ROUTE_STATION_TOOL_NAME)
  ) {
    return TAGO_ROUTE_STATION_TOOL_NAME
  }
  if (
    hasSuccessfulRouteStationSearch(messages) &&
    !usedToolNames.has(TAGO_ARRIVAL_TOOL_NAME) &&
    isAvailableOrSyncedAdapter(available, TAGO_ARRIVAL_TOOL_NAME)
  ) {
    return TAGO_ARRIVAL_TOOL_NAME
  }
  return undefined
}

export function buildTagoBusFollowupPromptIfNeeded({
  messages,
  availableToolNames,
}: {
  messages: readonly unknown[]
  availableToolNames: Iterable<string>
}): string | undefined {
  const userText = latestUserText(messages)
  if (!isTagoBusQuery(userText)) return undefined
  const available = new Set(availableToolNames)
  const usedToolNames = toolUseNames(messages)
  const routeNo = routeNoFromUserText(userText)
  const placeName = placeNameFromUserText(userText) ?? 'the citizen-named place'
  if (
    routeNo === undefined &&
    isTagoBusOriginDestinationQuery(userText) &&
    hasSuccessfulStationSearch(messages) &&
    !usedToolNames.has(TAGO_ARRIVAL_TOOL_NAME)
  ) {
    return (
      'TAGO bus origin-destination limitation: the citizen asked for an origin-to-destination trip without a route number. ' +
      'The available TAGO adapters expose stop search, route-number search, route passing stops, and stop-based current arrivals; ' +
      'they do not prove an origin-destination route from stop arrivals alone. Do not call tago_bus_arrival_search for this OD request. ' +
      'Write the final Korean answer now from the station evidence, explain that current TAGO tools need a route number or exact stop/route to check arrivals, ' +
      'and do not claim that a bus route to the destination was found.'
    )
  }
  if (
    routeNo === undefined &&
    hasSuccessfulStationSearch(messages) &&
    !usedToolNames.has(TAGO_ARRIVAL_TOOL_NAME) &&
    available.has(TAGO_ARRIVAL_TOOL_NAME)
  ) {
    return (
      'Required follow-up for this TAGO bus chain: the station search has returned nodeid. ' +
      `Before any final answer, call ${TAGO_ARRIVAL_TOOL_NAME} with city_code:"21" ` +
      'and the best matching node_id from the station result to get current arrivals. ' +
      'Do not switch to route search unless the citizen named a route number.'
    )
  }
  if (
    routeNo !== undefined &&
    hasSuccessfulRouteSearch(messages) &&
    !usedToolNames.has(TAGO_ROUTE_STATION_TOOL_NAME) &&
    available.has(TAGO_ROUTE_STATION_TOOL_NAME)
  ) {
    return (
      'Required follow-up for this TAGO bus chain: the route search has returned route_id. ' +
      `Before any final answer, call ${TAGO_ROUTE_STATION_TOOL_NAME} with city_code:"21", ` +
      `that route_id, and node_nm:"${placeName}" to find the route's passing stop nodeid.`
    )
  }
  if (
    routeNo !== undefined &&
    hasSuccessfulRouteStationSearch(messages) &&
    !usedToolNames.has(TAGO_ARRIVAL_TOOL_NAME) &&
    available.has(TAGO_ARRIVAL_TOOL_NAME)
  ) {
    return (
      'Required follow-up for this TAGO bus chain: route passing-stop evidence has returned nodeid. ' +
      `Before any final answer, call ${TAGO_ARRIVAL_TOOL_NAME} with city_code:"21", ` +
      `a matching node_id, and route_no:"${routeNo}" or route_id to get current arrivals. ` +
      'If the first matching direction returns no arrivals, try the other matching nodeid before final prose.'
    )
  }
  return undefined
}

export function buildTagoBusCompletionPromptIfNeeded({
  messages,
}: {
  messages: readonly unknown[]
}): string | undefined {
  const userText = latestUserText(messages)
  if (!isTagoBusQuery(userText)) return undefined
  const usedToolNames = toolUseNames(messages)
  if (routeNoFromUserText(userText) === undefined) {
    return usedToolNames.has(TAGO_ARRIVAL_TOOL_NAME)
      ? TAGO_BUS_COMPLETION_PROMPT
      : undefined
  }
  if (
    !usedToolNames.has(TAGO_ROUTE_STATION_TOOL_NAME) ||
    !usedToolNames.has(TAGO_ARRIVAL_TOOL_NAME)
  ) {
    return undefined
  }
  return TAGO_BUS_COMPLETION_PROMPT
}

export function buildTagoBusFinalAnswerRepairPromptIfNeeded({
  messages,
}: {
  messages: readonly unknown[]
}): string | undefined {
  const userText = latestUserText(messages)
  if (!isTagoBusQuery(userText)) return undefined
  const usedToolNames = toolUseNames(messages)
  if (!usedToolNames.has(TAGO_ARRIVAL_TOOL_NAME)) return undefined
  if (hasTagoBusRepairPrompt(messages)) return undefined
  const assistantText = latestAssistantText(messages)
  if (!TAGO_BUS_PENDING_FINAL_RE.test(assistantText)) return undefined
  return TAGO_BUS_REPAIR_PROMPT
}

export function shouldWithholdTagoBusFinalAnswer({
  messages,
  candidate,
}: {
  messages: readonly unknown[]
  candidate: unknown
}): boolean {
  if (hasTagoBusRepairPrompt(messages)) return false
  return (
    buildTagoBusFinalAnswerRepairPromptIfNeeded({
      messages: [...messages, candidate],
    }) !== undefined
  )
}

export function buildAirKoreaCompletionPromptIfNeeded({
  messages,
}: {
  messages: readonly unknown[]
}): string | undefined {
  const userText = latestUserText(messages)
  if (!AIRKOREA_RE.test(userText)) return undefined
  const usedToolNames = toolUseNames(messages)
  if (!usedToolNames.has(AIRKOREA_TOOL_NAME)) return undefined
  return AIRKOREA_COMPLETION_PROMPT + (airKoreaExactRowsSummary(messages) ?? '')
}

export function buildAirKoreaFinalAnswerRepairPromptIfNeeded({
  messages,
}: {
  messages: readonly unknown[]
}): string | undefined {
  const userText = latestUserText(messages)
  if (!AIRKOREA_RE.test(userText)) return undefined
  const usedToolNames = toolUseNames(messages)
  if (!usedToolNames.has(AIRKOREA_TOOL_NAME)) return undefined
  if (hasAirKoreaRepairPrompt(messages)) return undefined
  const assistantText = latestAssistantText(messages)
  if (!AIRKOREA_UNSUPPORTED_LOCATION_CLAIM_RE.test(assistantText)) return undefined
  return AIRKOREA_REPAIR_PROMPT + (airKoreaExactRowsSummary(messages) ?? '')
}

export function shouldWithholdAirKoreaFinalAnswer({
  messages,
  candidate,
}: {
  messages: readonly unknown[]
  candidate: unknown
}): boolean {
  if (hasAirKoreaRepairPrompt(messages)) return false
  return (
    buildAirKoreaFinalAnswerRepairPromptIfNeeded({
      messages: [...messages, candidate],
    }) !== undefined
  )
}

export function buildGenericPendingFinalAnswerRepairPromptIfNeeded({
  messages,
}: {
  messages: readonly unknown[]
}): string | undefined {
  if (!hasToolResult(messages)) return undefined
  if (hasGenericPendingFinalRepairPrompt(messages)) return undefined
  const assistantText = latestAssistantText(messages)
  if (!GENERIC_PENDING_FINAL_RE.test(assistantText)) return undefined
  return GENERIC_PENDING_FINAL_REPAIR_PROMPT
}

export function shouldWithholdGenericPendingFinalAnswer({
  messages,
  candidate,
}: {
  messages: readonly unknown[]
  candidate: unknown
}): boolean {
  if (hasGenericPendingFinalRepairPrompt(messages)) return false
  return (
    buildGenericPendingFinalAnswerRepairPromptIfNeeded({
      messages: [...messages, candidate],
    }) !== undefined
  )
}

function needsEmergencyRoomSearch(text: string): boolean {
  return MEDICAL_COLLAPSE_OR_ER_RE.test(text) && !NON_MEDICAL_EMERGENCY_RE.test(text)
}

function selectKmaAviationTool(
  userText: string,
  available: Set<string>,
  usedToolNames: Set<string>,
  preferUnused: boolean,
): string | undefined {
  const preferAmos = AMOS_PREFERENCE_RE.test(userText) && GIMPO_RE.test(userText)
  const candidates = preferAmos
    ? ['kma_apihub_url_air_amos_minute', 'kma_apihub_url_air_metar_decoded']
    : ['kma_apihub_url_air_metar_decoded', 'kma_apihub_url_air_amos_minute']
  if (preferUnused) {
    const unused = candidates.filter(candidate => !usedToolNames.has(candidate))
    const unusedChoice = chooseAvailableOrSyncedAdapter(available, unused)
    if (unusedChoice) return unusedChoice
  }
  return chooseAvailableOrSyncedAdapter(available, candidates)
}

function selectProtectedCheckTool(
  userText: string,
  available: Set<string>,
): string | undefined {
  const candidates = [
    MOBILE_ID_RE.test(userText) ? 'mock_verify_mobile_id' : undefined,
    SIMPLE_AUTH_RE.test(userText) ? 'mock_verify_module_simple_auth' : undefined,
    SIMPLE_AUTH_RE.test(userText) ? 'mock_verify_ganpyeon_injeung' : undefined,
    MYDATA_RE.test(userText) ? 'mock_verify_mydata' : undefined,
    ...PROTECTED_CHECK_TOOLS,
  ].filter((toolName): toolName is string => typeof toolName === 'string')
  return chooseAvailableOrSyncedAdapter(available, candidates)
}

function hasAnyToolUse(usedToolNames: Set<string>, candidates: readonly string[]): boolean {
  return candidates.some(candidate => usedToolNames.has(candidate))
}

function requiredKmaAviationTools(
  userText: string,
  available: Set<string>,
): string[] {
  const candidates = GIMPO_RE.test(userText)
    ? ['kma_apihub_url_air_metar_decoded', 'kma_apihub_url_air_amos_minute']
    : ['kma_apihub_url_air_metar_decoded']
  return candidates.filter(candidate => isAvailableOrSyncedAdapter(available, candidate))
}

export function shouldSuppressUmmayaToolCallsForAnswerSynthesis({
  messages,
  tools,
}: {
  messages: readonly Message[]
  tools: Tools
}): boolean {
  const available = availableToolNamesFromTools(tools)
  const userText = latestUserText(messages)
  const usedToolNames = toolUseNames(messages)
  if (
    isMedicalCollapseQuery(userText) &&
    usedToolNames.has(NMC_AED_TOOL_NAME)
  ) {
    return true
  }
  if (
    PROTECTED_QUERY_RE.test(userText) &&
    hasAnyToolUse(usedToolNames, PROTECTED_CHECK_TOOLS)
  ) {
    return true
  }
  if (
    isKmaAnalysisMapText(userText) &&
    usedToolNames.has(KMA_ANALYSIS_CHART_TOOL_NAME)
  ) {
    return true
  }
  if (AIRKOREA_RE.test(userText) && usedToolNames.has(AIRKOREA_TOOL_NAME)) {
    return true
  }
  if (
    isTagoBusQuery(userText) &&
    usedToolNames.has(TAGO_ARRIVAL_TOOL_NAME)
  ) {
    return true
  }
  if (!isAirportAviationQuery(userText)) return false

  const requiredTools = requiredKmaAviationTools(userText, available)
  if (requiredTools.length === 0) return false

  return requiredTools.every(toolName => usedToolNames.has(toolName))
}

function publicDataMismatchTargetTool(
  latestToolResult: string,
): string | undefined {
  const candidate = PUBLIC_DATA_MISMATCH_CALL_RE.exec(latestToolResult)?.[1]
  if (!candidate) return undefined
  return candidate
}

export function selectUmmayaToolChoiceOverride({
  messages,
  tools,
}: {
  messages: readonly Message[]
  tools: Tools
}): BetaToolChoiceTool | undefined {
  const available = availableToolNamesFromTools(tools)
  const userText = latestUserText(messages)
  const latestToolResult = latestToolResultText(messages)
  const usedToolNames = toolUseNames(messages)
  const airportAviationQuery = isAirportAviationQuery(userText)
  const usedAviationTool = hasAnyToolUse(usedToolNames, KMA_AIR_TOOLS)
  const publicDataTargetTool = publicDataMismatchTargetTool(latestToolResult)
  if (
    shouldSuppressUmmayaToolCallsForAnswerSynthesis({
      messages,
      tools,
    })
  ) {
    return undefined
  }

  if (
    publicDataTargetTool &&
    !usedToolNames.has(publicDataTargetTool) &&
    isAvailableOrSyncedAdapter(available, publicDataTargetTool)
  ) {
    return { type: 'tool', name: publicDataTargetTool }
  }

  if (
    AIRKOREA_RE.test(userText) &&
    !usedToolNames.has(AIRKOREA_TOOL_NAME) &&
    isAvailableOrSyncedAdapter(available, AIRKOREA_TOOL_NAME)
  ) {
    return { type: 'tool', name: AIRKOREA_TOOL_NAME }
  }

  if (
    PPS_BID_RE.test(userText) &&
    !usedToolNames.has(PPS_BID_TOOL_NAME) &&
    isAvailableOrSyncedAdapter(available, PPS_BID_TOOL_NAME)
  ) {
    return { type: 'tool', name: PPS_BID_TOOL_NAME }
  }

  if (
    needsEmergencyRoomSearch(userText) &&
    available.has(KAKAO_COORD_TO_REGION_TOOL_NAME) &&
    !usedToolNames.has(KAKAO_COORD_TO_REGION_TOOL_NAME) &&
    !hasSuccessfulRegionLocateResult(messages) &&
    hasSuccessfulPoiLocateResult(messages)
  ) {
    return { type: 'tool', name: KAKAO_COORD_TO_REGION_TOOL_NAME }
  }

  if (
    needsEmergencyRoomSearch(userText) &&
    available.has(NMC_EMERGENCY_TOOL_NAME) &&
    !usedToolNames.has(NMC_EMERGENCY_TOOL_NAME) &&
    hasSuccessfulRegionLocateResult(messages)
  ) {
    return { type: 'tool', name: NMC_EMERGENCY_TOOL_NAME }
  }

  const needsGimpoAviationFollowup =
    airportAviationQuery &&
    GIMPO_RE.test(userText) &&
    usedToolNames.has('kma_apihub_url_air_metar_decoded') &&
    !usedToolNames.has('kma_apihub_url_air_amos_minute') &&
    isAvailableOrSyncedAdapter(available, 'kma_apihub_url_air_amos_minute')

  const shouldForceAviation =
    latestToolResult.includes('KMA aviation tool-choice mismatch') ||
    (airportAviationQuery && !usedAviationTool) ||
    needsGimpoAviationFollowup
  if (shouldForceAviation) {
    const name = selectKmaAviationTool(
      userText,
      available,
      usedToolNames,
      usedAviationTool,
    )
    if (name) return { type: 'tool', name }
  }

  const shouldForceKmaAnalysis =
    latestToolResult.includes('KMA analysis tool-choice mismatch') ||
    (isKmaAnalysisMapText(userText) &&
      !usedToolNames.has(KMA_ANALYSIS_CHART_TOOL_NAME))
  if (
    shouldForceKmaAnalysis &&
    isAvailableOrSyncedAdapter(available, KMA_ANALYSIS_CHART_TOOL_NAME)
  ) {
    return { type: 'tool', name: KMA_ANALYSIS_CHART_TOOL_NAME }
  }

  const shouldForceAed = buildNmcAedFollowupPromptIfNeeded({
    messages,
    availableToolNames: available,
  })
  if (shouldForceAed && available.has(NMC_AED_TOOL_NAME)) {
    return { type: 'tool', name: NMC_AED_TOOL_NAME }
  }

  const tagoToolName = selectTagoBusToolChoice(
    userText,
    available,
    usedToolNames,
    messages,
  )
  if (tagoToolName) {
    return { type: 'tool', name: tagoToolName }
  }

  const shouldForceProtected =
    latestToolResult.includes('Protected-domain tool-choice mismatch') ||
    (PROTECTED_QUERY_RE.test(userText) &&
      !hasAnyToolUse(usedToolNames, PROTECTED_CHECK_TOOLS))
  if (shouldForceProtected) {
    const name = selectProtectedCheckTool(`${userText}\n${latestToolResult}`, available)
    if (name) return { type: 'tool', name }
  }

  return undefined
}
