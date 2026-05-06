// SPDX-License-Identifier: Apache-2.0
// Source: specs/288-shortcut-tier1-port/contracts/keybinding-schema.ts (Spec 288)
//
// Verbatim copy of the contract type surface. This file is the source of
// truth for every consumer in tui/src/keybindings/ and tui/src/components/
// history/. Any deviation between this file and the contract is a Spec 288
// violation. Re-exported from ./index.ts.
//
// The runtime registry/resolver/announcer ports (T012/T013/T014/T015) live
// in sibling files; this module contributes only the types they implement.

// -----------------------------------------------------------------------------
// Legacy types — retained for the legacy resolver/parser/validate surface.
// ParsedKeystroke, Chord, KeybindingBlock, KeybindingContextName, and
// ParsedBinding were previously defined elsewhere; they live here so every
// import of `./types` (or `./types.js`) resolves without error.
// -----------------------------------------------------------------------------

/** A parsed keystroke with modifier flags. Matches the shape built by parser.ts. */
export type ParsedKeystroke = {
  key: string
  ctrl: boolean
  alt: boolean
  shift: boolean
  meta: boolean
  super: boolean
}

/** An ordered sequence of keystrokes forming a chord (e.g. ctrl+k ctrl+s). */
export type Chord = ParsedKeystroke[]

/**
 * A broad context name string used by the legacy resolver/validate surface.
 * Intentionally wider than the Spec 288 `KeybindingContext` union — the legacy
 * system accepts any string context (e.g. "Autocomplete", "Plugin", etc.).
 */
export type KeybindingContextName = string

/**
 * A block in the legacy JSON keybindings format:
 *   { "context": "Chat", "bindings": { "ctrl+k": "history-search" } }
 */
export type KeybindingBlock = {
  context: string
  bindings: Record<string, string | null>
}

/**
 * A single parsed binding from a KeybindingBlock row.
 * `action` is null when the chord is explicitly unbound.
 */
export type ParsedBinding = Readonly<{
  chord: ParsedKeystroke[]
  action: string | null
  context: KeybindingContextName
}>

// -----------------------------------------------------------------------------
// Context enum — narrowed subset of CC's 18 contexts
// -----------------------------------------------------------------------------

export const KEYBINDING_CONTEXTS = [
  'Global',
  'Chat',
  'HistorySearch',
  'Confirmation',
] as const
export type KeybindingContext = (typeof KEYBINDING_CONTEXTS)[number]

export const KEYBINDING_CONTEXT_DESCRIPTIONS: Record<
  KeybindingContext,
  string
> = {
  Global: 'Always active unless claimed by a higher-priority context',
  Chat: 'Input bar focused',
  HistorySearch: 'Ctrl+R history search overlay open',
  Confirmation: 'Permission or consent prompt open',
}

// -----------------------------------------------------------------------------
// Tier 1 action enum — exactly seven actions
// -----------------------------------------------------------------------------

// Tier 1 = the actions whose chords are loaded into the runtime
// `KeybindingProvider`. Spec 288 originally limited Tier 1 to seven
// Korean-named actions; KOSMOS code paths (CtrlOToExpand, REPL, Messages, …)
// however call `useKeybinding(...)` and `getDisplayText(...)` with the
// CC-namespaced action ids that are byte-identical with the restored CC
// reference. Without those ids in Tier 1, the chord-aware path fails for
// every Ctrl+O / Ctrl+T / etc. press — see Epic #2766 follow-up
// (root-cause capture under `specs/integration-verification/`).
//
// Adding the CC ids here is the minimum viable fix: it does NOT replace
// the Korean action names (those remain reserved + first-class), it
// merely lets the existing CC-port surface area resolve through the same
// chord registry without needing a per-callsite useInput fallback.
//
// Reference: `.references/claude-code-sourcemap/restored-src/src/keybindings/schema.ts`
// (full action namespace) — only the actively wired-up actions are added
// here; the remainder will follow when their callsites are ported (Epic
// pending: full CC keybinding parity).
export const TIER_ONE_ACTIONS = [
  // KOSMOS-coined Tier 1 actions
  'agent-interrupt',
  'session-exit',
  'draft-cancel',
  'history-search',
  'history-prev',
  'history-next',
  'permission-mode-cycle',
  // CC-namespaced actions actively wired by REPL.tsx / CtrlOToExpand /
  // GlobalKeybindingHandlers and required for citizen-facing UX.
  'app:toggleTranscript',
] as const
export type TierOneAction = (typeof TIER_ONE_ACTIONS)[number]

