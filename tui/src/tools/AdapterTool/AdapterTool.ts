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
import { LookupPrimitive } from '../LookupPrimitive/LookupPrimitive.js'
import { ResolveLocationPrimitive } from '../ResolveLocationPrimitive/ResolveLocationPrimitive.js'
import { SubmitPrimitive } from '../SubmitPrimitive/SubmitPrimitive.js'
import { VerifyPrimitive } from '../VerifyPrimitive/VerifyPrimitive.js'

type AdapterPrimitive = 'find' | 'locate' | 'send' | 'check'

type InputSchema = z.ZodType<{ [key: string]: unknown }>

const ROOT_PRIMITIVE_TOOL_NAMES = new Set(['locate', 'find', 'check', 'send'])

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
    ]) {
      tokens.add(token)
    }
  }
  if (/(응급|응급실|er|emergency)/u.test(compact)) {
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
  if (/(aed|자동심장|심장충격|제세동)/u.test(compact)) {
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
  if (/(근처|주변|인근|가까운|역|터미널|공항|캠퍼스|대학교|대학|해수욕장|시장|공원|랜드마크|nearby|around)/u.test(compact)) {
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
  return score
}

export function selectTopKAdapterToolNamesForQuery(
  query: string,
  maxResults = 5,
): string[] {
  const normalizedQuery = query.trim()
  if (!normalizedQuery || maxResults <= 0) return []
  const queryTokens = expandedQueryTokens(normalizedQuery)
  const ranked = listAdapters()
    .filter(entry => !ROOT_PRIMITIVE_TOOL_NAMES.has(entry.tool_id))
    .map(entry => ({
      entry,
      score: scoreAdapterEntry(entry, queryTokens, normalizedQuery),
    }))
    .filter(candidate => candidate.score > 0)
    .sort((a, b) => {
      if (b.score !== a.score) return b.score - a.score
      return a.entry.tool_id.localeCompare(b.entry.tool_id)
    })

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

    async validateInput(input) {
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
      return { result: true as const }
    },

    async call(input, context) {
      return dispatchPrimitive({
        primitive,
        toolName: entry.tool_id,
        args: input,
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
