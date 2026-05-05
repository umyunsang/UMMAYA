// SPDX-License-Identifier: Apache-2.0
// Wave-2 G7 (audit specs/realuse-audit-2026-05-05) — regression guard for
// the slash-autocomplete prefix matcher. Closes F-alpha-03 (`/he` → /branch
// /fork /export), F-alpha-14 (`/fork` Enter dispatched /branch), F-delta-08
// (`/p` showed /export /help /config /branch /resume instead of /plugins).
// Layer 1b — bun:test, no PTY, no Ink rendering.
import { describe, it, expect } from 'bun:test'
import { generateCommandSuggestions } from '../../../utils/suggestions/commandSuggestions.js'
import { UI_L2_SLASH_COMMANDS, matchPrefix } from '../../../commands/catalog.js'
import type { Command } from '../../../commands.js'

function makeLocalCmd(name: string, description: string, aliases?: string[]): Command {
  return {
    type: 'local' as const,
    name,
    description,
    aliases,
    isHidden: false,
    inputSchema: {},
    userFacingName: () => name,
    call: async () => ({ type: 'result' as const, resultForAssistant: '' }),
  } as unknown as Command
}

// Production-shaped: /branch carries aliases: ['fork'] (tui/src/commands/branch/index.ts).
// Reproducing the alias relationship is essential — the bug surfaces because
// Fuse fuzzy-matches both `/fork` (exact name) AND `/branch` (exact alias),
// then a re-render shifts selectedSuggestion onto /branch.
const KOSMOS_CITIZEN_COMMANDS: Command[] = UI_L2_SLASH_COMMANDS
  .filter(e => !e.hidden)
  .map(e => {
    const raw = e.name.startsWith('/') ? e.name.slice(1) : e.name
    const aliases = raw === 'branch' ? ['fork'] : undefined
    return makeLocalCmd(raw, e.description_en, aliases)
  })

describe('G7 F-alpha-03 — /he must surface only prefix matches', () => {
  it('typing "/he" must yield only /help (no /branch /fork /export)', () => {
    const s = generateCommandSuggestions('/he', KOSMOS_CITIZEN_COMMANDS)
    const names = s.map(x => x.displayText)
    for (const bad of ['/branch', '/fork', '/export']) {
      expect(names).not.toContain(bad)
    }
    expect(names).toContain('/help')
  })
})

describe('G7 F-delta-08 — /p must surface only /plugins', () => {
  it('typing "/p" must NOT yield /export /help /config /branch /resume', () => {
    const s = generateCommandSuggestions('/p', KOSMOS_CITIZEN_COMMANDS)
    const names = s.map(x => x.displayText)
    for (const bad of ['/export', '/help', '/config', '/branch', '/resume']) {
      expect(names).not.toContain(bad)
    }
    expect(names).toContain('/plugins')
  })
})

describe('G7 F-alpha-14 — /fork Enter must execute /fork (not /branch)', () => {
  it('typing "/fork" — first suggestion must be /fork, /branch must NOT appear', () => {
    const s = generateCommandSuggestions('/fork', KOSMOS_CITIZEN_COMMANDS)
    expect(s[0]?.displayText).toBe('/fork')
    // Strict prefix means alias-only matches are excluded.
    const names = s.map(x => x.displayText)
    expect(names).not.toContain('/branch')
    expect(names).not.toContain('/branch (fork)')
  })
})

describe('G7 matchPrefix sanity (the catalog SSOT helper is correct)', () => {
  it('matchPrefix("/he") === [/help]', () => {
    expect(matchPrefix('/he').map(e => e.name)).toEqual(['/help'])
  })
  it('matchPrefix("/p") === [/plugins]', () => {
    expect(matchPrefix('/p').map(e => e.name)).toEqual(['/plugins'])
  })
  it('matchPrefix("/fork") starts with /fork', () => {
    expect(matchPrefix('/fork').map(e => e.name)[0]).toBe('/fork')
  })
})
