// SPDX-License-Identifier: Apache-2.0
// Source: .references/claude-code-sourcemap/restored-src/src/components/HelpV2/ (CC 2.1.88, research-use)
// Spec 1635 P4 UI L2 — T060 HelpV2Grouped (FR-029, US5).
//
// Renders the /help 4-group output: Session / Permission / Tool / Storage.
// Consumes groupCatalog(UI_L2_SLASH_COMMANDS) as SSOT — no inline command list.
// Visual layout mirrors CC HelpV2/Commands.tsx at ≥90% fidelity (FR-034 / SC-009).

import React from 'react';
import { Box, Text, useInput } from 'ink';
import { useKeybinding } from '../../keybindings/useKeybinding.js';
import { useTheme } from '../../theme/provider.js';
import {
  groupCatalog,
  GROUP_ORDER,
  type SlashCommandGroupT,
} from '../../schemas/ui-l2/slash-command.js';
import {
  UI_L2_SLASH_COMMANDS,
  type SlashCommandCatalogEntryT,
} from '../../commands/catalog.js';
import { useUiL2I18n } from '../../i18n/uiL2.js';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export type HelpV2GroupedProps = {
  /** Called when the citizen dismisses (presses Escape). */
  onDismiss?: () => void;
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function groupLabel(group: SlashCommandGroupT, i18n: ReturnType<typeof useUiL2I18n>): string {
  switch (group) {
    case 'session':    return i18n.helpGroupSession;
    case 'permission': return i18n.helpGroupPermission;
    case 'tool':       return i18n.helpGroupTool;
    case 'storage':    return i18n.helpGroupStorage;
  }
}

function formatArgSig(sig: string | null): string {
  return sig ? ` ${sig}` : '';
}

// ---------------------------------------------------------------------------
// CommandRow — single command entry inside a group
// ---------------------------------------------------------------------------

function CommandRow({ entry }: { entry: SlashCommandCatalogEntryT }): React.ReactElement {
  const theme = useTheme();
  const locale = process.env['KOSMOS_TUI_LOCALE'] ?? 'ko';
  const description = locale === 'en' ? entry.description_en : entry.description_ko;

  return (
    <Box paddingLeft={2} marginBottom={0}>
      <Box width={28} flexShrink={0}>
        <Text bold color={theme.kosmosCore}>
          {entry.name}
          <Text color={theme.subtle}>{formatArgSig(entry.arg_signature)}</Text>
        </Text>
      </Box>
      <Text color={theme.text} wrap="truncate-end">
        {description}
      </Text>
    </Box>
  );
}

// ---------------------------------------------------------------------------
// GroupSection — one of the four help groups
// ---------------------------------------------------------------------------

function GroupSection({
  group,
  entries,
  label,
}: {
  group: SlashCommandGroupT;
  entries: SlashCommandCatalogEntryT[];
  label: string;
}): React.ReactElement {
  const theme = useTheme();

  if (entries.length === 0) return <></>;

  return (
    <Box flexDirection="column" marginBottom={1}>
      <Box paddingLeft={1} marginBottom={0}>
        <Text bold color={theme.wordmark}>
          {`─── ${label} ───`}
        </Text>
      </Box>
      {entries.map((entry) => (
        <CommandRow key={entry.name} entry={entry} />
      ))}
    </Box>
  );
}

// ---------------------------------------------------------------------------
// HelpV2Grouped — main exported component (T060)
// ---------------------------------------------------------------------------

/**
 * Renders all KOSMOS slash commands grouped into the four canonical sections:
 * Session / Permission / Tool / Storage (FR-029).
 *
 * Data sourced from `UI_L2_SLASH_COMMANDS` via `groupCatalog()` — never
 * hard-coded inline.  The component is stateless and pure-display; dismiss
 * callback is forwarded from the /help command handler (T061).
 */
export function HelpV2Grouped({ onDismiss }: HelpV2GroupedProps): React.ReactElement {
  const theme = useTheme();
  const i18n = useUiL2I18n();
  const grouped = groupCatalog(UI_L2_SLASH_COMMANDS);

  // Defense-in-depth: register both `useKeybinding('help:dismiss')` for
  // the CC HelpV2 keybinding-registry contract and a direct `useInput`
  // Escape watcher for runtimes whose keybinding chord registry does NOT
  // bind `help:dismiss → Escape` by default (Tier 1 chord catalogue
  // covers a fixed set; `help:dismiss` is not Tier 1 in KOSMOS, so the
  // useKeybinding path needs a useInput fallback to actually fire on
  // raw Escape bytes from the PTY). With the Bun-native PTY harness
  // delivering raw `\x1b` immediately (no tmux escape-time race), the
  // useInput branch is the path that actually triggers in
  // integration-verification frame 28+.
  useKeybinding('help:dismiss', () => {
    onDismiss?.();
  }, { context: 'Help' });
  useInput((_input, key) => {
    if (!onDismiss) return;
    if (key.escape) {
      onDismiss();
    }
  });

  return (
    <Box flexDirection="column" paddingX={1} paddingY={1}>
      {/* Header — mirrors CC HelpV2 title bar */}
      <Box marginBottom={1}>
        <Text bold color={theme.kosmosCore}>
          {'✻ KOSMOS · '}
        </Text>
        <Text color={theme.wordmark}>
          {'도움말 / Help'}
        </Text>
      </Box>

      {/* Four group sections in canonical order */}
      {GROUP_ORDER.map((group) => (
        <GroupSection
          key={group}
          group={group}
          entries={grouped[group]}
          label={groupLabel(group, i18n)}
        />
      ))}

      {/* Footer dismiss hint — mirrors CC HelpV2 footer */}
      <Box marginTop={1}>
        <Text dimColor>
          {'Esc · 닫기 (dismiss)'}
          {onDismiss ? '' : ''}
        </Text>
      </Box>
    </Box>
  );
}
