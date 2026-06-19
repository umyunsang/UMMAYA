import { describe, expect, test } from 'bun:test'
import { queryHaiku } from '../../../src/services/api/ummaya.js'
import { responseForTextDelta, withFriendliEnv } from './ummaya-provider-friendli.helpers.js'

describe('UMMAYA non-streaming provider helpers', () => {
  test('queryHaiku sends the supplied userPrompt to FriendliAI', async () => {
    await withFriendliEnv(async () => {
      let capturedMessages: unknown

      await queryHaiku({
        userPrompt: '세션 제목을 생성할 실제 사용자 요청입니다.',
        options: {
          getToolPermissionContext: async () => ({}),
          model: 'LGAI-EXAONE/K-EXAONE-236B-A23B',
          isNonInteractiveSession: false,
          querySource: 'generate_session_title',
          agents: [],
          allowedAgentTypes: [],
          mcpTools: [],
          fetchOverride: async (_input, init) => {
            if (typeof init?.body !== 'string') {
              throw new Error('expected JSON provider body')
            }
            const parsed = JSON.parse(init.body) as { messages?: unknown }
            capturedMessages = parsed.messages
            return responseForTextDelta('{"title":"부가세 신고 준비"}')
          },
        },
      })

      expect(capturedMessages).toEqual(
        expect.arrayContaining([
          expect.objectContaining({
            role: 'user',
            content: '세션 제목을 생성할 실제 사용자 요청입니다.',
          }),
        ]),
      )
    })
  })
})
