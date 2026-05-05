// SPDX-License-Identifier: Apache-2.0
// Spec 288 — Tier 1 keybinding defaults.
//
// This file exports KOSMOS Tier 1 defaults as a flat `KeybindingEntry[]` so
// the registry, loader, and validate tests consume a single typed surface.
// The old `KeybindingBlock[]` format is retained under `DEFAULT_BINDING_BLOCKS`
// for the legacy `KeybindingSetup` component; it is NOT the canonical source.

import { parseChord } from './chord'
import type { ChordString, KeybindingContext, KeybindingEntry, TierOneAction } from './types'
import { getPlatform } from '../utils/platform.js'
import { isRunningWithBun } from '../utils/bundledMode.js'
import { satisfies } from 'src/utils/semver.js'

// Platform-specific image paste shortcut:
// - Windows: alt+v (ctrl+v is system paste)
// - Other platforms: ctrl+v
const IMAGE_PASTE_KEY = getPlatform() === 'windows' ? 'alt+v' : 'ctrl+v'

// Modifier-only chords (like shift+tab) may fail on Windows Terminal without VT mode
const SUPPORTS_TERMINAL_VT_MODE =
  getPlatform() !== 'windows' ||
  (isRunningWithBun()
    ? satisfies(process.versions.bun, '>=1.2.23')
    : satisfies(process.versions.node, '>=22.17.0 <23.0.0 || >=24.2.0'))

// Platform-specific mode cycle shortcut:
// - Windows without VT mode: meta+m → normalised to alt+m
// - Other platforms: shift+tab
const MODE_CYCLE_KEY: string = SUPPORTS_TERMINAL_VT_MODE ? 'shift+tab' : 'alt+m'

// Exported so tests can assert it is one of the two documented values.
export const MODE_CYCLE_DEFAULT_CHORD: string = MODE_CYCLE_KEY

// ---------------------------------------------------------------------------
// Tier 1 registry entries
// ---------------------------------------------------------------------------

function entry(
  action: TierOneAction,
  defaultChordStr: string,
  context: KeybindingContext,
  description: string,
  opts: { remappable?: boolean; reserved?: boolean; mutates_buffer?: boolean } = {},
): KeybindingEntry {
  const default_chord = parseChord(defaultChordStr)
  return Object.freeze({
    action,
    default_chord,
    effective_chord: default_chord,
    context,
    description,
    remappable: opts.remappable ?? true,
    reserved: opts.reserved ?? false,
    mutates_buffer: opts.mutates_buffer ?? false,
  })
}

export const DEFAULT_BINDINGS: ReadonlyArray<KeybindingEntry> = Object.freeze([
  entry('agent-interrupt', 'ctrl+c', 'Global',
    '에이전트 루프를 중단합니다. 두 번 누르면 세션을 종료합니다.',
    { remappable: false, reserved: true }),
  entry('session-exit', 'ctrl+d', 'Global',
    '세션을 안전하게 종료합니다. 빈 입력 창에서만 동작합니다.',
    { remappable: false, reserved: true }),
  entry('draft-cancel', 'escape', 'Chat',
    '입력 초안을 비웁니다.',
    { remappable: true, reserved: false, mutates_buffer: true }),
  entry('history-search', 'ctrl+r', 'Global',
    '이력 검색 오버레이를 엽니다.',
    { remappable: true, reserved: false }),
  entry('history-prev', 'up', 'Chat',
    '이전 질문을 불러옵니다.',
    { remappable: true, reserved: false }),
  entry('history-next', 'down', 'Chat',
    '다음 질문을 불러옵니다.',
    { remappable: true, reserved: false }),
  entry('permission-mode-cycle', MODE_CYCLE_KEY, 'Global',
    '권한 모드를 순환합니다 (default → acceptEdits → bypassPermissions → plan).',
    { remappable: true, reserved: false }),
])

// ---------------------------------------------------------------------------
// Helpers consumed by loader, registry, and tests
// ---------------------------------------------------------------------------

/**
 * Returns a Map from TierOneAction to its KeybindingEntry (based on defaults).
 * Tests and the registry use this to build or compare against defaults.
 */
export function defaultBindingsByAction(): ReadonlyMap<TierOneAction, KeybindingEntry> {
  const m = new Map<TierOneAction, KeybindingEntry>()
  for (const e of DEFAULT_BINDINGS) {
    m.set(e.action, e)
  }
  return m
}

/**
 * Get the path to the user keybindings file.
 * Extracted here to avoid circular imports between loadUserBindings and defaultBindings.
 */
export function getKeybindingsPath(): string {
  const { join } = require('path') as typeof import('path')
  const { getClaudeConfigHomeDir } = require('../utils/envUtils.js') as typeof import('../utils/envUtils.js')
  return join(getClaudeConfigHomeDir(), 'keybindings.json')
}

// ---------------------------------------------------------------------------
// Legacy `KeybindingBlock[]` surface for the `KeybindingSetup` component.
// We import `feature` lazily to avoid breaking the block declarations.
// ---------------------------------------------------------------------------

import type { KeybindingBlock } from './types.js'
import { feature } from 'bun:bundle'

