import { buildTool, type ToolDef } from '../../Tool.js'
import { isTodoV2Enabled } from '../../utils/tasks.js'
import { TASK_UPDATE_TOOL_NAME } from './constants.js'
import { DESCRIPTION, PROMPT } from './prompt.js'
import {
  inputSchema,
  outputSchema,
  type InputSchema,
  type Output,
  type OutputSchema,
} from './schemas.js'
import { mapTaskUpdateResultToToolResultBlockParam } from './serialization.js'
import { callTaskUpdateTool } from './statusUpdate.js'

export type { Output } from './schemas.js'

export const TaskUpdateTool = buildTool({
  name: TASK_UPDATE_TOOL_NAME,
  searchHint: 'update a task',
  maxResultSizeChars: 100_000,
  async description() {
    return DESCRIPTION
  },
  async prompt() {
    return PROMPT
  },
  get inputSchema(): InputSchema {
    return inputSchema()
  },
  get outputSchema(): OutputSchema {
    return outputSchema()
  },
  userFacingName() {
    return 'TaskUpdate'
  },
  shouldDefer: true,
  isEnabled() {
    return isTodoV2Enabled()
  },
  isConcurrencySafe() {
    return true
  },
  toAutoClassifierInput(input) {
    const parts = [input.taskId]
    if (input.status) parts.push(input.status)
    if (input.subject) parts.push(input.subject)
    return parts.join(' ')
  },
  renderToolUseMessage() {
    return null
  },
  call(input, context) {
    return callTaskUpdateTool(input, context)
  },
  mapToolResultToToolResultBlockParam: mapTaskUpdateResultToToolResultBlockParam,
} satisfies ToolDef<InputSchema, Output>)
