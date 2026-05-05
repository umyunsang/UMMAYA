// SPDX-License-Identifier: Apache-2.0
// KOSMOS-original — Lead-FU-5 (S7 /agents data wire)
//
// Process-wide singleton tracking subscriptions opened during the current
// REPL session. Populated by SubscribePrimitive.call() on success; consumed
// by /agents command (resolveInitialEntries) so the citizen can SEE that
// their `subscribe` requests actually opened a channel.
//
// Background:
//   Before this fix, AgentVisibilityPanel was wired ONLY to backend
//   `worker_status` IPC frames (Spec 027 Agent Swarm) — but the backend
//   never emits them for subscribe primitive calls. Result: 3 successful
//   subscribe invocations → /agents perpetually shows "활성 부처 에이전트
//   없음", in violation of the KOSMOS thesis ("국민이 국가행정시스템을 쉽게
//   이용"). This registry is the smallest-surface-area fix: TUI-only state,
//   no IPC schema changes, no backend changes.
//
// Architecture parallels: pendingCallSingleton (TUI-only call tracking),
// receipt store (TUI-only consent ledger mirror).

export interface SubscriptionEntry {
  /** Handle id returned by the backend ``subscribe`` primitive. */
  handleId: string
  /** Adapter tool_id the LLM passed to ``subscribe``. */
  toolId: string
  /** Display label — derived from tool_id prefix (best-effort). */
  ministry: string
  /** ``cbs_broadcast`` / ``rest_pull`` / ``rss`` / ``unknown``. */
  kind: string
  /** ``session`` / ``short`` / ``long`` / undefined. */
  lifetime?: string
  /** ISO 8601 timestamp of when the subscription opened. */
  openedAt: string
}

class SubscriptionRegistry {
  private entries = new Map<string, SubscriptionEntry>()

  record(entry: SubscriptionEntry): void {
    this.entries.set(entry.handleId, entry)
  }

  /** Return a stable, insertion-ordered snapshot of current subscriptions. */
  list(): SubscriptionEntry[] {
    return Array.from(this.entries.values())
  }

  remove(handleId: string): void {
    this.entries.delete(handleId)
  }

  clear(): void {
    this.entries.clear()
  }

  size(): number {
    return this.entries.size
  }
}

let _registry: SubscriptionRegistry | null = null

export function getOrCreateSubscriptionRegistry(): SubscriptionRegistry {
  if (_registry === null) {
    _registry = new SubscriptionRegistry()
  }
  return _registry
}

export function resetSubscriptionRegistry(): void {
  if (_registry !== null) {
    _registry.clear()
    _registry = null
  }
}

// ---------------------------------------------------------------------------
// Tool-id → ministry display label.
//
// Best-effort string match against the prefix of the registered adapter
// tool_id. The list mirrors the canonical adapter naming convention from
// `docs/api/` (Spec 1637 catalog). Unknown prefixes fall back to the raw
// tool_id so the citizen still sees something meaningful — never an empty
// or generic placeholder.
//
// Audit-5 P1 fix (2026-05-04): the canonical mock subscribe adapters
// register as `mock_cbs_disaster_v1`, `mock_rss_public_notices_v1`, and
// `mock_rest_pull_tick_v1` (see kosmos.tools.mock.__init__). The prior
// regex set collapsed every `mock_*` id into the fallback "MOCK" leading
// token because no entry inspected the modality token after `mock_`. The
// modality-aware patterns below run BEFORE the agency-prefix patterns so
// `mock_cbs_*` resolves to "CBS" / `mock_rss_*` to "RSS" / `mock_rest_*`
// to "REST" — matching the citizen-visible categorization in proposal-iv
// (subscribe rows are dot-color green regardless of agency).
// ---------------------------------------------------------------------------

const MINISTRY_PREFIXES: Array<[RegExp, string]> = [
  // Mock subscribe adapters — modality-aware (must precede generic mock_).
  [/^mock_cbs_/i, 'CBS'],
  [/^mock_rss_/i, 'RSS'],
  [/^mock_rest_pull_/i, 'REST'],
  // Mock verify / submit adapters — keep agency token where present.
  [/^mock_verify_mobile_id/i, 'MOBILE-ID'],
  [/^mock_verify_mydata/i, 'MYDATA'],
  [/^mock_verify_module_/i, 'AUTH-MODULE'],
  [/^mock_verify_/i, 'VERIFY'],
  [/^mock_submit_module_/i, 'SUBMIT-MODULE'],
  [/^mock_submit_/i, 'SUBMIT'],
  // Generic mock_ fallback — surfaces "MOCK" instead of the leading token
  // so the citizen sees a coherent category for any new mock adapter that
  // doesn't yet have a modality-specific entry above.
  [/^mock_/i, 'MOCK'],
  // Live agency adapters — canonical prefix → agency label.
  [/^kma_/i, 'KMA'],
  [/^koroad_/i, 'KOROAD'],
  [/^hira_/i, 'HIRA'],
  [/^nmc_/i, 'NMC'],
  [/^mohw_/i, 'MOHW'],
  [/^nfa119_/i, 'NFA119'],
  [/^cbs_/i, 'CBS'],
  [/^kbs_/i, 'KBS'],
  [/^safety_/i, '안전처'],
  [/^disaster_/i, '재난처'],
  [/^plugin\./i, '플러그인'],
]

export function deriveMinistryFromToolId(toolId: string): string {
  for (const [regex, label] of MINISTRY_PREFIXES) {
    if (regex.test(toolId)) return label
  }
  // Fallback: use the leading token before underscore/dot
  const head = toolId.split(/[._]/)[0]
  return head && head.length > 0 ? head.toUpperCase() : toolId
}
