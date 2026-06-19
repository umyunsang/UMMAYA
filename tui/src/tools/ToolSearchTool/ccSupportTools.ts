/* eslint-disable custom-rules/no-process-env-top-level, @typescript-eslint/no-require-imports */
import { feature } from 'bun:bundle'
import type { Tool, Tools } from '../../Tool.js'
import { isAgentSwarmsEnabled } from '../../utils/agentSwarmsEnabled.js'
import { hasEmbeddedSearchTools } from '../../utils/embeddedTools.js'
import { isEnvTruthy } from '../../utils/envUtils.js'
import { isPowerShellToolEnabled } from '../../utils/shell/shellToolUtils.js'
import { isTodoV2Enabled } from '../../utils/tasks.js'
import { isWorktreeModeEnabled } from '../../utils/worktreeModeEnabled.js'
import { AgentTool } from '../AgentTool/AgentTool.js'
import { AskUserQuestionTool } from '../AskUserQuestionTool/AskUserQuestionTool.js'
import { BashTool } from '../BashTool/BashTool.js'
import { BriefTool } from '../BriefTool/BriefTool.js'
import { ConfigTool } from '../ConfigTool/ConfigTool.js'
import { EnterPlanModeTool } from '../EnterPlanModeTool/EnterPlanModeTool.js'
import { EnterWorktreeTool } from '../EnterWorktreeTool/EnterWorktreeTool.js'
import { ExitPlanModeV2Tool } from '../ExitPlanModeTool/ExitPlanModeV2Tool.js'
import { ExitWorktreeTool } from '../ExitWorktreeTool/ExitWorktreeTool.js'
import { FileEditTool } from '../FileEditTool/FileEditTool.js'
import { FileReadTool } from '../FileReadTool/FileReadTool.js'
import { FileWriteTool } from '../FileWriteTool/FileWriteTool.js'
import { GlobTool } from '../GlobTool/GlobTool.js'
import { GrepTool } from '../GrepTool/GrepTool.js'
import { LSPTool } from '../LSPTool/LSPTool.js'
import { ListMcpResourcesTool } from '../ListMcpResourcesTool/ListMcpResourcesTool.js'
import { NotebookEditTool } from '../NotebookEditTool/NotebookEditTool.js'
import { ReadMcpResourceTool } from '../ReadMcpResourceTool/ReadMcpResourceTool.js'
import {
  REPL_TOOL_NAME,
  REPL_ONLY_TOOLS,
  isReplModeEnabled,
} from '../REPLTool/constants.js'
import { SkillTool } from '../SkillTool/SkillTool.js'
import { TaskCreateTool } from '../TaskCreateTool/TaskCreateTool.js'
import { TaskGetTool } from '../TaskGetTool/TaskGetTool.js'
import { TaskListTool } from '../TaskListTool/TaskListTool.js'
import { TaskOutputTool } from '../TaskOutputTool/TaskOutputTool.js'
import { TaskStopTool } from '../TaskStopTool/TaskStopTool.js'
import { TaskUpdateTool } from '../TaskUpdateTool/TaskUpdateTool.js'
import { TodoWriteTool } from '../TodoWriteTool/TodoWriteTool.js'
import { TungstenTool } from '../TungstenTool/TungstenTool.js'
import { WebFetchTool } from '../WebFetchTool/WebFetchTool.js'
import { WebSearchTool } from '../WebSearchTool/WebSearchTool.js'
import { TestingPermissionTool } from '../testing/TestingPermissionTool.js'

export { REPL_ONLY_TOOLS, REPL_TOOL_NAME, isReplModeEnabled }

const CC_SUPPORT_TOOLS_ENV = 'UMMAYA_ENABLE_CC_SUPPORT_TOOLS'

const REPLTool =
  process.env.USER_TYPE === 'ant'
    ? require('../REPLTool/REPLTool.js').REPLTool
    : null
