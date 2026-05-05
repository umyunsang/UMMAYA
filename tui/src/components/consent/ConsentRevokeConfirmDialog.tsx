// SPDX-License-Identifier: Apache-2.0
// Epic 2 — /consent revoke <rcpt-id> confirmation modal (FR-020/021).
//
// CC reference: .references/claude-code-sourcemap/restored-src/src/components/permissions/PermissionRequest.tsx
//   (CC 2.1.88, research-use) — modal layout, Y/N/A key-handling pattern.
// KOSMOS adaptation: consent revoke scope, PIPA §36 citation, border+color
//   matching HelpV2Grouped (AGENTS.md "Infrastructure insights" #3/#4).
//
// Key-handling rules (AGENTS.md "Infrastructure insights" #4):
//   - useInput Esc fallback is MANDATORY because 'consent:revoke:dismiss' has no
//     chord in defaultBindings.ts.
//   - The caller MUST set isLocalJSXCommand: false so PromptInput.tsx:244's
//     isModalOverlayActive stays false and this component's useInput hooks fire.
//
// Props:
//   receipt  — the receipt being revoked (for display)
//   onConfirm(scope) — called when citizen presses Y or A
//   onCancel — called when citizen presses N or Esc
//   locale   — display locale ('ko' | 'en'), default 'ko'

import React from 'react';
import { Box, Text, useInput } from 'ink';
import { useTheme } from '../../theme/provider.js';
import type { PermissionReceiptT } from '../../schemas/ui-l2/permission.js';
import { LAYER_VISUAL } from '../../schemas/ui-l2/permission.js';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ConsentRevokeScope = 'once' | 'session-all';

export type ConsentRevokeConfirmDialogProps = {
  /** The receipt to be revoked (shown in the confirm summary). */
  receipt: PermissionReceiptT;
  /** Called when citizen presses Y (once) or A (session-all). */
  onConfirm: (scope: ConsentRevokeScope) => void;
  /** Called when citizen presses N or Esc. */
  onCancel: () => void;
  /** Display locale — defaults to 'ko'. */
  locale?: 'ko' | 'en';
};

// ---------------------------------------------------------------------------
// Locale strings
// ---------------------------------------------------------------------------

const STRINGS = {
  ko: {
    title: '권한 영수증 철회',
    subtitle: 'Consent receipt revocation',
    pipaNote:
      '개인정보보호법 제36조 정정·삭제권에 따라 귀하는 동의를 철회할 수 있습니다.',
    pipaNoteEn:
      'PIPA §36: You have the right to withdraw consent and request correction/deletion.',
    targetLabel: '철회 대상',
    toolLabel: '도구',
    layerLabel: '레이어',
    decisionLabel: '결정',
    dateLabel: '승인 일시',
    choicePrompt: '[Y] 이 영수증만 철회  [A] 세션 전체 철회  [N / Esc] 취소',
    alreadyRevoked: '이미 철회된 영수증입니다.',
    warningSession: '경고: [A]를 선택하면 현재 세션의 모든 영수증이 철회됩니다.',
  },
  en: {
    title: 'Consent Receipt Revocation',
    subtitle: '권한 영수증 철회',
    pipaNote:
      'PIPA §36: You have the right to withdraw consent and request correction/deletion.',
    pipaNoteEn:
      '개인정보보호법 제36조 정정·삭제권에 따라 귀하는 동의를 철회할 수 있습니다.',
    targetLabel: 'Target',
    toolLabel: 'Tool',
    layerLabel: 'Layer',
    decisionLabel: 'Decision',
    dateLabel: 'Approved at',
    choicePrompt: '[Y] This receipt only  [A] All session receipts  [N / Esc] Cancel',
    alreadyRevoked: 'This receipt has already been revoked.',
    warningSession: 'Warning: [A] will revoke ALL receipts in the current session.',
  },
} as const;

// ---------------------------------------------------------------------------
// ConsentRevokeConfirmDialog
// ---------------------------------------------------------------------------

