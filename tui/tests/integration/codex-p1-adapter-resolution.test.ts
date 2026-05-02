// SPDX-License-Identifier: Apache-2.0
// Epic ε #2296 · T033 — US2 integration: Codex P1 adapter resolution end-to-end.
//
// Covers SC-006 (nmc_emergency_search reaches validateInput successfully after
// manifest sync) and all 4 US2 acceptance scenarios:
//
//   Scenario 1: nmc_emergency_search resolves through synced manifest.
//   Scenario 2: WebFetch resolves through internal-tools fallback.
//   Scenario 3: Cache replaces on second frame (FR-016 replace-not-merge).
//   Scenario 4: Bogus tool_id fails with named AdapterNotFound.
//
// This is the *integration* complement to the unit tests in T015
// (adapterManifest.test.ts + primitive/lookup-validation-fallback.test.ts +
//  primitive/submit-citation-from-manifest.test.ts).  Integration means we
// simulate the full IPC frame ingestion path: a synthetic "backend" writes an
// AdapterManifestSyncFrame, the frame router calls ingestManifestFrame(), and
// then validateInput() is exercised against the populated cache.
//
// References:
//   specs/2296-ax-mock-adapters/contracts/ipc-adapter-manifest-frame.md § 5.2-5.3
//   specs/2296-ax-mock-adapters/tasks.md T033

import { describe, test, expect, beforeEach } from 'bun:test'
import {
  ingestManifestFrame,
  resolveAdapter,
  isManifestSynced,
  clearManifestCache,
} from '../../src/services/api/adapterManifest'
import { LookupPrimitive } from '../../src/tools/LookupPrimitive/LookupPrimitive'
import type { AdapterManifestSyncFrame } from '../../src/ipc/frames.generated'
import type { ToolUseContext } from '../../src/Tool'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build a minimal ToolUseContext stub for validateInput tests. */
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

/**
 * Build a synthetic AdapterManifestSyncFrame mimicking a real backend emission.
 * Represents the frame that kosmos.ipc.adapter_manifest_emitter.emit_manifest()
 * would write to stdout when the Mock backend boots.
 */
function makeBackendManifestFrame(
  entries: AdapterManifestSyncFrame['entries'],
): AdapterManifestSyncFrame {
  return {
    kind: 'adapter_manifest_sync',
    version: '1.0',
    session_id: 'integration-test-session',
    correlation_id: 'int-corr-' + Math.random().toString(36).slice(2, 10),
    ts: new Date().toISOString(),
    role: 'backend',
    frame_seq: 0,
    entries,
    manifest_hash: 'a'.repeat(64), // synthetic hash — structural validation only
    emitter_pid: 99999,
  } satisfies AdapterManifestSyncFrame
}

/** Simulate IPC frame router processing the frame (mirrors T010 wiring). */
function simulateIpcFrameIngestion(frame: AdapterManifestSyncFrame): void {
  // T010 wires this: when frame.kind === 'adapter_manifest_sync', call ingestManifestFrame.
  if (frame.kind === 'adapter_manifest_sync') {
    ingestManifestFrame(frame)
  }
}

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  clearManifestCache()
})

// ---------------------------------------------------------------------------
// Scenario 1 — nmc_emergency_search resolves through synced manifest (SC-006)
// ---------------------------------------------------------------------------

describe('US2 Scenario 1: nmc_emergency_search resolves through synced manifest', () => {
  test('validates successfully after backend emits manifest containing nmc_emergency_search', async () => {
    // Pre-condition: manifest not yet synced.
    expect(isManifestSynced()).toBe(false)

    // Simulate backend boot: emit_manifest() writes this frame; TUI IPC router
    // calls ingestManifestFrame().
    const backendFrame = makeBackendManifestFrame([
      {
        tool_id: 'nmc_emergency_search',
        name: 'NMC Emergency Bed Availability (Live)',
        primitive: 'lookup',
        policy_authority_url: 'https://www.e-gen.or.kr/nemc/main.do',
        source_mode: 'live',
      },
      {
        tool_id: 'resolve_location',
        name: 'Resolve Location',
        primitive: 'resolve_location',
        policy_authority_url: undefined,
        source_mode: 'internal',
      },
    ])

    simulateIpcFrameIngestion(backendFrame)

    // Post-condition: manifest synced.
    expect(isManifestSynced()).toBe(true)

    // The adapter must be resolvable.
    const entry = resolveAdapter('nmc_emergency_search')
    expect(entry).toBeDefined()
    expect(entry!.tool_id).toBe('nmc_emergency_search')
    expect(entry!.policy_authority_url).toBe('https://www.e-gen.or.kr/nemc/main.do')
    expect(entry!.source_mode).toBe('live')

    // LookupPrimitive.validateInput must resolve nmc_emergency_search (Tier 1 path).
    const ctx = makeContext() // no internal tools with this name
    const result = await LookupPrimitive.validateInput(
      { tool_id: 'nmc_emergency_search', params: {} },
      ctx,
    )
    expect(result.result).toBe(true)

    // Citation slot must be populated from the manifest entry (FR-018).
    const citations = (ctx as { kosmosCitations?: { real_classification_url: string }[] }).kosmosCitations
    expect(citations).toBeDefined()
    expect(citations!.length).toBeGreaterThan(0)
    expect(citations![0]?.real_classification_url).toBe('https://www.e-gen.or.kr/nemc/main.do')
  })
})

