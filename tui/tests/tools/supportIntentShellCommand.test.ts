import { describe, expect, test } from 'bun:test'
import {
  expandedToolSearchTerms,
  selectRecoveredSupportToolNamesForQuery,
} from '../../src/tools/ToolSearchTool/supportIntentHints.js'

describe('shell support intent recovery', () => {
  test('does not treat terminal streaming discussion as shell execution', () => {
    const prompt =
      '터미널 LLM 답변 스트리밍이 사용자에게 실시간처럼 느껴져야 하는 이유를 한국어로 설명해줘.'

    expect(selectRecoveredSupportToolNamesForQuery(prompt)).not.toContain(
      'workspace_bash',
    )
    expect(expandedToolSearchTerms(prompt.toLowerCase())).not.toContain('bash')
  })

  test('keeps explicit shell and git command requests on workspace_bash', () => {
    const prompts = [
      '셸 명령으로 git status --short 실행해줘.',
      '터미널에서 `git diff --stat` 명령을 돌려줘.',
      '현재 저장소의 git 상태를 확인해줘.',
    ] as const

    for (const prompt of prompts) {
      expect(selectRecoveredSupportToolNamesForQuery(prompt)).toContain(
        'workspace_bash',
      )
      expect(expandedToolSearchTerms(prompt.toLowerCase())).toContain('bash')
    }
  })
})
