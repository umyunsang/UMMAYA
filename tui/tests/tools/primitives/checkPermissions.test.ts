// SPDX-License-Identifier: Apache-2.0
// Spec 2638 — 4 Primitive checkPermissions contract tests.
//
// Verifies the explicit checkPermissions declarations added to each primitive:
//   - LookupPrimitive  → { behavior: 'allow', updatedInput: input }
//   - VerifyPrimitive  → { behavior: 'ask',   message: '권한 위임 필요: ...' }
//   - SubmitPrimitive  → { behavior: 'ask',   message: '권한 위임 필요: ...' }
//   - SubscribePrimitive → { behavior: 'ask', message: '권한 위임 필요: ...' }
//
// All tests run headlessly — no React render context required.
// The method is a plain async function on the tool object.

import { describe, expect, it } from 'bun:test'
import { LookupPrimitive } from '../../../src/tools/LookupPrimitive/LookupPrimitive.js'
import { VerifyPrimitive } from '../../../src/tools/VerifyPrimitive/VerifyPrimitive.js'
import { SubmitPrimitive } from '../../../src/tools/SubmitPrimitive/SubmitPrimitive.js'
import { SubscribePrimitive } from '../../../src/tools/SubscribePrimitive/SubscribePrimitive.js'

// Minimal input stubs that satisfy the z.object({ tool_id, params }) schema.
const lookupInput = { tool_id: 'kma_forecast_fetch', params: { lat: 37.5, lon: 127.0 } }
const verifyInput = { tool_id: 'gongdong_injeungseo', params: {} }
const submitInput = { tool_id: 'koroad_accident_report', params: {} }
const subscribeInput = { tool_id: 'nmc_emergency_subscribe', params: {} }

describe('LookupPrimitive.checkPermissions', () => {
  it('returns behavior=allow for read-only lookup', async () => {
    const result = await LookupPrimitive.checkPermissions(lookupInput)
    expect(result.behavior).toBe('allow')
  })

  it('updatedInput is the passed-in input (no mutation)', async () => {
    const result = await LookupPrimitive.checkPermissions(lookupInput)
    expect((result as { updatedInput?: unknown }).updatedInput).toEqual(lookupInput)
  })
})

describe('VerifyPrimitive.checkPermissions', () => {
  it('returns behavior=ask (citizen must authorize credential delegation)', async () => {
    const result = await VerifyPrimitive.checkPermissions(verifyInput)
    expect(result.behavior).toBe('ask')
  })

  it('message contains 권한 위임 필요', async () => {
    const result = await VerifyPrimitive.checkPermissions(verifyInput) as { message: string }
    expect(result.message).toContain('권한 위임 필요')
  })

  it('message contains 인증', async () => {
    const result = await VerifyPrimitive.checkPermissions(verifyInput) as { message: string }
    expect(result.message).toContain('인증')
  })
})

describe('SubmitPrimitive.checkPermissions', () => {
  it('returns behavior=ask (side-effecting — citizen must confirm)', async () => {
    const result = await SubmitPrimitive.checkPermissions(submitInput)
    expect(result.behavior).toBe('ask')
  })

  it('message contains 권한 위임 필요', async () => {
    const result = await SubmitPrimitive.checkPermissions(submitInput) as { message: string }
    expect(result.message).toContain('권한 위임 필요')
  })

  it('message contains 제출', async () => {
    const result = await SubmitPrimitive.checkPermissions(submitInput) as { message: string }
    expect(result.message).toContain('제출')
  })
})

describe('SubscribePrimitive.checkPermissions', () => {
  it('returns behavior=ask (stream must be authorized before opening)', async () => {
    const result = await SubscribePrimitive.checkPermissions(subscribeInput)
    expect(result.behavior).toBe('ask')
  })

  it('message contains 권한 위임 필요', async () => {
    const result = await SubscribePrimitive.checkPermissions(subscribeInput) as { message: string }
    expect(result.message).toContain('권한 위임 필요')
  })

  it('message contains 구독', async () => {
    const result = await SubscribePrimitive.checkPermissions(subscribeInput) as { message: string }
    expect(result.message).toContain('구독')
  })
})

describe('Primitive checkPermissions — behavior contract invariants', () => {
  it('only lookup returns allow; the 3 side-effecting primitives return ask', async () => {
    const [lookup, verify, submit, subscribe] = await Promise.all([
      LookupPrimitive.checkPermissions(lookupInput),
      VerifyPrimitive.checkPermissions(verifyInput),
      SubmitPrimitive.checkPermissions(submitInput),
      SubscribePrimitive.checkPermissions(subscribeInput),
    ])
    expect(lookup.behavior).toBe('allow')
    expect(verify.behavior).toBe('ask')
    expect(submit.behavior).toBe('ask')
    expect(subscribe.behavior).toBe('ask')
  })
})
