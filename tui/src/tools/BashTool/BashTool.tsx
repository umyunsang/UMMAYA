import { TOOL_SUMMARY_MAX_LENGTH } from '../../constants/toolLimits.js';
import { buildTool, type ToolDef } from '../../Tool.js';
import { isEnvTruthy } from '../../utils/envUtils.js';
import { truncate } from '../../utils/format.js';
import { getPlansDirectory } from '../../utils/plans.js';
import { parseSedEditCommand } from './sedEditParser.js';
import { shouldUseSandboxForShell } from './sandboxPolicy.js';
import { BASH_TOOL_NAME } from './toolName.js';
import { loadBashCallRuntime } from './callLoader.js';
import { loadBashCommandClassificationRuntime } from './commandClassificationLoader.js';
import { isShellOutputLineTruncated } from './lineTruncation.js';
import { loadBashPermissionRuntime } from './permissionLoader.js';
import { loadBashResultRuntime } from './resultLoader.js';
import { inputSchema, outputSchema, type BashToolInput, type InputSchema, type Out } from './schemas.js';
import type { BashProgress } from '../../types/tools.js';
import { loadBashUI } from './uiLoader.js';

export type { BashProgress } from '../../types/tools.js';
export type { BashToolInput, Out } from './schemas.js';

function sedEditUserFacingName(filePath: string): string {
  return filePath.startsWith(getPlansDirectory()) ? 'Updated plan' : 'Update';
}

type BashCommandClassificationRuntime = ReturnType<
  typeof loadBashCommandClassificationRuntime
>;
type BashUIRuntime = ReturnType<typeof loadBashUI>;

type BashPermissionRuntime = ReturnType<typeof loadBashPermissionRuntime>;
type BashResultRuntime = ReturnType<typeof loadBashResultRuntime>;
type BashCallRuntime = ReturnType<typeof loadBashCallRuntime>;

const renderToolUseMessage: BashUIRuntime['renderToolUseMessage'] = (...args) =>
  loadBashUI().renderToolUseMessage(...args);
const renderToolUseProgressMessage: BashUIRuntime['renderToolUseProgressMessage'] = (...args) =>
  loadBashUI().renderToolUseProgressMessage(...args);
const renderToolUseQueuedMessage: BashUIRuntime['renderToolUseQueuedMessage'] = (...args) =>
  loadBashUI().renderToolUseQueuedMessage(...args);
const renderToolResultMessage: BashUIRuntime['renderToolResultMessage'] = (...args) =>
  loadBashUI().renderToolResultMessage(...args);
const renderToolUseErrorMessage: BashUIRuntime['renderToolUseErrorMessage'] = (...args) =>
  loadBashUI().renderToolUseErrorMessage(...args);
const validateBashInput: BashPermissionRuntime['validateBashInput'] = input =>
  loadBashPermissionRuntime().validateBashInput(input);
const isBashReadOnly: BashPermissionRuntime['isBashReadOnly'] = input =>
  loadBashPermissionRuntime().isBashReadOnly(input);
const prepareBashPermissionMatcher: BashPermissionRuntime['prepareBashPermissionMatcher'] = input =>
  loadBashPermissionRuntime().prepareBashPermissionMatcher(input);
const checkBashPermissions: BashPermissionRuntime['checkBashPermissions'] = (input, context) =>
  loadBashPermissionRuntime().checkBashPermissions(input, context);
const mapBashToolResultToBlock: BashResultRuntime['mapBashToolResultToBlock'] = (output, toolUseID) =>
  loadBashResultRuntime().mapBashToolResultToBlock(output, toolUseID);
const callBashTool: BashCallRuntime['callBashTool'] = (...args) =>
  loadBashCallRuntime().callBashTool(...args);

export const isSearchOrReadBashCommand: BashCommandClassificationRuntime['isSearchOrReadBashCommand'] = command =>
  loadBashCommandClassificationRuntime().isSearchOrReadBashCommand(command);
export const detectBlockedSleepPattern: BashCommandClassificationRuntime['detectBlockedSleepPattern'] = command =>
  loadBashCommandClassificationRuntime().detectBlockedSleepPattern(command);

export const BashTool = buildTool({
  name: BASH_TOOL_NAME,
  searchHint: 'execute shell commands',
  maxResultSizeChars: 30_000,
  strict: true,
  async description({ description }) {
    return description || 'Run shell command';
  },
  async prompt() {
    const { getSimplePrompt } = await import('./prompt.js');
    return getSimplePrompt();
  },
  isConcurrencySafe(input) {
    return this.isReadOnly?.(input) ?? false;
  },
  isReadOnly: isBashReadOnly,
  toAutoClassifierInput(input) {
    return input.command;
  },
  preparePermissionMatcher: prepareBashPermissionMatcher,
  isSearchOrReadCommand(input) {
    const parsed = inputSchema().safeParse(input);
    if (!parsed.success) {
      return {
        isSearch: false,
        isRead: false,
        isList: false
      };
    }
    return isSearchOrReadBashCommand(parsed.data.command);
  },
  get inputSchema(): InputSchema {
    return inputSchema();
  },
  get outputSchema() {
    return outputSchema();
  },
  userFacingName(input) {
    if (!input) {
      return 'Bash';
    }
    if (input.command) {
      const sedInfo = parseSedEditCommand(input.command);
      if (sedInfo) {
        return sedEditUserFacingName(sedInfo.filePath);
      }
    }
    return isEnvTruthy(process.env.CLAUDE_CODE_BASH_SANDBOX_SHOW_INDICATOR) && shouldUseSandboxForShell(input) ? 'SandboxedBash' : 'Bash';
  },
  getToolUseSummary(input) {
    if (!input?.command) {
      return null;
    }
    const { command, description } = input;
    if (description) {
      return description;
    }
    return truncate(command, TOOL_SUMMARY_MAX_LENGTH);
  },
  getActivityDescription(input) {
    if (!input?.command) {
      return 'Running command';
    }
    const desc = input.description ?? truncate(input.command, TOOL_SUMMARY_MAX_LENGTH);
    return `Running ${desc}`;
  },
  validateInput: validateBashInput,
  checkPermissions: checkBashPermissions,
  renderToolUseMessage,
  renderToolUseProgressMessage,
  renderToolUseQueuedMessage,
  renderToolResultMessage,
  extractSearchText({ stdout, stderr }) {
    return stderr ? `${stdout}\n${stderr}` : stdout;
  },
  mapToolResultToToolResultBlockParam: mapBashToolResultToBlock,
  call: callBashTool,
  renderToolUseErrorMessage,
  isResultTruncated(output) {
    return isShellOutputLineTruncated(output.stdout) || isShellOutputLineTruncated(output.stderr);
  }
} satisfies ToolDef<InputSchema, Out, BashProgress>);
