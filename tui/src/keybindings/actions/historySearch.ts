// SPDX-License-Identifier: Apache-2.0
// Spec 288 · T037 — `history-search` action handler (User Story 6).
//
// Closes #1584. FR-020 / FR-021 / FR-022.
//
// Contract:
//   - On dispatch, the resolver invokes `openHistorySearchOverlay()` which
//     builds an `OverlayOpenRequest` carrying:
//       * the consent-scoped entries (current-session + optional cross-session
//         when memdir USER consent is granted, else current-session only),
//       * the saved input draft (so `escape` restores it byte-for-byte),
//       * an `announcer.announce()` call within 1 s of dispatch (FR-030).
//   - On `enter`, the selected entry's `query_text` becomes the new draft.
//   - On `escape`, the saved draft is restored verbatim.
//
// This handler is pure — it returns the request envelope rather than mounting
// a component itself. Runtime history search remains owned by the CC
// `components/HistorySearchDialog.tsx` path.

import {
  type AccessibilityAnnouncer,
  type AnnouncementPriority,
} from '../types'

// ---------------------------------------------------------------------------
// Inputs
// ---------------------------------------------------------------------------

export type HistoryEntry = Readonly<{
  query_text: string
  timestamp: string // ISO 8601
  session_id: string
  consent_scope: 'current-session' | 'cross-session'
}>

export type ConsentState = Readonly<{
  /** True when the citizen has granted memdir USER tier consent (Epic D). */
  memdir_user_granted: boolean
}>

export type HistorySearchActionInput = Readonly<{
  /** Whole history accessible to the layer (current + cross when present). */
  all_entries: ReadonlyArray<HistoryEntry>
  /** Current draft buffer text — restored verbatim on `escape` (FR-022). */
  saved_draft: string
  /** Consent-scope flags driving FR-021 filtering. */
  consent: ConsentState
  /** Announcer shim — required for FR-030. */
  announcer: AccessibilityAnnouncer
  /** Now epoch-millis for telemetry; injectable for tests. */
  now?: () => number
}>

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

export type OverlayOpenRequest = Readonly<{
  /** Filtered entries the citizen is allowed to see (FR-021). */
  visible_entries: ReadonlyArray<HistoryEntry>
  /** Saved draft preserved for byte-for-byte restore on escape (FR-022). */
  saved_draft: string
  /** True when consent gating excluded cross-session entries (FR-021 notice). */
  scope_notice: boolean
  /** Wall-clock millis at which the overlay was requested (for SLO checks). */
  opened_at: number
}>

// ---------------------------------------------------------------------------
// Filtering — consent scope (FR-021)
// ---------------------------------------------------------------------------

export function filterByConsentScope(
  entries: ReadonlyArray<HistoryEntry>,
  consent: ConsentState,
): ReadonlyArray<HistoryEntry> {
  if (consent.memdir_user_granted) return entries
  // Without USER consent: current-session entries only.  Out-of-scope rows
  // are silently filtered — the resolver still emits a `blocked` span with
  // `consent-out-of-scope` only when the citizen *attempts* to traverse
  // a prior-session entry; here we elide them up-front so they never even
  // surface in the overlay.
  return entries.filter((e) => e.consent_scope === 'current-session')
}

// ---------------------------------------------------------------------------
// Action handler — invoked by the resolver
// ---------------------------------------------------------------------------

const SCOPE_NOTICE_MESSAGE =
  '이력 검색 오버레이가 열렸습니다. 이전 세션 이력을 보려면 메모리 동의가 필요합니다.'
const FULL_SCOPE_MESSAGE = '이력 검색 오버레이가 열렸습니다.'

export function openHistorySearchOverlay(
  input: HistorySearchActionInput,
): OverlayOpenRequest {
  const { all_entries, saved_draft, consent, announcer } = input
  const now = (input.now ?? Date.now)()

  // Apply the consent gate once up-front (FR-021).
  const visible = filterByConsentScope(all_entries, consent)
  const scopeNotice = !consent.memdir_user_granted

  // FR-030 — every Tier 1 action emits an accessibility announcement
  // within 1 s of dispatch.  The announcer ships polite messages by
  // default; the scope notice escalates to assertive so screen readers
  // interrupt and read it (citizens learning the keymap miss it
  // otherwise).
  const priority: AnnouncementPriority = scopeNotice ? 'assertive' : 'polite'
  announcer.announce(
    scopeNotice ? SCOPE_NOTICE_MESSAGE : FULL_SCOPE_MESSAGE,
    { priority },
  )

  return Object.freeze({
    visible_entries: Object.freeze(visible.slice()),
    saved_draft,
    scope_notice: scopeNotice,
    opened_at: now,
  })
}

// ---------------------------------------------------------------------------
// Selection / cancel handlers — small but exported so the overlay stays
// purely presentational.
// ---------------------------------------------------------------------------

export type SelectionResult = Readonly<{
  kind: 'selected'
  next_draft: string
}>

export type CancelResult = Readonly<{
  kind: 'cancelled'
  next_draft: string
}>

export function selectHistoryEntry(
  entry: HistoryEntry,
  announcer: AccessibilityAnnouncer,
): SelectionResult {
  announcer.announce(
    `이력 검색에서 항목을 불러왔습니다: ${entry.query_text}`,
    { priority: 'polite' },
  )
  return Object.freeze({ kind: 'selected', next_draft: entry.query_text })
}

export function cancelHistorySearch(
  request: OverlayOpenRequest,
  announcer: AccessibilityAnnouncer,
): CancelResult {
  announcer.announce('이력 검색을 취소하고 입력창으로 돌아갑니다.', {
    priority: 'polite',
  })
  return Object.freeze({
    kind: 'cancelled',
    next_draft: request.saved_draft, // FR-022 — byte-for-byte restore
  })
}
