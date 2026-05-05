// SPDX-License-Identifier: Apache-2.0
// Spec 1635 P4 UI L2 — AgentVisibilityPanel
//
// Source reference: cc:components/agents/AgentsList.tsx (Claude Code 2.1.88)
// Proposal-IV canonical 5-state visual per ministry agent.
// FR-025: 5-state enum (idle / dispatched / running / waiting-permission / done)
// FR-028: live-updated via Spec 027 mailbox WorkerStatusFrame events
//
// Dot color regulation per docs/wireframes/proposal-iv.mjs:
//   🔵 blue   lookup    · info retrieval
//   🟠 orange submit    · outbound write
//   🔴 red    verify    · identity gate
//   🟢 green  subscribe · passive stream
//   🟣 purple plugin.*  · plugin namespace

import * as React from 'react'
import { Box, Text } from 'ink'
import type { AgentVisibilityEntryT, AgentStateT } from '../../schemas/ui-l2/agent.js'
import { dotColorForPrimitive } from '../../schemas/ui-l2/agent.js'
import { useUiL2I18n } from '../../i18n/uiL2.js'
import type { IPCBridge } from '../../ipc/bridge.js'
import type { WorkerStatusFrame } from '../../ipc/frames.generated.js'

// ── Primitive dot color tokens → hex (matches _shared.mjs C palette) ────────
const PRIMITIVE_HEX: Record<string, string> = {
  primitiveLookup: '#60a5fa',    // blue   · lookup
  primitiveSubmit: '#fb923c',    // orange · submit
  primitiveVerify: '#f87171',    // red    · verify
  primitiveSubscribe: '#34d399', // green  · subscribe
  primitivePlugin: '#a78bfa',    // purple · plugin.*
}

function resolveDotHex(verb: string): string {
  const token = dotColorForPrimitive(verb)
  return PRIMITIVE_HEX[token] ?? '#8a8a8a'
}

// ── State label glyph ────────────────────────────────────────────────────────
const STATE_GLYPH: Record<AgentStateT, string> = {
  idle: '○',
  dispatched: '◌',
  running: '⏺',
  'waiting-permission': '⊡',
  done: '✓',
}

const STATE_COLOR: Record<AgentStateT, string> = {
  idle: '#5c5c5c',
  dispatched: '#8a8a8a',
  running: '#4fd1c5',
  'waiting-permission': '#fbbf24',
  done: '#34d399',
}

// ── AgentVisibilityRow ────────────────────────────────────────────────────────

interface AgentVisibilityRowProps {
  entry: AgentVisibilityEntryT
  showDetail: boolean
  /** Which primitive the worker is currently executing — for dot color */
  currentPrimitive?: string
}

export function AgentVisibilityRow({
  entry,
  showDetail,
  currentPrimitive = 'lookup',
}: AgentVisibilityRowProps): React.ReactNode {
  const i18n = useUiL2I18n()
  const dotHex = resolveDotHex(currentPrimitive)
  const stateGlyph = STATE_GLYPH[entry.state]
  const stateColor = STATE_COLOR[entry.state]
  const stateLabel = i18n.agentStateLabel(entry.state)

  const slaDisplay =
    entry.sla_remaining_ms !== null
      ? `${Math.max(0, Math.round(entry.sla_remaining_ms / 1000))}s`
      : '—'

  const avgDisplay =
    entry.rolling_avg_response_ms !== null
      ? `${Math.round(entry.rolling_avg_response_ms)}ms`
      : '—'

  const healthColor =
    entry.health === 'green'
      ? '#34d399'
      : entry.health === 'amber'
        ? '#fbbf24'
        : '#f87171'

  return (
    <Box>
      {/* Primitive dot with verb color */}
      <Text color={dotHex} bold>{'⏺ '}</Text>
      {/* Ministry name padded */}
      <Text bold>{entry.ministry.padEnd(8)}</Text>
      {/* State glyph + label */}
      <Text color={stateColor}>{stateGlyph} </Text>
      <Text color={stateColor}>{stateLabel.padEnd(18)}</Text>
      {/* Detail columns if --detail */}
      {showDetail && (
        <>
          <Text color="#8a8a8a">{slaDisplay.padEnd(8)}</Text>
          <Text color={healthColor}>{entry.health.padEnd(8)}</Text>
          <Text color="#8a8a8a">{avgDisplay}</Text>
        </>
      )}
    </Box>
  )
}

// ── AgentVisibilityPanel ─────────────────────────────────────────────────────

export interface AgentVisibilityPanelProps {
  /**
   * Initial snapshot of agent entries. Updated in-place via WorkerStatusFrame
   * events from the IPC bridge (FR-028).
   */
  initialEntries: AgentVisibilityEntryT[]
  showDetail?: boolean
  /** Optional IPC bridge for live subscription (FR-028). If omitted, panel
   *  renders the static initialEntries snapshot only. */
  bridge?: IPCBridge
  /** Map from worker_id → current primitive verb (for dot color). */
  primitiveByWorker?: Record<string, string>
}

