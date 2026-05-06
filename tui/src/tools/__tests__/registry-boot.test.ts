// SPDX-License-Identifier: Apache-2.0
// Epic γ #2294 · T020 — ToolRegistry boot guard tests.
//
// Covers 3 of the 4 cases from contracts/registry-boot-guard.md § Test plan:
//   Case 1: Full 5-primitive registry boot — ok === true, primitives = 5, durationMs ≤ 200.
//   Case 2: Synthetic registry with a primitive missing renderToolResultMessage — ok === false.
//   Case 3: Synthetic registry where one tool has isMcp: undefined — ok === false.
//   Case 4: Citation enforcement is inside validateInput (Spec 2294 R-3), NOT in the boot guard.
//           (Skipped per task spec — boot guard only does structural member presence.)
//
// Case 1 uses LookupPrimitive (real) + compliant synthetic stubs for the other
// four, demonstrating the same guard
// correctness as calling getAllBaseTools() would.

import { describe, test, expect } from 'bun:test'
import type { Tool } from '../../Tool.js'
import { LookupPrimitive } from '../LookupPrimitive/LookupPrimitive.js'
import { verifyBootRegistry } from '../../services/toolRegistry/bootGuard.js'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build a minimal fake primitive that satisfies the 9-member contract. */
function fakePrimitive(name: string, overrides: Partial<Record<string, unknown>> = {}): Tool {
  const base: Record<string, unknown> = {
    name,
    description: async () => `${name} description`,
    inputSchema: { _def: {} },
    isReadOnly: () => true,
    isMcp: false,
    validateInput: async () => ({ result: true }),
    call: async () => ({ data: {} }),
    renderToolUseMessage: () => null,
    renderToolResultMessage: () => null,
    // Extra non-contract fields (allowed — guard only checks required 9)
    isEnabled: () => true,
    searchHint: '',
  }
  return { ...base, ...overrides } as unknown as Tool
}

// ---------------------------------------------------------------------------
// Case 1: Full 5-primitive registry boot
// Uses LookupPrimitive (real) + synthetic stubs for ResolveLocation/Submit/Verify/Subscribe.
// ---------------------------------------------------------------------------

describe('verifyBootRegistry — full 5-primitive registry (Case 1)', () => {
  test('passes with ok === true, 5 primitives, durationMs ≤ 200', () => {
    const registry: readonly Tool[] = [
      LookupPrimitive,
      fakePrimitive('resolve_location'),
      fakePrimitive('submit'),
      fakePrimitive('verify'),
      fakePrimitive('subscribe'),
    ]
    const result = verifyBootRegistry(registry)

    expect(result.ok).toBe(true)
    if (!result.ok) return // narrow type

    expect(result.primitives).toBe(5)
    expect(result.entries).toBe(5)
    // SC-002: wall-clock budget on developer laptop
    expect(result.durationMs).toBeLessThanOrEqual(200)
  })
})

// ---------------------------------------------------------------------------
// Case 2: Synthetic registry — primitive missing renderToolResultMessage
// ---------------------------------------------------------------------------

describe('verifyBootRegistry — missing renderToolResultMessage (Case 2)', () => {
  test('returns ok === false, offendingTool = lookup, missingMembers contains renderToolResultMessage', () => {
    // Codex P2 fix moved the "all 5 reserved primitives present" check ahead
    // of the 9-member walk. The registry must contain all 5 primitive names
    // for the per-member walk to be reached.
    const brokenLookup = fakePrimitive('lookup', {
      renderToolResultMessage: undefined,
    })
    const registry: readonly Tool[] = [
      brokenLookup,
      fakePrimitive('resolve_location'),
      fakePrimitive('submit'),
      fakePrimitive('verify'),
      fakePrimitive('subscribe'),
    ]

    const result = verifyBootRegistry(registry)

    expect(result.ok).toBe(false)
    if (result.ok) return // narrow type

    expect(result.offendingTool).toBe('lookup')
    expect(result.missingMembers).toContain('renderToolResultMessage')

    // Diagnostic must name the tool, the 9-member contract, and Korean text
    expect(result.diagnostic).toContain('lookup')
    expect(result.diagnostic).toContain('9-member')
    expect(result.diagnostic).toContain('KOSMOS는 9-member ToolDef 계약을')
  })
})

// ---------------------------------------------------------------------------
// Case 3: Synthetic registry — isMcp === undefined (not a boolean)
// ---------------------------------------------------------------------------

describe('verifyBootRegistry — isMcp undefined (Case 3)', () => {
  test('returns ok === false, missingMembers contains isMcp', () => {
    const brokenSubmit = fakePrimitive('submit', {
      isMcp: undefined,
    })
    const registry: readonly Tool[] = [
      fakePrimitive('lookup'),
      fakePrimitive('resolve_location'),
      brokenSubmit,
      fakePrimitive('verify'),
      fakePrimitive('subscribe'),
    ]

    const result = verifyBootRegistry(registry)

    expect(result.ok).toBe(false)
    if (result.ok) return // narrow type

    expect(result.missingMembers).toContain('isMcp')
  })
})

// ---------------------------------------------------------------------------
// Case 4 (Codex P2): Reserved primitive set incomplete — fail closed.
// Without this guard, accidentally removing one primitive from registration
// would still produce ok:true with primitives < 5.
// ---------------------------------------------------------------------------

describe('verifyBootRegistry — missing reserved primitive (Case 4 / Codex P2)', () => {
  test('returns ok === false when subscribe is missing from registry', () => {
    const registry: readonly Tool[] = [
      fakePrimitive('lookup'),
      fakePrimitive('resolve_location'),
      fakePrimitive('submit'),
      fakePrimitive('verify'),
      // 'subscribe' deliberately omitted
    ]

    const result = verifyBootRegistry(registry)

    expect(result.ok).toBe(false)
    if (result.ok) return // narrow type

    expect(result.offendingTool).toBe('<reserved-primitive-set>')
    expect(result.missingMembers).toEqual(['subscribe'])
    expect(result.diagnostic).toContain('subscribe')
    expect(result.diagnostic).toContain('5-primitive')
  })

  test('returns ok === false when ALL primitives are missing (empty registry)', () => {
    const result = verifyBootRegistry([])

    expect(result.ok).toBe(false)
    if (result.ok) return // narrow type

    expect(result.offendingTool).toBe('<reserved-primitive-set>')
    // All five reserved names are missing.
    expect(result.missingMembers).toEqual([
      'lookup',
      'resolve_location',
      'submit',
      'verify',
      'subscribe',
    ])
  })
})
