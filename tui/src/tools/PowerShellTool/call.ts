import type { CanUseToolFn } from 'src/hooks/useCanUseTool.js';
import { type AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS, logEvent } from '../../services/analytics/index.js';
import type { ToolCallProgress, ToolUseContext } from '../../Tool.js';
import type { AssistantMessage } from '../../types/message.js';
import type { PowerShellProgress } from '../../types/tools.js';
import { extractClaudeCodeHints } from '../../utils/claudeCodeHints.js';
import { ShellError } from '../../utils/errors.js';
import { maybeRecordPluginHint } from '../../utils/plugins/hintRecommendation.js';
import type { ExecResult } from '../../utils/ShellCommand.js';
import { EndTruncatingAccumulator } from '../../utils/stringUtils.js';
import { trackGitOperations } from '../shared/gitOperationTracking.js';
import { resetShellCwdIfOutsideProject } from '../BashTool/cwdReset.js';
import { isImageOutput, resizeShellImageOutput, stdErrAppendShellResetMessage, stripEmptyLines } from '../BashTool/shellOutputUtils.js';
import { getCommandTypeForLogging } from './commandClassification.js';
import { interpretCommandResult } from './commandSemantics.js';
import { persistLargePowerShellOutput } from './outputPersistence.js';
import { runPowerShellCommand } from './shellExecution.js';
import { isWindowsSandboxPolicyViolation, WINDOWS_SANDBOX_POLICY_REFUSAL } from './validation.js';
import type { Out, PowerShellToolInput } from './schemas.js';

const EOL = '\n';

export async function callPowerShellTool(
  input: PowerShellToolInput,
  toolUseContext: ToolUseContext,
  _canUseTool?: CanUseToolFn,
  _parentMessage?: AssistantMessage,
  onProgress?: ToolCallProgress<PowerShellProgress>
): Promise<{ readonly data: Out }> {
  if (isWindowsSandboxPolicyViolation()) {
    throw new Error(WINDOWS_SANDBOX_POLICY_REFUSAL);
  }
  const { abortController, setToolJSX } = toolUseContext;
  const isMainThread = !toolUseContext.agentId;
  try {
    const result = await consumePowerShellCommand({ input, toolUseContext, isMainThread, onProgress });
    const isPreFlightSentinel = result.code === 0 && !result.stdout && result.stderr && !result.backgroundTaskId;
    if (!isPreFlightSentinel) {
      trackGitOperations(input.command, result.code, result.stdout);
    }
    const isInterrupt = result.interrupted && abortController.signal.reason === 'interrupt';
    const stderrForShellReset = getShellResetStderr(toolUseContext, isMainThread);
    if (result.backgroundTaskId) {
      return buildBackgroundResult(input.command, result, stderrForShellReset, isMainThread);
    }
    const stdout = prepareCompletedStdout(result, input.command, isMainThread);
    const interpretation = interpretCommandResult(input.command, result.code, stdout, result.stderr || '');
    if (result.preSpawnError) {
      throw new Error(result.preSpawnError);
    }
    if (interpretation.isError && !isInterrupt) {
      throw new ShellError(stdout, result.stderr || '', result.code, result.interrupted);
    }
    const persisted = await persistLargePowerShellOutput(result);
    const imageResult = await normalizeImageOutput(stdout, result.outputFilePath, persisted.size);
    const finalStderr = [result.stderr || '', stderrForShellReset].filter(Boolean).join('\n');
    logEvent('tengu_powershell_tool_command_executed', {
      command_type: getCommandTypeForLogging(input.command),
      stdout_length: imageResult.stdout.length,
      stderr_length: finalStderr.length,
      exit_code: result.code,
      interrupted: result.interrupted
    });
    return {
      data: {
        stdout: imageResult.stdout,
        stderr: finalStderr,
        interrupted: result.interrupted,
        returnCodeInterpretation: interpretation.message,
        isImage: imageResult.isImage,
        persistedOutputPath: persisted.path,
        persistedOutputSize: persisted.size
      }
    };
  } finally {
    if (setToolJSX) setToolJSX(null);
  }
}