// -----------------------------------------------------------------------------
// Chord grammar — mirrors CC parser.ts
// -----------------------------------------------------------------------------

export type Modifier = 'ctrl' | 'shift' | 'alt' | 'meta'
export const MODIFIER_ORDER: readonly Modifier[] = [
  'ctrl',
  'shift',
  'alt',
  'meta',
] as const

// Branded string. Construct via parser.ts (Lead-owned, T004); this module
// only narrows from `string` for type-flow. The `__brand` is unique-symbol
// so unsafe casts are caught at compile time.
declare const CHORD_BRAND: unique symbol
export type ChordString = string & { readonly [CHORD_BRAND]: 'ChordString' }

// -----------------------------------------------------------------------------
// KeybindingEntry — one row in the registry
// -----------------------------------------------------------------------------

export type KeybindingEntry = Readonly<{
  action: TierOneAction
  default_chord: ChordString
  effective_chord: ChordString | null
  context: KeybindingContext
  description: string
  remappable: boolean
  reserved: boolean
  mutates_buffer: boolean
}>

// -----------------------------------------------------------------------------
// Runtime event + resolution
// -----------------------------------------------------------------------------

export type ChordEvent = Readonly<{
  raw: string
  chord: ChordString
  ctrl: boolean
  shift: boolean
  alt: boolean
  meta: boolean
  timestamp: number
}>

export type BlockedReason =
  | 'ime-composing'
  | 'buffer-non-empty'
  | 'permission-mode-blocked'
  | 'consent-out-of-scope'

export type ResolutionResult =
  | Readonly<{
      kind: 'dispatched'
      action: TierOneAction
      context: KeybindingContext
    }>
  | Readonly<{ kind: 'blocked'; action: TierOneAction; reason: BlockedReason }>
  | Readonly<{ kind: 'no-match' }>
  | Readonly<{
      kind: 'double-press-armed'
      action: TierOneAction
      expires_at: number
    }>
  | Readonly<{ kind: 'double-press-fired'; action: TierOneAction }>

// -----------------------------------------------------------------------------
// Registry surface — consumed by useKeybinding hook (T018)
// -----------------------------------------------------------------------------

export interface KeybindingRegistry {
  readonly entries: ReadonlyMap<TierOneAction, KeybindingEntry>
  lookupByChord(
    chord: ChordString,
    context: KeybindingContext,
  ): KeybindingEntry | null
  describe(action: TierOneAction): string
}

// -----------------------------------------------------------------------------
// User override loader contract
// -----------------------------------------------------------------------------

export type UserOverrideEntry = {
  chord: ChordString
  action: TierOneAction | null
}

export interface UserOverrideLoader {
  load(path: string): ReadonlyArray<UserOverrideEntry>
  // Contract: MUST NOT throw on missing/invalid file (FR-023, FR-024).
  //          Parse errors logged; defaults applied.
}

// -----------------------------------------------------------------------------
// Accessibility announcer contract (KWCAG 2.1 § 4.1.3)
// -----------------------------------------------------------------------------

export type AnnouncementPriority = 'polite' | 'assertive'

export interface AccessibilityAnnouncer {
  announce(
    message: string,
    options?: { priority?: AnnouncementPriority },
  ): void
  // Contract: message MUST reach the screen-reader channel within 1 s (FR-030).
}

// -----------------------------------------------------------------------------
// Audit + cancellation integration contracts
// -----------------------------------------------------------------------------

export type ReservedActionAuditPayload = Readonly<{
  event_type: 'user-interrupted' | 'session-exited'
  session_id: string
  interrupted_tool_call_id?: string
}>

export interface AuditWriter {
  writeReservedAction(payload: ReservedActionAuditPayload): Promise<void>
}

export interface CancellationSignal {
  cancelActiveAgentLoop(session_id: string): Promise<void>
}
