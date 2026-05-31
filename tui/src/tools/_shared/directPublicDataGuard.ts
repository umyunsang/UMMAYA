import type { ToolUseContext, ValidationResult } from '../../Tool.js'
import { resolveAdapter } from '../../services/api/adapterManifest.js'
import { isNonSyntheticUserMessageText } from './citizenUserText.js'
import { textFromContent } from './nmcAedGuard.js'

const PPS_BID_RE = /(입찰|나라장터|조달청|공고|전기공사|bid|procurement)/iu
const AIRKOREA_RE =
  /(미세먼지|초미세먼지|대기질|대기오염|마스크|pm\s*2\.?5|pm\s*10|air\s*korea|airkorea)/iu
const KMA_CHART_RE = /(일기도|분석일기도|지도\s*자료|비구름|바람\s*흐름|synoptic|weather\s*chart)/iu
const KMA_WEATHER_RE =
  /(날씨|현재\s*기상|실황|관측|예보|기온|습도|풍속|지금\s*비|비\s*(와|오|올|내리)|우산|강수|소나기|산책|퇴근|current\s+weather|forecast|rain|umbrella|precipitation|temperature)/iu
const TAGO_BUS_RE =
  /(버스|시내버스|정류장|정류소|노선|도착|언제\s*와|몇\s*분|bus|route|arrival|station)/iu
const TAGO_ROUTE_NO_RE = /(?:^|[^\d])(\d{1,4}(?:-\d)?)\s*번/u
const KOREAN_SIDO_ABBREVIATIONS: Record<string, string> = {
  서울: '서울특별시',
  부산: '부산광역시',
  대구: '대구광역시',
  인천: '인천광역시',
  광주: '광주광역시',
  대전: '대전광역시',
  울산: '울산광역시',
  세종: '세종특별자치시',
  경기: '경기도',
  강원: '강원특별자치도',
  충북: '충청북도',
  충남: '충청남도',
  전북: '전북특별자치도',
  전남: '전라남도',
  경북: '경상북도',
  경남: '경상남도',
  제주: '제주특별자치도',
}

const AIRKOREA_SIDO_ALIASES: Record<string, string> = {
  서울특별시: '서울',
  부산광역시: '부산',
  대구광역시: '대구',
  인천광역시: '인천',
  광주광역시: '광주',
  대전광역시: '대전',
  울산광역시: '울산',
  세종특별자치시: '세종',
  경기도: '경기',
  강원특별자치도: '강원',
  강원도: '강원',
  충청북도: '충북',
  충청남도: '충남',
  전북특별자치도: '전북',
  전라북도: '전북',
  전라남도: '전남',
  경상북도: '경북',
  경상남도: '경남',
  제주특별자치도: '제주',
  제주도: '제주',
}

type DirectTarget = {
  toolIds: readonly string[]
  label: string
  hint: string
}

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

function latestUserText(context: ToolUseContext): string {
  const messages = Array.isArray(context.messages) ? context.messages : []
  for (let idx = messages.length - 1; idx >= 0; idx -= 1) {
    const message = messages[idx]
    if (messageRole(message) !== 'user') continue
    const text = textFromContent(messageContent(message))
    if (isNonSyntheticUserMessageText(message, text)) return text
  }
  return ''
}

function routeNoFromUserText(text: string): string | undefined {
  const match = TAGO_ROUTE_NO_RE.exec(text)
  return match?.[1]
}

function sidoNameFromUserText(text: string): string | undefined {
  for (const fullName of Object.values(KOREAN_SIDO_ABBREVIATIONS)) {
    if (text.includes(fullName)) return fullName
  }
  for (const [shortName, fullName] of Object.entries(KOREAN_SIDO_ABBREVIATIONS)) {
    const pattern = new RegExp(
      `${shortName}(?:시|도|특별시|광역시|특별자치시|특별자치도)?`,
      'u',
    )
    if (pattern.test(text)) return fullName
  }
  return undefined
}

function airkoreaSidoName(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined
  const trimmed = value.trim()
  if (!trimmed) return undefined
  return AIRKOREA_SIDO_ALIASES[trimmed] ?? trimmed
}