type ConsumeInput = {
  readonly input: PowerShellToolInput;
  readonly toolUseContext: ToolUseContext;
  readonly isMainThread: boolean;
  readonly onProgress?: ToolCallProgress<PowerShellProgress>;
};

async function consumePowerShellCommand({
  input,
  toolUseContext,
  isMainThread,
  onProgress
}: ConsumeInput): Promise<ExecResult> {
  const commandGenerator = runPowerShellCommand({
    input,
    abortController: toolUseContext.abortController,
    setAppState: toolUseContext.setAppStateForTasks ?? toolUseContext.setAppState,
    setToolJSX: toolUseContext.setToolJSX,
    preventCwdChanges: !isMainThread,
    isMainThread,
    toolUseId: toolUseContext.toolUseId,
    agentId: toolUseContext.agentId
  });
  let progressCounter = 0;
  let generatorResult;
  do {
    generatorResult = await commandGenerator.next();
    if (!generatorResult.done && onProgress) {
      const progress = generatorResult.value;
      onProgress({
        toolUseID: `ps-progress-${progressCounter++}`,
        data: {
          type: 'powershell_progress',
          output: progress.output,
          fullOutput: progress.fullOutput,
          elapsedTimeSeconds: progress.elapsedTimeSeconds,
          totalLines: progress.totalLines,
          totalBytes: progress.totalBytes,
          timeoutMs: progress.timeoutMs,
          taskId: progress.taskId
        }
      });
    }
  } while (!generatorResult.done);
  return generatorResult.value;
}

function getShellResetStderr(toolUseContext: ToolUseContext, isMainThread: boolean): string {
  if (!isMainThread) {
    return '';
  }
  const appState = toolUseContext.getAppState();
  return resetShellCwdIfOutsideProject(appState.toolPermissionContext) ? stdErrAppendShellResetMessage('') : '';
}

function buildBackgroundResult(command: string, result: ExecResult, stderrForShellReset: string, isMainThread: boolean): { readonly data: Out } {
  const extracted = extractClaudeCodeHints(result.stdout || '', command);
  if (isMainThread && extracted.hints.length > 0) {
    for (const hint of extracted.hints) maybeRecordPluginHint(hint);
  }
  return {
    data: {
      stdout: extracted.stripped,
      stderr: [result.stderr || '', stderrForShellReset].filter(Boolean).join('\n'),
      interrupted: false,
      backgroundTaskId: result.backgroundTaskId,
      backgroundedByUser: result.backgroundedByUser,
      assistantAutoBackgrounded: result.assistantAutoBackgrounded
    }
  };
}

function prepareCompletedStdout(result: ExecResult, command: string, isMainThread: boolean): string {
  const stdoutAccumulator = new EndTruncatingAccumulator();
  const processedStdout = (result.stdout || '').trimEnd();
  stdoutAccumulator.append(processedStdout + EOL);
  let stdout = stripEmptyLines(stdoutAccumulator.toString());
  const extracted = extractClaudeCodeHints(stdout, command);
  stdout = extracted.stripped;
  if (isMainThread && extracted.hints.length > 0) {
    for (const hint of extracted.hints) maybeRecordPluginHint(hint);
  }
  return stdout;
}

type ImageOutput = {
  readonly stdout: string;
  readonly isImage: boolean;
};

async function normalizeImageOutput(stdout: string, outputFilePath?: string, persistedOutputSize?: number): Promise<ImageOutput> {
  if (!isImageOutput(stdout)) {
    return { stdout, isImage: false };
  }
  const resized = await resizeShellImageOutput(stdout, outputFilePath, persistedOutputSize);
  if (resized) {
    return { stdout: resized, isImage: true };
  }
  return { stdout, isImage: false };
}
