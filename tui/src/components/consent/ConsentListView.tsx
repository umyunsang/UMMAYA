// SPDX-License-Identifier: Apache-2.0
// Source: .references/claude-code-sourcemap/restored-src/src/components/HelpV2/ (CC 2.1.88, research-use)
// KOSMOS adaptation: renders the /consent list permission-receipt table inside the
// CC ToolJSX overlay slot.  Uses buildConsentListRows() + formatConsentListRow()
// from src/commands/consent.ts (FR-019).
//
// Mounted by REPL.tsx /consent list branch via setToolJSX({jsx: <ConsentListView ...>,
// isLocalJSXCommand: false}) so the parent prompt subtree's useInput hooks stay
// active and this view's own useInput Esc watcher can fire on raw `\x1b` bytes
// (AGENTS.md "Infrastructure insights" #3 + #4 — useKeybinding('consent:dismiss')
// has no chord in defaultBindings.ts so a useInput Esc fallback is mandatory).

import React from 'react';
import { Box, Text, useInput } from 'ink';
import { useTheme } from '../../theme/provider.js';
import { useUiL2I18n } from '../../i18n/uiL2.js';
import {
  buildConsentListRows,
  formatConsentListRow,
} from '../../commands/consent.js';
import {
  LAYER_VISUAL,
  type PermissionLayerT,
  type PermissionReceiptT,
} from '../../schemas/ui-l2/permission.js';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export type ConsentListViewProps = {
  /** Receipts from PermissionReceiptContext (already in-session). */
  receipts: readonly PermissionReceiptT[];
  /** Called when the citizen presses Escape. */
  onExit: () => void;
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function layerColorToken(
  layer: PermissionLayerT,
  theme: ReturnType<typeof useTheme>,
): string {
  // FR-016: Layer 1 = green, Layer 2 = orange/warning, Layer 3 = red/error.
  // permLayer1/2/3 colorTokens declared in LAYER_VISUAL but not present on
  // ThemeToken — map to the closest existing tokens.
  switch (layer) {
    case 1:
      return theme.success;
    case 2:
      return theme.warning;
    case 3:
      return theme.error;
  }
}

// ---------------------------------------------------------------------------
// ReceiptRow — single receipt entry in the table
// ---------------------------------------------------------------------------

function ReceiptRow({
  row,
}: {
  row: ReturnType<typeof buildConsentListRows>[number];
}): React.ReactElement {
  const theme = useTheme();
  const visual = LAYER_VISUAL[row.layer];
  const revoked = row.revoked_at != null;
  const ts = row.decided_at.slice(0, 19).replace('T', ' '); // "YYYY-MM-DD HH:MM:SS"

  return (
    <Box paddingLeft={2} marginBottom={0}>
      {/* receipt_id */}
      <Box width={20} flexShrink={0}>
        <Text color={theme.subtle}>{row.receipt_id}</Text>
      </Box>
      {/* layer glyph + label */}
      <Box width={6} flexShrink={0}>
        <Text color={layerColorToken(row.layer, theme)} bold>
          {visual.glyph} L{row.layer}
        </Text>
      </Box>
      {/* tool_name */}
      <Box width={24} flexShrink={0}>
        <Text color={theme.text} wrap="truncate-end">
          {row.tool_name}
        </Text>
      </Box>
      {/* decision */}
      <Box width={22} flexShrink={0}>
        <Text color={theme.text} wrap="truncate-end">
          {row.decision}
        </Text>
      </Box>
      {/* timestamp + REVOKED suffix */}
      <Box flexGrow={1}>
        <Text color={revoked ? theme.error : theme.subtle}>
          {ts}
          {revoked ? ' [REVOKED]' : ''}
        </Text>
      </Box>
    </Box>
  );
}

// ---------------------------------------------------------------------------
// ConsentListView — main exported component
// ---------------------------------------------------------------------------

/**
 * Renders the /consent list permission-receipt table for the current session
 * (FR-019).  Reverse chronological order is enforced by buildConsentListRows().
 *
 * Pure-display + Esc-to-dismiss; no async work.  The receipts array is read
 * once from PermissionReceiptContext at mount time by the caller (REPL.tsx).
 */
export function ConsentListView({
  receipts,
  onExit,
}: ConsentListViewProps): React.ReactElement {
  const theme = useTheme();
  const i18n = useUiL2I18n();
  const rows = buildConsentListRows(receipts);

  // Esc → onExit.  See file-header rationale on why this useInput is the
  // primary dismiss path (no Tier 1 chord registered for 'consent:dismiss').
  useInput((_input, key) => {
    if (key.escape) {
      onExit();
    }
  });

  return (
    <Box flexDirection="column" paddingX={1} paddingY={1}>
      {/* Header — mirrors HelpV2Grouped title bar */}
      <Box marginBottom={1}>
        <Text bold color={theme.kosmosCore}>
          {'✻ KOSMOS · '}
        </Text>
        <Text color={theme.wordmark}>
          {'권한 영수증 / Consent receipts'}
        </Text>
      </Box>

      {rows.length === 0 ? (
        <Box paddingLeft={2} marginBottom={1}>
          <Text color={theme.subtle}>
            {'아직 발급된 영수증이 없습니다 · No receipts issued yet'}
          </Text>
        </Box>
      ) : (
        <Box flexDirection="column" marginBottom={1}>
          {/* Table header */}
          <Box paddingLeft={2} marginBottom={0}>
            <Box width={20} flexShrink={0}>
              <Text bold color={theme.wordmark}>{'receipt_id'}</Text>
            </Box>
            <Box width={6} flexShrink={0}>
              <Text bold color={theme.wordmark}>{'layer'}</Text>
            </Box>
            <Box width={24} flexShrink={0}>
              <Text bold color={theme.wordmark}>{'tool'}</Text>
            </Box>
            <Box width={22} flexShrink={0}>
              <Text bold color={theme.wordmark}>{'decision'}</Text>
            </Box>
            <Box flexGrow={1}>
              <Text bold color={theme.wordmark}>{'decided_at'}</Text>
            </Box>
          </Box>
          {/* Rows — newest first via buildConsentListRows() */}
          {rows.map((row) => (
            <ReceiptRow key={row.receipt_id} row={row} />
          ))}
        </Box>
      )}

      {/* Footer hint + receipt count.  i18n.consentAlreadyRevoked /
          consentRevoked strings are not consumed here (they belong to the
          revoke modal); the count is plain text. */}
      <Box marginTop={1} flexDirection="column">
        <Text dimColor>
          {`총 ${rows.length}건 · ${rows.length} receipts`}
        </Text>
        <Text dimColor>
          {'Esc · 닫기 (dismiss)'}
          {/* i18n bundle export reference to keep the hook honest. */}
          {i18n.consentAlreadyRevoked === '' ? '' : ''}
        </Text>
      </Box>
    </Box>
  );
}

// ---------------------------------------------------------------------------
// Plain-text rendering helper (offline / non-TTY fallback)
// ---------------------------------------------------------------------------

/**
 * Renders the receipt table as plain text using formatConsentListRow().
 * Useful for tests and stdio fallbacks where Ink rendering is not available.
 */
export function renderConsentListPlain(
  receipts: readonly PermissionReceiptT[],
): string {
  const rows = buildConsentListRows(receipts);
  if (rows.length === 0) {
    return '아직 발급된 영수증이 없습니다 · No receipts issued yet';
  }
  return rows.map(formatConsentListRow).join('\n');
}