/**
 * T053: Proposal-IV 5-state panel rendering active ministry agents.
 *
 * Subscribes to WorkerStatusFrame events from the Spec 027 mailbox channel
 * via the IPC bridge (T057). When no bridge is provided, renders the
 * initialEntries snapshot (useful for testing and the /agents static display).
 *
 * CC reference: AgentsList.tsx — BorderedNotice + rows pattern.
 * Proposal-IV canonical visual: AgentsCommand state (State 4).
 */
export function AgentVisibilityPanel({
  initialEntries,
  showDetail = false,
  bridge,
  primitiveByWorker = {},
}: AgentVisibilityPanelProps): React.ReactNode {
  const i18n = useUiL2I18n()

  // Live-update state seeded from props (T057 subscription wires into this)
  const [entries, setEntries] =
    React.useState<AgentVisibilityEntryT[]>(initialEntries)

  // Keep a ref so the async listener closure always sees the latest entries
  const entriesRef = React.useRef(entries)
  entriesRef.current = entries

  // ── T057: Subscribe to WorkerStatusFrame events (FR-028) ─────────────────
  // We iterate the bridge frames async iterable in a useEffect and update
  // entries when a WorkerStatusFrame arrives. This is push-based (no polling),
  // satisfying SC-007 ≤500 ms p95.
  React.useEffect(() => {
    if (!bridge) return

    let cancelled = false

    async function listenForAgentUpdates(): Promise<void> {
      try {
        for await (const frame of bridge!.frames()) {
          if (cancelled) break
          // Only process WorkerStatusFrame (kind = 'worker_status')
          if (frame.kind !== 'worker_status') continue
          const wsf = frame as WorkerStatusFrame
          if (!wsf.worker_id || !wsf.status) continue

          // Map IPC status → AgentState (IPC uses underscore; our schema dashes)
          const newState = mapIpcStatus(wsf.status)
          if (!newState) continue

          setEntries((prev) => {
            const idx = prev.findIndex((e) => e.agent_id === wsf.worker_id)
            if (idx === -1) {
              // New worker — create entry
              const entry: AgentVisibilityEntryT = {
                agent_id: wsf.worker_id,
                ministry: wsf.role_id ?? wsf.worker_id,
                state: newState,
                sla_remaining_ms: null,
                health: 'green',
                rolling_avg_response_ms: null,
                last_transition_at: wsf.ts ?? new Date().toISOString(),
              }
              return [...prev, entry]
            }
            // Update existing entry
            const updated = [...prev]
            updated[idx] = {
              ...updated[idx]!,
              state: newState,
              last_transition_at: wsf.ts ?? updated[idx]!.last_transition_at,
            }
            return updated
          })
        }
      } catch (_err) {
        // Bridge closed or errored — stop silently (bridge has its own crash handler)
      }
    }

    void listenForAgentUpdates()
    return () => {
      cancelled = true
    }
  }, [bridge])

  // Sync initialEntries prop changes (e.g., when parent re-queries snapshot)
  React.useEffect(() => {
    setEntries(initialEntries)
  }, [initialEntries])

  const label = `◆ ${i18n.agentsTitle} · ${entries.length} agents`

  return (
    <Box
      borderStyle="round"
      borderColor="#4fd1c5"
      flexDirection="column"
      paddingX={1}
    >
      {/* Header */}
      <Box marginBottom={1}>
        <Text color="#4fd1c5" bold>{label}</Text>
      </Box>

      {/* Detail column header — Lead-FU-5: render even when empty so
          --detail mode is visually distinguishable from the simple list. */}
      {showDetail && (
        <Box marginBottom={1}>
          <Text color="#5c5c5c">
            {'  '}
            {'부처'.padEnd(10)}
            {'상태'.padEnd(20)}
            {'SLA'.padEnd(8)}
            {'건강'.padEnd(8)}
            {'평균응답'}
          </Text>
        </Box>
      )}

      {/* Agent rows */}
      {entries.length === 0 ? (
        <Box flexDirection="column">
          <Text color="#5c5c5c">{'  활성 부처 에이전트 없음'}</Text>
          {showDetail && (
            <Text color="#5c5c5c" dimColor>
              {'  subscribe 도구 호출 시 여기에 활성 채널이 표시됩니다.'}
            </Text>
          )}
        </Box>
      ) : (
        entries.map((entry) => (
          <AgentVisibilityRow
            key={entry.agent_id}
            entry={entry}
            showDetail={showDetail}
            currentPrimitive={
              primitiveByWorker[entry.agent_id]
                ?? (entry.agent_id.startsWith('subscribe:') ? 'subscribe' : 'lookup')
            }
          />
        ))
      )}

      {/* Footer hint */}
      {!showDetail && entries.length > 0 && (
        <Box marginTop={1}>
          <Text color="#5c5c5c" dimColor>
            {'  /agents --detail 로 SLA · 건강 · 응답속도 확인'}
          </Text>
        </Box>
      )}
    </Box>
  )
}

// ── IPC status → AgentState mapping ─────────────────────────────────────────

type IpcStatus = 'idle' | 'running' | 'waiting_permission' | 'error'

function mapIpcStatus(status: IpcStatus | string): AgentStateT | null {
  switch (status) {
    case 'idle':
      return 'idle'
    case 'running':
      return 'running'
    case 'waiting_permission':
      return 'waiting-permission'
    case 'error':
      return 'done' // terminal state — treat error as done for display
    default:
      return null
  }
}
