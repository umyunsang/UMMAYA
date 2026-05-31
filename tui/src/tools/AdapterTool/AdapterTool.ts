import { z } from 'zod/v4'
import {
  buildTool,
  type Tool,
  type ToolDef,
  type ToolInputJSONSchema,
  type Tools,
} from '../../Tool.js'
import {
  listAdapters,
  resolveAdapter,
  type AdapterManifestEntry,
} from '../../services/api/adapterManifest.js'
import { getOrCreateUmmayaBridge } from '../../ipc/bridgeSingleton.js'
import { getOrCreatePendingCallRegistry } from '../../ipc/pendingCallSingleton.js'
import { dispatchPrimitive } from '../_shared/dispatchPrimitive.js'
import { validateKmaAviationToolChoice } from '../_shared/kmaAviationGuard.js'
import { validateKmaAnalysisToolChoice } from '../_shared/kmaAnalysisGuard.js'
import { validateNmcAedToolChoice } from '../_shared/nmcAedGuard.js'
import {
  normalizeDirectPublicDataToolInput,
  validateDirectPublicDataToolChoice,
} from '../_shared/directPublicDataGuard.js'
import { LookupPrimitive } from '../LookupPrimitive/LookupPrimitive.js'
import { ResolveLocationPrimitive } from '../ResolveLocationPrimitive/ResolveLocationPrimitive.js'
import { SubmitPrimitive } from '../SubmitPrimitive/SubmitPrimitive.js'
import { VerifyPrimitive } from '../VerifyPrimitive/VerifyPrimitive.js'

type AdapterPrimitive = 'find' | 'locate' | 'send' | 'check'

type InputSchema = z.ZodType<{ [key: string]: unknown }>

const ROOT_PRIMITIVE_TOOL_NAMES = new Set(['locate', 'find', 'check', 'send'])
const KMA_URL_AIR_TOOL_NAMES = new Set([
  'kma_apihub_url_air_amos_minute',
  'kma_apihub_url_air_metar_decoded',
])
const KMA_ANALYSIS_TOOL_NAMES = new Set([
  'kma_apihub_url_high_resolution_grid_point',
  'kma_apihub_url_aws_objective_analysis_grid',
  'kma_apihub_url_analysis_weather_chart_image',
])
const TAGO_BUS_TOOL_NAMES = new Set([
  'tago_bus_station_search',
  'tago_bus_arrival_search',
  'tago_bus_route_search',
  'tago_bus_route_station_search',
  'tago_bus_location_search',
])
const KMA_GIMHAE_AIRPORT_RE = /(김해공항|gimhae|rkpk)/iu
const KMA_GIMPO_AIRPORT_RE = /(김포공항|gimpo|rkss)/iu
const KMA_AIRPORT_NAME_RE = /(공항|\bairport\b|\brk[a-z]{2}\b|station\s*\d{2,3})/iu
const KMA_AIRPORT_AVIATION_RE =
  /(amos|metar|speci|rvr|항공기상|공항기상|활주로|runway|aviation|비행기|항공편|비행편|이륙|착륙|결항|지연|운항|뜰\s*만|뜨나|뜰\s*수|flight|take\s*off|landing|delay|cancel)/iu
const KMA_RUNWAY_AREA_RE =
  /(amos|활주로|rvr|runway|시정|visibility|공항기상관측|매분)/iu
const KMA_ANALYSIS_DATA_RE =
  /(분석자료|이미\s*분석|고해상도\s*격자|객관분석|aws\s*객관|지도\s*자료|일기도|분석일기도|비구름|바람\s*흐름|synoptic|weather\s*chart|objective\s*analysis|high[-\s]?resolution|grid)/iu
const KMA_ANALYSIS_MAP_RE =
  /(일기도|분석일기도|지도\s*자료|비구름|바람\s*흐름|synoptic|weather\s*chart)/iu
const KMA_ANALYSIS_POINT_RE =
  /(주변|근처|특정지점|좌표|위도|경도|\blat\b|\blon\b|공항\s*주변)/iu
const KMA_LIFESTYLE_WEATHER_RE =
  /(날씨|현재\s*기상|실황|관측|예보|기온|습도|풍속|지금\s*비|비\s*(와|오|올|내리)|우산|강수|소나기|산책|퇴근|current\s+weather|forecast|rain|umbrella|precipitation|temperature)/iu
const KMA_LIFESTYLE_WEATHER_TOOL_NAMES = new Set([
  'kma_current_observation',
  'kma_ultra_short_term_forecast',
  'kma_short_term_forecast',
])
const HIRA_MEDICAL_DETAIL_RE =
  /((병원|의료기관|의원).*(상세|진료과|진료과목|진료시간|주차)|(상세|진료시간|주차|응급실).*(병원|의료기관|의원)|ykiho|detail)/iu
const MOIS_EMERGENCY_CALL_BOX_RE =
  /(안전\s*비상벨|비상벨|긴급\s*신고함|긴급신고함|방범벨|emergency\s+call\s+box)/iu
const GYERYONG_ASSISTIVE_CHARGER_RE =
  /((전동보장구|전동\s*휠체어|보장구|장애인).*(충전|충전소|충전장소)|(충전|충전소|충전장소).*(전동보장구|전동\s*휠체어|보장구|장애인)|계룡시?.*(충전소|충전\s*장소))/iu
const MOF_OCEAN_WATER_QUALITY_RE =
  /(해양\s*수질|해양수질|수질\s*자동\s*측정|용존산소|\bpH\b|water\s+quality|ocean\s+water)/iu
