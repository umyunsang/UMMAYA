import { describe, expect, test } from 'bun:test'
import { AgentTool } from '../../src/tools/AgentTool/AgentTool.js'
import { TaskOutputTool } from '../../src/tools/TaskOutputTool/TaskOutputTool.js'
import { TaskStopTool } from '../../src/tools/TaskStopTool/TaskStopTool.js'
import { getEmptyToolPermissionContext } from '../../src/Tool.js'
import type { AssistantMessage } from '../../src/types/message.js'

function baseContext(task: Record<string, unknown>) {
  return {
    abortController: new AbortController(),
    getAppState: () => ({
      tasks: { [String(task.id)]: task },
      toolPermissionContext: getEmptyToolPermissionContext(),
    }),
    setAppState: () => {},
  }
}

const assistantMessage: AssistantMessage = {
  role: 'assistant',
  content: [{ type: 'text', text: 'agent task support' }],
}

describe('agent and task support substrate', () => {
  test('agent_task_tools_emit_progress_cancel_and_join_keys', async () => {
    const missingAgentJoinKey = AgentTool.outputSchema.safeParse({
      status: 'async_launched',
      agentId: 'agent-task-12',
      description: 'Collect evidence',
      prompt: 'Run the focused proof',
      outputFile: '/tmp/agent-task-12.jsonl',
      canReadOutputFile: true,
    })
    expect(missingAgentJoinKey.success).toBe(false)

    const mappedAgent = AgentTool.mapToolResultToToolResultBlockParam(
      {
        status: 'async_launched',
        agentId: 'agent-task-12',
        description: 'Collect evidence',
        prompt: 'Run the focused proof',
        outputFile: '/tmp/agent-task-12.jsonl',
        canReadOutputFile: true,
        evidenceJoinKey: 'toolu-parent:agent-task-12',
        parentToolUseId: 'toolu-parent',
        resumeToken: 'resume:agent-task-12',
        permissionFlow: 'coordinator_parent_round_trip',
      },
      'toolu-parent',
    )
    const agentText =
      typeof mappedAgent.content === 'string'
        ? mappedAgent.content
        : mappedAgent.content.map(block => block.text).join('\n')
    expect(agentText).toContain('evidence_join_key: toolu-parent:agent-task-12')
    expect(agentText).toContain('parent_tool_use_id: toolu-parent')
    expect(agentText).toContain('resume_token: resume:agent-task-12')
    expect(agentText).toContain(
      'permission_flow: coordinator_parent_round_trip',
    )

    const task = {
      id: 'task-12-running',
      type: 'local_bash',
      status: 'running',
      description: 'Task 12 focused proof',
      toolUseId: 'toolu-parent',
      shellCommand: {
        taskOutput: {
          getStdout: async () => 'partial output',
          getStderr: () => '',
        },
      },
      result: { code: null },
    }
    const progress: Array<{ data: Record<string, unknown> }> = []
    const collectProgress = (event: { data: Record<string, unknown> }) => {
      progress.push(event)
    }
    await TaskOutputTool.call(
      { task_id: 'task-12-running', block: true, timeout: 0 },
      baseContext(task),
      async () => ({ behavior: 'allow', updatedInput: {} }),
      assistantMessage,
      collectProgress,
    )
    expect(progress[0]?.data.evidenceJoinKey).toBe(
      'toolu-parent:task-12-running',
    )
    expect(progress[0]?.data.parentToolUseId).toBe('toolu-parent')

    const missingStopJoinKey = TaskStopTool.outputSchema.safeParse({
      message: 'Successfully stopped task: task-12-running',
      task_id: 'task-12-running',
      task_type: 'local_agent',
    })
    expect(missingStopJoinKey.success).toBe(false)
  })
})
