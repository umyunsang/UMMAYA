// SPDX-License-Identifier: Apache-2.0
// Regression for duplicated KOSMOS primitive permission prompts.
//
// Backend-dispatched primitives must not also ask through the CC client-side
// Tool.checkPermissions path. The Python stdio dispatcher owns the canonical
// PermissionRequestFrame for verify/submit/subscribe via GATED_PRIMITIVES.

import { describe, expect, it } from 'bun:test'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'

const BACKEND_GATED_PRIMITIVE_FILES = [
  '../../../src/tools/VerifyPrimitive/VerifyPrimitive.ts',
  '../../../src/tools/SubmitPrimitive/SubmitPrimitive.ts',
  '../../../src/tools/SubscribePrimitive/SubscribePrimitive.ts',
] as const

describe('G4 — backend owns KOSMOS primitive permission prompts', () => {
  it('frontend wrappers allow and let backend permission_request drive the gauntlet', () => {
    for (const relativePath of BACKEND_GATED_PRIMITIVE_FILES) {
      const text = readFileSync(join(import.meta.dir, relativePath), 'utf8')

      expect(text).toContain('Backend owns the KOSMOS permission gauntlet')
      expect(text).toContain('async checkPermissions(input)')
      expect(text).toContain(
        "return { behavior: 'allow' as const, updatedInput: input }",
      )

      const checkPermissionsStart = text.indexOf('async checkPermissions(input)')
      expect(checkPermissionsStart).toBeGreaterThanOrEqual(0)
      const callStart = text.indexOf('async call(', checkPermissionsStart)
      const block = text.slice(checkPermissionsStart, callStart)
      expect(block).not.toContain("behavior: 'ask'")
    }
  })
})
