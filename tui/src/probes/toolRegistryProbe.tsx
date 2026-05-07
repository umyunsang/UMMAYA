// SPDX-License-Identifier: Apache-2.0
// Epic γ #2294 · T019 — ToolRegistry boot probe.
//
// Standalone script invoked via `bun run probe:tool-registry`.
// Runs verifyBootRegistry() against the active KOSMOS primitives and prints the
// success line; exits 0 on pass / 1 on fail.
//
// Usage (from /tui):
//   bun run probe:tool-registry
//
// Expected success output:
//   tool_registry: <N> entries verified (4 primitives) in <D>ms

import { LookupPrimitive } from '../tools/LookupPrimitive/LookupPrimitive.js'
import { ResolveLocationPrimitive } from '../tools/ResolveLocationPrimitive/ResolveLocationPrimitive.js'
import { SubmitPrimitive } from '../tools/SubmitPrimitive/SubmitPrimitive.js'
import { VerifyPrimitive } from '../tools/VerifyPrimitive/VerifyPrimitive.js'
import { verifyBootRegistry } from '../services/toolRegistry/bootGuard.js'
import type { Tool } from '../Tool.js'

const primitiveRegistry: readonly Tool[] = [
  LookupPrimitive as unknown as Tool,
  ResolveLocationPrimitive as unknown as Tool,
  SubmitPrimitive as unknown as Tool,
  VerifyPrimitive as unknown as Tool,
]

const result = verifyBootRegistry(primitiveRegistry)

if (!result.ok) {
  console.error(result.diagnostic)
  process.exit(1)
}

console.log(
  `tool_registry: ${result.entries} entries verified ` +
    `(${result.primitives} primitives) in ${Math.round(result.durationMs)}ms`,
)
process.exit(0)
