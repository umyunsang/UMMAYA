// SPDX-License-Identifier: Apache-2.0
// Lead-FU-5 (S7 /agents data wire) — /agents command empty-state + detail
// header rendering tests, plus subscription-registry data wire validation.
//
// Background:
//   The /agents command historically returned an empty array from
//   resolveInitialEntries(), relying entirely on the WorkerStatusFrame
//   subscription that is never triggered for `subscribe` primitive calls.
//   This test proves the wiring now reads from the in-process subscription
//   registry so subscribe → /agents shows the citizen their open channels.

import { describe, expect, it, beforeEach } from 'bun:test'
import * as React from 'react'
import { render } from 'ink-testing-library'
import { renderAgentsCommand } from '../../src/commands/agents.tsx'
import {
  getOrCreateSubscriptionRegistry,
  resetSubscriptionRegistry,
  deriveMinistryFromToolId,
} from '../../src/state/subscriptionRegistry.js'

beforeEach(() => {
  resetSubscriptionRegistry()
})

describe('/agents command — detail empty state (Lead-FU-5)', () => {
  it('--detail with no subscriptions still renders column header', () => {
    const { lastFrame } = render(
      React.createElement(
        React.Fragment,
        null,
        renderAgentsCommand('--detail', () => {}),
      ),
    )
    const frame = lastFrame() ?? ''
    expect(frame).toContain('부처')
    expect(frame).toContain('상태')
    expect(frame).toContain('SLA')
    expect(frame).toContain('subscribe 도구 호출 시')
  })

  it('default /agents with no subscriptions shows compact empty state', () => {
    const { lastFrame } = render(
      React.createElement(
        React.Fragment,
        null,
        renderAgentsCommand('', () => {}),
      ),
    )
    const frame = lastFrame() ?? ''
    expect(frame).toContain('활성 부처 에이전트 없음')
    // Compact mode hides the placeholder hint
    expect(frame).not.toContain('subscribe 도구 호출 시')
  })
})

describe('/agents command — subscription registry wire (Lead-FU-5)', () => {
  it('renders 3 subscriptions recorded in the registry as 3 agent rows', () => {
    const reg = getOrCreateSubscriptionRegistry()
    reg.record({
      handleId: 'sub-cbs-1',
      toolId: 'cbs_disaster_alert_subscribe',
      ministry: deriveMinistryFromToolId('cbs_disaster_alert_subscribe'),
      kind: 'cbs_broadcast',
      lifetime: 'session',
      openedAt: new Date().toISOString(),
    })
    reg.record({
      handleId: 'sub-kma-2',
      toolId: 'kma_forecast_rss',
      ministry: deriveMinistryFromToolId('kma_forecast_rss'),
      kind: 'rss',
      lifetime: 'session',
      openedAt: new Date().toISOString(),
    })
    reg.record({
      handleId: 'sub-koroad-3',
      toolId: 'koroad_traffic_pull',
      ministry: deriveMinistryFromToolId('koroad_traffic_pull'),
      kind: 'rest_pull',
      lifetime: 'long',
      openedAt: new Date().toISOString(),
    })

    const { lastFrame } = render(
      React.createElement(
        React.Fragment,
        null,
        renderAgentsCommand('', () => {}),
      ),
    )
    const frame = lastFrame() ?? ''
    expect(frame).toContain('3 agents')
    expect(frame).toContain('CBS')
    expect(frame).toContain('KMA')
    expect(frame).toContain('KOROAD')
    // Empty-state placeholder must not render when data is present
    expect(frame).not.toContain('활성 부처 에이전트 없음')
  })

  it('--detail mode shows subscription entries with full columns', () => {
    const reg = getOrCreateSubscriptionRegistry()
    reg.record({
      handleId: 'sub-cbs-detail',
      toolId: 'cbs_disaster_alert_subscribe',
      ministry: 'CBS',
      kind: 'cbs_broadcast',
      openedAt: new Date().toISOString(),
    })

    const { lastFrame } = render(
      React.createElement(
        React.Fragment,
        null,
        renderAgentsCommand('--detail', () => {}),
      ),
    )
    const frame = lastFrame() ?? ''
    expect(frame).toContain('CBS')
    // Header columns visible alongside data row
    expect(frame).toContain('부처')
    expect(frame).toContain('SLA')
    expect(frame).toContain('green')
    // SLA renders as '—' for subscriptions (no time-bound SLA)
    expect(frame).toContain('—')
  })
})

