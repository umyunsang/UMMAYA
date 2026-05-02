// SPDX-License-Identifier: Apache-2.0
// Epic ε #2296 · T015 — LookupPrimitive.validateInput two-tier resolution tests.
//
// Covers (contracts/ipc-adapter-manifest-frame.md § 7):
//   Test 5: Cold-boot race — validateInput before manifest arrives.
//   Test 6: Tier-1 resolves backend adapter + citation populated.
//   Test 7: Tier-2 fallback — internal-tools path for WebFetch.
//   Test 8: AdapterNotFound — bogus tool_id fails with named error.

import { describe, test, expect, beforeEach } from 'bun:test'
import {
  ingestManifestFrame,
  clearManifestCache,
} from '../../src/services/api/adapterManifest'
import { LookupPrimitive } from '../../src/tools/LookupPrimitive/LookupPrimitive'
import type { AdapterManifestSyncFrame } from '../../src/ipc/frames.generated'
import type { ToolUseContext } from '../../src/Tool'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Minimal ToolUseContext stub for validateInput unit tests. */
function makeContext(internalToolNames: string[] = []): ToolUseContext {
  const tools = internalToolNames.map((name) => ({
    name,
    real_domain_policy: {
      real_classification_url: `https://example.gov.kr/${name}/policy`,
      policy_authority: `${name} Policy Authority`,
    },
  }))

  return {
    options: {
      commands: [],
      debug: false,
      mainLoopModel: 'test-model',
      tools: tools as unknown as ToolUseContext['options']['tools'],
      verbose: false,
      thinkingConfig: { type: 'disabled' } as ToolUseContext['options']['thinkingConfig'],
      mcpClients: [],
      mcpResources: {},
      isNonInteractiveSession: true,
      agentDefinitions: { definitions: [] } as unknown as ToolUseContext['options']['agentDefinitions'],
    },
    abortController: new AbortController(),
    readFileState: {} as ToolUseContext['readFileState'],
    getAppState: () => ({}) as unknown as ReturnType<ToolUseContext['getAppState']>,
    setAppState: () => {},
    setSharedAppState: () => {},
  } as ToolUseContext
}

function makeManifestFrame(
  entries: AdapterManifestSyncFrame['entries'],
): AdapterManifestSyncFrame {
  return {
    kind: 'adapter_manifest_sync',
    version: '1.0',
    session_id: 'test-session',
    correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9C1',
    ts: new Date().toISOString(),
    role: 'backend',
    frame_seq: 0,
    entries,
    manifest_hash: 'a'.repeat(64),
    emitter_pid: 12345,
  } satisfies AdapterManifestSyncFrame
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  clearManifestCache()
})

// ---------------------------------------------------------------------------
// Test 5 — Cold-boot race (FR-019)
// ---------------------------------------------------------------------------

describe('LookupPrimitive.validateInput: cold-boot race', () => {
  test('fails closed with manifest-not-synced message before any frame arrives', async () => {
    const ctx = makeContext()
    const result = await LookupPrimitive.validateInput(
      { tool_id: 'nmc_emergency_search', params: {} },
      ctx,
    )
    expect(result.result).toBe(false)
    const msg = (result as { message?: string }).message ?? ''
    expect(msg).toContain('manifest not yet synced')
  })

  // Spec 2521 (2026-05-01): the search-mode bypass test was deleted.
  // BM25 adapter discovery is now a backend-internal mechanism injected
  // into the system prompt's <available_adapters> dynamic suffix; it is
  // never a callable mode for the LLM, so there is no "search bypass"
  // path to validate here. Cold-boot semantics for the only remaining
  // mode (fetch) are covered by the manifest-not-yet-synced test above.
})

// ---------------------------------------------------------------------------
// Test 6 — Tier-1 resolves backend adapter (FR-017)
// ---------------------------------------------------------------------------

describe('LookupPrimitive.validateInput: tier-1 backend manifest resolution', () => {
  test('resolves nmc_emergency_search from synced manifest + populates citation', async () => {
    // Ingest a manifest containing nmc_emergency_search
    ingestManifestFrame(
      makeManifestFrame([
        {
          tool_id: 'nmc_emergency_search',
          name: 'NMC Emergency Bed Availability',
          primitive: 'lookup',
          policy_authority_url: 'https://www.e-gen.or.kr/nemc/main.do',
          source_mode: 'live',
        },
      ]),
    )

    const ctx = makeContext() // no internal tools with this name
    const result = await LookupPrimitive.validateInput(
      { tool_id: 'nmc_emergency_search', params: {} },
      ctx,
    )

    expect(result.result).toBe(true)
    // Citation must be populated from the manifest entry
    const citations = (ctx as { kosmosCitations?: { real_classification_url: string }[] }).kosmosCitations
    expect(citations).toBeDefined()
    expect(citations![0]?.real_classification_url).toBe('https://www.e-gen.or.kr/nemc/main.do')
  })
})

// ---------------------------------------------------------------------------
// Test 7 — Tier-2 fallback — internal tools (FR-018)
// ---------------------------------------------------------------------------

describe('LookupPrimitive.validateInput: tier-2 internal tools fallback', () => {
  test('WebFetch resolves via internal-tools path when absent from manifest', async () => {
    // Manifest with no WebFetch entry
    ingestManifestFrame(
      makeManifestFrame([
        {
          tool_id: 'nmc_emergency_search',
          name: 'NMC Emergency Bed Availability',
          primitive: 'lookup',
          policy_authority_url: 'https://www.e-gen.or.kr/nemc/main.do',
          source_mode: 'live',
        },
      ]),
    )

    // Internal tools list contains WebFetch
    const ctx = makeContext(['WebFetch'])
    const result = await LookupPrimitive.validateInput(
      { tool_id: 'WebFetch', params: {} },
      ctx,
    )

    expect(result.result).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// Test 8 — AdapterNotFound (FR-020)
// ---------------------------------------------------------------------------

describe('LookupPrimitive.validateInput: AdapterNotFound fail-closed', () => {
  test('bogus_tool_id fails with named error message', async () => {
    ingestManifestFrame(
      makeManifestFrame([
        {
          tool_id: 'nmc_emergency_search',
          name: 'NMC Emergency Bed Availability',
          primitive: 'lookup',
          policy_authority_url: 'https://www.e-gen.or.kr/nemc/main.do',
          source_mode: 'live',
        },
      ]),
    )

    const ctx = makeContext() // no internal tools
    const result = await LookupPrimitive.validateInput(
      { tool_id: 'bogus_tool_xyz', params: {} },
      ctx,
    )

    expect(result.result).toBe(false)
    const msg = (result as { message?: string }).message ?? ''
    expect(msg).toContain('AdapterNotFound')
    expect(msg).toContain('bogus_tool_xyz')
  })
})
