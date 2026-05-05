// SPDX-License-Identifier: Apache-2.0
// Epic 1 finish — FR-012: KOSMOS bypass detection backstop.
//
// The CC `bypassPermissions` flag gates the dangerous-mode UX.  In KOSMOS
// the gauntlet must NEVER be silently skipped for IRREVERSIBLE primitives
// (submit / subscribe) regardless of bypassPermissions or auto-mode state.
//
// This module exposes two guards:
//   - isKosmosBypassAllowed(primitive, toolPermissionContext)
//     Returns true only when bypass is safe (lookup / verify).
//     Returns false + emits a warning for submit (irreversible) / subscribe.
//
//   - assertKosmosGauntletRequired(primitive, toolPermissionContext)
//     Throws if a blocked primitive is called in bypass mode (test helper).
//
// CC reference: utils/permissions/bypassPermissionsKillswitch.ts (CC 2.1.88)
// KOSMOS adaptation: stateless pure-function guard, no React hooks, no module
// singleton. Safe to call from any context (hooks, test fixtures, tool call).

import type { ToolPermissionContext } from '../../Tool.js'
import type { KosmosPrimitive } from './aalToLayer.js'

// ---------------------------------------------------------------------------
// Primitives that MUST always go through the gauntlet (fail-closed).
// ---------------------------------------------------------------------------

/**
 * Primitives that are NEVER allowed to bypass the permission gauntlet,
 * even when `bypassPermissions` is true or the session is in auto-mode.
 *
 * Rationale (FR-012):
 *   - submit:    side-effecting, potentially irreversible (Layer 2/3).
 *   - subscribe: session-lifetime subscription with potential data egress (Layer 2).
 *   - verify:    delegates real credentials to external auth vendor (Layer 1).
 *   - lookup:    read-only; intentionally excluded — bypass is safe here.
 */
export const BYPASS_BLOCKED_PRIMITIVES: ReadonlySet<KosmosPrimitive> = new Set<KosmosPrimitive>([
  'verify',
  'submit',
  'subscribe',
])

// ---------------------------------------------------------------------------
// isKosmosBypassAllowed — fail-closed predicate
// ---------------------------------------------------------------------------

/**
 * Returns `true` if the primitive MAY proceed without the permission gauntlet
 * (i.e., in bypass / auto-mode without a human approval prompt).
 *
 * Always returns `false` for primitives in BYPASS_BLOCKED_PRIMITIVES
 * regardless of `toolPermissionContext.bypassPermissions`.
 *
 * Always returns `true` for `lookup` — it is read-only and side-effect-free.
 */
export function isKosmosBypassAllowed(
  primitive: KosmosPrimitive,
  _toolPermissionContext?: Pick<ToolPermissionContext, 'bypassPermissions'>,
): boolean {
  if (primitive === 'lookup') {
    // lookup: read-only, bypass is always safe.
    return true
  }
  if (BYPASS_BLOCKED_PRIMITIVES.has(primitive)) {
    // FR-012: blocked regardless of bypass flag.
    return false
  }
  // Default: honour the bypassPermissions flag.
  return _toolPermissionContext?.bypassPermissions ?? false
}

// ---------------------------------------------------------------------------
// assertKosmosGauntletRequired — defensive check for tests / call-sites
// ---------------------------------------------------------------------------

/**
 * Throws a descriptive error if `primitive` is in BYPASS_BLOCKED_PRIMITIVES
 * and `toolPermissionContext.bypassPermissions` is true.
 *
 * Intended usage: call from `checkPermissions` implementations in each
 * primitive tool BEFORE delegating to the CC `{ behavior: 'ask' }` path.
 * In production, the CC pipeline never bypasses `{ behavior: 'ask' }` for
 * blocked primitives because KOSMOS does not wire `bypassPermissions: true`
 * for citizen sessions.  This assert is a belt-and-suspenders guard for
 * future configuration drift.
 *
 * @throws Error if bypass is attempted on a blocked primitive.
 */
export function assertKosmosGauntletRequired(
  primitive: KosmosPrimitive,
  toolPermissionContext?: Pick<ToolPermissionContext, 'bypassPermissions'>,
): void {
  if (
    BYPASS_BLOCKED_PRIMITIVES.has(primitive) &&
    toolPermissionContext?.bypassPermissions === true
  ) {
    throw new Error(
      `[KOSMOS FR-012] Bypass attempted on gauntlet-required primitive '${primitive}'. ` +
        `bypassPermissions must not be set for citizen-facing primitives.`,
    )
  }
}
