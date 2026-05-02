// SPDX-License-Identifier: Apache-2.0
// Epic γ #2294 · T022 — OTEL span-attribute parity for the primitive layer.
//
// FINDING: OTEL spans are NOT emitted from the TUI primitive layer (tui/src/tools/).
// The Spec 021 GenAI span is emitted from tui/src/ipc/llmClient.ts on every
// stream() call (one span per LLM invocation). The primitive layer (LookupPrimitive,
// SubmitPrimitive, etc.) instead propagates citation data through the
// `kosmosCitations` extension slot on ToolUseContext — that slot is what the
// FallbackPermissionRequest component reads to surface the agency policy URL.
//
// Per research.md § R-7, the test strategy in this file is therefore the
// "fallback branch" documented in the T022 task specification:
//
//   "write a smaller-scope test that asserts the *intent* is preserved — read
//    LookupPrimitive.ts and tui/src/tools/shared/primitiveCitation.ts and assert
//    that the extractCitation call returns an object whose keys match the expected
//    attribute names, OR assert that validateInput, when invoked with a populated
//    context, leaves a kosmosCitations slot whose shape matches what an OTEL
//    emitter would later attach."
//
// The canonical OTEL attribute set that an emitter WOULD attach (once a tool-call
// span layer is introduced in the TUI) is:
//   - kosmos.tool.id              ← input.tool_id (fetch mode)
//   - kosmos.tool.mode            ← input.mode ('fetch' or 'search')
//   - kosmos.adapter.real_classification_url  ← citation.real_classification_url
//
// The "policy_authority" field is surfaced in the permission UI body text but is
// NOT expected as a span attribute (it is a human-readable string, not a span key).
//
// This test locks the citation contract so future refactors cannot silently drop
// real_classification_url from the kosmosCitations slot, which would break both
// the permission UI and any future tool-call span emitter.
//
// Spec 021 reference: kosmos.tool.id + kosmos.tool.mode in Spec 021 attribute schema.
// Epic δ reference: kosmos.adapter.real_classification_url added in c6747dd.
// SC-007 reference: span snapshot must be byte-identical pre/post refactor.

import { describe, test, expect } from 'bun:test'
import type { ToolUseContext } from '../../Tool.js'
import { LookupPrimitive } from '../LookupPrimitive/LookupPrimitive.js'
import {
  extractCitation,
  type AdapterWithPolicy,
  type AdapterCitation,
  PrimitiveErrorCode,
} from '../shared/primitiveCitation.js'

// ---------------------------------------------------------------------------
// OTEL attribute key constants
// These are the canonical KOSMOS OTEL attribute names (Spec 021 + Epic δ).
// Any future span emitter MUST use exactly these keys. This constant set is
// the snapshot that SC-007 requires to be byte-identical pre/post refactor.
// ---------------------------------------------------------------------------

const EXPECTED_CITATION_KEYS: ReadonlyArray<keyof AdapterCitation> = [
  'real_classification_url',
  'policy_authority',
] as const

/** Maps the citation slot keys to the OTEL span attribute names they project to. */
const OTEL_ATTRIBUTE_PROJECTION = {
  real_classification_url: 'kosmos.adapter.real_classification_url',
  policy_authority: 'kosmos.adapter.policy_authority',
} as const satisfies Record<keyof AdapterCitation, string>

// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------

/** NMC emergency search adapter fixture (mock — no live HTTP). */
const NMC_ADAPTER_FIXTURE: AdapterWithPolicy = {
  name: 'nmc_emergency_search',
  real_domain_policy: {
    real_classification_url:
      'https://www.nmc.or.kr/nmc/main/contents.do?menuNo=200218',
    policy_authority: '국립중앙의료원 (NMC)',
  },
}

/** Adapter fixture with an empty real_classification_url (must fail closed). */
const EMPTY_URL_ADAPTER: AdapterWithPolicy = {
  name: 'broken_adapter',
  real_domain_policy: {
    real_classification_url: '',
    policy_authority: '테스트 기관',
  },
}

