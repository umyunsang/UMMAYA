// SPDX-License-Identifier: Apache-2.0
// Epic γ #2294 · T021 · US3 — Adapter policy citation surfaces verbatim in permission UI.
//
// SC-003: 100% of adapter-routed permission prompts contain a verbatim
// real_classification_url; 0% contain any KOSMOS-invented phrase from the
// blocklist below. All assertions use the synthetic KOROAD adapter fixture.
//
// Coverage:
//  1. Happy-path: validateInput populates kosmosCitations on context.
//  2. Blocklist: renderToolResultMessage output contains no KOSMOS-invented phrases.
//  3. Citation-missing: empty policy fields → errorCode 1002 + Korean message.
//  4. Adapter-not-found: unknown tool_id → errorCode 1001.

import { describe, test, expect } from 'bun:test'
import type { ToolUseContext } from '../../Tool.js'
import {
  PrimitiveErrorCode,
  extractCitation,
} from '../shared/primitiveCitation.js'
import { LookupPrimitive } from '../LookupPrimitive/LookupPrimitive.js'
import { SubmitPrimitive } from '../SubmitPrimitive/SubmitPrimitive.js'
import { VerifyPrimitive } from '../VerifyPrimitive/VerifyPrimitive.js'

// ---------------------------------------------------------------------------
// SC-003 blocklist — phrases KOSMOS must never invent.
// ---------------------------------------------------------------------------
const FORBIDDEN_KOSMOS_INVENTED_PHRASES: readonly string[] = [
  '안전한 권한 등급',
  '본 시스템은',
  'KOSMOS는 다음과 같이',
  '권한 등급 1',
  '권한 등급 2',
  '권한 등급 3',
]

// ---------------------------------------------------------------------------
// Synthetic adapter fixture — realistic KOROAD policy citation.
// ---------------------------------------------------------------------------
const KOROAD_CITATION_URL = 'https://www.koroad.or.kr/.../privacy'
const KOROAD_POLICY_AUTHORITY = '도로교통공단'

const syntheticAdapter = {
  name: 'koroad_accident_hazard_search',
  real_domain_policy: {
    real_classification_url: KOROAD_CITATION_URL,
    policy_authority: KOROAD_POLICY_AUTHORITY,
  },
}

// ---------------------------------------------------------------------------
// Minimal ToolUseContext builder — only options.tools is required by validateInput.
// ---------------------------------------------------------------------------
function buildContext(tools: readonly { name: string; [k: string]: unknown }[]): ToolUseContext {
  return {
    options: {
      tools: tools as unknown as ToolUseContext['options']['tools'],
      commands: [],
      debug: false,
      mainLoopModel: 'test-model',
      verbose: false,
      thinkingConfig: { type: 'disabled' } as never,
      mcpClients: [],
      mcpResources: {},
      isNonInteractiveSession: true,
      agentDefinitions: { definitions: [], error: null } as never,
    },
    abortController: new AbortController(),
    readFileState: null as never,
    getAppState: () => null as never,
    setAppState: () => undefined,
    setInProgressToolUseIDs: () => undefined,
    setResponseLength: () => undefined,
    updateFileHistoryState: () => undefined,
    updateAttributionState: () => undefined,
    messages: [],
  }
}

