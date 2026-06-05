// SPDX-License-Identifier: Apache-2.0
// Epic γ #2294 · T020 — ToolRegistry boot guard tests.
//
// Covers 3 of the 4 cases from contracts/registry-boot-guard.md § Test plan:
//   Case 1: Full active-primitive registry boot — ok === true, primitives = 5, durationMs ≤ 200.
//   Case 2: Synthetic registry with a primitive missing renderToolResultMessage — ok === false.
//   Case 3: Synthetic registry where one tool has isMcp: undefined — ok === false.
//   Case 4: Citation enforcement is inside validateInput (Spec 2294 R-3), NOT in the boot guard.
//           (Skipped per task spec — boot guard only does structural member presence.)
//
// NOTE: SubmitPrimitive / VerifyPrimitive are authored in
// `.ts` files with JSX by sonnet-submit/verify teammates (T010-T018).
// Bun 1.3.x cannot parse JSX in `.ts` files without a global loader override.
// Case 1 therefore uses LookupPrimitive + ResolveLocationPrimitive +
// compliant synthetic stubs for the other two, demonstrating the same guard
// correctness as calling getAllBaseTools() would.

import { describe, test, expect } from 'bun:test'
import type { Tool } from '../../Tool.js'
import { LookupPrimitive } from '../LookupPrimitive/LookupPrimitive.js'
import { ResolveLocationPrimitive } from '../ResolveLocationPrimitive/ResolveLocationPrimitive.js'
import { verifyBootRegistry } from '../../services/toolRegistry/bootGuard.js'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build a minimal fake primitive that satisfies the 10-member contract. */
function fakePrimitive(name: string, overrides: Partial<Record<string, unknown>> = {}): Tool {
  const base: Record<string, unknown> = {
    name,
    description: async () => `${name} description`,
    inputSchema: { _def: {} },
    isReadOnly: () => true,
    isMcp: false,
    validateInput: async () => ({ result: true }),
    call: async () => ({ data: {} }),
    mapToolResultToToolResultBlockParam: (content: unknown, toolUseID: string) => ({
      type: 'tool_result',
      tool_use_id: toolUseID,
      content: JSON.stringify(content),
    }),
    renderToolUseMessage: () => null,
    renderToolResultMessage: () => null,
    // Extra non-contract fields (allowed — guard only checks required 10)
    isEnabled: () => true,
    searchHint: '',
  }
  return { ...base, ...overrides } as unknown as Tool
}

// ---------------------------------------------------------------------------
// Case 1: Full active-primitive registry boot
// Uses LookupPrimitive and ResolveLocationPrimitive (real) + synthetic stubs for Submit/Verify
// (those are authored with JSX in .ts files; Bun 1.3.x
// cannot load them without a loader override that breaks unrelated .ts files).
// ---------------------------------------------------------------------------

describe('verifyBootRegistry — full active-primitive registry (Case 1)', () => {
  test('passes with ok === true, 5 primitives, durationMs ≤ 200', () => {
    const registry: readonly Tool[] = [
      LookupPrimitive,
      ResolveLocationPrimitive,
      fakePrimitive('send'),
      fakePrimitive('check'),
      fakePrimitive('document'),
    ]
    const result = verifyBootRegistry(registry)

    expect(result.ok).toBe(true)
    if (!result.ok) return // narrow type

    expect(result.primitives).toBe(5)
    expect(result.entries).toBe(5)
    // SC-002: wall-clock budget on developer laptop
    expect(result.durationMs).toBeLessThanOrEqual(200)
  })

  test('real locate primitive maps successful output into a tool_result block', () => {
    const block = ResolveLocationPrimitive.mapToolResultToToolResultBlockParam(
      {
        ok: true,
        result: { kind: 'locate', address_name: 'Busan Saha-gu Dadae 1-dong' },
        outbound_traces: [{ should_not_reach_llm: true }],
      },
      'toolu-locate',
    )

    expect(block.type).toBe('tool_result')
    expect(block.tool_use_id).toBe('toolu-locate')
    expect(block.content).not.toContain('outbound_traces')
    expect(block.content).toContain('Busan Saha-gu Dadae 1-dong')
  })
})

