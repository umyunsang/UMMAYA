// SPDX-License-Identifier: Apache-2.0
// Epic γ #2294 · T004 · ToolRegistry boot guard.
//
// Walks every active registered KOSMOS primitive (lookup / resolve_location /
// submit / verify) at process boot and asserts that
// each one exposes the full `Tool<>` 9-member surface from
// `tui/src/Tool.ts` (byte-identical to CC `Tool.ts`). Fails closed with a
// Korean diagnostic if any member is missing.
//
// Scope (per Epic γ research § R-2): the primitives are the contract surface
// the LLM sees. Auxiliary tools (WebFetch/Calculator/...) inherit CC's port
// and stay typecheck-enforced; this guard adds the runtime backstop only for
// primitives, where contributor plugins (Spec 1636) routinely forget the
// optional render-result method.
//
// Adapter citation invariance (FR-009) is enforced inside each primitive's
// `validateInput` at call time, not here — the TS side never imports the
// 18 adapter manifests directly; they live in the Python backend
// (Spec 1634 IPC). The primitive surfaces the citation gap as a
// `CitationMissing` validation error, which fails the call before the
// permission prompt is shown.

import type { Tool } from '../../Tool.js'

const PRIMITIVE_NAMES = ['lookup', 'resolve_location', 'submit', 'verify'] as const
export type PrimitiveName = (typeof PRIMITIVE_NAMES)[number]

const REQUIRED_MEMBERS = [
  'name',
  'description',
  'inputSchema',
  'isReadOnly',
  'isMcp',
  'validateInput',
  'call',
  'renderToolUseMessage',
  'renderToolResultMessage',
] as const

export type BootResult =
  | {
      ok: true
      entries: number
      primitives: number
      durationMs: number
    }
  | {
      ok: false
      offendingTool: string
      missingMembers: string[]
      diagnostic: string
    }

/**
 * Verify that every KOSMOS primitive in the registered tool array exposes the
 * full 9-member `Tool<>` contract from `tui/src/Tool.ts`. Returns the
 * structured `BootResult`. Caller decides whether to `process.exit(1)` or
 * throw — the guard itself has no side effects beyond reading the registry.
 *
 * Performance: O(P × M) where P = number of active primitives (4) and M = required
 * member count (9) — bounded at 36 property reads. Wall-clock budget on a
 * developer laptop: ≤ 200 ms (Spec SC-002).
 */
export function verifyBootRegistry(registry: readonly Tool[]): BootResult {
  const start = performance.now()

  const primitives = registry.filter(t =>
    (PRIMITIVE_NAMES as readonly string[]).includes(t.name),
  )

  // Codex P2 fix — fail closed when any active reserved primitive is
  // accidentally unregistered. Without this check, removing a primitive
  // would still produce ok:true with primitives < 5.
  if (primitives.length !== PRIMITIVE_NAMES.length) {
    const present = new Set(primitives.map(t => t.name))
    const missingNames = PRIMITIVE_NAMES.filter(n => !present.has(n))
    return {
      ok: false,
      offendingTool: '<reserved-primitive-set>',
      missingMembers: missingNames as unknown as string[],
      diagnostic:
        `[KOSMOS][bootGuard] 활성 primitive 중 일부가 ToolRegistry에 등록되지 않았습니다. ` +
        `누락: ${missingNames.join(', ')}.\n` +
        `KOSMOS는 활성 primitive(lookup/resolve_location/submit/verify) 모두 등록되어야 부팅을 허용합니다.\n` +
        `참조: specs/2294-5-primitive-align/contracts/registry-boot-guard.md`,
    }
  }

  for (const tool of primitives) {
    const missing: string[] = []
    for (const member of REQUIRED_MEMBERS) {
      // `isMcp` is a boolean — undefined counts as missing. All others must
      // be non-undefined (functions or schema objects).
      const value = (tool as unknown as Record<string, unknown>)[member]
      if (member === 'isMcp') {
        if (typeof value !== 'boolean') missing.push(member)
      } else if (value === undefined || value === null) {
        missing.push(member)
      }
    }
    if (missing.length > 0) {
      return {
        ok: false,
        offendingTool: tool.name,
        missingMembers: missing,
        diagnostic:
          `[KOSMOS][bootGuard] 도구 '${tool.name}' 등록 검증 실패. ` +
          `누락 필드: ${missing.join(', ')}.\n` +
          `KOSMOS는 9-member ToolDef 계약을 준수하는 도구만 부팅 시점에 받아들입니다.\n` +
          `참조: specs/2294-5-primitive-align/contracts/primitive-shape.md`,
      }
    }
  }

  return {
    ok: true,
    entries: registry.length,
    primitives: primitives.length,
    durationMs: performance.now() - start,
  }
}
