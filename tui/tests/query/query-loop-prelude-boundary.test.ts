import { describe, expect, test } from 'bun:test'
import {
  assistantMessages,
  createNamedTool,
  runQueryForPromptWithFirstAssistantContent,
  textOf,
} from './query-loop-visible-progress.helpers.js'

describe('query loop prelude boundary', () => {
  test('preserves obeyed workspace tool prelude before the tool boundary', async () => {
    const dynamicPrelude =
      '현재 저장소 상태를 확인하기 위해 git status를 실행하겠습니다.'
    const emitted = await runQueryForPromptWithFirstAssistantContent({
      prompt: '현재 저장소의 git 상태를 확인해줘.',
      firstContent: [
        { type: 'text', text: dynamicPrelude },
        {
          type: 'tool_use',
          id: 'call-git-status-1',
          name: 'workspace_bash',
          input: {},
        },
      ],
      tools: [createNamedTool('workspace_bash')],
    })
    const firstAssistant = assistantMessages(emitted)[0]
    if (!firstAssistant) throw new Error('expected first assistant')
    expect(textOf(firstAssistant)).toContain(dynamicPrelude)
    expect(
      firstAssistant.message.content.some(
        block => block.type === 'tool_use' && block.name === 'workspace_bash',
      ),
    ).toBe(true)
  })

  test('preserves obeyed document prelude before the tool boundary', async () => {
    const dynamicPrelude =
      '문서 구조와 빈칸을 확인하기 위해 먼저 document 도구를 사용하겠습니다.'
    const emitted = await runQueryForPromptWithFirstAssistantContent({
      prompt:
        '/Users/um-yunsang/UMMAYA/.omo/evidence/final-tui-release-readiness-20260614/03-stage-a-manual-tui/document-fixtures/readonly-inspect.docx 문서의 구조와 빈칸만 확인해줘. 절대 수정하거나 저장하지 마.',
      firstContent: [
        { type: 'text', text: dynamicPrelude },
        {
          type: 'tool_use',
          id: 'call-document-inspect-1',
          name: 'document',
          input: {},
        },
      ],
      tools: [createNamedTool('document')],
    })
    const firstAssistant = assistantMessages(emitted)[0]
    if (!firstAssistant) throw new Error('expected first assistant')
    expect(textOf(firstAssistant)).toContain(dynamicPrelude)
    expect(
      firstAssistant.message.content.some(
        block => block.type === 'tool_use' && block.name === 'document',
      ),
    ).toBe(true)
  })
})