function ppsCurrentWeekWindow(now = new Date()): {
  start: string
  end: string
} {
  const kstNow = new Date(now.getTime() + 9 * 60 * 60 * 1000)
  const day = kstNow.getUTCDay()
  const mondayOffset = (day + 6) % 7
  const weekStart = new Date(
    Date.UTC(
      kstNow.getUTCFullYear(),
      kstNow.getUTCMonth(),
      kstNow.getUTCDate() - mondayOffset,
      0,
      0,
    ),
  )
  const todayEnd = new Date(
    Date.UTC(
      kstNow.getUTCFullYear(),
      kstNow.getUTCMonth(),
      kstNow.getUTCDate(),
      23,
      59,
    ),
  )
  return { start: formatPpsDateTime(weekStart), end: formatPpsDateTime(todayEnd) }
}

function formatPpsDateTime(date: Date): string {
  const year = String(date.getUTCFullYear()).padStart(4, '0')
  const month = String(date.getUTCMonth() + 1).padStart(2, '0')
  const day = String(date.getUTCDate()).padStart(2, '0')
  const hour = String(date.getUTCHours()).padStart(2, '0')
  const minute = String(date.getUTCMinutes()).padStart(2, '0')
  return `${year}${month}${day}${hour}${minute}`
}

function directTargetForUserText(text: string): DirectTarget | undefined {
  if (KMA_CHART_RE.test(text)) {
    return {
      toolIds: ['kma_apihub_url_analysis_weather_chart_image'],
      label: 'kma_apihub_url_analysis_weather_chart_image',
      hint:
        "params must follow the weather chart/map schema: anal_time is required as UTC YYYYMMDDHHMM. Use the latest completed official analysis slot and include minutes, for example '202605281200', not a 10-digit KST hour.",
    }
  }
  if (PPS_BID_RE.test(text)) {
    return {
      toolIds: ['pps_bid_public_info'],
      label: 'pps_bid_public_info',
      hint:
        "params must include inqry_bgn_dt/inqry_end_dt as valid YYYYMMDDHHMM and inqry_div:'1' unless the citizen asks for opening datetime. Keep each PPS call within a 31-day window. Copy citizen keywords into bid_ntce_nm and use region/industry filters only when the citizen supplied them; do not hard-code 전기공사 or 부산광역시 for unrelated procurement questions.",
    }
  }
  if (AIRKOREA_RE.test(text)) {
    return {
      toolIds: ['airkorea_ctprvn_air_quality'],
      label: 'airkorea_ctprvn_air_quality',
      hint:
        "params should include sido_name:'부산', plus optional page_no/num_of_rows/ver exactly as the adapter schema exposes.",
    }
  }
  if (TAGO_BUS_RE.test(text)) {
    return {
      toolIds: [
        'tago_bus_station_search',
        'tago_bus_arrival_search',
        'tago_bus_route_search',
        'tago_bus_route_station_search',
        'tago_bus_location_search',
      ],
      label: 'TAGO bus adapters',
      hint:
        "use TAGO bus schemas for bus arrival/route requests. If a route number is named, call tago_bus_route_search for route_id, then tago_bus_route_station_search with route_id and node_nm to find passing stops. Call tago_bus_arrival_search with city_code, node_id, and route_no or route_id. If node_id is unknown, tago_bus_station_search can list nearby named stops.",
    }
  }
  if (KMA_WEATHER_RE.test(text)) {
    return {
      toolIds: [
        'kakao_keyword_search',
        'kakao_address_search',
        'kakao_coord_to_region',
        'kma_current_observation',
        'kma_ultra_short_term_forecast',
        'kma_short_term_forecast',
      ],
      label: 'KMA weather/location adapters',
      hint:
        'use a location adapter first when coordinates are missing, then KMA current-observation or forecast schemas for rain/umbrella/current-weather values. Do not use air-quality or bus adapters for ordinary weather.',
    }
  }
  return undefined
}

function hasAnyRegisteredTarget(target: DirectTarget): boolean {
  return target.toolIds.some(toolId => resolveAdapter(toolId))
}

const KMA_CHART_PARAM_NAMES = new Set([
  'anal_time',
  'is_typ',
  'image_type',
  'group_name',
  'meta',
])
const TAGO_TOOL_RE = /^tago_bus_/u

