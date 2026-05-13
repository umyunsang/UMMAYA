// SPDX-License-Identifier: Apache-2.0
// Spec 2294 — SSOT for AAL→Layer mapping.
//
// FR-005 matrix (canonical, do not duplicate elsewhere):
//   find             → null  (bypass — no permission gauntlet)
//   check (any AAL)  → 1     (green ⓵, low risk)
//   send (non-irr)   → 2     (orange ⓶, medium risk)
//   send (irr=true)  → 3     (red ⓷, high risk)
//
// Previously scattered across:
//   src/ummaya/tools/policy_derivation.py:57
//   src/ummaya/cli/cli_init.py:95
//   src/ummaya/ipc/stdio.py:1378
//   tui/src/schemas/ui-l2/permission.ts:43 (LAYER_VISUAL reused, not duplicated)

import type { PermissionLayerT } from '../../schemas/ui-l2/permission.js'

/**
 * UMMAYA active primitive verb identifiers. Aligns with L1-C C1 reserved
 * primitives declared in docs/requirements/ummaya-migration-tree.md.
 */
export type UmmayaPrimitive = 'find' | 'check' | 'send'

/**
 * Map a UMMAYA primitive verb + optional irreversibility flag to a permission
 * layer number (1 = low risk / green, 2 = medium / orange, 3 = high / red),
 * or `null` for primitives that bypass the gauntlet entirely.
 *
 * @param primitive - The primitive verb declared by the tool adapter.
 * @param isIrreversible - For `send`, whether the action is irreversible
 *   (e.g., financial write, government record mutation). Ignored for other
 *   primitives. Defaults to `false`.
 * @returns The permission layer number, or `null` for bypass (find).
 */
export function aalToLayer(
  primitive: UmmayaPrimitive,
  isIrreversible = false,
): PermissionLayerT | null {
  switch (primitive) {
    case 'find':
      return null
    case 'check':
      return 1
    case 'send':
      return isIrreversible ? 3 : 2
  }
}
