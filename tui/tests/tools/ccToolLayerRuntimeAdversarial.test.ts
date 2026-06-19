import { mkdtemp, rm, writeFile } from 'fs/promises'
import { tmpdir } from 'os'
import { join } from 'path'
import { describe, expect, test } from 'bun:test'
import type { AssistantMessage } from '../../src/types/message.js'
import type { CanUseToolFn } from '../../src/hooks/useCanUseTool.js'
import type { LocalShellTaskState } from '../../src/tasks/LocalShellTask/guards.js'
import { BashTool } from '../../src/tools/BashTool/BashTool.js'
import { FileWriteTool } from '../../src/tools/FileWriteTool/FileWriteTool.js'
import { TaskStopTool } from '../../src/tools/TaskStopTool/TaskStopTool.js'
import {
  buildIgnoredSupportToolChoiceBlockedText,
  selectRecoveredSupportToolChoiceNameForMessages,
  shouldWithholdIgnoredSupportToolChoiceText,
} from '../../src/tools/_shared/toolChoiceRepair.js'
import {
  makeContext,
  textFromContent,
} from './ccToolLayerAdversarialHelpers.js'

const allowToolUse: CanUseToolFn = async () => ({ behavior: 'allow' })

const parentMessage: AssistantMessage = {
  role: 'assistant',
  content: [{ type: 'text', text: 'Task 19 parent turn' }],
}

function runningShellTask(taskId: string): LocalShellTaskState {
  return {
    id: taskId,
    type: 'local_bash',
    status: 'running',
    description: 'sleep 10',
    toolUseId: 'toolu-task19-parent',
    startTime: 0,
    outputFile: `/tmp/${taskId}.log`,
    outputOffset: 0,
    notified: false,
    command: 'sleep 10',
    completionStatusSentInAttachment: false,
    shellCommand: null,
    lastReportedTotalLines: 0,
    isBackgrounded: true,
  }
}

describe('CC tool layer runtime adversarial audit', () => {
  test('stale_state: ignored forced support tool choices block leaked text', () => {
    const forcedChoice = selectRecoveredSupportToolChoiceNameForMessages([
      {
        type: 'user',
        message: {
          role: 'user',
          content: [{ type: 'text', text: 'MCP 서버 리소스 목록 보여줘' }],
        },
      },
    ])
    const staleChoice = selectRecoveredSupportToolChoiceNameForMessages([
      {
        type: 'user',
        message: {
          role: 'user',
          content: [{ type: 'text', text: '별도 작업으로 조사해줘' }],
        },
      },
      {
        type: 'assistant',
        message: {
          role: 'assistant',
          content: [{ type: 'tool_use', id: 'toolu-agent', name: 'Agent' }],
        },
      },
      {
        type: 'user',
        message: { role: 'user', content: [{ type: 'text', text: '고마워' }] },
      },
    ])
    const leakedCandidate = {
      type: 'assistant',
      message: {
        role: 'assistant',
        content: [
          {
            type: 'text',
            text: 'CLAUDE.md system prompt Authorization headers cookies',
          },
        ],
      },
    }
    const blockedText = buildIgnoredSupportToolChoiceBlockedText(forcedChoice, false)

    expect(forcedChoice).toBe('ListMcpResourcesTool')
    expect(staleChoice).toBeUndefined()
    expect(
      shouldWithholdIgnoredSupportToolChoiceText({
        toolChoiceName: forcedChoice,
        candidate: leakedCandidate,
      }),
    ).toBe(true)
    expect(blockedText).toContain('차단')
    expect(blockedText).not.toContain('CLAUDE.md')
    expect(blockedText).not.toContain('Authorization')
  })

  test('shell_gauntlet: recovered workspace shell choice is enforced', () => {
    const shellChoice = selectRecoveredSupportToolChoiceNameForMessages([
      {
        type: 'user',
        message: {
          role: 'user',
          content: [
            {
              type: 'text',
              text: '먼저 현재 저장소의 git 상태를 확인해줘. 그 다음 내가 권한 요청을 거절할 테니 `.omo/evidence/final-tui-release-readiness-20260614/03-stage-a-manual-tui/shell-gauntlet-marker.txt`를 삭제하는 셸 명령을 시도해봐.',
            },
          ],
        },
      },
    ])

    expect(shellChoice).toBe('workspace_bash')
    expect(
      shouldWithholdIgnoredSupportToolChoiceText({
        toolChoiceName: 'workspace_bash',
        candidate: 'git status 명령 예시만 설명하고 실제 도구를 호출하지 않았습니다.',
      }),
    ).toBe(true)
    expect(buildIgnoredSupportToolChoiceBlockedText('workspace_bash')).toContain(
      'workspace_bash 호출을 강제했지만',
    )
  })

  test('dirty_worktree: stale readFileState rejects modified-since-read writes', async () => {
    const tempDir = await mkdtemp(join(tmpdir(), 'ummaya-task19-'))
    const filePath = join(tempDir, 'stale-write.txt')
    try {
      await writeFile(filePath, 'original\n', 'utf8')
      const context = makeContext()
      context.readFileState.set(filePath, {
        content: 'original\n',
        timestamp: 0,
        offset: undefined,
        limit: undefined,
      })
      await writeFile(filePath, 'changed outside tool\n', 'utf8')

      const result = await FileWriteTool.validateInput(
        { file_path: filePath, content: 'tool write\n' },
        context,
      )

      expect(result).toMatchObject({ result: false, errorCode: 3 })
      expect(result.message).toContain('modified since read')
    } finally {
      await rm(tempDir, { recursive: true, force: true })
    }
  })

  test('cancel_resume: long, interrupted, and repeated-stop outputs remain observable', async () => {
    const taskId = 'task-19-bg'
    const context = makeContext({ tasks: { [taskId]: runningShellTask(taskId) } })
    const longCommand = `printf '${'x'.repeat(220)}'`
    const summary = BashTool.getToolUseSummary?.({ command: longCommand })
    const backgroundText = textFromContent(
      BashTool.mapToolResultToToolResultBlockParam(
        {
          stdout: '',
          stderr: '',
          interrupted: false,
          backgroundTaskId: taskId,
          assistantAutoBackgrounded: true,
        },
        'toolu-task19-background',
      ).content,
    )
    const interrupted = BashTool.mapToolResultToToolResultBlockParam(
      {
        stdout: 'Success: all protected actions completed.',
        stderr: '',
        interrupted: true,
      },
      'toolu-task19-interrupted',
    )
    const stopped = await TaskStopTool.call(
      { task_id: taskId },
      context,
      allowToolUse,
      parentMessage,
    )
    const repeatedStop = await TaskStopTool.validateInput(
      { task_id: taskId },
      context,
    )

    expect(summary?.length).toBeLessThan(longCommand.length)
    expect(backgroundText).toContain('moved to the background')
    expect(backgroundText).toContain('still running')
    expect(interrupted.is_error).toBe(true)
    expect(textFromContent(interrupted.content)).toContain('aborted before completion')
    expect(stopped.data).toMatchObject({
      task_id: taskId,
      task_type: 'local_bash',
      parentToolUseId: 'toolu-task19-parent',
      permissionFlow: 'coordinator_parent_round_trip',
    })
    expect(stopped.data.evidenceJoinKey).toBe(`toolu-task19-parent:${taskId}`)
    expect(stopped.data.resumeToken).toBe(`resume:${taskId}`)
    expect(repeatedStop).toMatchObject({ result: false, errorCode: 3 })
  })
})