const PPS_SHOPPING_RE = /(종합\s*쇼핑몰|쇼핑몰|계약\s*물품|물품\s*조회|shopping\s*mall)/iu
const PPS_BID_RE = /(입찰|나라장터|조달청|\bbid\b|procurement|tender)/iu
const PROTECTED_QUERY_RE =
  /(본인확인|인증|간편인증|모바일\s*(?:신분증|id)|mobile\s*id|마이데이터|mydata|증명원|소득금액증명|소득금액증명원|주민등록등본|민원|발급)/iu
const PROTECTED_MOBILE_ID_RE = /(mobile\s*id|모바일\s*(?:신분증|id)|mobile_id)/iu
const PROTECTED_SIMPLE_AUTH_RE =
  /(simple_auth|간편인증|ganpyeon|소득금액증명|증명원|민원|발급)/iu
const PROTECTED_MYDATA_RE = /(mydata|마이데이터)/iu
const PROTECTED_CHECK_TOOL_NAMES = [
  'mock_verify_module_simple_auth',
  'mock_verify_ganpyeon_injeung',
  'mock_verify_mobile_id',
  'mock_verify_mydata',
] as const
const TAGO_BUS_RE =
  /(버스|시내버스|정류장|정류소|노선|도착|언제\s*와|몇\s*분|bus|route|arrival|station)/iu
const AED_REQUEST_RE = /(aed|자동심장|심장충격|제세동)/iu
const EMERGENCY_REQUEST_RE = /(응급|응급실|\ber\b|emergency)/iu
const MEDICAL_COLLAPSE_RE =
  /(사람이\s*쓰러|쓰러졌|쓰러져|의식\s*잃|의식을\s*잃|심정지|호흡이\s*없|숨을\s*안|collapsed|unconscious|cardiac\s*arrest)/iu
const TRAFFIC_HAZARD_RE =
  /(교통사고|사고\s*위험|사고다발|위험\s*(구간|도로|지점)|어린이보호구역|보호구역|도로\s*구간|accident|hazard|hotspot)/iu

const fallbackInputSchema = z.object({}).passthrough() as InputSchema

type JsonObject = Record<string, unknown>

