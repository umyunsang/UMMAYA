// SPDX-License-Identifier: Apache-2.0

import { describe, expect, test } from 'bun:test'
import { argumentsForPrimitive } from './documentDispatchArguments.js'

function contextWithLatestUserText(userQuery: string): {
  readonly messages: readonly unknown[]
} {
  return {
    messages: [
      {
        type: 'user',
        message: { role: 'user', content: userQuery },
      },
    ],
  }
}

describe('documentDispatchArguments', () => {
  test('adds current user query to write document IPC calls', () => {
    const userQuery =
      '/tmp/weekly.hwpx 문서 내용을 파악해서 다음 주차 활동일지로 알아서 작성하고, 저장은 /tmp/weekly-auto.hwpx 로 해줘.'
    const args = {
      correlation_id: 'corr-document',
      document: { path: '/tmp/weekly.hwpx', expected_format: 'hwpx' },
      operation: 'fill',
      instruction: '문서 내용을 다음 주차 활동일지로 작성하세요.',
    }

    const result = argumentsForPrimitive({
      primitive: 'document',
      args,
      context: contextWithLatestUserText(userQuery),
    })

    expect(result).toEqual({ ...args, __ummaya_user_query: userQuery })
    expect(args).not.toHaveProperty('__ummaya_user_query')
  })

  test('does not add current user query to well-formed read-only document IPC calls', () => {
    const userQuery =
      '/tmp/business-plan.docx 양식의 빈칸과 문항을 먼저 파악해줘. 아직 문서에는 쓰지 마.'
    const args = {
      correlation_id: 'corr-document-readonly',
      document: { path: '/tmp/business-plan.docx', expected_format: 'docx' },
      operation: 'extract',
      instruction: '사업계획서 양식의 모든 빈칸, 문항, 서식을 구조적으로 추출하세요.',
    }

    const result = argumentsForPrimitive({
      primitive: 'document',
      args,
      context: contextWithLatestUserText(userQuery),
    })

    expect(result).toBe(args)
    expect(JSON.stringify(result)).not.toContain('__ummaya_user_query')
  })

  test('adds current user query to malformed read-only document IPC calls', () => {
    const userQuery =
      '/tmp/readonly.docx 문서의 구조와 빈칸만 확인해줘. 절대 수정하거나 저장하지 마.'
    const args = { operation: 'inspect' }

    const result = argumentsForPrimitive({
      primitive: 'document',
      args,
      context: contextWithLatestUserText(userQuery),
    })

    expect(result).toEqual({
      operation: 'inspect',
      __ummaya_user_query: userQuery,
    })
    expect(args).not.toHaveProperty('__ummaya_user_query')
  })
})
