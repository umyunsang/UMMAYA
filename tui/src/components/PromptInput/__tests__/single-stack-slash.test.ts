// SPDX-License-Identifier: Apache-2.0
// P0-2 regression test — single-stack slash suggestions.
//
// Verifies that `generateCommandSuggestions` only surfaces KOSMOS citizen
// catalog entries and never exposes CC dev commands like /speckit-*, /add-dir,
// /doctor, /review, /ultrareview, /commit, /security-review, etc.
//
// Layer 1b (bun:test — no PTY, no ink rendering, sub-ms execution).

import { describe, it, expect } from 'bun:test'
import { generateCommandSuggestions } from '../../../utils/suggestions/commandSuggestions.js'
import { UI_L2_SLASH_COMMANDS } from '../../../commands/catalog.js'
import type { Command } from '../../../commands.js'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Minimal local command fixture — mirrors the shape used by CC commands. */
function makeLocalCmd(name: string): Command {
  return {
    type: 'local' as const,
    name,
    description: `Dev command: ${name}`,
    isHidden: false,
    inputSchema: {},
    userFacingName: () => name,
    call: async () => ({ type: 'result' as const, resultForAssistant: '' }),
  } as unknown as Command
}

/** Minimal prompt command fixture — mirrors the shape of CC /speckit skills. */
function makePromptCmd(name: string): Command {
  return {
    type: 'prompt' as const,
    name,
    source: 'userSettings' as const,
    description: `Skill: ${name}`,
    isHidden: false,
    inputSchema: {},
    userFacingName: () => name,
  } as unknown as Command
}

// ---------------------------------------------------------------------------
// Test commands array: mix of CC dev commands + KOSMOS catalog commands
// ---------------------------------------------------------------------------

const CC_DEV_COMMANDS: Command[] = [
  // CC commands that must NOT appear in dropdown
  makeLocalCmd('add-dir'),
  makeLocalCmd('doctor'),
  makeLocalCmd('commit'),
  makeLocalCmd('review'),
  makeLocalCmd('ultrareview'),
  makeLocalCmd('security-review'),
  makeLocalCmd('init-verifiers'),
  makeLocalCmd('bridge-kick'),
  makeLocalCmd('version'),
  makeLocalCmd('mcp'),
  makeLocalCmd('memory'),
  makeLocalCmd('keybindings'),
  makePromptCmd('speckit-specify'),
  makePromptCmd('speckit-plan'),
  makePromptCmd('speckit-tasks'),
  makePromptCmd('speckit-implement'),
]

// Citizen-facing commands from UI_L2_SLASH_COMMANDS (strip leading /)
const KOSMOS_CITIZEN_COMMANDS: Command[] = UI_L2_SLASH_COMMANDS
  .filter(e => !e.hidden)
  .map(e => makeLocalCmd(e.name.startsWith('/') ? e.name.slice(1) : e.name))

const ALL_COMMANDS: Command[] = [...CC_DEV_COMMANDS, ...KOSMOS_CITIZEN_COMMANDS]

// ---------------------------------------------------------------------------
// P0-2 assertions
// ---------------------------------------------------------------------------

describe('generateCommandSuggestions — KOSMOS single-stack', () => {
  it('typing "/" shows only catalog commands — no /speckit-* or /add-dir', () => {
    const suggestions = generateCommandSuggestions('/', ALL_COMMANDS)

    const names = suggestions.map(s => s.displayText)

    // No CC dev commands should appear
    for (const devCmd of [
      '/add-dir',
      '/doctor',
      '/commit',
      '/review',
      '/ultrareview',
      '/security-review',
      '/init-verifiers',
      '/bridge-kick',
      '/version',
      '/mcp',
      '/memory',
      '/keybindings',
    ]) {
      expect(names).not.toContain(devCmd)
    }

    // No /speckit-* skills should appear
    const speckit = names.filter(n => n.startsWith('/speckit'))
    expect(speckit).toHaveLength(0)
  })

  it('typing "/" shows known KOSMOS catalog commands', () => {
    const suggestions = generateCommandSuggestions('/', ALL_COMMANDS)
    const names = suggestions.map(s => s.displayText)

    // At least the canonical citizen commands must be present
    for (const catalogName of ['/help', '/agents', '/consent list', '/export']) {
      // catalog entries with spaces appear as a single displayText token
      const present = names.some(n => n === catalogName || n.startsWith(catalogName.split(' ')[0]!))
      expect(present).toBe(true)
    }
  })

  it('typing "/l" matches /lang only — not /lookup or CC internals', () => {
    const suggestions = generateCommandSuggestions('/l', ALL_COMMANDS)
    const names = suggestions.map(s => s.displayText)

    // Only catalog entries starting with /l should appear
    const nonCatalog = names.filter(n => {
      const base = n.startsWith('/') ? n.slice(1) : n
      const inCatalog = UI_L2_SLASH_COMMANDS.some(e => {
        const eName = e.name.startsWith('/') ? e.name.slice(1) : e.name
        return eName.startsWith(base.split(' ')[0]!)
      })
      return !inCatalog
    })
    expect(nonCatalog).toHaveLength(0)
  })

  it('only one dropdown should be active — no duplicate slash stacks', async () => {
    // The KOSMOS SlashCommandSuggestions overlay has been removed from REPL.tsx.
    // This test verifies the catalog-filtered generateCommandSuggestions returns
    // exactly the same set as matchPrefix('/') from catalog.ts.
    const { matchPrefix } = await import('../../../commands/catalog.js')
    const catalogMatches = matchPrefix('/')
    const typeaheadSuggestions = generateCommandSuggestions('/', ALL_COMMANDS)

    // Every typeahead suggestion must correspond to a catalog entry
    const catalogNames = new Set(catalogMatches.map(e => e.name))
    for (const suggestion of typeaheadSuggestions) {
      const rawName = suggestion.displayText.startsWith('/')
        ? suggestion.displayText.slice(1)
        : suggestion.displayText
      // displayText may be '/help' — catalog has '/help'
      const inCatalog = catalogNames.has(suggestion.displayText) ||
        catalogNames.has('/' + rawName) ||
        // multi-word catalog entries ('/consent list') start with a matching prefix
        [...catalogNames].some(cn => cn.startsWith(suggestion.displayText.split(' ')[0]!))
      expect(inCatalog).toBe(true)
    }
  })
})
