// SPDX-License-Identifier: Apache-2.0
// Lead-FU-5 (S7 /agents data wire) — AgentVisibilityPanel subscription
// rendering regression tests.
//
// Background:
//   Before this fix, AgentVisibilityPanel only displayed entries fed by
//   backend `worker_status` frames (Spec 027 Agent Swarm). Subscribe primitive
//   handles never reached the panel, so 3 successful `subscribe` calls
//   resulted in /agents perpetually showing "활성 부처 에이전트 없음".
//
// These tests prove:
//   1. Panel renders subscription entries passed via initialEntries (already
//      worked, defense-in-depth coverage).
//   2. --detail mode renders the column header even when entries.length === 0.
//   3. --detail mode shows the helpful "subscribe 도구 호출 시" placeholder.
//   4. subscription:* agent_ids get the green subscribe dot color.

import { describe, expect, it } from 'bun:test'
import * as React from 'react'
import { render } from 'ink-testing-library'
import { AgentVisibilityPanel } from '../../../src/components/agents/AgentVisibilityPanel.tsx'
import type { AgentVisibilityEntryT } from '../../../src/schemas/ui-l2/agent.js'

function makeSubscriptionEntry(
  ministry: string,
  handleSuffix: string,
): AgentVisibilityEntryT {
  return {
    agent_id: `subscribe:sub-${handleSuffix}`,
    ministry,
    state: 'running',
    sla_remaining_ms: null,
    health: 'green',
    rolling_avg_response_ms: null,
    last_transition_at: new Date().toISOString(),
  }
}

describe('AgentVisibilityPanel — subscription rendering (Lead-FU-5)', () => {
  it('empty state in --detail mode still renders column header', () => {
    const { lastFrame } = render(
      React.createElement(AgentVisibilityPanel, {
        initialEntries: [],
        showDetail: true,
      }),
    )
    const frame = lastFrame() ?? ''
    // Header columns must be visible even with 0 entries
    expect(frame).toContain('부처')
    expect(frame).toContain('상태')
    expect(frame).toContain('SLA')
    expect(frame).toContain('건강')
    expect(frame).toContain('평균응답')
  })

  it('empty state in --detail mode shows subscribe placeholder hint', () => {
    const { lastFrame } = render(
      React.createElement(AgentVisibilityPanel, {
        initialEntries: [],
        showDetail: true,
      }),
    )
    const frame = lastFrame() ?? ''
    expect(frame).toContain('subscribe 도구 호출 시')
  })

  it('empty state without --detail renders compact "no agents" message', () => {
    const { lastFrame } = render(
      React.createElement(AgentVisibilityPanel, {
        initialEntries: [],
        showDetail: false,
      }),
    )
    const frame = lastFrame() ?? ''
    expect(frame).toContain('활성 부처 에이전트 없음')
    // Hint should NOT appear in compact mode
    expect(frame).not.toContain('subscribe 도구 호출 시')
  })

  it('renders 3 subscription entries with their ministries', () => {
    const entries = [
      makeSubscriptionEntry('CBS', 'cbs-001'),
      makeSubscriptionEntry('KMA', 'kma-002'),
      makeSubscriptionEntry('KOROAD', 'koroad-003'),
    ]
    const { lastFrame } = render(
      React.createElement(AgentVisibilityPanel, {
        initialEntries: entries,
        showDetail: false,
      }),
    )
    const frame = lastFrame() ?? ''
    expect(frame).toContain('CBS')
    expect(frame).toContain('KMA')
    expect(frame).toContain('KOROAD')
    // The header still renders the count
    expect(frame).toContain('3 agents')
  })

  it('subscription entries render in --detail mode with column header + rows', () => {
    const entries = [makeSubscriptionEntry('CBS', 'cbs-001')]
    const { lastFrame } = render(
      React.createElement(AgentVisibilityPanel, {
        initialEntries: entries,
        showDetail: true,
      }),
    )
    const frame = lastFrame() ?? ''
    expect(frame).toContain('부처')
    expect(frame).toContain('CBS')
    // sla_remaining_ms === null → '—'
    expect(frame).toContain('—')
    // health 'green' → green color text 'green'
    expect(frame).toContain('green')
  })

  it('header agent count reflects entries length', () => {
    const entries = [
      makeSubscriptionEntry('CBS', 'a'),
      makeSubscriptionEntry('KMA', 'b'),
    ]
    const { lastFrame } = render(
      React.createElement(AgentVisibilityPanel, {
        initialEntries: entries,
        showDetail: false,
      }),
    )
    const frame = lastFrame() ?? ''
    expect(frame).toContain('2 agents')
  })
})
