import React from 'react'
import { FallbackToolUseErrorMessage } from '../../components/FallbackToolUseErrorMessage.js'
import { FallbackToolUseRejectedMessage } from '../../components/FallbackToolUseRejectedMessage.js'
import { MessageResponse } from '../../components/MessageResponse.js'
import { Box, Text } from '../../ink.js'
import { useShortcutDisplay } from '../../keybindings/useShortcutDisplay.js'
import type { ProgressMessage } from '../../types/message.js'
import { jsonParse } from '../../utils/slowOperations.js'
import { countCharInString } from '../../utils/stringUtils.js'
import type { ThemeName } from '../../utils/theme.js'
import { AgentPromptDisplay, AgentResponseDisplay } from '../AgentTool/UI.js'
import BashToolResultMessage from '../BashTool/BashToolResultMessage.js'
import type { TaskOutputToolInput, TaskOutputToolOutput } from './schemas.js'
import { taskOutputToolOutputSchema } from './schemas.js'

type TaskOutputResultDisplayProps = {
  readonly content: TaskOutputToolOutput | string
  readonly verbose?: boolean
  readonly theme: ThemeName
}

function parseTaskOutputResult(
  content: TaskOutputToolOutput | string,
): TaskOutputToolOutput {
  if (typeof content !== 'string') return content
  return taskOutputToolOutputSchema.parse(jsonParse(content))
}

function readTaskDescription(
  message: ProgressMessage | undefined,
): string | undefined {
  const data = message?.data
  if (typeof data !== 'object' || data === null) return undefined
  if (!('taskDescription' in data)) return undefined
  return typeof data.taskDescription === 'string'
    ? data.taskDescription
    : undefined
}

function StillRunningMessage(): React.ReactNode {
  return (
    <MessageResponse>
      <Text dimColor={true}>Task is still running…</Text>
    </MessageResponse>
  )
}

export function renderTaskOutputUseMessage(
  input: Partial<TaskOutputToolInput>,
): React.ReactNode {
  const { block = true } = input
  return block ? '' : 'non-blocking'
}

export function renderTaskOutputUseTag(
  input: Partial<TaskOutputToolInput>,
): React.ReactNode {
  if (!input.task_id) return null
  return <Text dimColor> {input.task_id}</Text>
}

export function renderTaskOutputUseProgressMessage(
  progressMessages: readonly ProgressMessage[],
): React.ReactNode {
  const taskDescription = readTaskDescription(
    progressMessages[progressMessages.length - 1],
  )
  return (
    <Box flexDirection="column">
      {taskDescription && (
        <Text>
          {'  '}
          {taskDescription}
        </Text>
      )}
      <Text>
        {'     '}Waiting for task{' '}
        <Text dimColor>(esc to give additional instructions)</Text>
      </Text>
    </Box>
  )
}

export function TaskOutputResultDisplay({
  content,
  verbose = false,
  theme,
}: TaskOutputResultDisplayProps): React.ReactNode {
  const result = parseTaskOutputResult(content)
  if (!result.task) {
    return (
      <MessageResponse>
        <Text dimColor={true}>No task output available</Text>
      </MessageResponse>
    )
  }

  const { task } = result
  const expandShortcut = useShortcutDisplay(
    'app:toggleTranscript',
    'Global',
    'ctrl+o',
  )

  switch (task.task_type) {
    case 'local_bash':
      return (
        <BashToolResultMessage
          content={{
            stdout: task.output,
            stderr: '',
            isImage: false,
            dangerouslyDisableSandbox: true,
            returnCodeInterpretation: task.error,
          }}
          verbose={verbose}
        />
      )
    case 'local_agent':
      return renderLocalAgentOutput(result, expandShortcut, verbose, theme)
    case 'remote_agent':
      return renderRemoteAgentOutput(task, expandShortcut, verbose)
    case 'in_process_teammate':
    case 'local_workflow':
    case 'monitor_mcp':
    case 'dream':
      return renderGenericTaskOutput(task)
  }
}

function renderLocalAgentOutput(
  result: TaskOutputToolOutput,
  expandShortcut: string,
  verbose: boolean,
  theme: ThemeName,
): React.ReactNode {
  const task = result.task
  if (!task) return null

  if (result.retrieval_status === 'success') {
    if (!verbose) {
      return (
        <MessageResponse>
          <Text dimColor={true}>Read output ({expandShortcut} to expand)</Text>
        </MessageResponse>
      )
    }

    const lineCount = task.result
      ? countCharInString(task.result, '\n') + 1
      : 0
    return (
      <Box flexDirection="column">
        <Text>
          {task.description} ({lineCount} lines)
        </Text>
        <Box flexDirection="column" paddingLeft={2} marginTop={1}>
          {task.prompt && (
            <AgentPromptDisplay prompt={task.prompt} theme={theme} dim={true} />
          )}
          {task.result && (
            <Box marginTop={1}>
              <AgentResponseDisplay
                content={[{ type: 'text', text: task.result }]}
                theme={theme}
              />
            </Box>
          )}
          {task.error && (
            <Box flexDirection="column" marginTop={1}>
              <Text color="error" bold={true}>
                Error:
              </Text>
              <Box paddingLeft={2}>
                <Text color="error">{task.error}</Text>
              </Box>
            </Box>
          )}
        </Box>
      </Box>
    )
  }

  if (result.retrieval_status === 'timeout' || task.status === 'running') {
    return <StillRunningMessage />
  }
  if (result.retrieval_status === 'not_ready') return <StillRunningMessage />
  return (
    <MessageResponse>
      <Text dimColor={true}>Task not ready</Text>
    </MessageResponse>
  )
}

function renderRemoteAgentOutput(
  task: NonNullable<TaskOutputToolOutput['task']>,
  expandShortcut: string,
  verbose: boolean,
): React.ReactNode {
  return (
    <Box flexDirection="column">
      <Text>
        {'  '}
        {task.description} [{task.status}]
      </Text>
      {task.output && verbose && (
        <Box paddingLeft={4} marginTop={1}>
          <Text>{task.output}</Text>
        </Box>
      )}
      {!verbose && task.output && (
        <Text dimColor={true}>
          {'     '}({expandShortcut} to expand)
        </Text>
      )}
    </Box>
  )
}

function renderGenericTaskOutput(
  task: NonNullable<TaskOutputToolOutput['task']>,
): React.ReactNode {
  return (
    <Box flexDirection="column">
      <Text>
        {'  '}
        {task.description} [{task.status}]
      </Text>
      {task.output && (
        <Box paddingLeft={4}>
          <Text>{task.output.slice(0, 500)}</Text>
        </Box>
      )}
    </Box>
  )
}

export function renderTaskOutputResultMessage(
  content: TaskOutputToolOutput | string,
  verbose: boolean,
  theme: ThemeName,
): React.ReactNode {
  return (
    <TaskOutputResultDisplay content={content} verbose={verbose} theme={theme} />
  )
}

export function renderTaskOutputRejectedMessage(): React.ReactNode {
  return <FallbackToolUseRejectedMessage />
}

export function renderTaskOutputErrorMessage(
  result: unknown,
  verbose: boolean,
): React.ReactNode {
  return <FallbackToolUseErrorMessage result={result} verbose={verbose} />
}
