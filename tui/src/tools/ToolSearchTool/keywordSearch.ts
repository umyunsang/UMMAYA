import { findToolByName, type Tool, type Tools } from '../../Tool.js'
import { escapeRegExp } from '../../utils/stringUtils.js'
import { getToolDescriptionMemoized } from './descriptionCache.js'
import {
  expandedIntentTermSet,
  expandedToolSearchTerms,
} from './supportIntentHints.js'

type ParsedToolName = {
  readonly parts: readonly string[]
  readonly full: string
  readonly isMcp: boolean
}

type ScoredTool = {
  readonly name: string
  readonly score: number
}

function parseToolName(name: string): ParsedToolName {
  if (name.startsWith('mcp__')) {
    const withoutPrefix = name.replace(/^mcp__/, '').toLowerCase()
    const parts = withoutPrefix.split('__').flatMap(part => part.split('_'))
    return {
      parts: parts.filter(Boolean),
      full: withoutPrefix.replace(/__/g, ' ').replace(/_/g, ' '),
      isMcp: true,
    }
  }

  const parts = name
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/_/g, ' ')
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)

  return {
    parts,
    full: parts.join(' '),
    isMcp: false,
  }
}

function compileTermPatterns(terms: readonly string[]): Map<string, RegExp> {
  const patterns = new Map<string, RegExp>()
  for (const term of terms) {
    if (!patterns.has(term)) {
      patterns.set(term, new RegExp(`\\b${escapeRegExp(term)}\\b`))
    }
  }
  return patterns
}

function getTermPattern(
  patterns: ReadonlyMap<string, RegExp>,
  term: string,
): RegExp {
  return patterns.get(term) ?? new RegExp(`\\b${escapeRegExp(term)}\\b`)
}

function splitQueryTerms(queryLower: string): {
  readonly requiredTerms: readonly string[]
  readonly optionalTerms: readonly string[]
  readonly queryTerms: readonly string[]
} {
  const queryTerms = expandedToolSearchTerms(queryLower)
  const requiredTerms: string[] = []
  const optionalTerms: string[] = []
  for (const term of queryTerms) {
    if (term.startsWith('+') && term.length > 1) {
      requiredTerms.push(term.slice(1))
    } else {
      optionalTerms.push(term)
    }
  }
  return { requiredTerms, optionalTerms, queryTerms }
}

function requiredTermMatches({
  parsed,
  descNormalized,
  hintNormalized,
  expandedTerms,
  termPatterns,
  term,
}: {
  readonly parsed: ParsedToolName
  readonly descNormalized: string
  readonly hintNormalized: string
  readonly expandedTerms: ReadonlySet<string>
  readonly termPatterns: ReadonlyMap<string, RegExp>
  readonly term: string
}): boolean {
  const pattern = getTermPattern(termPatterns, term)
  const canUsePromptBody = !expandedTerms.has(term)
  return (
    parsed.parts.includes(term) ||
    parsed.parts.some(part => part.includes(term)) ||
    (canUsePromptBody && pattern.test(descNormalized)) ||
    (hintNormalized.length > 0 && pattern.test(hintNormalized))
  )
}

async function filterRequiredTermMatches(
  deferredTools: Tools,
  tools: Tools,
  requiredTerms: readonly string[],
  expandedTerms: ReadonlySet<string>,
  termPatterns: ReadonlyMap<string, RegExp>,
): Promise<Tools> {
  if (requiredTerms.length === 0) return deferredTools
  const matches = await Promise.all(
    deferredTools.map(async tool => {
      const parsed = parseToolName(tool.name)
      const description = await getToolDescriptionMemoized(tool.name, tools)
      const descNormalized = description.toLowerCase()
      const hintNormalized = tool.searchHint?.toLowerCase() ?? ''
      const matchesAll = requiredTerms.every(term =>
        requiredTermMatches({
          parsed,
          descNormalized,
          hintNormalized,
          expandedTerms,
          termPatterns,
          term,
        }),
      )
      return matchesAll ? tool : null
    }),
  )
  return matches.filter((tool): tool is Tool => tool !== null)
}

async function scoreTool(
  tool: Tool,
  tools: Tools,
  allScoringTerms: readonly string[],
  expandedTerms: ReadonlySet<string>,
  termPatterns: ReadonlyMap<string, RegExp>,
): Promise<ScoredTool> {
  const parsed = parseToolName(tool.name)
  const description = await getToolDescriptionMemoized(tool.name, tools)
  const descNormalized = description.toLowerCase()
  const hintNormalized = tool.searchHint?.toLowerCase() ?? ''
  let score = 0

  for (const term of allScoringTerms) {
    const pattern = getTermPattern(termPatterns, term)
    if (parsed.parts.includes(term)) {
      score += parsed.isMcp ? 12 : 10
    } else if (parsed.parts.some(part => part.includes(term))) {
      score += parsed.isMcp ? 6 : 5
    }
    if (parsed.full.includes(term) && score === 0) {
      score += 3
    }
    if (hintNormalized.length > 0 && pattern.test(hintNormalized)) {
      score += 4
    }
    if (!expandedTerms.has(term) && pattern.test(descNormalized)) {
      score += 2
    }
  }

  return { name: tool.name, score }
}

export async function searchToolsWithKeywords(
  query: string,
  deferredTools: Tools,
  tools: Tools,
  maxResults: number,
): Promise<string[]> {
  const queryLower = query.toLowerCase().trim()
  const exactMatch =
    deferredTools.find(tool => tool.name.toLowerCase() === queryLower) ??
    findToolByName(tools, queryLower)
  if (exactMatch) {
    return [exactMatch.name]
  }

  if (queryLower.startsWith('mcp__') && queryLower.length > 5) {
    const prefixMatches = deferredTools
      .filter(tool => tool.name.toLowerCase().startsWith(queryLower))
      .slice(0, maxResults)
      .map(tool => tool.name)
    if (prefixMatches.length > 0) {
      return prefixMatches
    }
  }

  const { requiredTerms, optionalTerms, queryTerms } = splitQueryTerms(queryLower)
  const allScoringTerms =
    requiredTerms.length > 0 ? [...requiredTerms, ...optionalTerms] : queryTerms
  const expandedTerms = expandedIntentTermSet(queryLower)
  const termPatterns = compileTermPatterns(allScoringTerms)
  const candidateTools = await filterRequiredTermMatches(
    deferredTools,
    tools,
    requiredTerms,
    expandedTerms,
    termPatterns,
  )
  const scored = await Promise.all(
    candidateTools.map(tool =>
      scoreTool(tool, tools, allScoringTerms, expandedTerms, termPatterns),
    ),
  )

  return scored
    .filter(item => item.score > 0)
    .sort((left, right) => right.score - left.score)
    .slice(0, maxResults)
    .map(item => item.name)
}