function isJsonObject(value: unknown): value is JsonObject {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function asJsonObject(value: unknown): JsonObject {
  return isJsonObject(value) ? value : {}
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string')
    : []
}

function schemaDescription(schema: JsonObject): string | undefined {
  return typeof schema.description === 'string' && schema.description.trim()
    ? schema.description
    : undefined
}

function applyJsonSchemaMetadata(schema: z.ZodTypeAny, jsonSchema: JsonObject): z.ZodTypeAny {
  let result = schema
  const description = schemaDescription(jsonSchema)
  if (description) {
    result = result.describe(description)
  }
  if (Object.prototype.hasOwnProperty.call(jsonSchema, 'default')) {
    result = result.default(jsonSchema.default)
  }
  return result
}

function zodUnion(schemas: z.ZodTypeAny[]): z.ZodTypeAny {
  if (schemas.length === 0) {
    return z.unknown()
  }
  if (schemas.length === 1) {
    return schemas[0] ?? z.unknown()
  }
  return z.union(schemas as [z.ZodTypeAny, z.ZodTypeAny, ...z.ZodTypeAny[]])
}

function zodLiteralUnion(values: unknown[]): z.ZodTypeAny {
  const literals = values.map(value => z.literal(value as string | number | boolean | null))
  return zodUnion(literals)
}

function resolveRef(root: JsonObject, ref: string): JsonObject | undefined {
  if (!ref.startsWith('#/$defs/')) {
    return undefined
  }
  const defName = decodeURIComponent(ref.slice('#/$defs/'.length))
  const defs = asJsonObject(root.$defs)
  const resolved = defs[defName]
  return isJsonObject(resolved) ? resolved : undefined
}

function zodFromJsonSchema(schema: JsonObject, root: JsonObject): z.ZodTypeAny {
  if (typeof schema.$ref === 'string') {
    const resolved = resolveRef(root, schema.$ref)
    if (resolved) {
      return applyJsonSchemaMetadata(zodFromJsonSchema(resolved, root), schema)
    }
  }

  const variants = Array.isArray(schema.anyOf)
    ? schema.anyOf
    : Array.isArray(schema.oneOf)
      ? schema.oneOf
      : undefined
  if (variants) {
    const variantSchemas = variants
      .filter(isJsonObject)
      .map(variant => zodFromJsonSchema(variant, root))
    return applyJsonSchemaMetadata(zodUnion(variantSchemas), schema)
  }

  if (Array.isArray(schema.enum) && schema.enum.length > 0) {
    return applyJsonSchemaMetadata(zodLiteralUnion(schema.enum), schema)
  }

  if (Object.prototype.hasOwnProperty.call(schema, 'const')) {
    return applyJsonSchemaMetadata(
      z.literal(schema.const as string | number | boolean | null),
      schema,
    )
  }

  const typeValue = schema.type
  if (Array.isArray(typeValue)) {
    const nonNullTypes = typeValue.filter(item => item !== 'null')
    const nullable = nonNullTypes.length !== typeValue.length
    const typedSchemas = nonNullTypes.map(typeName =>
      zodFromJsonSchema({ ...schema, type: typeName }, root),
    )
    const base = zodUnion(typedSchemas)
    return applyJsonSchemaMetadata(nullable ? base.nullable() : base, schema)
  }

  switch (typeValue) {
    case 'string':
      return applyJsonSchemaMetadata(z.string(), schema)
    case 'integer':
      return applyJsonSchemaMetadata(z.number().int(), schema)
    case 'number':
      return applyJsonSchemaMetadata(z.number(), schema)
    case 'boolean':
      return applyJsonSchemaMetadata(z.boolean(), schema)
    case 'array': {
      const itemSchema = isJsonObject(schema.items)
        ? zodFromJsonSchema(schema.items, root)
        : z.unknown()
      return applyJsonSchemaMetadata(z.array(itemSchema), schema)
    }
    case 'object': {
      const properties = asJsonObject(schema.properties)
      const required = new Set(asStringArray(schema.required))
      const shape: Record<string, z.ZodTypeAny> = {}
      for (const [propertyName, propertySchemaRaw] of Object.entries(properties)) {
        const propertySchema = asJsonObject(propertySchemaRaw)
        let fieldSchema = zodFromJsonSchema(propertySchema, root)
        if (
          !required.has(propertyName) &&
          !Object.prototype.hasOwnProperty.call(propertySchema, 'default')
        ) {
          fieldSchema = fieldSchema.optional()
        }
        shape[propertyName] = fieldSchema
      }
      const objectSchema =
        schema.additionalProperties === false
          ? z.object(shape).strict()
          : z.object(shape).passthrough()
      return applyJsonSchemaMetadata(objectSchema, schema)
    }
    case 'null':
      return applyJsonSchemaMetadata(z.null(), schema)
    default:
      return applyJsonSchemaMetadata(z.unknown(), schema)
  }
}

function inputSchemaFor(entry: AdapterManifestEntry): InputSchema {
  const schema = asJsonObject(entry.input_schema_json)
  if (schema.type !== 'object') {
    return fallbackInputSchema
  }
  return zodFromJsonSchema(schema, schema) as InputSchema
}

function inputJSONSchemaFor(entry: AdapterManifestEntry): ToolInputJSONSchema | undefined {
  const schema = asJsonObject(entry.input_schema_json)
  if (schema.type !== 'object') {
    return undefined
  }
  return schema as ToolInputJSONSchema
}

function primitiveFor(entry: AdapterManifestEntry): AdapterPrimitive {
  return entry.primitive as AdapterPrimitive
}

function primitiveToolFor(primitive: AdapterPrimitive): Tool {
  switch (primitive) {
    case 'locate':
      return ResolveLocationPrimitive as Tool
    case 'send':
      return SubmitPrimitive as Tool
    case 'check':
      return VerifyPrimitive as Tool
    case 'find':
    default:
      return LookupPrimitive as Tool
  }
}

function rootInputFor(entry: AdapterManifestEntry, input: Record<string, unknown>) {
  return {
    tool_id: entry.tool_id,
    params: input,
  }
}

function validateAdapterContractInput(
  toolId: string,
  input: Record<string, unknown>,
) {
  if (toolId !== 'kma_apihub_url_analysis_weather_chart_image') return undefined
  const analTime = input.anal_time
  if (typeof analTime === 'string' && /^\d{12}$/u.test(analTime)) return undefined
  return {
    result: false as const,
    message:
      'KMA analysis weather-chart schema mismatch: anal_time is required as UTC YYYYMMDDHHMM. ' +
      "Use a 12-digit official analysis time with minutes, for example '202605281200', not a 10-digit KST hour. " +
      'If the citizen asks for now/today, choose the latest completed official UTC analysis slot and report upstream failure directly if APIHub has no chart.',
    errorCode: 1,
  }
}

export function isAdapterToolName(name: string): boolean {
  return resolveAdapter(name) !== undefined
}

export function isRootPrimitiveToolName(name: string): boolean {
  return ROOT_PRIMITIVE_TOOL_NAMES.has(name)
}

export function getAdapterToolByName(name: string): Tool | undefined {
  const entry = resolveAdapter(name)
  return entry ? buildAdapterTool(entry) : undefined
}

export function getAdapterTools(): Tools {
  return listAdapters().map(buildAdapterTool)
}

function searchTokens(text: string): string[] {
  return text.toLowerCase().match(/[\p{L}\p{N}_-]+/gu) ?? []
}

function expandedQueryTokens(query: string): Set<string> {
  const tokens = new Set(searchTokens(query))
  const compact = query.toLowerCase()
  const airportAviationQuery = isAirportAviationQuery(query)
  if (/[날씨기상비강수기온습도풍속예보관측실황]/u.test(compact)) {
    for (const token of [
      '날씨',
      '기상',
      '현재',
      '관측',
      '실황',
      'weather',
      'current',
      'observation',
      'forecast',
      'temperature',
      'precipitation',
      'humidity',
      'wind',
      'kma',
      '초단기실황',
      '초단기예보',
      '단기예보',
      '우산',
      'nx',
      'ny',
      'base_date',
      'base_time',
    ]) {
      tokens.add(token)
    }
  }
  const medicalEmergencyQuery = isMedicalEmergencyQuery(query)
  const collapseOrAedQuery = isCollapseOrAedQuery(query)
  if (EMERGENCY_REQUEST_RE.test(compact) && medicalEmergencyQuery) {
    for (const token of [
      '응급',
      '응급실',
      '응급의료',
      '응급의료센터',
      '실시간',
      '병상',
      '야간',
      'emergency',
      'room',
      'er',
      'nmc',
    ]) {
      tokens.add(token)
    }
  }
  if (collapseOrAedQuery) {
    for (const token of [
      '응급',
      '응급실',
      '응급의료',
      '응급의료센터',
      'aed',
      '자동심장충격기',
      '자동제세동기',
      '심장충격기',
      '응급처치',
      '심정지',
      '의식불명',
      'emergency',
      'room',
      'er',
      'defibrillator',
      'cardiac',
      'arrest',
      'nmc',
    ]) {
      tokens.add(token)
    }
  }
  if (/(병원|의료|진료|약국|hospital|clinic|medical)/u.test(compact)) {
    for (const token of [
      '병원',
      '의료기관',
      '진료',
      '진료과목',
      '야간',
      '약국',
      'hospital',
      'clinic',
      'medical',
      'nearby',
    ]) {
      tokens.add(token)
    }
  }
  if (HIRA_MEDICAL_DETAIL_RE.test(query)) {
    for (const token of [
      '상세정보',
      '진료과',
      '진료과목',
      '진료시간',
      '주차',
      '요양기호',
      'ykiho',
      'hira',
      'detail',
      'specialty',
    ]) {
      tokens.add(token)
    }
  }
  if (MOIS_EMERGENCY_CALL_BOX_RE.test(query)) {
    for (const token of [
      '안전비상벨',
      '비상벨',
      '긴급신고함',
      '방범',
      '행정안전부',
      'mois',
      'emergency',
      'call',
      'box',
    ]) {
      tokens.add(token)
    }
  }
  if (GYERYONG_ASSISTIVE_CHARGER_RE.test(query)) {
    for (const token of [
      '계룡시',
      '전동보장구',
      '전동휠체어',
      '보장구',
      '장애인',
      '충전소',
      '충전장소',
      'accessibility',
      'charger',
    ]) {
      tokens.add(token)
    }
  }
  if (MOF_OCEAN_WATER_QUALITY_RE.test(query)) {
    for (const token of [
      '해양수산부',
      '해양수질',
      '수질자동측정망',
      '관측소',
      'sea3003',
      '용존산소',
      'water',
      'quality',
      'ocean',
    ]) {
      tokens.add(token)
    }
  }
  if (isPpsBidQuery(query)) {
    for (const token of [
      '조달청',
      '나라장터',
      '입찰공고',
      '공사입찰',
      'bidntcenm',
      'inqrybgndt',
      'inqryenddt',
      'pps',
      'bid',
      'procurement',
    ]) {
      tokens.add(token)
    }
  }
  if (isProtectedCheckQuery(query)) {
    for (const token of [
      '본인확인',
      '인증',
      '간편인증',
      '모바일신분증',
      '모바일id',
      '소득금액증명원',
      '증명원',
      '홈택스',
      '정부24',
      'check',
      'verify',
      'identity',
      'simple',
      'auth',
      'mobile',
      'id',
      'mydata',
    ]) {
      tokens.add(token)
    }
  }
  if (isTagoBusQuery(query)) {
    for (const token of [
      '국토교통부',
      'tago',
      '버스',
      '시내버스',
      '버스정류소',
      '정류장',
      '정류소',
      '노선',
      '노선번호',
      '버스도착',
      '도착',
      'nodeid',
      'nodenm',
      'nodeno',
      'routeid',
      'routeno',
      'citycode',
      'bus',
      'station',
      'route',
      'arrival',
    ]) {
      tokens.add(token)
    }
  }
  if (collapseOrAedQuery) {
    for (const token of ['aed', '자동심장충격기', '자동제세동기', '심장충격기', '위치']) {
      tokens.add(token)
    }
  }
  if (/(미세먼지|초미세|대기질|공기질|airquality|air quality)/u.test(compact)) {
    for (const token of ['미세먼지', '대기질', '대기오염', 'airkorea', 'air', 'quality']) {
      tokens.add(token)
    }
  }
  if (/(법률|변호사|무료상담|상담)/u.test(compact)) {
    for (const token of ['법률', '변호사', '마을변호사', '상담', 'legal', 'lawyer']) {
      tokens.add(token)
    }
  }
  if (/(장례|화장|봉안|장사|funeral)/u.test(compact)) {
    for (const token of ['장례', '장례식장', '시설사용료', 'funeral', 'fee']) {
      tokens.add(token)
    }
  }
  if (/(취업|채용|공고|공무원|job|recruit)/u.test(compact)) {
    for (const token of ['취업', '채용', '공고', '공무원', 'public', 'job']) {
      tokens.add(token)
    }
  }
  if (/(대학|등록금|유학생|tuition|university)/u.test(compact)) {
    for (const token of ['대학', '등록금', '유학생', '대학알리미', 'tuition', 'university']) {
      tokens.add(token)
    }
  }
  if (/(전력|전기|한전|계약종별|power|kepco)/u.test(compact)) {
    for (const token of ['전력', '전기사용량', '계약종별', '한전', 'kepco', 'power', 'usage']) {
      tokens.add(token)
    }
  }
  if (/(특보|예비특보|경보|주의보|태풍|warning|alert)/u.test(compact)) {
    for (const token of ['특보', '예비특보', '경보', '주의보', '기상청', 'weather', 'alert']) {
      tokens.add(token)
    }
  }
  if (airportAviationQuery) {
    for (const token of [
      'metar',
      'speci',
      'amos',
      '항공기상',
      '공항기상',
      '항공',
      '비행기',
      '항공편',
      '운항',
      '이륙',
      '시정',
      'rvr',
      'wind',
      'visibility',
    ]) {
      tokens.add(token)
    }
    if (KMA_GIMPO_AIRPORT_RE.test(query) && KMA_RUNWAY_AREA_RE.test(query)) {
      for (const token of [
        'amos',
        '공항기상관측',
        '매분자료',
        '활주로',
        '김포공항',
        'stn110',
        'runway',
        'visibility',
      ]) {
        tokens.add(token)
      }
    }
  }
  if (KMA_ANALYSIS_DATA_RE.test(query)) {
    for (const token of [
      '분석자료',
      '고해상도',
      '격자자료',
      '객관분석',
      'aws',
      '분석일기도',
      '지도',
      '비구름',
      '바람흐름',
      'objective',
      'analysis',
      'grid',
      'chart',
    ]) {
      tokens.add(token)
    }
  }
  if (/(교통사고|사고\s*위험|사고다발|위험\s*(구간|도로|지점)|어린이보호구역|보호구역|도로\s*구간|accident|hazard|hotspot)/u.test(compact)) {
    for (const token of [
      '교통사고',
      '사고',
      '위험',
      '위험지점',
      '사고다발',
      '사고다발구역',
      '어린이보호구역',
      '행정동코드',
      'koroad',
      'accident',
      'hazard',
      'hotspot',
    ]) {
      tokens.add(token)
    }
  }
  if (/(주소|위치|좌표|행정|[가-힣]+(시|군|구|동|읍|면|로|길))/u.test(compact)) {
    for (const token of [
      'locate',
      '위치',
      '주소',
      '좌표',
      '행정동',
      '법정동',
      'geocode',
      'address',
      'kakao',
    ]) {
      tokens.add(token)
    }
  }
  if (
    !airportAviationQuery &&
    /(근처|주변|인근|가까운|역|터미널|공항|캠퍼스|대학교|대학|해수욕장|시장|공원|랜드마크|nearby|around)/u.test(compact)
  ) {
    for (const token of [
      '장소',
      '키워드',
      'poi',
      '랜드마크',
      '역',
      'keyword',
      'station',
      'place',
    ]) {
      tokens.add(token)
    }
  }
  return tokens
}

type ScoredAdapterEntry = {
  entry: AdapterManifestEntry
  score: number
}

function queryExplicitlyMentionsCoordinates(query: string): boolean {
  return /좌표|위도|경도|\blat\b|\blon\b|\blongitude\b|\blatitude\b|wgs84|coord|coord2region|reverse geocode|q0|q1/i.test(query)
}

function isReverseGeocodeAdapter(toolId: string): boolean {
  return toolId === 'kakao_coord_to_region' || toolId === 'sgis_adm_cd_lookup'
}

function queryTargetsKoroadHazardDataset(query: string): boolean {
  return /(사고\s*위험|위험\s*(구간|도로|지점)|도로\s*구간|어린이보호구역|보호구역|스쿨존|행정동코드|adm_cd|hazard|hotspot)/iu.test(query)
}

function isAirportAviationQuery(query: string): boolean {
  return KMA_AIRPORT_NAME_RE.test(query) && KMA_AIRPORT_AVIATION_RE.test(query)
}

function isMedicalEmergencyQuery(query: string): boolean {
  return (
    (EMERGENCY_REQUEST_RE.test(query) ||
      AED_REQUEST_RE.test(query) ||
      MEDICAL_COLLAPSE_RE.test(query)) &&
    !MOIS_EMERGENCY_CALL_BOX_RE.test(query)
  )
}

function isCollapseOrAedQuery(query: string): boolean {
  return (
    (AED_REQUEST_RE.test(query) || MEDICAL_COLLAPSE_RE.test(query)) &&
    !MOIS_EMERGENCY_CALL_BOX_RE.test(query)
  )
}

function isLocationAdapter(entry: AdapterManifestEntry): boolean {
  return entry.primitive === 'locate' || ROOT_PRIMITIVE_TOOL_NAMES.has(entry.tool_id)
}

function isKmaAnalysisQuery(query: string): boolean {
  return KMA_ANALYSIS_DATA_RE.test(query)
}

function isLifestyleWeatherQuery(query: string): boolean {
  return (
    KMA_LIFESTYLE_WEATHER_RE.test(query) &&
    !isAirportAviationQuery(query) &&
    !isKmaAnalysisQuery(query) &&
    !isMedicalEmergencyQuery(query) &&
    !TRAFFIC_HAZARD_RE.test(query) &&
    !MOF_OCEAN_WATER_QUALITY_RE.test(query)
  )
}

function isPpsBidQuery(query: string): boolean {
  return PPS_BID_RE.test(query) && !PPS_SHOPPING_RE.test(query)
}

function isProtectedCheckQuery(query: string): boolean {
  return PROTECTED_QUERY_RE.test(query)
}

function protectedCheckToolPreference(query: string): string[] {
  const preferred = [
    PROTECTED_MOBILE_ID_RE.test(query) ? 'mock_verify_mobile_id' : undefined,
    PROTECTED_SIMPLE_AUTH_RE.test(query) ? 'mock_verify_module_simple_auth' : undefined,
    PROTECTED_SIMPLE_AUTH_RE.test(query) ? 'mock_verify_ganpyeon_injeung' : undefined,
    PROTECTED_MYDATA_RE.test(query) ? 'mock_verify_mydata' : undefined,
    ...PROTECTED_CHECK_TOOL_NAMES,
  ].filter((toolName): toolName is string => typeof toolName === 'string')
  return [...new Set(preferred)]
}

function isTagoBusQuery(query: string): boolean {
  return TAGO_BUS_RE.test(query)
}

function isKmaAnalysisMapQuery(query: string): boolean {
  return KMA_ANALYSIS_MAP_RE.test(query)
}

function isKmaAnalysisPointQuery(query: string): boolean {
  return KMA_ANALYSIS_POINT_RE.test(query) && !isKmaAnalysisMapQuery(query)
}

function queryPrefersPoiLocation(query: string): boolean {
  return /(근처|주변|인근|가까운|역|터미널|공항|캠퍼스|대학교|대학|해수욕장|시장|공원|랜드마크|nearby|around)/iu.test(query)
}

function scoreAdapterEntry(
  entry: AdapterManifestEntry,
  queryTokens: Set<string>,
  query: string,
): number {
  const searchHint = entry.search_hint.toLowerCase()
  const description = (entry.llm_description ?? '').toLowerCase()
  const haystack = [
    entry.tool_id,
    entry.name,
    entry.primitive,
    searchHint,
    description,
  ].join(' ').toLowerCase()
  const hintTokens = new Set(searchTokens(searchHint))
  let score = 0
  for (const token of queryTokens) {
    if (!token) continue
    if (entry.tool_id.toLowerCase().includes(token)) score += 12
    if (hintTokens.has(token)) score += 8
    else if (searchHint.includes(token)) score += 4
    if (description.includes(token)) score += 2
    if (haystack.includes(token)) score += 1
  }
  if (query.toLowerCase().includes(entry.tool_id.toLowerCase())) score += 1000
  if (
    isReverseGeocodeAdapter(entry.tool_id) &&
    !queryExplicitlyMentionsCoordinates(query)
  ) {
    score = Math.max(0, score - 24)
  }
  if (queryTargetsKoroadHazardDataset(query)) {
    if (entry.tool_id === 'koroad_accident_hazard_search') score += 32
    if (entry.tool_id === 'koroad_accident_search') score = 0
  }
  if (isKmaAnalysisQuery(query)) {
    if (entry.tool_id === 'kma_apihub_url_analysis_weather_chart_image') {
      score += isKmaAnalysisMapQuery(query) ? 900 : isKmaAnalysisPointQuery(query) ? -20 : 150
    }
    if (entry.tool_id === 'kma_apihub_url_high_resolution_grid_point') {
      score += isKmaAnalysisPointQuery(query) ? 900 : 450
    }
    if (entry.tool_id === 'kma_apihub_url_aws_objective_analysis_grid') {
      score += isKmaAnalysisPointQuery(query) ? 800 : 400
    }
    if (isKmaAnalysisPointQuery(query) && queryPrefersPoiLocation(query)) {
      if (entry.tool_id === 'kakao_keyword_search') score += 30
      if (entry.tool_id === 'kakao_address_search') score = Math.max(1, score - 15)
    }
  }
  if (isLifestyleWeatherQuery(query)) {
    if (entry.tool_id === 'kakao_keyword_search') score += 1100
    if (entry.tool_id === 'kakao_address_search') score += 1000
    if (entry.tool_id === 'kma_current_observation') score += 900
    if (entry.tool_id === 'kma_ultra_short_term_forecast') score += 800
    if (entry.tool_id === 'kma_short_term_forecast') score += 650
    if (entry.tool_id === 'kakao_coord_to_region') score += 260
    if (entry.tool_id === 'juso_adm_cd_lookup') score += 260
    if (entry.tool_id === 'sgis_adm_cd_lookup') score += 260
  }
  if (HIRA_MEDICAL_DETAIL_RE.test(query)) {
    if (entry.tool_id === 'hira_medical_institution_detail') score += 650
  }
  if (MOIS_EMERGENCY_CALL_BOX_RE.test(query)) {
    if (entry.tool_id === 'mois_emergency_call_box_lookup') score += 1000
  }
  if (GYERYONG_ASSISTIVE_CHARGER_RE.test(query)) {
    if (entry.tool_id === 'gyeryong_assistive_device_charging_place_locate') {
      score += 1000
    }
  }
  if (MOF_OCEAN_WATER_QUALITY_RE.test(query)) {
    if (entry.tool_id === 'mof_ocean_water_quality_check') score += 1000
  }
  if (isPpsBidQuery(query)) {
    if (entry.tool_id === 'pps_bid_public_info') score += 1000
  }
  if (isProtectedCheckQuery(query) && entry.primitive === 'check') {
    const preference = protectedCheckToolPreference(query)
    const index = preference.indexOf(entry.tool_id)
    score += index >= 0 ? 1000 - index * 20 : 500
  }
  if (isTagoBusQuery(query)) {
    if (entry.tool_id === 'tago_bus_station_search') score += 1050
    if (entry.tool_id === 'tago_bus_arrival_search') score += 1000
    if (entry.tool_id === 'tago_bus_route_station_search') score += 950
    if (entry.tool_id === 'tago_bus_route_search') score += 850
    if (entry.tool_id === 'tago_bus_location_search') score += 650
  }
  if (isCollapseOrAedQuery(query)) {
    if (entry.tool_id === 'nmc_aed_site_locate') score += 900
    if (entry.tool_id === 'nmc_emergency_search') score += 700
    if (queryPrefersPoiLocation(query) && entry.tool_id === 'kakao_keyword_search') score += 120
  }
  if (
    KMA_GIMPO_AIRPORT_RE.test(query) &&
    KMA_RUNWAY_AREA_RE.test(query) &&
    KMA_AIRPORT_AVIATION_RE.test(query) &&
    entry.tool_id === 'kma_apihub_url_air_amos_minute'
  ) {
    score += 500
  }
  return score
}

function filterSpecialCaseRanked(
  query: string,
  ranked: ScoredAdapterEntry[],
): ScoredAdapterEntry[] {
  let filtered = ranked
  if (isKmaAnalysisQuery(query)) {
    const allowLocation = isKmaAnalysisPointQuery(query)
    const preferPoiLocation = queryPrefersPoiLocation(query)
    filtered = filtered
      .filter(candidate => {
        if (KMA_ANALYSIS_TOOL_NAMES.has(candidate.entry.tool_id)) return true
        return allowLocation && isLocationAdapter(candidate.entry)
      })
      .map(candidate => {
        if (!allowLocation || !isLocationAdapter(candidate.entry)) return candidate
        let score = Math.max(1, candidate.score - 10)
        if (preferPoiLocation && candidate.entry.tool_id === 'kakao_keyword_search') {
          score += 30
        } else if (preferPoiLocation && candidate.entry.tool_id === 'kakao_address_search') {
          score = Math.max(1, score - 15)
        }
        return { ...candidate, score }
      })
      .sort((a, b) => {
        if (b.score !== a.score) return b.score - a.score
        return a.entry.tool_id.localeCompare(b.entry.tool_id)
      })
  }
  if (isLifestyleWeatherQuery(query)) {
    const allowed = filtered.filter(
      candidate =>
        KMA_LIFESTYLE_WEATHER_TOOL_NAMES.has(candidate.entry.tool_id) ||
        isLocationAdapter(candidate.entry),
    )
    if (allowed.length > 0) {
      filtered = allowed.sort((a, b) => {
        if (b.score !== a.score) return b.score - a.score
        return a.entry.tool_id.localeCompare(b.entry.tool_id)
      })
    }
  }
  if (isPpsBidQuery(query)) {
    const allowed = filtered.filter(candidate => candidate.entry.tool_id === 'pps_bid_public_info')
    if (allowed.length > 0) {
      filtered = allowed.sort((a, b) => {
        if (b.score !== a.score) return b.score - a.score
        return a.entry.tool_id.localeCompare(b.entry.tool_id)
      })
    }
  }
  if (isProtectedCheckQuery(query)) {
    const preference = protectedCheckToolPreference(query)
    const allowed = filtered.filter(candidate => candidate.entry.primitive === 'check')
    if (allowed.length > 0) {
      filtered = allowed.sort((a, b) => {
        const aIndex = preference.indexOf(a.entry.tool_id)
        const bIndex = preference.indexOf(b.entry.tool_id)
        const aRank = aIndex >= 0 ? aIndex : Number.MAX_SAFE_INTEGER
        const bRank = bIndex >= 0 ? bIndex : Number.MAX_SAFE_INTEGER
        if (aRank !== bRank) return aRank - bRank
        if (b.score !== a.score) return b.score - a.score
        return a.entry.tool_id.localeCompare(b.entry.tool_id)
      })
    }
  }
  if (isTagoBusQuery(query)) {
    const allowed = filtered.filter(candidate => TAGO_BUS_TOOL_NAMES.has(candidate.entry.tool_id))
    if (allowed.length > 0) {
      filtered = allowed.sort((a, b) => {
        if (b.score !== a.score) return b.score - a.score
        return a.entry.tool_id.localeCompare(b.entry.tool_id)
      })
    }
  }
  if (isCollapseOrAedQuery(query)) {
    const allowed = filtered.filter(candidate => {
      if (candidate.entry.tool_id === 'nmc_aed_site_locate') return true
      if (candidate.entry.tool_id === 'nmc_emergency_search') return true
      return isLocationAdapter(candidate.entry)
    })
    if (allowed.some(candidate => candidate.entry.tool_id === 'nmc_aed_site_locate')) {
      filtered = allowed.sort((a, b) => {
        if (b.score !== a.score) return b.score - a.score
        return a.entry.tool_id.localeCompare(b.entry.tool_id)
      })
    }
  }
  if (KMA_GIMHAE_AIRPORT_RE.test(query) && KMA_AIRPORT_AVIATION_RE.test(query)) {
    filtered = filtered.filter(
      candidate => candidate.entry.tool_id !== 'kma_apihub_url_air_amos_minute',
    )
  }
  if (isAirportAviationQuery(query)) {
    const hasAirUrlCandidate = filtered.some(candidate =>
      KMA_URL_AIR_TOOL_NAMES.has(candidate.entry.tool_id),
    )
    if (hasAirUrlCandidate) {
      filtered = filtered.filter(
        candidate =>
          !isLocationAdapter(candidate.entry) &&
          candidate.entry.tool_id !== 'kma_current_observation',
      )
    }
  }
  return filtered
}

export function selectTopKAdapterToolNamesForQuery(
  query: string,
  maxResults = 5,
): string[] {
  const normalizedQuery = query.trim()
  if (!normalizedQuery || maxResults <= 0) return []
  const queryTokens = expandedQueryTokens(normalizedQuery)
  const ranked = filterSpecialCaseRanked(
    normalizedQuery,
    listAdapters()
    .filter(entry => !ROOT_PRIMITIVE_TOOL_NAMES.has(entry.tool_id))
    .map(entry => ({
      entry,
      score: scoreAdapterEntry(entry, queryTokens, normalizedQuery),
    }))
    .filter(candidate => candidate.score > 0)
    .sort((a, b) => {
      if (b.score !== a.score) return b.score - a.score
      return a.entry.tool_id.localeCompare(b.entry.tool_id)
    }),
  )

  return pickDiverseAdapterToolNames(ranked, maxResults)
}

function pickDiverseAdapterToolNames(
  ranked: ScoredAdapterEntry[],
  maxResults: number,
): string[] {
  const selected: string[] = []
  const seen = new Set<string>()
  const add = (candidate: ScoredAdapterEntry): void => {
    if (selected.length >= maxResults || seen.has(candidate.entry.tool_id)) return
    selected.push(candidate.entry.tool_id)
    seen.add(candidate.entry.tool_id)
  }

  const locateCandidates = ranked.filter(candidate => candidate.entry.primitive === 'locate')
  const actionCandidates = ranked.filter(candidate => candidate.entry.primitive !== 'locate')

  if (actionCandidates.length > 0) {
    const locateBudget = Math.min(2, Math.max(1, maxResults - 1))
    for (const candidate of locateCandidates.slice(0, locateBudget)) add(candidate)
    for (const candidate of actionCandidates) add(candidate)
  } else {
    for (const candidate of ranked) add(candidate)
  }

  for (const candidate of ranked) add(candidate)
  return selected
}

function buildAdapterTool(entry: AdapterManifestEntry): Tool {
  const primitive = primitiveFor(entry)
  const primitiveTool = primitiveToolFor(primitive)
  const adapterInputSchema = inputSchemaFor(entry)
  const adapterInputJSONSchema = inputJSONSchemaFor(entry)

  return buildTool({
    name: entry.tool_id,
    // Keep concrete public-service adapters in CC's Tool object shape, but do
    // not inline every synced adapter schema into the first LLM request. The
    // ToolSearch path loads the few adapters relevant to the citizen request.
    shouldDefer: true,
    searchHint: [entry.search_hint, entry.name, entry.tool_id, primitive]
      .filter(Boolean)
      .join(' '),
    maxResultSizeChars: primitiveTool.maxResultSizeChars,
    inputJSONSchema: adapterInputJSONSchema,

    get inputSchema(): InputSchema {
      return adapterInputSchema
    },

    get outputSchema() {
      return primitiveTool.outputSchema
    },

    isEnabled() {
      return true
    },

    isConcurrencySafe(input) {
      return primitiveTool.isConcurrencySafe(rootInputFor(entry, input))
    },

    isReadOnly(input) {
      return primitiveTool.isReadOnly(rootInputFor(entry, input))
    },

    isDestructive(input) {
      return primitiveTool.isDestructive?.(rootInputFor(entry, input)) ?? false
    },

    async description() {
      return entry.name
    },

    async prompt() {
      const description = entry.llm_description?.trim() || `${entry.name}.`
      return [
        description,
        `Concrete UMMAYA ${primitive} adapter. Call this tool directly with the ` +
          'adapter schema arguments supplied by the backend manifest.',
      ].join('\n\n')
    },

    async validateInput(input, context) {
      const directPublicDataChoice = validateDirectPublicDataToolChoice(
        entry.tool_id,
        context,
        input,
      )
      if (directPublicDataChoice) return directPublicDataChoice
      const kmaAviationChoice = validateKmaAviationToolChoice(entry.tool_id, context)
      if (kmaAviationChoice) return kmaAviationChoice
      const kmaAnalysisChoice = validateKmaAnalysisToolChoice(entry.tool_id, context)
      if (kmaAnalysisChoice) return kmaAnalysisChoice
      const nmcAedChoice = validateNmcAedToolChoice(entry.tool_id, context)
      if (nmcAedChoice) return nmcAedChoice
      if (!resolveAdapter(entry.tool_id)) {
        return {
          result: false as const,
          message: `Adapter '${entry.tool_id}' is not in the synced backend manifest.`,
          errorCode: 1,
        }
      }
      if (typeof input !== 'object' || input === null) {
        return {
          result: false as const,
          message: `Adapter '${entry.tool_id}' expects a JSON object argument.`,
          errorCode: 1,
        }
      }
      const contractInput = validateAdapterContractInput(
        entry.tool_id,
        input as Record<string, unknown>,
      )
      if (contractInput) return contractInput
      return { result: true as const }
    },

    async call(input, context) {
      const normalizedInput = normalizeDirectPublicDataToolInput(
        entry.tool_id,
        context,
        input,
      )
      return dispatchPrimitive({
        primitive,
        toolName: entry.tool_id,
        args: normalizedInput,
        context,
        registry: getOrCreatePendingCallRegistry(),
        bridge: getOrCreateUmmayaBridge(),
      })
    },

    userFacingName(input) {
      return primitiveTool.userFacingName(rootInputFor(entry, input ?? {}))
    },

    mapToolResultToToolResultBlockParam(output, toolUseID) {
      return primitiveTool.mapToolResultToToolResultBlockParam(output, toolUseID)
    },

    renderToolUseMessage(input, options) {
      const rendered = primitiveTool.renderToolUseMessage(
        rootInputFor(entry, input),
        options,
      )
      return rendered === null ? entry.tool_id : rendered
    },

    renderToolResultMessage(output, progressMessagesForMessage, options) {
      return primitiveTool.renderToolResultMessage?.(
        output,
        progressMessagesForMessage,
        options,
      ) ?? null
    },

    isResultTruncated(output) {
      return primitiveTool.isResultTruncated?.(output) ?? false
    },
  } satisfies ToolDef<InputSchema>)
}
