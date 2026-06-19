import { TOOL_SUMMARY_MAX_LENGTH } from '../../constants/toolLimits.js';
import { buildTool, type ToolDef } from '../../Tool.js';
import type { PowerShellProgress } from '../../types/tools.js';
import { truncate } from '../../utils/format.js';
import { isShellOutputLineTruncated } from '../BashTool/lineTruncation.js';
import { loadPowerShellCallRuntime } from './callLoader.js';
import { isSearchOrReadPowerShellCommand } from './commandClassification.js';
import { getPrompt } from './prompt.js';
import {
  checkPowerShellPermissions,
  isPowerShellReadOnly
} from './permissionClassification.js';
import { loadPowerShellResultRuntime } from './resultLoader.js';
import { inputSchema, outputSchema, type InputSchema, type Out, type PowerShellToolInput } from './schemas.js';
import { POWERSHELL_TOOL_NAME } from './toolName.js';
import { loadPowerShellUI } from './uiLoader.js';
import { validatePowerShellInput } from './validation.js';

export type { PowerShellProgress } from '../../types/tools.js';
export type { Out, PowerShellToolInput } from './schemas.js';
export { detectBlockedSleepPattern } from './commandClassification.js';

type PowerShellResultRuntime = ReturnType<typeof loadPowerShellResultRuntime>;
type PowerShellCallRuntime = ReturnType<typeof loadPowerShellCallRuntime>;
type PowerShellUIRuntime = ReturnType<typeof loadPowerShellUI>;

const mapPowerShellToolResultToBlock: PowerShellResultRuntime['mapPowerShellToolResultToBlock'] = (output, toolUseID) =>
  loadPowerShellResultRuntime().mapPowerShellToolResultToBlock(output, toolUseID);
const callPowerShellTool: PowerShellCallRuntime['callPowerShellTool'] = (...args) =>
  loadPowerShellCallRuntime().callPowerShellTool(...args);
const renderToolUseMessage: PowerShellUIRuntime['renderToolUseMessage'] = (...args) =>
  loadPowerShellUI().renderToolUseMessage(...args);
const renderToolUseProgressMessage: PowerShellUIRuntime['renderToolUseProgressMessage'] = (...args) =>
  loadPowerShellUI().renderToolUseProgressMessage(...args);
const renderToolUseQueuedMessage: PowerShellUIRuntime['renderToolUseQueuedMessage'] = (...args) =>
  loadPowerShellUI().renderToolUseQueuedMessage(...args);
const renderToolResultMessage: PowerShellUIRuntime['renderToolResultMessage'] = (...args) =>
  loadPowerShellUI().renderToolResultMessage(...args);
const renderToolUseErrorMessage: PowerShellUIRuntime['renderToolUseErrorMessage'] = (...args) =>
  loadPowerShellUI().renderToolUseErrorMessage(...args);

export const PowerShellTool = buildTool({
  name: POWERSHELL_TOOL_NAME,
  searchHint: 'execute Windows PowerShell commands',
  maxResultSizeChars: 30_000,
  strict: true,
  async description({ description }: Partial<PowerShellToolInput>): Promise<string> {
    return description || 'Run PowerShell command';
  },
  async prompt(): Promise<string> {
    return getPrompt();
  },
  isConcurrencySafe(input: PowerShellToolInput): boolean {
    return this.isReadOnly?.(input) ?? false;
  },
  isSearchOrReadCommand(input: Partial<PowerShellToolInput>) {
    if (!input.command) {
      return {
        isSearch: false,
        isRead: false
      };
    }
    return isSearchOrReadPowerShellCommand(input.command);
  },
  isReadOnly: isPowerShellReadOnly,
  toAutoClassifierInput(input) {
    return input.command;
  },
  get inputSchema(): InputSchema {
    return inputSchema();
  },
  get outputSchema() {
    return outputSchema();
  },
  userFacingName(): string {
    return 'PowerShell';
  },
  getToolUseSummary(input: Partial<PowerShellToolInput> | undefined): string | null {
    if (!input?.command) {
      return null;
    }
    const { command, description } = input;
    if (description) {
      return description;
    }
    return truncate(command, TOOL_SUMMARY_MAX_LENGTH);
  },
  getActivityDescription(input: Partial<PowerShellToolInput> | undefined): string {
    if (!input?.command) {
      return 'Running command';
    }
    const desc = input.description ?? truncate(input.command, TOOL_SUMMARY_MAX_LENGTH);
    return `Running ${desc}`;
  },
  isEnabled(): boolean {
    return true;
  },
  validateInput: validatePowerShellInput,
  checkPermissions: checkPowerShellPermissions,
  renderToolUseMessage,
  renderToolUseProgressMessage,
  renderToolUseQueuedMessage,
  renderToolResultMessage,
  renderToolUseErrorMessage,
  mapToolResultToToolResultBlockParam: mapPowerShellToolResultToBlock,
  call: callPowerShellTool,
  isResultTruncated(output: Out): boolean {
    return isShellOutputLineTruncated(output.stdout) || isShellOutputLineTruncated(output.stderr);
  }
} satisfies ToolDef<InputSchema, Out, PowerShellProgress>);
