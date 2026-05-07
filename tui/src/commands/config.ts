// SPDX-License-Identifier: Apache-2.0
// Spec 1635 P4 UI L2 — T064 /config command (FR-030, US5).
//
// Opens the ConfigOverlay for non-secret settings.
// Emits kosmos.ui.surface=config at command start (FR-037).

import { emitSurfaceActivation } from '../observability/surface.js';
import type { ConfigEntry } from '../components/config/ConfigOverlay.js';

// ---------------------------------------------------------------------------
// Static config catalog
// ---------------------------------------------------------------------------

// KOSMOS non-secret settings exposed in the overlay.
// Values are read from env at command time (never hardcoded).
export const KOSMOS_CONFIG_CATALOG: Omit<ConfigEntry, 'value'>[] = [
  {
    key: 'KOSMOS_TUI_LOCALE',
    label_ko: '표시 언어 (ko/en)',
    label_en: 'Display language (ko/en)',
    isSecret: false,
  },
  {
    key: 'KOSMOS_TUI_THEME',
    label_ko: '테마 (default/dark/light)',
    label_en: 'Theme (default/dark/light)',
    isSecret: false,
  },
  {
    key: 'KOSMOS_TUI_STREAM_CHUNK_TOKENS',
    label_ko: '스트리밍 chunk 토큰 수',
    label_en: 'Streaming chunk token count',
    isSecret: false,
  },
  {
    key: 'KOSMOS_AGENT_MAILBOX_ROOT',
    label_ko: '에이전트 메일박스 경로',
    label_en: 'Agent mailbox root path',
    isSecret: false,
  },
  {
    key: 'KOSMOS_OTLP_ENDPOINT',
    label_ko: 'OTLP 수집기 엔드포인트',
    label_en: 'OTLP collector endpoint',
    isSecret: false,
  },
];

// ---------------------------------------------------------------------------
// Result type
// ---------------------------------------------------------------------------

export type ConfigCommandResult = {
  /** Config entries populated with current env values */
  entries: ConfigEntry[];
  /** Whether the command should open the secret editor for a specific key */
  openSecretEditorFor: string | null;
};

// ---------------------------------------------------------------------------
// Command handler (T064)
// ---------------------------------------------------------------------------

/**
 * Execute the /config command.
 *
 * Emits `kosmos.ui.surface=config` (FR-037) and returns the config entry
 * list with current env values read at call time.
 *
 * @param openSecretFor  If provided, immediately routes to the secret editor
 *                       for that key (used for direct deep-links).
 */
export function executeConfig(openSecretFor?: string): ConfigCommandResult {
  // FR-037: emit surface activation at command start
  emitSurfaceActivation('config');

  const entries: ConfigEntry[] = KOSMOS_CONFIG_CATALOG.map((template) => ({
    ...template,
    value: process.env[template.key] ?? '',
  }));

  return {
    entries,
    openSecretEditorFor: openSecretFor ?? null,
  };
}

/**
 * Persist non-secret config changes.
 *
 * Writes non-secret values back to process.env (session-scope only).
 * Callers are responsible for persisting to .env files if desired.
 * Secret values MUST NOT be passed to this function — route them through
 * EnvSecretIsolatedEditor.onConfirm instead.
 */
export function applyConfigChanges(entries: ConfigEntry[]): void {
  for (const entry of entries) {
    if (entry.isSecret) continue; // safety guard — never apply secrets here
    if (entry.value !== '') {
      process.env[entry.key] = entry.value;
    }
  }
}
