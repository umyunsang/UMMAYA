// SPDX-License-Identifier: Apache-2.0
// Spec 2294 — KosmosPrimitivePermissionRequest component.
//
// Renders the KOSMOS permission gauntlet for the four reserved primitives:
//   lookup  → bypassed (null layer — this component is never rendered)
//   verify  → Layer 1 (green ⓵)
//   submit  → Layer 2 (orange ⓶) or Layer 3 (red ⓷) based on isIrreversible
//   subscribe → Layer 2 (orange ⓶)
//
// CC reference: .references/claude-code-sourcemap/restored-src/src/components/
//   permissions/PermissionRequest.tsx:47-80 (permissionComponentForTool switch).
//
// AGENTS.md insight #4 compliance:
//   - Direct useInput Esc fallback alongside useKeybinding to ensure dismiss
//     fires even when the action has no chord in defaultBindings.ts.

import React, { useCallback } from 'react'
import { Box, Text, useInput } from '../../../ink.js'
import { useKeybinding } from '../../../keybindings/useKeybinding.js'
import { LAYER_VISUAL } from '../../../schemas/ui-l2/permission.js'
import { aalToLayer, type KosmosPrimitive } from '../../../utils/permissions/aalToLayer.js'
import permissionKo from '../../../i18n/permission.ko.js'
import permissionEn from '../../../i18n/permission.en.js'
import { PermissionDialog } from '../PermissionDialog.js'
import { PermissionPrompt } from '../PermissionPrompt.js'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type PrimitiveDecision = 'allow_once' | 'allow_session' | 'deny'

export type KosmosPrimitivePermissionRequestProps = {
  /** The primitive verb triggering the gauntlet. */
  primitive: KosmosPrimitive
  /** Tool adapter name shown in the modal body. */
  toolName: string
  /**
   * For `submit` primitives: whether the action cannot be reversed.
   * Escalates from Layer 2 to Layer 3. Ignored for other primitives.
   */
  isIrreversible?: boolean
  /** Receipt ID from Spec 033 ledger; shown in modal footer. */
  receiptId?: string
  /** Worker badge (swarm mode) — forwarded to PermissionDialog. */
  workerBadge?: { label: string; color: string }
  /** Called when the user makes a decision. */
  onDecision: (decision: PrimitiveDecision) => void
  /** Called to close / unmount the component. */
  onDismiss: () => void
}

// ---------------------------------------------------------------------------
// Locale selection (mirrors tui/src/i18n/index.ts pattern)
// ---------------------------------------------------------------------------
const LOCALE = process.env['KOSMOS_TUI_LOCALE'] ?? 'ko'
const strings = LOCALE === 'en' ? permissionEn : permissionKo

// ---------------------------------------------------------------------------
// Helper — layer-based color token for PermissionDialog border
// ---------------------------------------------------------------------------
function layerToColorToken(layer: 1 | 2 | 3): string {
  return LAYER_VISUAL[layer].colorToken
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function KosmosPrimitivePermissionRequest({
  primitive,
  toolName,
  isIrreversible = false,
  receiptId,
  workerBadge,
  onDecision,
  onDismiss,
}: KosmosPrimitivePermissionRequestProps): React.ReactNode {
  const layer = aalToLayer(primitive, isIrreversible)

  // lookup → null layer means bypass; component should not be rendered.
  // Guard defensively nonetheless.
  if (layer === null) {
    return null
  }

  const visual = LAYER_VISUAL[layer]

  // ------------------------------------------------------------------
  // Modal title and body — switch on primitive (FR-005)
  // ------------------------------------------------------------------
  let title: string
  let body: string

  switch (primitive) {
    case 'verify':
      title = strings.verifyModalTitle
      body = strings.verifyModalBody(toolName)
      break
    case 'submit':
      title = strings.submitModalTitle(isIrreversible)
      body = strings.submitModalBody(toolName, isIrreversible)
      break
    case 'subscribe':
      title = strings.subscribeModalTitle
      body = strings.subscribeModalBody(toolName)
      break
    default:
      // lookup — should not reach here
      return null
  }

  // ------------------------------------------------------------------
  // Decision handlers
  // ------------------------------------------------------------------
  const handleSelect = useCallback(
    (value: PrimitiveDecision) => {
      onDecision(value)
      onDismiss()
    },
    [onDecision, onDismiss],
  )

  const handleDismiss = useCallback(() => {
    onDecision('deny')
    onDismiss()
  }, [onDecision, onDismiss])

  // ------------------------------------------------------------------
  // AGENTS.md insight #4: direct useInput Esc fallback in case
  // 'primitive:dismiss' has no chord in defaultBindings.ts yet.
  // ------------------------------------------------------------------
  useKeybinding('confirm:no' as never, handleDismiss, { isActive: true })
  useInput((_input, key) => {
    if (key.escape) {
      handleDismiss()
    }
  })

  // ------------------------------------------------------------------
  // Y / A / N selector (UI-C spec: Y=once / A=session / N=deny)
  // ------------------------------------------------------------------
  const options = [
    { label: strings.selectorAllowOnce, value: 'allow_once' as PrimitiveDecision },
    { label: strings.selectorAllowSession, value: 'allow_session' as PrimitiveDecision },
    { label: strings.selectorDeny, value: 'deny' as PrimitiveDecision },
  ]

  // ------------------------------------------------------------------
  // Layer label line (e.g. "⓵ 낮은 위험 (레이어 1)")
  // ------------------------------------------------------------------
  const layerLabel =
    layer === 1
      ? strings.layer1Label
      : layer === 2
        ? strings.layer2Label
        : strings.layer3Label

  return (
    <PermissionDialog
      title={title}
      color={layerToColorToken(layer) as never}
      workerBadge={workerBadge as never}
    >
      {/* Layer indicator */}
      <Box paddingX={2} paddingTop={1}>
        <Text bold>
          {visual.glyph} {layerLabel}
        </Text>
      </Box>

      {/* Body text (tool name + PIPA citation) */}
      <Box paddingX={2} paddingBottom={1}>
        <Text dimColor={false}>{body}</Text>
      </Box>

      {/* Y / A / N prompt */}
      <PermissionPrompt
        options={options}
        onSelect={handleSelect}
        onCancel={handleDismiss}
        question={`"${toolName}" 실행을 허용하시겠습니까?`}
      />

      {/* PIPA notice + optional receipt ID */}
      <Box paddingX={2} paddingBottom={1} flexDirection="column">
        <Text dimColor>{strings.pipaNotice}</Text>
        {receiptId != null && (
          <Text dimColor>{strings.receiptIdLabel(receiptId)}</Text>
        )}
      </Box>
    </PermissionDialog>
  )
}