export const DEFAULT_BINDING_BLOCKS: KeybindingBlock[] = [
  {
    context: 'Global',
    bindings: {
      'ctrl+c': 'app:interrupt',
      'ctrl+d': 'app:exit',
      'ctrl+l': 'app:redraw',
      'ctrl+t': 'app:toggleTodos',
      'ctrl+o': 'app:toggleTranscript',
      ...(feature('KAIROS') || feature('KAIROS_BRIEF')
        ? { 'ctrl+shift+b': 'app:toggleBrief' as const }
        : {}),
      'ctrl+shift+o': 'app:toggleTeammatePreview',
      'ctrl+r': 'history:search',
      ...(feature('QUICK_SEARCH')
        ? {
            'ctrl+shift+f': 'app:globalSearch' as const,
            'cmd+shift+f': 'app:globalSearch' as const,
            'ctrl+shift+p': 'app:quickOpen' as const,
            'cmd+shift+p': 'app:quickOpen' as const,
          }
        : {}),
      ...(feature('TERMINAL_PANEL') ? { 'meta+j': 'app:toggleTerminal' } : {}),
    },
  },
  {
    context: 'Chat',
    bindings: {
      escape: 'chat:cancel',
      'ctrl+x ctrl+k': 'chat:killAgents',
      [MODE_CYCLE_KEY]: 'chat:cycleMode',
      'meta+p': 'chat:modelPicker',
      'meta+o': 'chat:fastMode',
      'meta+t': 'chat:thinkingToggle',
      enter: 'chat:submit',
      up: 'history:previous',
      down: 'history:next',
      'ctrl+_': 'chat:undo',
      'ctrl+shift+-': 'chat:undo',
      'ctrl+x ctrl+e': 'chat:externalEditor',
      'ctrl+g': 'chat:externalEditor',
      'ctrl+s': 'chat:stash',
      [IMAGE_PASTE_KEY]: 'chat:imagePaste',
      ...(feature('MESSAGE_ACTIONS')
        ? { 'shift+up': 'chat:messageActions' as const }
        : {}),
      ...(feature('VOICE_MODE') ? { space: 'voice:pushToTalk' } : {}),
    },
  },
  {
    context: 'HistorySearch',
    bindings: {
      'ctrl+r': 'historySearch:next',
      escape: 'historySearch:accept',
      tab: 'historySearch:accept',
      'ctrl+c': 'historySearch:cancel',
      enter: 'historySearch:execute',
    },
  },
  {
    context: 'Confirmation',
    bindings: {
      y: 'confirm:yes',
      n: 'confirm:no',
      enter: 'confirm:yes',
      escape: 'confirm:no',
      up: 'confirm:previous',
      down: 'confirm:next',
      tab: 'confirm:nextField',
      space: 'confirm:toggle',
      'shift+tab': 'confirm:cycleMode',
      'ctrl+e': 'confirm:toggleExplanation',
      'ctrl+d': 'permission:toggleDebug',
    },
  },
  // Audit-4 P0-1 fix — Select context navigation chords. CC's Select
  // component (tui/src/components/CustomSelect/use-select-input.ts) is
  // entirely keybinding-driven: Enter/Up/Down/Escape resolve via
  // useKeybindings({ 'select:accept': ..., 'select:next': ..., ... }).
  // Without these chords the Permission Gauntlet Select stays frozen on
  // the first option. This block is consumed by
  // loadKeybindingsSyncWithWarnings (loadUserBindings.ts) and merged
  // into the runtime ChordInterceptor binding set.
  {
    context: 'Select',
    bindings: {
      enter: 'select:accept',
      escape: 'select:cancel',
      up: 'select:previous',
      down: 'select:next',
    },
  },
  // G2 fix (PR #2773 — realuse-audit-2026-05-05 § G2) — Autocomplete
  // context chords. AGENTS.md infra-insight #4: useTypeahead.tsx:1276
  // calls `useKeybindings(autocompleteHandlers, { context: 'Autocomplete' })`
  // and registers handlers for `autocomplete:dismiss / accept / previous /
  // next`, but the chord registry never resolved Esc/Tab/Up/Down to those
  // actions (the chord block was missing, so resolveKeyWithChordState
  // returned `none`). Esc then fell through to PromptInput's main useInput
  // which has no autocomplete-clear branch — citizens reported Esc as a
  // no-op while suggestions were visible (F-alpha-04). Mirrors CC
  // restored-src defaultBindings.ts line 100.
  {
    context: 'Autocomplete',
    bindings: {
      tab: 'autocomplete:accept',
      escape: 'autocomplete:dismiss',
      up: 'autocomplete:previous',
      down: 'autocomplete:next',
    },
  },
  // G2 fix (PR #2773) — Help overlay dismiss chord. HelpV2Grouped.tsx:132
  // calls `useKeybinding('help:dismiss', ..., { context: 'Help' })` to
  // honour the CC HelpV2 keybinding-registry contract; without an
  // Esc-bound chord the keybinding path was a no-op. The component already
  // pairs the `useKeybinding` with a direct `useInput((_, k) => k.escape
  // && onDismiss())` fallback (defense-in-depth, AGENTS.md insight #4),
  // but adding the chord here aligns the registry path with CC and stops
  // Esc from leaking into the Chat-context `draft-cancel` action while
  // /help is open (F-alpha-05, F-delta-04). Mirrors CC line 215.
  {
    context: 'Help',
    bindings: {
      escape: 'help:dismiss',
    },
  },
]
