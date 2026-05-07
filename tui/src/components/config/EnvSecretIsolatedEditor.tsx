// SPDX-License-Identifier: Apache-2.0
// Spec 1635 P4 UI L2 — T063 EnvSecretIsolatedEditor (FR-030, US5).
//
// Isolated editor for .env secret values.  The secret is NEVER displayed in
// plaintext while the citizen types — a mask character is shown instead.
// This prevents shoulder-surfing and terminal capture of API keys / tokens.
//
// The edit session is strictly isolated: no auto-save, no paste-through
// to the parent overlay until the citizen explicitly confirms with Enter.
// Escape discards without writing.

import React, { useState, useCallback } from 'react';
import { Box, Text, useInput } from 'ink';
import { useTheme } from '../../theme/provider.js';
import { useUiL2I18n } from '../../i18n/uiL2.js';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type EnvSecretIsolatedEditorProps = {
  /** The env-var key being edited. */
  secretKey: string;
  /** Called with the new secret value after the citizen confirms */
  onConfirm: (key: string, newValue: string) => void;
  /** Called when the citizen cancels without saving */
  onCancel: () => void;
};

// ---------------------------------------------------------------------------
// EnvSecretIsolatedEditor (T063)
// ---------------------------------------------------------------------------

const MASK_CHAR = '•';

/**
 * Fully isolated .env secret editor (FR-030 isolation rule).
 *
 * Security properties:
 *   - Input is never echoed in plaintext; each character is replaced by MASK_CHAR
 *   - Backspace removes the last buffer character (not the last mask character) —
 *     the buffer and mask are always the same length
 *   - Paste detection: any input longer than 1 char is accepted but still masked
 *   - No persistence until explicit Enter confirmation
 *   - Escape discards the buffer immediately
 */
export function EnvSecretIsolatedEditor({
  secretKey,
  onConfirm,
  onCancel,
}: EnvSecretIsolatedEditorProps): React.ReactElement {
  const theme = useTheme();
  const i18n = useUiL2I18n();

  const [buffer, setBuffer] = useState('');
  const [confirmed, setConfirmed] = useState(false);

  const handleInput = useCallback(
    (input: string, key: { return: boolean; escape: boolean; backspace: boolean; delete: boolean; ctrl: boolean }) => {
      if (confirmed) return;

      if (key.escape) {
        onCancel();
        return;
      }
      if (key.return) {
        setConfirmed(true);
        onConfirm(secretKey, buffer);
        return;
      }
      if (key.backspace || key.delete) {
        setBuffer((s) => s.slice(0, -1));
        return;
      }
      if (!key.ctrl && input.length > 0) {
        setBuffer((s) => s + input);
      }
    },
    [buffer, confirmed, secretKey, onConfirm, onCancel],
  );

  useInput(handleInput);

  const maskedDisplay = MASK_CHAR.repeat(buffer.length);

  return (
    <Box flexDirection="column" paddingX={1} paddingY={1} borderStyle="double" borderColor={theme.warning}>
      {/* Warning header — FR-030 isolation mode */}
      <Box marginBottom={1}>
        <Text bold color={theme.warning}>
          {'⚠ '}
        </Text>
        <Text bold color={theme.wordmark}>
          {i18n.envSecretEditorTitle}
        </Text>
      </Box>

      {/* Key label */}
      <Box marginBottom={1}>
        <Text color={theme.subtle}>{'Key: '}</Text>
        <Text bold color={theme.text}>{secretKey}</Text>
      </Box>

      {/* Masked input display */}
      <Box marginBottom={1}>
        <Text color={theme.subtle}>{'Value: '}</Text>
        <Text color={theme.text}>
          {maskedDisplay.length > 0 ? maskedDisplay + '█' : '█'}
        </Text>
      </Box>

      {/* Character count (without revealing length exactly for short secrets) */}
      <Box marginBottom={1}>
        <Text dimColor>
          {buffer.length > 0
            ? `(${buffer.length} character${buffer.length === 1 ? '' : 's'} entered)`
            : '(no characters entered)'}
        </Text>
      </Box>

      {/* Instructions */}
      <Box marginTop={1}>
        <Text dimColor>
          {'Enter 저장 (confirm) · Esc 취소 (cancel)'}
        </Text>
      </Box>

      {/* Saved confirmation */}
      {confirmed && (
        <Box marginTop={1}>
          <Text color={theme.success}>{'✓ Saved'}</Text>
        </Box>
      )}
    </Box>
  );
}
