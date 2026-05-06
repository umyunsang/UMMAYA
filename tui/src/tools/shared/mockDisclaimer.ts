// SPDX-License-Identifier: Apache-2.0
// KOSMOS-original — Audit-2 P0 fix · mock disclaimer helpers.
//
// Citizen-safety directive: any tool result whose payload contains
// ``_mode === "mock"`` MUST display a prominent disclaimer so citizens
// immediately recognise that no real administrative action was taken.
//
// Spec 024 transparency fields used:
//   _mode                   — "mock" | "live" (stamped by transparency.py)
//   _reference_implementation
//   _actual_endpoint_when_live
//   _security_wrapping_pattern
//   _policy_authority
//   _international_reference
//
// Usage in every primitive renderer:
//   const mock = extractMockMeta(result)
//   if (mock.isMock) { ... render with 🧪 모의 prefix and dim-cyan color }

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface MockMeta {
  /** True when `_mode === "mock"` is present in the payload. */
  isMock: boolean
  /** Text of the `_actual_endpoint_when_live` field if present. */
  actualEndpointWhenLive?: string
  /** Text of the `_reference_implementation` field if present. */
  referenceImplementation?: string
  /** Text of the `_policy_authority` field if present. */
  policyAuthority?: string
  /** Text of the `_international_reference` field if present. */
  internationalReference?: string
}

// ---------------------------------------------------------------------------
// extractMockMeta
// ---------------------------------------------------------------------------

/**
 * Extract mock-disclaimer metadata from an adapter result payload.
 *
 * The ``payload`` may be:
 *   - The entire primitive output (``{ ok, result, ... }``) — for top-level check.
 *   - The inner ``result`` value from a successful primitive response.
 *
 * Both are checked.  Returns ``isMock: false`` when the payload is absent or
 * not a plain object.
 */
export function extractMockMeta(payload: unknown): MockMeta {
  if (!payload || typeof payload !== 'object') {
    return { isMock: false }
  }

  const p = payload as Record<string, unknown>
  const result =
    typeof p['result'] === 'object' && p['result'] !== null
      ? (p['result'] as Record<string, unknown>)
      : undefined
  const adapterReceipt =
    typeof result?.['adapter_receipt'] === 'object' &&
    result['adapter_receipt'] !== null
      ? (result['adapter_receipt'] as Record<string, unknown>)
      : undefined

  // Check the outer envelope first (``{ok, result, _mode}``),
  // then fall through to the inner ``result`` field and submit's opaque
  // ``adapter_receipt``. SubmitOutput intentionally keeps domain data under
  // adapter_receipt, including the Spec 024 transparency stamp.
  const mode =
    typeof p['_mode'] === 'string'
      ? p['_mode']
      : typeof result?.['_mode'] === 'string'
        ? (result['_mode'] as string)
        : typeof adapterReceipt?.['_mode'] === 'string'
          ? (adapterReceipt['_mode'] as string)
          : undefined

  if (mode !== 'mock') {
    return { isMock: false }
  }

  // Pick fields from whichever level has them — prefer inner result.
  const inner =
    typeof adapterReceipt?.['_mode'] === 'string'
      ? adapterReceipt
      : typeof result?.['_mode'] === 'string'
        ? result
        : p

  return {
    isMock: true,
    actualEndpointWhenLive:
      typeof inner['_actual_endpoint_when_live'] === 'string'
        ? inner['_actual_endpoint_when_live']
        : undefined,
    referenceImplementation:
      typeof inner['_reference_implementation'] === 'string'
        ? inner['_reference_implementation']
        : undefined,
    policyAuthority:
      typeof inner['_policy_authority'] === 'string'
        ? inner['_policy_authority']
        : undefined,
    internationalReference:
      typeof inner['_international_reference'] === 'string'
        ? inner['_international_reference']
        : undefined,
  }
}

// ---------------------------------------------------------------------------
// Mock label helpers (stateless, no React import — primitives stay in .ts)
// ---------------------------------------------------------------------------

/** Korean prefix for all mock tool results. */
export const MOCK_PREFIX = '🧪 모의'

/**
 * Return the mock-prefixed Korean label for a primitive success action.
 *
 * Examples:
 *   mockLabel('인증 완료')  → '🧪 모의 인증 완료'
 *   mockLabel('제출 접수')  → '🧪 모의 제출 접수'
 */
export function mockLabel(label: string): string {
  return `${MOCK_PREFIX} ${label}`
}
