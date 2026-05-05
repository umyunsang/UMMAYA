// SPDX-License-Identifier: Apache-2.0
// Spec 1635 P4 UI L2 — /agents command (FR-026, T055)
//
// Supports two invocation forms:
//   /agents          — default list: proposal-iv 5-state per active ministry
//   /agents --detail — adds SLA-remaining / health / rolling-avg response
//
// The command resolves active AgentVisibilityEntry records from the process-
// level IPC bridge (if available) and renders AgentVisibilityPanel.
//
// T056 and T059 are Lead scope (REPL.tsx wiring + OTEL emission).
// This module exposes a pure command handler callable from the REPL command
// dispatcher without touching REPL.tsx.

import * as React from 'react'
import { Box, Text, useInput } from 'ink'
import { AgentVisibilityPanel } from '../components/agents/AgentVisibilityPanel.js'
import type { AgentVisibilityEntryT } from '../schemas/ui-l2/agent.js'
import { AgentVisibilityEntry } from '../schemas/ui-l2/agent.js'
import { emitSurfaceActivation } from '../observability/surface.js'
import { getOrCreateKosmosBridge } from '../ipc/bridgeSingleton.js'
import { getOrCreateSubscriptionRegistry } from '../state/subscriptionRegistry.js'

// ---------------------------------------------------------------------------
// Argument parsing
// ---------------------------------------------------------------------------

export interface AgentsCommandArgs {
  detail: boolean
}

/**
 * Parse raw /agents argument string.
 * Accepts: '' | '--detail'
 */
export function parseAgentsArgs(raw: string): AgentsCommandArgs {
  const trimmed = raw.trim()
  return { detail: trimmed === '--detail' || trimmed === '-d' }
}

// ---------------------------------------------------------------------------
// Snapshot resolver
// ---------------------------------------------------------------------------

/**
 * Build the initial AgentVisibilityEntry snapshot from any TUI-side state
 * the process holds. In addition to the WorkerStatusFrame stream that
 * AgentVisibilityPanel subscribes to (T057, Spec 027 Agent Swarm), this
 * function pulls open subscription handles from the in-process subscription
 * registry (Lead-FU-5) so citizens see the channels they have opened via
 * the ``subscribe`` primitive — even before any worker_status frame arrives.
 *
 * Each subscription is rendered as a "running" agent row with the ministry
 * derived from the adapter ``tool_id`` prefix (KMA / KOROAD / NMC / ...).
 *
 * Never throws — returns empty array on any failure.
 */
function resolveInitialEntries(): AgentVisibilityEntryT[] {
  const entries: AgentVisibilityEntryT[] = []

  try {
    const subscriptions = getOrCreateSubscriptionRegistry().list()
    for (const sub of subscriptions) {
      // The subscribe primitive opens a session-lifetime channel; until the
      // backend emits an explicit close, treat the handle as "running".
      const candidate: AgentVisibilityEntryT = {
        agent_id: `subscribe:${sub.handleId}`,
        ministry: sub.ministry,
        state: 'running',
        sla_remaining_ms: null,
        health: 'green',
        rolling_avg_response_ms: null,
        last_transition_at: sub.openedAt,
      }
      // Defensive: validate before pushing so a malformed entry can't crash
      // the panel render. AgentVisibilityEntry is the canonical Zod schema.
      const parsed = AgentVisibilityEntry.safeParse(candidate)
      if (parsed.success) entries.push(parsed.data)
    }
  } catch {
    // Registry not initialized (e.g., test bootstrap) — fall through.
  }

  return entries
}

// ---------------------------------------------------------------------------
// React component rendered by the command dispatcher
// ---------------------------------------------------------------------------

interface AgentsCommandViewProps {
  showDetail: boolean
  onExit?: () => void
}

/**
 * The JSX node rendered when /agents is invoked.
 * Wraps AgentVisibilityPanel with an exit hint footer.
 */
function AgentsCommandView({
  showDetail,
  onExit,
}: AgentsCommandViewProps): React.ReactNode {
  // Emit surface activation (FR-037)
  React.useEffect(() => {
    emitSurfaceActivation('agents', { 'kosmos.agents.detail': showDetail })
  }, [showDetail])

  // Defense-in-depth Esc dismiss — mirrors HelpV2Grouped (REPL.tsx:3344-3355
  // comment block). The /agents command mounts via setToolJSX, and even with
  // `isLocalJSXCommand: false` the parent prompt's Esc handlers may not route
  // back here. Owning Esc directly via `useInput` guarantees the overlay can
  // always be dismissed. AGENTS.md "Infrastructure insights" #3 + #4: every
  // overlay whose dismiss key races with parent tear-down MUST own its own
  // useInput Esc fallback (the chord registry covers Tier 1 only — `agents:dismiss`
  // is not Tier 1 in defaultBindings.ts, so a `useKeybinding` alone never fires).
  useInput((_input, key) => {
    if (!onExit) return
    if (key.escape) {
      onExit()
    }
  })

  let bridge: ReturnType<typeof getOrCreateKosmosBridge> | undefined
  try {
    bridge = getOrCreateKosmosBridge()
  } catch {
    // Bridge not available (e.g., test environment) — panel shows static snapshot
    bridge = undefined
  }

  const initialEntries = resolveInitialEntries()

  return (
    <Box flexDirection="column">
      <AgentVisibilityPanel
        initialEntries={initialEntries}
        showDetail={showDetail}
        bridge={bridge}
      />
      <Box marginTop={1}>
        <Text color="#5c5c5c" dimColor>
          {showDetail
            ? '  /agents 로 간단 목록 전환 · ESC 종료'
            : '  /agents --detail 로 SLA · 건강 · 응답속도 · ESC 종료'}
        </Text>
      </Box>
    </Box>
  )
}

// ---------------------------------------------------------------------------
// Command handler — compatible with the existing command registry pattern
// ---------------------------------------------------------------------------

/**
 * Main entry point for the /agents [--detail] command.
 *
 * Returns a React node (compatible with LocalJSXCommandOnDone pattern used
 * throughout the codebase).  The `raw` parameter is the string after `/agents`.
 */
export function renderAgentsCommand(
  raw: string = '',
  onExit?: () => void,
): React.ReactNode {
  const args = parseAgentsArgs(raw)
  return React.createElement(AgentsCommandView, {
    showDetail: args.detail,
    onExit,
  })
}

/**
 * Validate arguments for the agents command.
 * Returns null on success, an error string on failure.
 */
export function validateAgentsArgs(raw: string): string | null {
  const trimmed = raw.trim()
  if (trimmed === '' || trimmed === '--detail' || trimmed === '-d') return null
  return `Unknown argument: "${trimmed}". Usage: /agents [--detail]`
}