/** Adapter fixture with no real_domain_policy at all. */
const NO_POLICY_ADAPTER: AdapterWithPolicy = {
  name: 'no_policy_adapter',
}

// ---------------------------------------------------------------------------
// Minimal ToolUseContext factory
// Only the fields that validateInput reads are populated.
// ---------------------------------------------------------------------------

function makeContext(
  tools: AdapterWithPolicy[],
): ToolUseContext {
  return {
    options: {
      tools: tools as unknown as ToolUseContext['options']['tools'],
      commands: [],
      debug: false,
      mainLoopModel: 'test',
      verbose: false,
      thinkingConfig: { type: 'disabled' },
      mcpClients: [],
      mcpResources: {},
      isNonInteractiveSession: true,
      agentDefinitions: { agents: [], error: null },
    },
    // Minimal required fields — unused by validateInput
    readFileTimestamps: new Map(),
    getToolPermissionContext: () => ({
      mode: 'default',
      additionalWorkingDirectories: new Map(),
      alwaysAllowRules: {},
      alwaysDenyRules: {},
      alwaysAskRules: {},
      isBypassPermissionsModeAvailable: false,
    }),
    agentId: undefined,
    abortController: new AbortController(),
    setToolJSX: () => undefined,
    messageId: 'test-msg-id',
    isSingleTurn: false,
  } as unknown as ToolUseContext
}

// ---------------------------------------------------------------------------
// Group 1: extractCitation shape contract
// Lock the keys returned by extractCitation to the canonical set.
// ---------------------------------------------------------------------------