const SuggestBackgroundPRTool =
  process.env.USER_TYPE === 'ant'
    ? require('../SuggestBackgroundPRTool/SuggestBackgroundPRTool.js')
        .SuggestBackgroundPRTool
    : null
const SleepTool =
  feature('PROACTIVE') || feature('KAIROS')
    ? require('../SleepTool/SleepTool.js').SleepTool
    : null
const cronTools = feature('AGENT_TRIGGERS')
  ? [
      require('../ScheduleCronTool/CronCreateTool.js').CronCreateTool,
      require('../ScheduleCronTool/CronDeleteTool.js').CronDeleteTool,
      require('../ScheduleCronTool/CronListTool.js').CronListTool,
    ]
  : []
const RemoteTriggerTool = feature('AGENT_TRIGGERS_REMOTE')
  ? require('../RemoteTriggerTool/RemoteTriggerTool.js').RemoteTriggerTool
  : null
const MonitorTool = feature('MONITOR_TOOL')
  ? require('../MonitorTool/MonitorTool.js').MonitorTool
  : null
const SendUserFileTool = feature('KAIROS')
  ? require('../SendUserFileTool/SendUserFileTool.js').SendUserFileTool
  : null
const PushNotificationTool =
  feature('KAIROS') || feature('KAIROS_PUSH_NOTIFICATION')
    ? require('../PushNotificationTool/PushNotificationTool.js')
        .PushNotificationTool
    : null
const SubscribePRTool = feature('KAIROS_GITHUB_WEBHOOKS')
  ? require('../SubscribePRTool/SubscribePRTool.js').SubscribePRTool
  : null
const OverflowTestTool = feature('OVERFLOW_TEST_TOOL')
  ? require('../OverflowTestTool/OverflowTestTool.js').OverflowTestTool
  : null
const CtxInspectTool = feature('CONTEXT_COLLAPSE')
  ? require('../CtxInspectTool/CtxInspectTool.js').CtxInspectTool
  : null
const TerminalCaptureTool = feature('TERMINAL_PANEL')
  ? require('../TerminalCaptureTool/TerminalCaptureTool.js').TerminalCaptureTool
  : null
const WebBrowserTool = feature('WEB_BROWSER_TOOL')
  ? require('../WebBrowserTool/WebBrowserTool.js').WebBrowserTool
  : null
const coordinatorModeModule = feature('COORDINATOR_MODE')
  ? require('../../coordinator/coordinatorMode.js')
  : null
const SnipTool = feature('HISTORY_SNIP')
  ? require('../SnipTool/SnipTool.js').SnipTool
  : null
const ListPeersTool = feature('UDS_INBOX')
  ? require('../ListPeersTool/ListPeersTool.js').ListPeersTool
  : null
const WorkflowTool = feature('WORKFLOW_SCRIPTS')
  ? (() => {
      require('../WorkflowTool/bundled/index.js').initBundledWorkflows()
      return require('../WorkflowTool/WorkflowTool.js').WorkflowTool
    })()
  : null
const VerifyPlanExecutionTool =
  process.env.CLAUDE_CODE_VERIFY_PLAN === 'true'
    ? require('../VerifyPlanExecutionTool/VerifyPlanExecutionTool.js')
        .VerifyPlanExecutionTool
    : null

function getTeamCreateTool() {
  return require('../TeamCreateTool/TeamCreateTool.js').TeamCreateTool
}

function getTeamDeleteTool() {
  return require('../TeamDeleteTool/TeamDeleteTool.js').TeamDeleteTool
}

function getSendMessageTool() {
  return require('../SendMessageTool/SendMessageTool.js').SendMessageTool
}

function getPowerShellTool() {
  if (!isPowerShellToolEnabled()) return null
  return require('../PowerShellTool/PowerShellTool.js').PowerShellTool
}

function asDeferredCcSupportTool(tool: Tool): Tool {
  if (tool.alwaysLoad === true || tool.shouldDefer === true) return tool
  return { ...tool, shouldDefer: true }
}

