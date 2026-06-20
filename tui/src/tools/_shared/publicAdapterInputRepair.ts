const MOJ_VILLAGE_LAWYER_TOOL_ID = 'moj_village_lawyer_lookup'

const KOREAN_SIDO_ALIASES: readonly [shortName: string, pattern: RegExp][] = [
  ['서울', /서울(?:특별시|시)?/u],
  ['부산', /부산(?:광역시|시)?/u],
  ['대구', /대구(?:광역시|시)?/u],
  ['인천', /인천(?:광역시|시)?/u],
  ['광주', /광주(?:광역시|시)?/u],
  ['대전', /대전(?:광역시|시)?/u],
  ['울산', /울산(?:광역시|시)?/u],
  ['세종', /세종(?:특별자치시|시)?/u],
  ['경기', /(?:경기(?:도)?|경기도)/u],
  ['강원', /(?:강원(?:특별자치도|도)?|강원도)/u],
  ['충북', /(?:충북(?:도)?|충청북도)/u],
  ['충남', /(?:충남(?:도)?|충청남도)/u],
  ['전북', /(?:전북(?:특별자치도|도)?|전라북도)/u],
  ['전남', /(?:전남(?:도)?|전라남도)/u],
  ['경북', /(?:경북(?:도)?|경상북도)/u],
  ['경남', /(?:경남(?:도)?|경상남도)/u],
  ['제주', /제주(?:특별자치도|도)?/u],
]

const KOREAN_CITY_OR_DISTRICT_RE = /([가-힣]{2,}(?:시|군|구))/u
const KOREAN_VILLAGE_RE = /([가-힣]{1,}(?:동|읍|면|리))/u

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function hasText(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0
}

function extractKoreanRegionForMojVillageLawyer(
  text: string,
): { state: string; city?: string; village?: string } | null {
  let selected:
    | { shortName: string; index: number; endIndex: number }
    | undefined

  for (const [shortName, pattern] of KOREAN_SIDO_ALIASES) {
    const match = pattern.exec(text)
    if (!match || match.index < 0) continue
    const endIndex = match.index + match[0].length
    if (!selected || match.index < selected.index) {
      selected = { shortName, index: match.index, endIndex }
    }
  }

  if (!selected) return null

  const afterState = text.slice(selected.endIndex)
  const city = KOREAN_CITY_OR_DISTRICT_RE.exec(afterState)?.[1]
  const afterCity = city ? afterState.slice(afterState.indexOf(city) + city.length) : ''
  const village = KOREAN_VILLAGE_RE.exec(afterCity)?.[1]

  return {
    state: selected.shortName,
    ...(city ? { city } : {}),
    ...(village ? { village } : {}),
  }
}

function mergeMissingMojRegionFields(
  target: Record<string, unknown>,
  region: { state: string; city?: string; village?: string },
): Record<string, unknown> | null {
  const updates: Record<string, string> = {}
  if (!hasText(target.state)) updates.state = region.state
  if (region.city && !hasText(target.city)) updates.city = region.city
  if (region.village && !hasText(target.village)) updates.village = region.village
  if (Object.keys(updates).length === 0) return null
  return { ...target, ...updates }
}

export function backfillMojVillageLawyerRegionInput(
  toolName: string,
  input: Record<string, unknown>,
  citizenText: string,
): Record<string, unknown> {
  const region = extractKoreanRegionForMojVillageLawyer(citizenText)
  if (!region) return input

  if (toolName === 'find' && input.tool_id === MOJ_VILLAGE_LAWYER_TOOL_ID) {
    const params = input.params
    if (params !== undefined && !isPlainRecord(params)) return input
    const merged = mergeMissingMojRegionFields(params ?? {}, region)
    return merged ? { ...input, params: merged } : input
  }

  if (toolName === MOJ_VILLAGE_LAWYER_TOOL_ID) {
    const merged = mergeMissingMojRegionFields(input, region)
    return merged ?? input
  }

  return input
}
