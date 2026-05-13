// SPDX-License-Identifier: Apache-2.0
// Spec 2638 — active primitive checkPermissions contract tests.
//
// Verifies the explicit checkPermissions declarations added to each primitive:
//   - find/check/send classes declare the expected permission behavior.
//
// All tests run headlessly — no React render context required.
// The method is a plain async function on the tool object.

import { describe, expect, it } from 'bun:test'
import { LookupPrimitive } from '../../../src/tools/LookupPrimitive/LookupPrimitive.js'
import { VerifyPrimitive } from '../../../src/tools/VerifyPrimitive/VerifyPrimitive.js'
import { SubmitPrimitive } from '../../../src/tools/SubmitPrimitive/SubmitPrimitive.js'

// Minimal input stubs that satisfy the z.object({ tool_id, params }) schema.
const findInput = { tool_id: 'kma_forecast_fetch', params: { lat: 37.5, lon: 127.0 } }
const checkInput = { tool_id: 'gongdong_injeungseo', params: {} }
const sendInput = { tool_id: 'koroad_accident_report', params: {} }

describe('LookupPrimitive.checkPermissions', () => {
  it('returns behavior=allow for read-only find', async () => {
    const result = await LookupPrimitive.checkPermissions(findInput)
    expect(result.behavior).toBe('allow')
  })

  it('updatedInput is the passed-in input (no mutation)', async () => {
    const result = await LookupPrimitive.checkPermissions(findInput)
    expect((result as { updatedInput?: unknown }).updatedInput).toEqual(findInput)
  })
})

describe('VerifyPrimitive.checkPermissions', () => {
  it('returns behavior=ask (citizen must authorize credential delegation)', async () => {
    const result = await VerifyPrimitive.checkPermissions(checkInput)
    expect(result.behavior).toBe('ask')
  })

  it('message contains 권한 위임 필요', async () => {
    const result = await VerifyPrimitive.checkPermissions(checkInput) as { message: string }
    expect(result.message).toContain('권한 위임 필요')
  })

  it('message contains 인증', async () => {
    const result = await VerifyPrimitive.checkPermissions(checkInput) as { message: string }
    expect(result.message).toContain('인증')
  })
})

describe('SubmitPrimitive.checkPermissions', () => {
  it('returns behavior=ask (side-effecting — citizen must confirm)', async () => {
    const result = await SubmitPrimitive.checkPermissions(sendInput)
    expect(result.behavior).toBe('ask')
  })

  it('message contains 권한 위임 필요', async () => {
    const result = await SubmitPrimitive.checkPermissions(sendInput) as { message: string }
    expect(result.message).toContain('권한 위임 필요')
  })

  it('message contains 제출', async () => {
    const result = await SubmitPrimitive.checkPermissions(sendInput) as { message: string }
    expect(result.message).toContain('제출')
  })
})

describe('Primitive checkPermissions — behavior contract invariants', () => {
  it('only find returns allow; check and send return ask', async () => {
    const [find, check, send] = await Promise.all([
      LookupPrimitive.checkPermissions(findInput),
      VerifyPrimitive.checkPermissions(checkInput),
      SubmitPrimitive.checkPermissions(sendInput),
    ])
    expect(find.behavior).toBe('allow')
    expect(check.behavior).toBe('ask')
    expect(send.behavior).toBe('ask')
  })
})
