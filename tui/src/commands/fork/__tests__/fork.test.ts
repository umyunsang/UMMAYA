// SPDX-License-Identifier: Apache-2.0
// KOSMOS — /fork command surface tests.
//
// Verifies that:
//   1. /fork is a first-class command in the COMMANDS registry (not just an
//      alias gated by feature('FORK_SUBAGENT')).
//   2. /fork's load() target is the same module as /branch — they share the
//      session-fork JSONL-copy implementation.
//   3. /fork is discoverable via the UI L2 autocomplete catalog.
//   4. /branch keeps the legacy ['fork'] alias for belt-and-suspenders.
//
// Decision context: docs/decisions/fork-command-decision.md (2026-05-04).
import { describe, it, expect } from 'bun:test'
import fork from '../index.js'
import branch from '../../branch/index.js'
import {
  UI_L2_SLASH_COMMANDS,
  matchPrefix,
  findCatalogEntry,
} from '../../catalog.js'

describe('/fork command surface', () => {
  it('exposes a canonical "fork" command with the local-jsx type', () => {
    expect(fork.name).toBe('fork')
    expect(fork.type).toBe('local-jsx')
    expect(fork.description).toBeTruthy()
  })

  it('declares an argument hint matching /branch (both accept [name])', () => {
    expect(fork.argumentHint).toBe('[name]')
    expect(branch.argumentHint).toBe('[name]')
  })

  it('shares its handler module with /branch (zero implementation duplication)', async () => {
    // Both load() targets resolve to branch/branch.ts. We compare exported
    // function references rather than module identity (Bun module cache may
    // produce wrapped instances) — `call` is the local-jsx entry point.
    const forkModule = (await fork.load()) as { call: unknown }
    const branchModule = (await branch.load()) as { call: unknown }
    expect(typeof forkModule.call).toBe('function')
    expect(forkModule.call).toBe(branchModule.call)
  })

  it('keeps the historical ["fork"] alias on /branch (defense-in-depth)', () => {
    expect(branch.aliases).toEqual(['fork'])
  })

  it('appears in the UI L2 slash-command catalog under the session group', () => {
    const entry = findCatalogEntry('/fork')
    expect(entry).toBeDefined()
    expect(entry?.group).toBe('session')
    expect(entry?.hidden).toBe(false)
    expect(entry?.description_ko).toContain('분기')
  })

  it('is matched by the autocomplete prefix lookup for "/fo" and "/fork"', () => {
    const prefixMatches = matchPrefix('/fo').map((e) => e.name)
    expect(prefixMatches).toContain('/fork')
    const exactMatches = matchPrefix('/fork').map((e) => e.name)
    expect(exactMatches).toContain('/fork')
  })

  it('also surfaces the /branch alias and /resume / /continue siblings', () => {
    // The four session-lifecycle commands promised by
    // docs/requirements/kosmos-migration-tree.md § L1-A · A5.
    const names = UI_L2_SLASH_COMMANDS.map((e) => e.name)
    expect(names).toContain('/fork')
    expect(names).toContain('/branch')
    expect(names).toContain('/resume')
    expect(names).toContain('/continue')
  })
})