// ---------------------------------------------------------------------------
// Case 2: Synthetic registry — primitive missing renderToolResultMessage
// ---------------------------------------------------------------------------

describe('verifyBootRegistry — missing renderToolResultMessage (Case 2)', () => {
  test('returns ok === false, offendingTool = lookup, missingMembers contains renderToolResultMessage', () => {
    // Codex P2 fix moved the "all active primitives present" check ahead
    // of the 9-member walk. The registry must contain all active primitive names
    // for the per-member walk to be reached.
    const brokenLookup = fakePrimitive('find', {
      renderToolResultMessage: undefined,
    })
    const registry: readonly Tool[] = [
      brokenLookup,
      fakePrimitive('locate'),
      fakePrimitive('send'),
      fakePrimitive('check'),
      fakePrimitive('document'),
    ]

    const result = verifyBootRegistry(registry)

    expect(result.ok).toBe(false)
    if (result.ok) return // narrow type

    expect(result.offendingTool).toBe('find')
    expect(result.missingMembers).toContain('renderToolResultMessage')

    // Diagnostic must name the tool, the ToolDef contract, and Korean text
    expect(result.diagnostic).toContain('find')
    expect(result.diagnostic).toContain('10-member')
    expect(result.diagnostic).toContain('UMMAYA는 10-member ToolDef 계약을')
  })
})

// ---------------------------------------------------------------------------
// Case 2b: Synthetic registry — primitive missing result mapper
// ---------------------------------------------------------------------------

describe('verifyBootRegistry — missing mapToolResultToToolResultBlockParam', () => {
  test('returns ok === false before runtime tool execution can crash', () => {
    const brokenLocate = fakePrimitive('locate', {
      mapToolResultToToolResultBlockParam: undefined,
    })
    const registry: readonly Tool[] = [
      fakePrimitive('find'),
      brokenLocate,
      fakePrimitive('send'),
      fakePrimitive('check'),
      fakePrimitive('document'),
    ]

    const result = verifyBootRegistry(registry)

    expect(result.ok).toBe(false)
    if (result.ok) return

    expect(result.offendingTool).toBe('locate')
    expect(result.missingMembers).toContain('mapToolResultToToolResultBlockParam')
  })
})

// ---------------------------------------------------------------------------
// Case 3: Synthetic registry — isMcp === undefined (not a boolean)
// ---------------------------------------------------------------------------

describe('verifyBootRegistry — isMcp undefined (Case 3)', () => {
  test('returns ok === false, missingMembers contains isMcp', () => {
    const brokenSubmit = fakePrimitive('send', {
      isMcp: undefined,
    })
    const registry: readonly Tool[] = [
      fakePrimitive('find'),
      fakePrimitive('locate'),
      brokenSubmit,
      fakePrimitive('check'),
      fakePrimitive('document'),
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
// would still produce ok:true with primitives < 4.
// ---------------------------------------------------------------------------

describe('verifyBootRegistry — missing reserved primitive (Case 4 / Codex P2)', () => {
  test('returns ok === false when verify is missing from registry', () => {
    const registry: readonly Tool[] = [
      fakePrimitive('find'),
      fakePrimitive('locate'),
      fakePrimitive('send'),
      fakePrimitive('document'),
      // 'check' deliberately omitted
    ]

    const result = verifyBootRegistry(registry)

    expect(result.ok).toBe(false)
    if (result.ok) return // narrow type

    expect(result.offendingTool).toBe('<reserved-primitive-set>')
    expect(result.missingMembers).toEqual(['check'])
    expect(result.diagnostic).toContain('check')
    expect(result.diagnostic).toContain('활성 primitive')
  })

  test('returns ok === false when ALL primitives are missing (empty registry)', () => {
    const result = verifyBootRegistry([])

    expect(result.ok).toBe(false)
    if (result.ok) return // narrow type

    expect(result.offendingTool).toBe('<reserved-primitive-set>')
    // All active reserved names are missing.
    expect(result.missingMembers).toEqual([
      'find',
      'locate',
      'send',
      'check',
      'document',
    ])
  })
})