// ---------------------------------------------------------------------------
// Helper: recursively flatten a React element tree to a plain string so the
// blocklist check can be done without a full render runtime.
// Handles: string, number, ReactElement (props.children), arrays.
// ---------------------------------------------------------------------------
function flattenReactNode(node: unknown): string {
  if (node === null || node === undefined) return ''
  if (typeof node === 'string') return node
  if (typeof node === 'number' || typeof node === 'boolean') return String(node)
  if (Array.isArray(node)) return node.map(flattenReactNode).join('')
  // React element — walk children in props
  if (typeof node === 'object' && node !== null && 'props' in (node as object)) {
    const el = node as { props?: { children?: unknown } }
    return flattenReactNode(el.props?.children)
  }
  return ''
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('extractCitation — unit sanity check', () => {
  test('returns citation fields verbatim from adapter with valid policy', () => {
    const citation = extractCitation(syntheticAdapter)
    expect(citation).not.toBeNull()
    expect(citation?.real_classification_url).toBe(KOROAD_CITATION_URL)
    expect(citation?.policy_authority).toBe(KOROAD_POLICY_AUTHORITY)
  })

  test('returns null when real_classification_url is empty', () => {
    const citation = extractCitation({
      name: 'test',
      real_domain_policy: { real_classification_url: '', policy_authority: KOROAD_POLICY_AUTHORITY },
    })
    expect(citation).toBeNull()
  })

  test('returns null when policy_authority is empty', () => {
    const citation = extractCitation({
      name: 'test',
      real_domain_policy: { real_classification_url: KOROAD_CITATION_URL, policy_authority: '' },
    })
    expect(citation).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// Happy-path: active primitives populate kosmosCitations on context.
// (LookupPrimitive mode='search' is excluded — it intentionally skips citation.)
// ---------------------------------------------------------------------------

describe('validateInput — happy path (citation populates context)', () => {
  test('LookupPrimitive mode=fetch: result true + kosmosCitations populated', async () => {
    const context = buildContext([syntheticAdapter])
    const result = await LookupPrimitive.validateInput(
      { tool_id: 'koroad_accident_hazard_search', params: {} },
      context,
    )

    expect(result.result).toBe(true)
    const citations = (context as unknown as Record<string, unknown>).kosmosCitations as { real_classification_url: string; policy_authority: string }[]
    expect(citations).toBeDefined()
    expect(citations[0].real_classification_url).toBe(KOROAD_CITATION_URL)
    expect(citations[0].policy_authority).toBe(KOROAD_POLICY_AUTHORITY)
  })

  test('SubmitPrimitive: result true + kosmosCitations populated', async () => {
    const context = buildContext([syntheticAdapter])
    const result = await SubmitPrimitive.validateInput(
      { tool_id: 'koroad_accident_hazard_search', params: {} },
      context,
    )

    expect(result.result).toBe(true)
    const citations = (context as unknown as Record<string, unknown>).kosmosCitations as { real_classification_url: string; policy_authority: string }[]
    expect(citations).toBeDefined()
    expect(citations[0].real_classification_url).toBe(KOROAD_CITATION_URL)
    expect(citations[0].policy_authority).toBe(KOROAD_POLICY_AUTHORITY)
  })

  test('VerifyPrimitive: result true + kosmosCitations populated', async () => {
    const context = buildContext([syntheticAdapter])
    const result = await VerifyPrimitive.validateInput(
      { tool_id: 'koroad_accident_hazard_search', params: {} },
      context,
    )

    expect(result.result).toBe(true)
    const citations = (context as unknown as Record<string, unknown>).kosmosCitations as { real_classification_url: string; policy_authority: string }[]
    expect(citations).toBeDefined()
    expect(citations[0].real_classification_url).toBe(KOROAD_CITATION_URL)
    expect(citations[0].policy_authority).toBe(KOROAD_POLICY_AUTHORITY)
  })

  // Spec 2521 (2026-05-01): the "mode=search bypasses citation" test
  // was deleted. BM25 adapter discovery is now a backend-internal
  // mechanism (auto-injected into the system prompt's
  // <available_adapters> dynamic suffix) — never an LLM-callable mode,
  // so there is no search-side citation path to skip. Citation
  // resolution for the remaining (fetch) mode is covered above.
})

// ---------------------------------------------------------------------------
// Blocklist: renderToolResultMessage output must not contain KOSMOS-invented phrases.
// Tests each primitive's ok=true render path.
// ---------------------------------------------------------------------------

describe('renderToolResultMessage — blocklist assertion (SC-003 0% rule)', () => {
  function assertNoForbiddenPhrases(rendered: unknown, label: string) {
    const flat = flattenReactNode(rendered)
    for (const phrase of FORBIDDEN_KOSMOS_INVENTED_PHRASES) {
      expect(flat).not.toContain(phrase)
    }
    // Sanity: rendered output is not empty for ok=true
    expect(flat.length).toBeGreaterThan(0)
    // Confirm the label matches (prevents false positives from null renders)
    expect(label).toBeTruthy()
  }

  test('LookupPrimitive ok=true mode=fetch: no forbidden phrases', () => {
    const output = {
      ok: true as const,
      result: {
        mode: 'fetch',
        tool_id: 'koroad_accident_hazard_search',
        result: [{ name: '테스트', url: KOROAD_CITATION_URL }],
      },
    }
    const rendered = LookupPrimitive.renderToolResultMessage(output, [], {
      theme: 'dark',
      tools: [],
      verbose: false,
    })
    assertNoForbiddenPhrases(rendered, 'LookupPrimitive fetch')
  })

  test('SubmitPrimitive ok=true: no forbidden phrases', () => {
    const output = {
      ok: true as const,
      result: {
        transaction_id: 'TXN-001',
        ministry: '도로교통공단',
        status: 'accepted',
      },
    }
    const rendered = SubmitPrimitive.renderToolResultMessage(output, [], {
      theme: 'dark',
      tools: [],
      verbose: false,
    })
    assertNoForbiddenPhrases(rendered, 'SubmitPrimitive ok=true')
  })

  test('VerifyPrimitive ok=true: no forbidden phrases', () => {
    const output = {
      ok: true as const,
      result: {
        status: 'verified',
        policy_authority: KOROAD_POLICY_AUTHORITY,
      },
    }
    const rendered = VerifyPrimitive.renderToolResultMessage(output, [], {
      theme: 'dark',
      tools: [],
      verbose: false,
    })
    assertNoForbiddenPhrases(rendered, 'VerifyPrimitive ok=true')
  })

})

// ---------------------------------------------------------------------------
// Citation-missing path: empty policy fields → CitationMissing (1002)
// ---------------------------------------------------------------------------

describe('validateInput — citation-missing path (errorCode 1002)', () => {
  const emptyPolicyAdapter = {
    name: 'koroad_accident_hazard_search',
    real_domain_policy: {
      real_classification_url: '',
      policy_authority: '',
    },
  }

  test('LookupPrimitive mode=fetch returns CitationMissing + Korean message', async () => {
    const context = buildContext([emptyPolicyAdapter])
    const result = await LookupPrimitive.validateInput(
      { tool_id: 'koroad_accident_hazard_search', params: {} },
      context,
    )

    expect(result.result).toBe(false)
    if (result.result) return // narrow type
    expect(result.errorCode).toBe(PrimitiveErrorCode.CitationMissing)
    expect(result.message).toContain('정책 인용')
  })

  test('SubmitPrimitive returns CitationMissing + Korean message', async () => {
    const context = buildContext([emptyPolicyAdapter])
    const result = await SubmitPrimitive.validateInput(
      { tool_id: 'koroad_accident_hazard_search', params: {} },
      context,
    )

    expect(result.result).toBe(false)
    if (result.result) return
    expect(result.errorCode).toBe(PrimitiveErrorCode.CitationMissing)
    expect(result.message).toContain('정책 인용')
  })

  test('VerifyPrimitive returns CitationMissing + Korean message', async () => {
    const context = buildContext([emptyPolicyAdapter])
    const result = await VerifyPrimitive.validateInput(
      { tool_id: 'koroad_accident_hazard_search', params: {} },
      context,
    )

    expect(result.result).toBe(false)
    if (result.result) return
    expect(result.errorCode).toBe(PrimitiveErrorCode.CitationMissing)
    expect(result.message).toContain('정책 인용')
  })

})

// ---------------------------------------------------------------------------
// Adapter-not-found path: unknown tool_id → AdapterNotFound (1001)
// ---------------------------------------------------------------------------

describe('validateInput — adapter-not-found path (errorCode 1001)', () => {
  test('LookupPrimitive mode=fetch returns AdapterNotFound for unknown tool_id', async () => {
    const context = buildContext([syntheticAdapter])
    const result = await LookupPrimitive.validateInput(
      { tool_id: 'nonexistent', params: {} },
      context,
    )

    expect(result.result).toBe(false)
    if (result.result) return
    expect(result.errorCode).toBe(PrimitiveErrorCode.AdapterNotFound)
  })

  test('SubmitPrimitive returns AdapterNotFound for unknown tool_id', async () => {
    const context = buildContext([syntheticAdapter])
    const result = await SubmitPrimitive.validateInput(
      { tool_id: 'nonexistent', params: {} },
      context,
    )

    expect(result.result).toBe(false)
    if (result.result) return
    expect(result.errorCode).toBe(PrimitiveErrorCode.AdapterNotFound)
  })

  test('VerifyPrimitive returns AdapterNotFound for unknown tool_id', async () => {
    const context = buildContext([syntheticAdapter])
    const result = await VerifyPrimitive.validateInput(
      { tool_id: 'nonexistent', params: {} },
      context,
    )

    expect(result.result).toBe(false)
    if (result.result) return
    expect(result.errorCode).toBe(PrimitiveErrorCode.AdapterNotFound)
  })

})
