// SPDX-License-Identifier: Apache-2.0
// Audit-5 P0-5 (2026-05-04) — citizen-side swarm-activation predicate wiring.
//
// Background:
//   The migration tree (`docs/requirements/kosmos-migration-tree.md § UI-D.2`)
//   commits to an "A + C union" trigger:
//     · Path A — the LLM's response mentions 3+ distinct ministries.
//     · Path C — the LLM tags its plan as "복잡" / "complex".
//   The pure predicate already lives at
//   `tui/src/schemas/ui-l2/agent.ts:shouldActivateSwarm`, but no caller
//   inspected assistant text to derive the predicate input. As a result the
//   `swarmActivated` i18n string was unreachable and `kosmosSwarmMode` was
//   set only via never-emitted backend signals.
//
// This module adds the missing analyzer:
//   `analyzeSwarmActivation(assistantText)` returns the predicate input
//   plus the boolean decision. REPL.tsx invokes it on every assistant
//   message and toasts the citizen via the existing UI-L2 i18n bundle when
//   the predicate flips from `false` to `true` for the current turn.
//
// Mention extraction is a closed-vocabulary scan against the canonical
// agency labels published in `docs/api/` (Spec 1637 catalog) plus the
// canonical Korean ministry display names. Free-text NLP is intentionally
// avoided — citizens see only the ministries we register adapters for, so
// any ministry substring not in the catalog is irrelevant to swarm-mode
// activation.

import { shouldActivateSwarm, type SwarmActivationInput } from '../schemas/ui-l2/agent.js'

// Closed vocabulary — pairs of (canonical label, recognition tokens).
// Tokens are case-insensitive substrings; multiple tokens map to one label
// so both Korean and English forms count as a single ministry mention.
//
// Mirrors the Spec 1637 `docs/api/` adapter catalog and
// `tui/src/state/subscriptionRegistry.ts MINISTRY_PREFIXES`. New agencies
// are added in both locations together.
const MINISTRY_VOCAB: ReadonlyArray<readonly [string, readonly string[]]> = [
  ['KMA', ['KMA', '기상청', '기상정보']],
  ['KOROAD', ['KOROAD', '도로교통공단', '교통공단']],
  ['HIRA', ['HIRA', '심평원', '건강보험심사평가원']],
  ['NMC', ['NMC', '국립중앙의료원', '응급의료']],
  ['MOHW', ['MOHW', '보건복지부', '복지부']],
  ['NFA119', ['NFA119', '소방청', '119']],
  ['NTS', ['NTS', '국세청', '홈택스']],
  ['NHIS', ['NHIS', '국민건강보험공단', '건강보험공단']],
  ['NPS', ['NPS', '국민연금공단']],
  ['CBS', ['CBS', '재난경보', '재난문자']],
  ['KBS', ['KBS', '한국방송공사']],
  ['MOLIT', ['MOLIT', '국토교통부']],
  ['MOIS', ['MOIS', '행정안전부', '정부24']],
  ['MOFA', ['MOFA', '외교부']],
]

// Korean / English markers that the LLM uses when self-tagging plan
// complexity. The `should activate swarm` predicate accepts only the
// canonical `'simple' | 'complex'` enum, so we collapse all matches to
// 'complex'.
const COMPLEX_MARKERS: readonly string[] = [
  '복잡',
  '복합',
  'complex',
  'multi-ministry',
  'multi-step plan',
  '여러 부처',
  '여러 기관',
]

export interface SwarmAnalyzerResult {
  /** Distinct canonical ministry labels detected in the text. */
  mentioned_ministries: readonly string[]
  /** Plan complexity tag derived from text markers. */
  complexity_tag: 'simple' | 'complex'
  /** Final decision from `shouldActivateSwarm` (A + C union per UI-D.2). */
  shouldActivate: boolean
  /** Trigger origin — useful for OTEL attribution / debug logs. */
  trigger: 'none' | 'three-plus-ministries' | 'complex-tag' | 'both'
}

/**
 * Inspect assistant response text for swarm-activation triggers.
 *
 * Pure function — never throws. On null / empty input returns the no-op
 * result (no activation, no mentions, simple). The mention scan walks the
 * closed `MINISTRY_VOCAB` and de-duplicates by canonical label so a
 * response that says "기상청 / KMA / 기상정보" still counts as one ministry.
 *
 * Used by REPL.tsx after each assistant turn to flip `kosmosSwarmMode`
 * and surface the i18n `swarmActivated` toast (Korean primary, English
 * fallback per UI-A.3).
 */
export function analyzeSwarmActivation(text: string | null | undefined): SwarmAnalyzerResult {
  if (text === null || text === undefined || text.length === 0) {
    return {
      mentioned_ministries: [],
      complexity_tag: 'simple',
      shouldActivate: false,
      trigger: 'none',
    }
  }
  const haystack = text.toLowerCase()

  // Ministry mentions — unique canonical labels.
  const mentioned: string[] = []
  for (const [label, tokens] of MINISTRY_VOCAB) {
    for (const token of tokens) {
      if (haystack.includes(token.toLowerCase())) {
        mentioned.push(label)
        break
      }
    }
  }

  // Complexity tag — first-match wins; canonical 'complex' otherwise simple.
  const complexity_tag: 'simple' | 'complex' = COMPLEX_MARKERS.some((marker) =>
    haystack.includes(marker.toLowerCase()),
  )
    ? 'complex'
    : 'simple'

  const input: SwarmActivationInput = {
    mentioned_ministries: mentioned,
    complexity_tag,
  }
  const shouldActivate = shouldActivateSwarm(input)

  // Trigger attribution: distinguish Path A vs Path C vs both — useful for
  // future OTEL spans (`kosmos.swarm.trigger=*`) and the migration-tree
  // audit ("which path actually fires in production").
  const distinctMinistryCount = new Set(mentioned).size
  let trigger: SwarmAnalyzerResult['trigger'] = 'none'
  if (shouldActivate) {
    const triggeredByA = distinctMinistryCount >= 3
    const triggeredByC = complexity_tag === 'complex'
    if (triggeredByA && triggeredByC) trigger = 'both'
    else if (triggeredByA) trigger = 'three-plus-ministries'
    else if (triggeredByC) trigger = 'complex-tag'
  }

  return {
    mentioned_ministries: mentioned,
    complexity_tag,
    shouldActivate,
    trigger,
  }
}