function validateTargetParams(
  target: DirectTarget,
  toolId: string,
  params: unknown,
  userText: string,
): ValidationResult | undefined {
  const record = asRecord(params) ?? {}
  if (target.toolIds[0] === 'kma_apihub_url_analysis_weather_chart_image' && toolId === target.toolIds[0]) {
    const extra = Object.keys(record).filter(key => !KMA_CHART_PARAM_NAMES.has(key))
    const analTime = record.anal_time
    if (extra.length > 0 || typeof analTime !== 'string' || !/^\d{12}$/u.test(analTime)) {
      return {
        result: false,
        message:
          'KMA analysis weather-chart schema mismatch: call kma_apihub_url_analysis_weather_chart_image with chart params only. ' +
          "Use anal_time as UTC YYYYMMDDHHMM, for example {\"anal_time\":\"202605281200\"}. " +
          `Do not add non-chart fields such as ${extra.length > 0 ? extra.join(', ') : 'org'} or append UTC text inside the value.`,
        errorCode: 1,
      }
    }
  }

  if (TAGO_TOOL_RE.test(toolId) && /부산|busan/iu.test(userText)) {
    const cityCode = record.city_code
    if (cityCode !== '21') {
      return {
        result: false,
        message:
          'TAGO city_code mismatch: the citizen request is for Busan, and the official TAGO getCtyCodeList mapping is Busan=21. ' +
          `Re-call the TAGO bus adapter with city_code:"21"; do not use non-Busan city_code ${String(cityCode)} for 부산.`,
        errorCode: 1,
      }
    }
  }

  if (toolId === 'tago_bus_arrival_search') {
    const routeNo = routeNoFromUserText(userText)
    const routeNoParam = record.route_no
    const routeIdParam = record.route_id
    if (
      routeNo !== undefined &&
      typeof routeNoParam !== 'string' &&
      typeof routeIdParam !== 'string'
    ) {
      return {
        result: false,
        message:
          `TAGO arrival route filter missing: the citizen asked for route ${routeNo}. ` +
          `Re-call tago_bus_arrival_search with route_no:"${routeNo}" or a route_id ` +
          'from tago_bus_route_search so the result is filtered against TAGO routeno/routeid. ' +
          'When a place is also named, use tago_bus_route_station_search to find the matching nodeid.',
        errorCode: 1,
      }
    }
  }

  if (toolId === 'tago_bus_station_search' && typeof record.route_id === 'string') {
    return {
      result: false,
      message:
        'TAGO station schema mismatch: route_id is for route passing-stop lookup, not stop-name search. ' +
        'Call tago_bus_route_station_search with city_code, route_id, and node_nm to find nodeid values on a route.',
      errorCode: 1,
    }
  }

  return undefined
}

export function normalizeDirectPublicDataToolInput(
  toolId: string,
  context: ToolUseContext,
  input: unknown,
): unknown {
  const userText = latestUserText(context)
  const record = asRecord(input)
  if (!record) return input
  if (toolId === 'airkorea_ctprvn_air_quality') {
    const normalized: Record<string, unknown> = { ...record }
    const fromInput = airkoreaSidoName(normalized.sido_name)
    const fromUser = airkoreaSidoName(sidoNameFromUserText(userText))
    const sidoName = fromInput ?? fromUser
    if (sidoName) normalized.sido_name = sidoName
    if (
      typeof normalized.num_of_rows !== 'number' ||
      normalized.num_of_rows < 100
    ) {
      normalized.num_of_rows = 100
    }
    return normalized
  }
  if (toolId !== 'pps_bid_public_info') return input
  if (!PPS_BID_RE.test(userText)) return input
  const normalized: Record<string, unknown> = { ...record }
  if (/이번\s*주/u.test(userText)) {
    const window = ppsCurrentWeekWindow()
    normalized.inqry_bgn_dt = window.start
    normalized.inqry_end_dt = window.end
    normalized.inqry_div = '1'
  }
  if (/전기\s*공사/iu.test(userText)) {
    normalized.bid_ntce_nm = '전기공사'
    normalized.indstryty_nm = '전기공사업'
  }
  const regionName = sidoNameFromUserText(userText)
  if (regionName) {
    normalized.prtcpt_lmt_rgn_nm = regionName
    normalized.region_name = regionName
  }
  return normalized
}

export function validateDirectPublicDataToolChoice(
  toolId: string,
  context: ToolUseContext,
  params?: unknown,
): ValidationResult | undefined {
  const userText = latestUserText(context)
  const target = directTargetForUserText(userText)
  if (!target) return undefined
  if (target.toolIds.includes(toolId)) {
    return validateTargetParams(target, toolId, params, userText)
  }
  if (!hasAnyRegisteredTarget(target)) return undefined
  return {
    result: false,
    message:
      `Public-data tool-choice mismatch: the latest citizen request matches ${target.label}. ` +
      `Call ${target.label} through the correct primitive instead of ${toolId}. ` +
      target.hint,
    errorCode: 1,
  }
}