describe('deriveMinistryFromToolId — prefix mapping', () => {
  it('maps known agency prefixes to canonical labels', () => {
    expect(deriveMinistryFromToolId('kma_forecast_rss')).toBe('KMA')
    expect(deriveMinistryFromToolId('koroad_traffic_pull')).toBe('KOROAD')
    expect(deriveMinistryFromToolId('hira_hospital_search')).toBe('HIRA')
    expect(deriveMinistryFromToolId('nmc_emergency_search')).toBe('NMC')
    expect(deriveMinistryFromToolId('mohw_welfare_check')).toBe('MOHW')
    expect(deriveMinistryFromToolId('nfa119_dispatch')).toBe('NFA119')
    expect(deriveMinistryFromToolId('cbs_disaster_alert_subscribe')).toBe('CBS')
  })

  it('maps plugin.* to the 플러그인 label', () => {
    expect(deriveMinistryFromToolId('plugin.seoul-subway')).toBe('플러그인')
    expect(deriveMinistryFromToolId('plugin.post-office')).toBe('플러그인')
  })

  it('falls back to leading token for unknown prefix', () => {
    expect(deriveMinistryFromToolId('newagency_lookup')).toBe('NEWAGENCY')
    expect(deriveMinistryFromToolId('foo')).toBe('FOO')
  })

  // Audit-5 P1 (2026-05-04) — mock_ adapters MUST surface modality-specific
  // labels, not collapse to "MOCK" via the leading-token fallback.
  it('maps mock subscribe adapters to modality labels', () => {
    expect(deriveMinistryFromToolId('mock_cbs_disaster_v1')).toBe('CBS')
    expect(deriveMinistryFromToolId('mock_rss_public_notices_v1')).toBe('RSS')
    expect(deriveMinistryFromToolId('mock_rest_pull_tick_v1')).toBe('REST')
  })

  it('maps mock verify adapters to AUTH category labels', () => {
    expect(deriveMinistryFromToolId('mock_verify_mobile_id')).toBe('MOBILE-ID')
    expect(deriveMinistryFromToolId('mock_verify_mydata')).toBe('MYDATA')
    expect(deriveMinistryFromToolId('mock_verify_module_modid')).toBe('AUTH-MODULE')
    expect(deriveMinistryFromToolId('mock_verify_module_kec')).toBe('AUTH-MODULE')
    expect(deriveMinistryFromToolId('mock_verify_gongdong_injeungseo')).toBe('VERIFY')
  })

  it('maps mock submit adapters to SUBMIT category labels', () => {
    expect(deriveMinistryFromToolId('mock_submit_module_gov24_minwon')).toBe('SUBMIT-MODULE')
    expect(deriveMinistryFromToolId('mock_submit_module_hometax_taxreturn')).toBe('SUBMIT-MODULE')
  })

  it('mock_ generic fallback surfaces "MOCK" not the bare leading token', () => {
    // Brand-new mock adapter that doesn't yet match a modality entry.
    expect(deriveMinistryFromToolId('mock_xyz_new_thing')).toBe('MOCK')
  })
})

describe('subscriptionRegistry — record / list / clear', () => {
  it('preserves insertion order across list()', () => {
    const reg = getOrCreateSubscriptionRegistry()
    reg.record({
      handleId: 'h1',
      toolId: 'cbs_a',
      ministry: 'CBS',
      kind: 'cbs',
      openedAt: new Date().toISOString(),
    })
    reg.record({
      handleId: 'h2',
      toolId: 'kma_b',
      ministry: 'KMA',
      kind: 'rss',
      openedAt: new Date().toISOString(),
    })

    const list = reg.list()
    expect(list).toHaveLength(2)
    expect(list[0]?.handleId).toBe('h1')
    expect(list[1]?.handleId).toBe('h2')
  })

  it('record with same handleId is idempotent (overwrites)', () => {
    const reg = getOrCreateSubscriptionRegistry()
    reg.record({
      handleId: 'h-same',
      toolId: 'cbs_a',
      ministry: 'CBS',
      kind: 'cbs',
      openedAt: new Date().toISOString(),
    })
    reg.record({
      handleId: 'h-same',
      toolId: 'cbs_a_v2',
      ministry: 'CBS',
      kind: 'cbs',
      openedAt: new Date().toISOString(),
    })

    const list = reg.list()
    expect(list).toHaveLength(1)
    expect(list[0]?.toolId).toBe('cbs_a_v2')
  })

  it('reset clears all recorded subscriptions', () => {
    const reg = getOrCreateSubscriptionRegistry()
    reg.record({
      handleId: 'h-temp',
      toolId: 'cbs_a',
      ministry: 'CBS',
      kind: 'cbs',
      openedAt: new Date().toISOString(),
    })
    expect(reg.size()).toBe(1)

    resetSubscriptionRegistry()
    expect(getOrCreateSubscriptionRegistry().size()).toBe(0)
  })
})
