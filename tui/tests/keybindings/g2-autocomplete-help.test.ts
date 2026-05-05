// SPDX-License-Identifier: Apache-2.0
// realuse-audit-2026-05-05 § G2 (PR #2773) — regression test for the missing
// Autocomplete + Help context blocks in DEFAULT_BINDING_BLOCKS. Closes
// F-alpha-04 (Esc not dismissing autocomplete dropdown), F-alpha-05 (Esc
// not dismissing /help overlay), F-delta-04 (same as F-alpha-05 in delta
// scenario), F-ε-05 (/agents Esc dismiss — fixed by side-effect of stopping
// Chat→draft-cancel from absorbing Esc when an overlay is mounted).
//
// Root cause: AGENTS.md infra-insight #4 — useKeybinding(action, handler)
// only fires when the chord registry has a default chord for that action.
// Brand-new actions (autocomplete:dismiss, help:dismiss) registered handlers
// but the chord registry never matched Esc to those actions because the
// chord blocks were missing from DEFAULT_BINDING_BLOCKS.
//
// The production runtime path is `resolveKeyWithChordState` (consumed by
// `KeybindingProviderSetup` line 252) which iterates `ParsedBinding[]`
// produced from `loadKeybindingsSyncWithWarnings` — that flow includes
// `DEFAULT_BINDING_BLOCKS`. The `resolve()` API used by `resolver.test.ts`
// goes through `buildRegistry()` which is Tier-1-only.

import { describe, expect, test } from 'bun:test'
import { resolveKeyWithChordState } from '../../src/keybindings/resolver'
import { loadKeybindingsSyncWithWarnings } from '../../src/keybindings/loadUserBindings'
import { DEFAULT_BINDING_BLOCKS } from '../../src/keybindings/defaultBindings'
import type { Key } from '../../src/ink'

function key(over: Partial<Key> = {}): Key {
  return {
    leftArrow: false,
    rightArrow: false,
    upArrow: false,
    downArrow: false,
    pageDown: false,
    pageUp: false,
    return: false,
    escape: false,
    ctrl: false,
    shift: false,
    tab: false,
    backspace: false,
    delete: false,
    meta: false,
    super: false,
    end: false,
    home: false,
    insert: false,
    f1: false,
    f2: false,
    f3: false,
    f4: false,
    f5: false,
    f6: false,
    f7: false,
    f8: false,
    f9: false,
    f10: false,
    f11: false,
    f12: false,
    ...over,
  } as Key
}

const PROD_BINDINGS = loadKeybindingsSyncWithWarnings().bindings

describe('G2 — Autocomplete context chords (F-alpha-04)', () => {
  test('Escape resolves to autocomplete:dismiss when Autocomplete in active list', () => {
    const result = resolveKeyWithChordState(
      '',
      key({ escape: true }),
      ['Autocomplete', 'Chat', 'Global'],
      PROD_BINDINGS,
      null,
    )
    // Last-match-wins under resolveKeyWithChordState — DEFAULT_BINDING_BLOCKS
    // is appended after the synthetic Tier-1 blocks, and within
    // DEFAULT_BINDING_BLOCKS Autocomplete is declared after Chat. So Esc
    // resolves to autocomplete:dismiss.
    expect(result.type).toBe('match')
    if (result.type !== 'match') throw new Error('unreachable')
    expect(result.action).toBe('autocomplete:dismiss')
  })

  test('Tab resolves to autocomplete:accept', () => {
    const result = resolveKeyWithChordState(
      '\t',
      key({ tab: true }),
      ['Autocomplete', 'Chat', 'Global'],
      PROD_BINDINGS,
      null,
    )
    expect(result.type).toBe('match')
    if (result.type !== 'match') throw new Error('unreachable')
    expect(result.action).toBe('autocomplete:accept')
  })

  test('Up/Down resolve to autocomplete:previous/next', () => {
    const upResult = resolveKeyWithChordState(
      '',
      key({ upArrow: true }),
      ['Autocomplete', 'Chat', 'Global'],
      PROD_BINDINGS,
      null,
    )
    const downResult = resolveKeyWithChordState(
      '',
      key({ downArrow: true }),
      ['Autocomplete', 'Chat', 'Global'],
      PROD_BINDINGS,
      null,
    )
    expect(upResult.type).toBe('match')
    expect(downResult.type).toBe('match')
    if (upResult.type !== 'match') throw new Error('unreachable')
    if (downResult.type !== 'match') throw new Error('unreachable')
    expect(upResult.action).toBe('autocomplete:previous')
    expect(downResult.action).toBe('autocomplete:next')
  })
})

describe('G2 — Help context chords (F-alpha-05, F-delta-04)', () => {
  test('Escape resolves to help:dismiss when Help in active list', () => {
    const result = resolveKeyWithChordState(
      '',
      key({ escape: true }),
      ['Help', 'Chat', 'Global'],
      PROD_BINDINGS,
      null,
    )
    expect(result.type).toBe('match')
    if (result.type !== 'match') throw new Error('unreachable')
    expect(result.action).toBe('help:dismiss')
  })

  test('Help context wins over Chat draft-cancel/chat:cancel when both active', () => {
    // Esc bound in three contexts at once: Chat(draft-cancel + chat:cancel)
    // and Help(help:dismiss). Last match wins → help:dismiss.
    const result = resolveKeyWithChordState(
      '',
      key({ escape: true }),
      ['Help', 'Chat', 'Global'],
      PROD_BINDINGS,
      null,
    )
    expect(result.type).toBe('match')
    if (result.type !== 'match') throw new Error('unreachable')
    expect(result.action).toBe('help:dismiss')
  })

  test('Without Help in active list, Esc still resolves to chat:cancel/draft-cancel', () => {
    // Sanity check: removing Help from the active list does NOT regress
    // the existing Chat-context Esc handler (draft-cancel via Tier 1
    // synthetic block + chat:cancel via DEFAULT_BINDING_BLOCKS). One of
    // those still wins so the input draft can still be cancelled.
    const result = resolveKeyWithChordState(
      '',
      key({ escape: true }),
      ['Chat', 'Global'],
      PROD_BINDINGS,
      null,
    )
    expect(result.type).toBe('match')
    if (result.type !== 'match') throw new Error('unreachable')
    expect(['draft-cancel', 'chat:cancel']).toContain(result.action)
  })
})

describe('G2 — DEFAULT_BINDING_BLOCKS catalogue invariants', () => {
  test('contains an Autocomplete context block', () => {
    const ctx = DEFAULT_BINDING_BLOCKS.find(
      (b) => b.context === 'Autocomplete',
    )
    expect(ctx).toBeDefined()
    expect(ctx!.bindings['escape']).toBe('autocomplete:dismiss')
    expect(ctx!.bindings['tab']).toBe('autocomplete:accept')
    expect(ctx!.bindings['up']).toBe('autocomplete:previous')
    expect(ctx!.bindings['down']).toBe('autocomplete:next')
  })

  test('contains a Help context block with escape→help:dismiss', () => {
    const ctx = DEFAULT_BINDING_BLOCKS.find((b) => b.context === 'Help')
    expect(ctx).toBeDefined()
    expect(ctx!.bindings['escape']).toBe('help:dismiss')
  })
})