/**
 * Confirmation modal for `/consent revoke <rcpt-id>`.
 *
 * Key bindings (AGENTS.md Infrastructure insights #3/#4):
 *   Y → onConfirm('once')
 *   A → onConfirm('session-all')
 *   N / Esc → onCancel()
 *
 * Caller MUST set `isLocalJSXCommand: false` when mounting via setToolJSX so
 * PromptInput's useInput hooks remain active and this component's Esc handler
 * fires (defense-in-depth per AGENTS.md insight #4).
 */
export function ConsentRevokeConfirmDialog({
  receipt,
  onConfirm,
  onCancel,
  locale = 'ko',
}: ConsentRevokeConfirmDialogProps): React.ReactElement {
  const theme = useTheme();
  const s = STRINGS[locale];
  const visual = LAYER_VISUAL[receipt.layer];
  const isRevoked = receipt.revoked_at !== null;
  const ts = receipt.decided_at.slice(0, 19).replace('T', ' ');

  // Primary key handler: Y, A, N.
  useInput((input, _key) => {
    const ch = input.toUpperCase();
    if (ch === 'Y') {
      onConfirm('once');
    } else if (ch === 'A') {
      onConfirm('session-all');
    } else if (ch === 'N') {
      onCancel();
    }
  });

  // Esc fallback — MANDATORY per AGENTS.md insight #4 (no chord in defaultBindings.ts).
  useInput((_input, key) => {
    if (key.escape) {
      onCancel();
    }
  });

  return (
    <Box
      flexDirection="column"
      paddingX={1}
      paddingY={1}
    >
      {/* Title bar — mirrors HelpV2Grouped pattern */}
      <Box marginBottom={1}>
        <Text bold color={theme.kosmosCore}>{'✻ KOSMOS · '}</Text>
        <Text color={theme.wordmark}>{s.title}</Text>
        <Text color={theme.subtle}>{' / '}</Text>
        <Text color={theme.subtle}>{s.subtitle}</Text>
      </Box>

      {/* PIPA §36 citation block */}
      <Box
        flexDirection="column"
        borderStyle="round"
        borderColor={theme.warning}
        paddingX={1}
        marginBottom={1}
      >
        <Text color={theme.warning} bold>{'PIPA §36'}</Text>
        <Text color={theme.text}>{s.pipaNote}</Text>
        <Text color={theme.subtle}>{s.pipaNoteEn}</Text>
      </Box>

      {/* Receipt summary */}
      <Box flexDirection="column" paddingLeft={2} marginBottom={1}>
        <Box>
          <Box width={18} flexShrink={0}>
            <Text color={theme.subtle}>{s.targetLabel}</Text>
          </Box>
          <Text color={theme.text}>{receipt.receipt_id}</Text>
        </Box>
        <Box>
          <Box width={18} flexShrink={0}>
            <Text color={theme.subtle}>{s.toolLabel}</Text>
          </Box>
          <Text color={theme.text}>{receipt.tool_name}</Text>
        </Box>
        <Box>
          <Box width={18} flexShrink={0}>
            <Text color={theme.subtle}>{s.layerLabel}</Text>
          </Box>
          <Text bold color={
            receipt.layer === 1 ? theme.success :
            receipt.layer === 2 ? theme.warning : theme.error
          }>
            {visual.glyph}{' L'}{receipt.layer}
          </Text>
        </Box>
        <Box>
          <Box width={18} flexShrink={0}>
            <Text color={theme.subtle}>{s.decisionLabel}</Text>
          </Box>
          <Text color={theme.text}>{receipt.decision}</Text>
        </Box>
        <Box>
          <Box width={18} flexShrink={0}>
            <Text color={theme.subtle}>{s.dateLabel}</Text>
          </Box>
          <Text color={theme.subtle}>{ts}</Text>
        </Box>
      </Box>

      {/* Already-revoked notice */}
      {isRevoked && (
        <Box paddingLeft={2} marginBottom={1}>
          <Text color={theme.warning}>{s.alreadyRevoked}</Text>
        </Box>
      )}

      {/* Session-all warning */}
      <Box paddingLeft={2} marginBottom={1}>
        <Text color={theme.subtle} dimColor>{s.warningSession}</Text>
      </Box>

      {/* Key choice prompt */}
      <Box paddingLeft={2} marginTop={1}>
        <Text bold color={theme.kosmosCore}>{s.choicePrompt}</Text>
      </Box>
    </Box>
  );
}
