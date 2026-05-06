// SPDX-License-Identifier: Apache-2.0
// Spec 2294 — SSOT for AAL→Layer mapping.
//
// FR-005 matrix (canonical, do not duplicate elsewhere):
//   lookup           → null  (bypass — no permission gauntlet)
//   verify (any AAL) → 1     (green ⓵, low risk)
//   submit (non-irr) → 2     (orange ⓶, medium risk)
//   submit (irr=true)→ 3     (red ⓷, high risk)
//   subscribe        → 2     (orange ⓶, medium risk)
//
// Previously scattered across:
//   src/kosmos/tools/policy_derivation.py:57
//   src/kosmos/cli/cli_init.py:95
//   src/kosmos/ipc/stdio.py:1378
//   previous TUI permission receipt UI (removed; CC PermissionRequest is canonical)

export type PermissionLayerT = 1 | 2 | 3

/**
 * KOSMOS primitive verb identifiers. Aligns with L1-C C1 four reserved
 * primitives declared in docs/requirements/kosmos-migration-tree.md.
 */
export type KosmosPrimitive = 'lookup' | 'verify' | 'submit' | 'subscribe'

/**
 * Map a KOSMOS primitive verb + optional irreversibility flag to a permission
 * layer number (1 = low risk / green, 2 = medium / orange, 3 = high / red),
 * or `null` for primitives that bypass the gauntlet entirely.
 *
 * @param primitive - The primitive verb declared by the tool adapter.
 * @param isIrreversible - For `submit`, whether the action is irreversible
 *   (e.g., financial write, government record mutation). Ignored for other
 *   primitives. Defaults to `false`.
 * @returns The permission layer number, or `null` for bypass (lookup).
 */
export function aalToLayer(
  primitive: KosmosPrimitive,
  isIrreversible = false,
): PermissionLayerT | null {
  switch (primitive) {
    case 'lookup':
      return null
    case 'verify':
      return 1
    case 'submit':
      return isIrreversible ? 3 : 2
    case 'subscribe':
      return 2
  }
}