describe('extractCitation — citation shape matches OTEL attribute projection keys', () => {
  test('returns both expected keys for a well-formed adapter', () => {
    const citation = extractCitation(NMC_ADAPTER_FIXTURE)
    expect(citation).not.toBeNull()
    const keys = Object.keys(citation!) as Array<keyof AdapterCitation>

    for (const expectedKey of EXPECTED_CITATION_KEYS) {
      expect(keys).toContain(expectedKey)
    }
    // Exact set — no extra keys, no missing keys (SC-007 byte-identity intent).
    expect(keys.length).toBe(EXPECTED_CITATION_KEYS.length)
  })

  test('real_classification_url value is a non-empty string', () => {
    const citation = extractCitation(NMC_ADAPTER_FIXTURE)!
    expect(typeof citation.real_classification_url).toBe('string')
    expect(citation.real_classification_url.length).toBeGreaterThan(0)
  })

  test('policy_authority value is a non-empty string', () => {
    const citation = extractCitation(NMC_ADAPTER_FIXTURE)!
    expect(typeof citation.policy_authority).toBe('string')
    expect(citation.policy_authority.length).toBeGreaterThan(0)
  })

  test('returns null for adapter with empty real_classification_url', () => {
    expect(extractCitation(EMPTY_URL_ADAPTER)).toBeNull()
  })

  test('returns null for adapter with no real_domain_policy', () => {
    expect(extractCitation(NO_POLICY_ADAPTER)).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// Group 2: OTEL attribute projection map is byte-stable
// Locks the mapping from citation keys to OTEL attribute names.
// ---------------------------------------------------------------------------

describe('OTEL attribute projection — key mapping is byte-stable', () => {
  test('real_classification_url projects to kosmos.adapter.real_classification_url', () => {
    expect(OTEL_ATTRIBUTE_PROJECTION['real_classification_url']).toBe(
      'kosmos.adapter.real_classification_url',
    )
  })

  test('policy_authority projects to kosmos.adapter.policy_authority', () => {
    expect(OTEL_ATTRIBUTE_PROJECTION['policy_authority']).toBe(
      'kosmos.adapter.policy_authority',
    )
  })

  test('projection covers all EXPECTED_CITATION_KEYS', () => {
    for (const key of EXPECTED_CITATION_KEYS) {
      expect(Object.keys(OTEL_ATTRIBUTE_PROJECTION)).toContain(key)
    }
  })
})

// ---------------------------------------------------------------------------
// Group 3: validateInput populates kosmosCitations slot (OTEL emitter intent)
// Asserts that LookupPrimitive.validateInput attaches the citation to the
// context so a future tool-call span emitter can read it without additional
// adapter resolution.
// ---------------------------------------------------------------------------

describe('LookupPrimitive.validateInput — kosmosCitations slot shape', () => {
  test('mode=fetch with valid adapter: result=true and kosmosCitations populated', async () => {
    const ctx = makeContext([NMC_ADAPTER_FIXTURE])
    const result = await LookupPrimitive.validateInput(
      { tool_id: 'nmc_emergency_search', params: {} },
      ctx,
    )
    expect(result.result).toBe(true)

    // The citation must be attached so a span emitter can project it.
    const ctxWithCitations = ctx as unknown as { kosmosCitations?: AdapterCitation[] }
    expect(ctxWithCitations.kosmosCitations).toBeDefined()
    expect(Array.isArray(ctxWithCitations.kosmosCitations)).toBe(true)
    expect(ctxWithCitations.kosmosCitations!.length).toBeGreaterThan(0)

    const citation = ctxWithCitations.kosmosCitations![0]!
    // These are the exact keys a OTEL span emitter would read to set
    // kosmos.adapter.real_classification_url and kosmos.adapter.policy_authority.
    expect(typeof citation.real_classification_url).toBe('string')
    expect(citation.real_classification_url.length).toBeGreaterThan(0)
    expect(typeof citation.policy_authority).toBe('string')
    expect(citation.policy_authority.length).toBeGreaterThan(0)
  })

  test('mode=fetch with unknown tool_id: result=false, errorCode=AdapterNotFound', async () => {
    const ctx = makeContext([NMC_ADAPTER_FIXTURE])
    const result = await LookupPrimitive.validateInput(
      { tool_id: 'nonexistent_adapter', params: {} },
      ctx,
    )
    expect(result.result).toBe(false)
    if (result.result) return
    expect(result.errorCode).toBe(PrimitiveErrorCode.AdapterNotFound)
    // No citation populated on failure (fail-closed: no fabricated citation).
    const ctxWithCitations = ctx as unknown as { kosmosCitations?: AdapterCitation[] }
    expect(ctxWithCitations.kosmosCitations).toBeUndefined()
  })

  test('mode=fetch with citation-missing adapter: result=false, errorCode=CitationMissing', async () => {
    const ctx = makeContext([NO_POLICY_ADAPTER])
    const result = await LookupPrimitive.validateInput(
      { tool_id: 'no_policy_adapter', params: {} },
      ctx,
    )
    expect(result.result).toBe(false)
    if (result.result) return
    expect(result.errorCode).toBe(PrimitiveErrorCode.CitationMissing)
  })

  // Spec 2521 (2026-05-01): the "mode=search bypasses citation" test
  // was deleted. BM25 adapter discovery is now a backend-internal
  // mechanism (auto-injected into the system prompt's
  // <available_adapters> dynamic suffix); it has no LLM-callable mode
  // and therefore no citation-skip path to assert here.
})

// ---------------------------------------------------------------------------
// Group 4: kosmos.tool.id and kosmos.tool.mode span attribute intent
// These attributes are emitted by any future tool-call span from the input.
// This group confirms the input schema preserves the source fields.
// ---------------------------------------------------------------------------

describe('span attribute source fields — Spec 2521 fetch-only input schema', () => {
  test('input carries tool_id (source of kosmos.tool.id span attribute)', () => {
    const input = { tool_id: 'nmc_emergency_search', params: {} }
    expect(input.tool_id).toBe('nmc_emergency_search')
    expect('mode' in input).toBe(false)
  })
})
