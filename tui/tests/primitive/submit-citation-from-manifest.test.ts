// SPDX-License-Identifier: Apache-2.0
// Epic ε #2296 · T015 — SubmitPrimitive.validateInput manifest citation tests.
//
// Covers (contracts/ipc-adapter-manifest-frame.md § 7):
//   Test 5 (Submit variant): cold-boot race before manifest arrives.
//   Test 6 (Submit variant): citation slot populated from manifest URL.
//   Test 8 (Submit variant): AdapterNotFound for unknown tool_id.

import { describe, test, expect, beforeEach } from 'bun:test'
import {
  ingestManifestFrame,
  clearManifestCache,
} from '../../src/services/api/adapterManifest'
import { SubmitPrimitive } from '../../src/tools/SubmitPrimitive/SubmitPrimitive'
import type { AdapterManifestSyncFrame } from '../../src/ipc/frames.generated'
import type { ToolUseContext } from '../../src/Tool'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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
// Cold-boot race (FR-019)
// ---------------------------------------------------------------------------

describe('SubmitPrimitive.validateInput: cold-boot race', () => {
  test('fails closed before any manifest frame arrives', async () => {
    const ctx = makeContext()
    const result = await SubmitPrimitive.validateInput(
      { tool_id: 'mock_submit_module_hometax_taxreturn', params: {} },
      ctx,
    )
    expect(result.result).toBe(false)
    const msg = (result as { message?: string }).message ?? ''
    expect(msg).toContain('manifest not yet synced')
  })
})

// ---------------------------------------------------------------------------
// Citation slot populated from manifest URL (FR-017)
// ---------------------------------------------------------------------------

describe('SubmitPrimitive.validateInput: citation from manifest', () => {
  test('policy_authority_url from manifest entry populates ummayaCitations', async () => {
    ingestManifestFrame(
      makeManifestFrame([
        {
          tool_id: 'mock_submit_module_hometax_taxreturn',
          name: 'Mock — Hometax Tax Return Submission',
          primitive: 'send',
          policy_authority_url:
            'https://www.nts.go.kr/nts/cm/cntnts/cntntsView.do?mi=12892&cntntsId=8104',
          source_mode: 'mock',
        },
      ]),
    )

    const ctx = makeContext()
    const result = await SubmitPrimitive.validateInput(
      { tool_id: 'mock_submit_module_hometax_taxreturn', params: {} },
      ctx,
    )

    expect(result.result).toBe(true)

    // Citation slot must be populated with the agency-published URL
    const citations = (ctx as { ummayaCitations?: { real_classification_url: string }[] }).ummayaCitations
    expect(citations).toBeDefined()
    expect(citations!.length).toBeGreaterThan(0)
    expect(citations![0]?.real_classification_url).toContain('nts.go.kr')
  })

  test('internal adapter (no policy URL) resolves without citation', async () => {
    ingestManifestFrame(
      makeManifestFrame([
        {
          tool_id: 'lookup',
          name: 'Lookup',
          primitive: 'find',
          policy_authority_url: undefined,
          source_mode: 'internal',
        },
      ]),
    )

    const ctx = makeContext()
    const result = await SubmitPrimitive.validateInput(
      { tool_id: 'lookup', params: {} },
      ctx,
    )

    // Internal adapters are allowed but have no citation URL
    expect(result.result).toBe(true)
    const citations = (ctx as { ummayaCitations?: unknown[] }).ummayaCitations
    expect(citations?.length ?? 0).toBe(0)
  })
})

// ---------------------------------------------------------------------------
// AdapterNotFound fail-closed (FR-020)
// ---------------------------------------------------------------------------

describe('SubmitPrimitive.validateInput: AdapterNotFound', () => {
  test('unknown tool_id after manifest sync fails with AdapterNotFound', async () => {
    ingestManifestFrame(
      makeManifestFrame([
        {
          tool_id: 'mock_submit_module_hometax_taxreturn',
          name: 'Mock — Hometax Tax Return Submission',
          primitive: 'send',
          policy_authority_url:
            'https://www.nts.go.kr/nts/cm/cntnts/cntntsView.do?mi=12892&cntntsId=8104',
          source_mode: 'mock',
        },
      ]),
    )

    const ctx = makeContext()
    const result = await SubmitPrimitive.validateInput(
      { tool_id: 'nonexistent_submit_tool', params: {} },
      ctx,
    )

    expect(result.result).toBe(false)
    const msg = (result as { message?: string }).message ?? ''
    expect(msg).toContain('AdapterNotFound')
    expect(msg).toContain('nonexistent_submit_tool')
  })
})
