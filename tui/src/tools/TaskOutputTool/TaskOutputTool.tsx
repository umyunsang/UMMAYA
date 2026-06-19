import type { Tool } from '../../Tool.js'
import { buildTool, type ToolDef } from '../../Tool.js'
import { TASK_OUTPUT_TOOL_NAME } from './constants.js'
import { callTaskOutputTool, validateTaskOutputInput } from './lookup.js'
import {
  renderTaskOutputErrorMessage,
  renderTaskOutputRejectedMessage,
  renderTaskOutputResultMessage,
  renderTaskOutputUseMessage,
  renderTaskOutputUseProgressMessage,
  renderTaskOutputUseTag,
} from './render.js'
import {
  inputSchema,
  type InputSchema,
  type TaskOutputToolOutput,
} from './schemas.js'
import { mapTaskOutputResultToToolResultBlockParam } from './serialization.js'

const BUILD_FLAVOR = 'external'

function isExternalBuild(): boolean {
  return BUILD_FLAVOR !== 'ant'
}

export type { TaskOutputProgress as Progress } from '../../types/tools.js'

export const TaskOutputTool: Tool<InputSchema, TaskOutputToolOutput> = buildTool({
  name: TASK_OUTPUT_TOOL_NAME,
  searchHint: 'read output/logs from a background task',
  maxResultSizeChars: 100_000,
  shouldDefer: true,
  aliases: ['AgentOutputTool', 'BashOutputTool'],
  userFacingName() {
    return 'Task Output'
  },
  get inputSchema(): InputSchema {
    return inputSchema()
  },
  async description() {
    return '[Deprecated] — prefer Read on the task output file path'
  },
  isConcurrencySafe(input) {
    return this.isReadOnly(input)
  },
  isEnabled() {
    return isExternalBuild()
  },
  isReadOnly(_input) {
    return true
  },
  toAutoClassifierInput(input) {
    return input.task_id
  },
  async prompt() {
    return `DEPRECATED: Prefer using the Read tool on the task's output file path instead. Background tasks return their output file path in the tool result, and you receive a <task-notification> with the same path when the task completes — Read that file directly.

- Retrieves output from a running or completed task (background shell, agent, or remote session)
- Takes a task_id parameter identifying the task
- Returns the task output along with status information
- Use block=true (default) to wait for task completion
- Use block=false for non-blocking check of current status
- Task IDs can be found using the /tasks command
- Works with all task types: background shells, async agents, and remote sessions`
  },
  validateInput: validateTaskOutputInput,
  call(input, toolUseContext, _canUseTool, _parentMessage, onProgress) {
    return callTaskOutputTool(input, toolUseContext, onProgress)
  },
  mapToolResultToToolResultBlockParam: mapTaskOutputResultToToolResultBlockParam,
  renderToolUseMessage: renderTaskOutputUseMessage,
  renderToolUseTag: renderTaskOutputUseTag,
  renderToolUseProgressMessage: renderTaskOutputUseProgressMessage,
  renderToolResultMessage(content, _, { verbose, theme }) {
    return renderTaskOutputResultMessage(content, verbose, theme)
  },
  renderToolUseRejectedMessage: renderTaskOutputRejectedMessage,
  renderToolUseErrorMessage(result, { verbose }) {
    return renderTaskOutputErrorMessage(result, verbose)
  },
} satisfies ToolDef<InputSchema, TaskOutputToolOutput>)

export default TaskOutputTool