export function areCcSupportToolsEnabled(): boolean {
  return process.env[CC_SUPPORT_TOOLS_ENV] !== '0'
}

export function getSupportSimpleModeTools(modelFacingTools: Tools): Tools {
  if (isReplModeEnabled() && REPLTool && areCcSupportToolsEnabled()) {
    const replSimple: Tool[] = [REPLTool]
    if (
      feature('COORDINATOR_MODE') &&
      coordinatorModeModule?.isCoordinatorMode()
    ) {
      replSimple.push(TaskStopTool, getSendMessageTool())
    }
    return replSimple
  }

  const simpleTools: Tool[] = [...modelFacingTools]
  if (
    feature('COORDINATOR_MODE') &&
    coordinatorModeModule?.isCoordinatorMode() &&
    areCcSupportToolsEnabled()
  ) {
    simpleTools.push(AgentTool, TaskStopTool, getSendMessageTool())
  }
  return simpleTools
}

export function getCcSupportCapabilityTools(): Tools {
  if (!areCcSupportToolsEnabled()) return []
  const powerShellTool = getPowerShellTool()
  return [
    AgentTool,
    TaskOutputTool,
    BashTool,
    ...(hasEmbeddedSearchTools() ? [] : [GlobTool, GrepTool]),
    ExitPlanModeV2Tool,
    FileReadTool,
    FileEditTool,
    FileWriteTool,
    NotebookEditTool,
    WebFetchTool,
    TodoWriteTool,
    WebSearchTool,
    TaskStopTool,
    AskUserQuestionTool,
    SkillTool,
    EnterPlanModeTool,
    ...(process.env.USER_TYPE === 'ant' ? [ConfigTool, TungstenTool] : []),
    ...(SuggestBackgroundPRTool ? [SuggestBackgroundPRTool] : []),
    ...(WebBrowserTool ? [WebBrowserTool] : []),
    ...(isTodoV2Enabled()
      ? [TaskCreateTool, TaskGetTool, TaskUpdateTool, TaskListTool]
      : []),
    ...(OverflowTestTool ? [OverflowTestTool] : []),
    ...(CtxInspectTool ? [CtxInspectTool] : []),
    ...(TerminalCaptureTool ? [TerminalCaptureTool] : []),
    ...(isEnvTruthy(process.env.ENABLE_LSP_TOOL) ? [LSPTool] : []),
    ...(isWorktreeModeEnabled() ? [EnterWorktreeTool, ExitWorktreeTool] : []),
    getSendMessageTool(),
    ...(ListPeersTool ? [ListPeersTool] : []),
    ...(isAgentSwarmsEnabled()
      ? [getTeamCreateTool(), getTeamDeleteTool()]
      : []),
    ...(VerifyPlanExecutionTool ? [VerifyPlanExecutionTool] : []),
    ...(process.env.USER_TYPE === 'ant' && REPLTool ? [REPLTool] : []),
    ...(WorkflowTool ? [WorkflowTool] : []),
    ...(SleepTool ? [SleepTool] : []),
    ...cronTools,
    ...(RemoteTriggerTool ? [RemoteTriggerTool] : []),
    ...(MonitorTool ? [MonitorTool] : []),
    BriefTool,
    ...(SendUserFileTool ? [SendUserFileTool] : []),
    ...(PushNotificationTool ? [PushNotificationTool] : []),
    ...(SubscribePRTool ? [SubscribePRTool] : []),
    ...(powerShellTool ? [powerShellTool] : []),
    ...(SnipTool ? [SnipTool] : []),
    ...(process.env.NODE_ENV === 'test' ? [TestingPermissionTool] : []),
    ListMcpResourcesTool,
    ReadMcpResourceTool,
  ].map(asDeferredCcSupportTool)
}
/* eslint-enable custom-rules/no-process-env-top-level, @typescript-eslint/no-require-imports */
