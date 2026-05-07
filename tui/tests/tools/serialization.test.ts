// SPDX-License-Identifier: Apache-2.0
// KOSMOS-original — Epic #2077 K-EXAONE tool wiring · T006.
//
// Test coverage for tui/src/query/toolSerialization.ts.
// Seven invariants per contracts/tool-serialization.md § Test coverage.

import { describe, test, expect } from 'bun:test'
import { LookupPrimitive } from '../../src/tools/LookupPrimitive/LookupPrimitive.js'
import { ResolveLocationPrimitive } from '../../src/tools/ResolveLocationPrimitive/ResolveLocationPrimitive.js'
import { SubmitPrimitive } from '../../src/tools/SubmitPrimitive/SubmitPrimitive.js'
import {
  toolToFunctionSchema,
  getToolDefinitionsForFrame,
} from '../../src/query/toolSerialization.js'

// ---------------------------------------------------------------------------
// Test 1 — lookup-primitive emits Draft 2020-12 schema
// ---------------------------------------------------------------------------
describe('toolToFunctionSchema - LookupPrimitive', () => {
  test('lookup-primitive emits Draft 2020-12 schema (Spec 2521 fetch-only)', async () => {
    const def = await toolToFunctionSchema(LookupPrimitive)

    expect(def.function.name).toBe('lookup')
    expect(def.type).toBe('function')

    const params = def.function.parameters as Record<string, unknown>
    // zod/v4 toJSONSchema emits $schema for Draft 2020-12
    expect(params['$schema']).toBe('https://json-schema.org/draft/2020-12/schema')
    // Spec 2521 (2026-05-01): the LLM-visible lookup surface is a single
    // object {tool_id, params} — BM25 search is a backend-internal
    // mechanism, not a callable mode. The previous anyOf discriminated
    // union (search|fetch) collapsed to a flat object.
    expect(params['type']).toBe('object')
    const properties = params['properties'] as Record<string, unknown>
    expect(properties).toBeDefined()
    expect(properties['tool_id']).toBeDefined()
    expect(properties['params']).toBeDefined()
    const required = params['required'] as string[]
    expect(required).toContain('tool_id')
    expect(required).toContain('params')
    expect(properties['mode']).toBeUndefined()
  })
})

// ---------------------------------------------------------------------------
// Test 2 — submit-primitive .describe(...) strings are preserved
// ---------------------------------------------------------------------------
describe('toolToFunctionSchema - SubmitPrimitive', () => {
  test('submit-primitive .describe() strings preserved in JSON Schema descriptions', async () => {
    const def = await toolToFunctionSchema(SubmitPrimitive)

    const params = def.function.parameters as Record<string, unknown>
    const properties = params['properties'] as Record<string, { description?: string }> | undefined
    expect(properties).toBeDefined()

    // SubmitPrimitive.inputSchema has:
    //   tool_id: z.string().min(1).describe('Registered adapter identifier (obtain via lookup mode=search)')
    const toolIdProp = properties!['tool_id']
    expect(toolIdProp).toBeDefined()
    expect(toolIdProp.description).toContain('Registered adapter identifier')
  })
})

// ---------------------------------------------------------------------------
// Test 3 — optional fields excluded from required
// ---------------------------------------------------------------------------
describe('toolToFunctionSchema - LookupPrimitive required fields', () => {
  test('Spec 2521: tool_id and params are the only required keys; mode is gone', async () => {
    const def = await toolToFunctionSchema(LookupPrimitive)

    const params = def.function.parameters as Record<string, unknown>
    const required = params['required'] as string[]
    // Fetch-only surface — both tool_id and params required, no mode.
    expect(required).toEqual(expect.arrayContaining(['tool_id', 'params']))
    expect(required).not.toContain('mode')
    expect(required).not.toContain('query')
  })
})

// ---------------------------------------------------------------------------
// Test 4 — resolve_location emits the canonical geocoding schema
// ---------------------------------------------------------------------------
describe('toolToFunctionSchema - ResolveLocationPrimitive', () => {
  test('resolve_location emits query/want/near schema', async () => {
    const def = await toolToFunctionSchema(ResolveLocationPrimitive)

    expect(def.function.name).toBe('resolve_location')
    const params = def.function.parameters as Record<string, unknown>
    const properties = params['properties'] as Record<string, unknown>
    const required = params['required'] as string[]

    expect(properties['query']).toBeDefined()
    expect(properties['want']).toBeDefined()
    expect(properties['near']).toBeDefined()
    expect(required).toContain('query')
  })
})

// ---------------------------------------------------------------------------
// Test 5 — getToolDefinitionsForFrame returns exactly 4 active primitives
// ---------------------------------------------------------------------------
describe('getToolDefinitionsForFrame', () => {
  test('returns exactly 4 published primitive entries', async () => {
    const defs = await getToolDefinitionsForFrame()
    expect(defs.length).toBe(4)
  })

  test('includes the expected primitive tool names', async () => {
    const defs = await getToolDefinitionsForFrame()
    const names = new Set(defs.map(d => d.function.name))

    expect(names.has('lookup')).toBe(true)
    expect(names.has('resolve_location')).toBe(true)
    expect(names.has('submit')).toBe(true)
    expect(names.has('verify')).toBe(true)
    expect(names.has('subscribe')).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// Test 6 — output is alphabetically sorted by function.name
// ---------------------------------------------------------------------------
describe('getToolDefinitionsForFrame - alphabetical sort', () => {
  test('definitions are sorted alphabetically by function.name', async () => {
    const defs = await getToolDefinitionsForFrame()
    const names = defs.map(d => d.function.name)
    const sorted = [...names].sort((a, b) => a.localeCompare(b))
    expect(names).toEqual(sorted)
  })
})

// ---------------------------------------------------------------------------
// Test 7 — output excludes CC-developer tools (Read, Bash, Glob)
// ---------------------------------------------------------------------------
describe('getToolDefinitionsForFrame - exclusions', () => {
  test('excludes Read, Bash, Glob and other CC-developer tools', async () => {
    const defs = await getToolDefinitionsForFrame()
    const names = new Set(defs.map(d => d.function.name))

    const excluded = ['Read', 'Bash', 'Glob', 'Write', 'Edit', 'Grep', 'NotebookEdit']
    for (const name of excluded) {
      expect(names.has(name)).toBe(false)
    }
  })
})

// ---------------------------------------------------------------------------
// Test 8 — serialization is deterministic
// ---------------------------------------------------------------------------
describe('getToolDefinitionsForFrame - determinism', () => {
  test('two consecutive calls produce structurally equal output', async () => {
    const first = await getToolDefinitionsForFrame()
    const second = await getToolDefinitionsForFrame()

    expect(JSON.stringify(first)).toBe(JSON.stringify(second))
  })
})
