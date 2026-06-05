import { describe, expect, test } from 'bun:test'

import { buildDocumentCompletionPromptIfNeeded } from '../../src/tools/_shared/toolChoiceRepair.js'
import type { Message } from '../../src/types/message.js'

describe('toolChoiceRepair document completion', () => {
  test('builds exact diff-only prompt when user asks for actual changes only', () => {
    const query =
      '다운로드 폴더에 있는 weekly.hwpx 문서내용을 파악하고 알아서 다음 주차 활동일지로 작성해줘. 최종적으로 실제로 바뀐 내용만 답변해줘.'
    const messages = [
      {
        type: 'user',
        message: { role: 'user', content: query },
      },
      {
        type: 'assistant',
        message: {
          role: 'assistant',
          content: [
            {
              type: 'tool_use',
              id: 'call-document-fill',
              name: 'document',
              input: { document: { path: '~/Downloads/weekly.hwpx' } },
            },
          ],
        },
      },
      {
        type: 'user',
        message: {
          role: 'user',
          content: [
            {
              type: 'tool_result',
              tool_use_id: 'call-document-fill',
              content: JSON.stringify({
                ok: true,
                result: {
                  tool_id: 'document',
                  status: 'ok',
                  diff: {
                    changes: [
                      {
                        target_path: '/hwpx/text[2]',
                        before_value: '13 주차 ',
                        after_value: '14주차',
                      },
                      {
                        target_path: '/hwpx/text[12]',
                        before_value: '2026.06.01 ~ 2026.06.07',
                        after_value: '2026.06.08~2026.06.14',
                      },
                    ],
                  },
                },
              }),
            },
          ],
        },
      },
    ] as unknown as Message[]

    const prompt = buildDocumentCompletionPromptIfNeeded({ messages })

    expect(prompt).toContain('Reply in Korean with exactly these lines')
    expect(prompt).toContain('실제 변경된 내용:')
    expect(prompt).toContain('- /hwpx/text[2]: 13 주차  -> 14주차')
    expect(prompt).toContain(
      '- /hwpx/text[12]: 2026.06.01 ~ 2026.06.07 -> 2026.06.08~2026.06.14',
    )
    expect(prompt).not.toContain('state whether the document was updated')
  })

  test('builds exact diff-and-save prompt when user asks for changed content and save location only', () => {
    const query =
      '다운로드 폴더에 있는 weekly.hwpx 문서내용을 파악하고 알아서 다음 주차 활동일지로 작성한 뒤 /Users/me/Downloads/weekly-14.hwpx 로 저장해줘. 최종적으로 실제로 바뀐 내용과 저장 위치만 답변해줘.'
    const messages = [
      {
        type: 'user',
        message: { role: 'user', content: query },
      },
      {
        type: 'assistant',
        message: {
          role: 'assistant',
          content: [
            {
              type: 'tool_use',
              id: 'call-document-fill',
              name: 'document',
              input: { document: { path: '~/Downloads/weekly.hwpx' } },
            },
          ],
        },
      },
      {
        type: 'user',
        message: {
          role: 'user',
          content: [
            {
              type: 'tool_result',
              tool_use_id: 'call-document-fill',
              content: JSON.stringify({
                ok: true,
                result: {
                  tool_id: 'document',
                  status: 'ok',
                  saved_exports: [
                    {
                      local_path: '/Users/me/Downloads/weekly-14.hwpx',
                      sha256: 'a'.repeat(64),
                    },
                  ],
                  diff: {
                    changes: [
                      {
                        target_path: '/hwpx/text[2]',
                        before_value: '13 주차 ',
                        after_value: '14주차',
                      },
                    ],
                  },
                },
              }),
            },
          ],
        },
      },
    ] as unknown as Message[]

    const prompt = buildDocumentCompletionPromptIfNeeded({ messages })

    expect(prompt).toContain('Reply in Korean with exactly these lines')
    expect(prompt).toContain('실제 변경된 내용:')
    expect(prompt).toContain('- /hwpx/text[2]: 13 주차  -> 14주차')
    expect(prompt).toContain('저장 위치:')
    expect(prompt).toContain('- /Users/me/Downloads/weekly-14.hwpx')
    expect(prompt).not.toContain('state whether the document was updated')
  })
})
