// SPDX-License-Identifier: Apache-2.0
// Audit-2 P0 · FindPrimitive mock-disclaimer unit tests.
//
// Citizen-safety: mock find results MUST display a Mock prefix and
// "Demo-only result" caveat.
// Live find results MUST NOT show any mock prefix.

import { test, expect, describe } from 'bun:test'
import { render } from 'ink-testing-library'
import type React from 'react'
import { LookupPrimitive } from '../LookupPrimitive.js'
import type { Output } from '../LookupPrimitive.js'
import type { ToolUseContext } from '../../../Tool.js'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderLookup(output: Output, opts: { verbose?: boolean } = {}): string {
  const element = LookupPrimitive.renderToolResultMessage!(
    output,
    null,
    { verbose: opts.verbose ?? false },
  )
  if (typeof element === 'string') return element
  if (element === null || element === undefined) return ''
  const { lastFrame } = render(element as React.ReactElement)
  return lastFrame() ?? ''
}

// ---------------------------------------------------------------------------
// Mock path — disclaimer required (fetch / record result)
// ---------------------------------------------------------------------------

describe('FindPrimitive renderToolResultMessage — mock disclaimer', () => {
  test('mock find (ok=true, _mode="mock" in result) shows Mock prefix', () => {
    const output: Output = {
      ok: true,
      result: {
        tool_id: 'mock_lookup_module_hometax_simplified',
        kind: 'record',
        fields: { tax_year: 2025, total_income: 50000000 },
        _mode: 'mock',
        _reference_implementation: 'ax-infrastructure-callable-channel',
        _actual_endpoint_when_live: 'https://api.hometax.go.kr/v1/lookup/simplified',
        _security_wrapping_pattern: 'OAuth2.1 + mTLS',
        _policy_authority: 'https://www.hometax.go.kr/policy',
        _international_reference: 'Singapore APEX',
      },
    }

    const frame = renderLookup(output)
    expect(frame).toContain('Mock Search result')
    expect(frame).toContain('Demo-only result')
  })

  test('mock lookup shows tool_id and count in parentheses', () => {
    const output: Output = {
      ok: true,
      result: {
        tool_id: 'mock_hira_hospital_search',
        kind: 'collection',
        items: [
          { name: 'Mock Hospital A', address: 'Busan Saha-gu' },
          { name: 'Mock Hospital B', address: 'Busan Seo-gu' },
        ],
        _mode: 'mock',
        _reference_implementation: 'ax-infrastructure-callable-channel',
        _actual_endpoint_when_live: 'https://api.hira.or.kr/v1/hospital/search',
        _security_wrapping_pattern: 'API Key + HTTPS',
        _policy_authority: 'https://www.hira.or.kr/policy',
        _international_reference: 'EU eHealth',
      },
    }

    const frame = renderLookup(output)
    expect(frame).toContain('Mock Search result')
    expect(frame).toContain('mock_hira_hospital_search')
    expect(frame).toContain('2 results')
  })

  test('mock lookup hides actual endpoint behind compact preview when long', () => {
    const output: Output = {
      ok: true,
      result: {
        tool_id: 'mock_lookup_module_gov24_certificate',
        kind: 'record',
        fields: { certificate_type: 'resident-registration-copy' },
        _mode: 'mock',
        _reference_implementation: 'ax-infrastructure-callable-channel',
        _actual_endpoint_when_live: 'https://api.gov24.go.kr/v1/certificate',
        _security_wrapping_pattern: 'OAuth2.1',
        _policy_authority: 'https://www.mois.go.kr/policy',
        _international_reference: 'Estonia X-Road',
      },
    }

    const frame = renderLookup(output)
    expect(frame).toContain('...')
    expect(frame).not.toContain('https://api.gov24.go.kr/v1/certificate')
  })
})

// ---------------------------------------------------------------------------
// Live path — NO mock disclaimer
// ---------------------------------------------------------------------------

describe('FindPrimitive renderToolResultMessage — live path (no mock disclaimer)', () => {
  test('live find (no _mode field) shows tool_id without Mock prefix', () => {
    const output: Output = {
      ok: true,
      result: {
        tool_id: 'kma_current_observation',
        kind: 'record',
        fields: { temperature: 18.7, humidity: 65 },
      },
    }

    const frame = renderLookup(output)
    expect(frame).toContain('kma_current_observation')
    expect(frame).not.toContain('Mock')
    expect(frame).not.toContain('Demo-only result')
  })

  test('live find with _mode="live" does NOT show mock disclaimer', () => {
    const output: Output = {
      ok: true,
      result: {
        tool_id: 'koroad_accident_hazard_search',
        kind: 'collection',
        items: [{ location: 'Busan Saha-gu' }],
        _mode: 'live',
      },
    }

    const frame = renderLookup(output)
    expect(frame).not.toContain('Mock')
    expect(frame).not.toContain('Demo-only result')
  })
})

// ---------------------------------------------------------------------------
// Error path preserved
// ---------------------------------------------------------------------------

describe('FindPrimitive renderToolResultMessage — error path preserved', () => {
  test('ok=false renders error message in red, no mock disclaimer', () => {
    const output: Output = {
      ok: false,
      error: {
        kind: 'tool_not_found',
        message: "Adapter 'unknown_tool' was not found.",
      },
    }

    const frame = renderLookup(output)
    expect(frame).toContain('Error:')
    expect(frame).toContain("Adapter 'unknown_tool' was not found")
    expect(frame).not.toContain('Mock')
  })
})

describe('FindPrimitive validateInput — primitive self-target guard', () => {
  test('normalizes find(find({tool_id: adapter})) envelope before validation', () => {
    const parsed = LookupPrimitive.inputSchema.parse({
      tool_id: 'find',
      params: {
        tool_id: 'pps_bid_public_info',
        inqry_bgn_dt: '202605250000',
        inqry_end_dt: '202605272359',
      },
    })

    expect(parsed).toEqual({
      tool_id: 'pps_bid_public_info',
      params: {
        inqry_bgn_dt: '202605250000',
        inqry_end_dt: '202605272359',
      },
    })
  })

  test('rejects find(find) before TS-side internal tool fallback', async () => {
    const result = await LookupPrimitive.validateInput!(
      { tool_id: 'find', params: {} },
      {
        options: {
          tools: [LookupPrimitive],
        },
      } as unknown as ToolUseContext,
    )

    expect(result.result).toBe(false)
    expect(result.message).toContain("Root primitive 'find' is not an adapter")
  })
})