// ---------------------------------------------------------------------------
// Scenario 2 — WebFetch resolves through internal-tools fallback (FR-018)
// ---------------------------------------------------------------------------

describe('US2 Scenario 2: WebFetch resolves through internal-tools fallback', () => {
  test('WebFetch absent from manifest but present in internal tools → resolves via Tier 2', async () => {
    // Manifest does NOT contain WebFetch — only backend adapters.
    const backendFrame = makeBackendManifestFrame([
      {
        tool_id: 'nmc_emergency_search',
        name: 'NMC Emergency Bed Availability (Live)',
        primitive: 'lookup',
        policy_authority_url: 'https://www.e-gen.or.kr/nemc/main.do',
        source_mode: 'live',
      },
    ])
    simulateIpcFrameIngestion(backendFrame)
    expect(isManifestSynced()).toBe(true)

    // Tier 1: WebFetch NOT in manifest.
    expect(resolveAdapter('WebFetch')).toBeUndefined()

    // Tier 2: context.options.tools contains WebFetch (internal tool).
    const ctx = makeContext(['WebFetch'])
    const result = await LookupPrimitive.validateInput(
      { tool_id: 'WebFetch', params: {} },
      ctx,
    )

    // Must succeed via Tier 2 fallback (FR-018).
    expect(result.result).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// Scenario 3 — Cache replaces on second frame (FR-016)
// ---------------------------------------------------------------------------

describe('US2 Scenario 3: cache replaces on second frame (FR-016)', () => {
  test('second manifest frame wholly replaces first — old entries evicted, new entries present', async () => {
    // First frame: contains nmc_emergency_search.
    const frame1 = makeBackendManifestFrame([
      {
        tool_id: 'nmc_emergency_search',
        name: 'NMC Emergency Bed Availability (Live)',
        primitive: 'lookup',
        policy_authority_url: 'https://www.e-gen.or.kr/nemc/main.do',
        source_mode: 'live',
      },
    ])
    simulateIpcFrameIngestion(frame1)
    expect(resolveAdapter('nmc_emergency_search')).toBeDefined()

    // Second frame: different backend pid, different entries — kma_forecast_fetch only.
    const frame2 = makeBackendManifestFrame([
      {
        tool_id: 'kma_forecast_fetch',
        name: 'KMA Short-Term Forecast (Live)',
        primitive: 'lookup',
        policy_authority_url: 'https://www.data.go.kr/data/15059093/openapi.do',
        source_mode: 'live',
      },
    ])
    simulateIpcFrameIngestion(frame2)

    // Old entry must be GONE (not merged — FR-016).
    expect(resolveAdapter('nmc_emergency_search')).toBeUndefined()

    // New entry must be present.
    const kmaEntry = resolveAdapter('kma_forecast_fetch')
    expect(kmaEntry).toBeDefined()
    expect(kmaEntry!.tool_id).toBe('kma_forecast_fetch')
    expect(kmaEntry!.policy_authority_url).toContain('data.go.kr')

    // Manifest is still synced after replacement.
    expect(isManifestSynced()).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// Scenario 4 — Bogus tool_id fails with named AdapterNotFound (FR-020)
// ---------------------------------------------------------------------------

describe('US2 Scenario 4: bogus tool_id fails with named AdapterNotFound', () => {
  test('unknown tool_id after manifest sync fails with AdapterNotFound containing tool_id', async () => {
    const backendFrame = makeBackendManifestFrame([
      {
        tool_id: 'nmc_emergency_search',
        name: 'NMC Emergency Bed Availability (Live)',
        primitive: 'lookup',
        policy_authority_url: 'https://www.e-gen.or.kr/nemc/main.do',
        source_mode: 'live',
      },
    ])
    simulateIpcFrameIngestion(backendFrame)
    expect(isManifestSynced()).toBe(true)

    // The bogus tool_id is not in the manifest and not in internal tools.
    const ctx = makeContext() // empty internal tools
    const BOGUS_ID = 'totally_bogus_nonexistent_adapter_xyz'

    const result = await LookupPrimitive.validateInput(
      { tool_id: BOGUS_ID, params: {} },
      ctx,
    )

    // Must fail (fail-closed, FR-020).
    expect(result.result).toBe(false)

    // Error message must name the missing adapter (named AdapterNotFound).
    const msg = (result as { message?: string }).message ?? ''
    expect(msg).toContain('AdapterNotFound')
    expect(msg).toContain(BOGUS_ID)
  })

  test('tool_id in manifest but wrong primitive still resolves (manifest is source of truth)', async () => {
    // The manifest is the authoritative source — if an entry is present, it resolves.
    const backendFrame = makeBackendManifestFrame([
      {
        tool_id: 'mock_submit_module_hometax_taxreturn',
        name: 'Mock Hometax Submit',
        primitive: 'submit', // NOTE: this is a submit primitive, not lookup
        policy_authority_url: 'https://www.nts.go.kr/nts/cm/cntnts/cntntsView.do?mi=12892&cntntsId=8104',
        source_mode: 'mock',
      },
    ])
    simulateIpcFrameIngestion(backendFrame)

    // The entry exists in the manifest regardless of primitive.
    const entry = resolveAdapter('mock_submit_module_hometax_taxreturn')
    expect(entry).toBeDefined()
    expect(entry!.primitive).toBe('submit')
  })
})
