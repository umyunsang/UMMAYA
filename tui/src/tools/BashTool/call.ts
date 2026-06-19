import type { CanUseToolFn } from 'src/hooks/useCanUseTool.js';
import { type AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS, logEvent } from '../../services/analytics/index.js';
import type { ToolCallProgress, ToolUseContext } from '../../Tool.js';
import type { AssistantMessage } from '../../types/message.js';
import type { BashProgress } from '../../types/tools.js';
import { extractClaudeCodeHints } from '../../utils/claudeCodeHints.js';
import { detectCodeIndexingFromCommand } from '../../utils/codeIndexing.js';
import { ShellError } from '../../utils/errors.js';
import { EndTruncatingAccumulator } from '../../utils/stringUtils.js';
import { maybeRecordPluginHint } from '../../utils/plugins/hintRecommendation.js';
import type { ExecResult } from '../../utils/ShellCommand.js';
import { resetShellCwdIfOutsideProject } from './cwdReset.js';
import { resizeShellImageOutput, stdErrAppendShellResetMessage, stripEmptyLines, isImageOutput } from './shellOutputUtils.js';
import { interpretCommandResult } from './commandSemantics.js';
import { trackGitOperations } from '../shared/gitOperationTracking.js';
import { runShellCommand } from './shellExecution.js';
import { persistLargeShellOutput } from './outputPersistence.js';
import { applySedEdit } from './sedEditExecution.js';
import { isSilentBashCommand } from './commandClassification.js';
import type { BashToolInput, Out } from './schemas.js';
import { annotateShellStderrWithSandboxFailures } from './sandboxPolicy.js';

const EOL = '\n';

export async function callBashTool(
  input: BashToolInput,
  toolUseContext: ToolUseContext,
  _canUseTool?: CanUseToolFn,
  parentMessage?: AssistantMessage,
  onProgress?: ToolCallProgress<BashProgress>
): Promise<{ readonly data: Out }> {
  if (input._simulatedSedEdit) {
    return applySedEdit(input._simulatedSedEdit, toolUseContext, parentMessage);
  }
  const { abortController, getAppState, setAppState, setToolJSX } = toolUseContext;
  const stdoutAccumulator = new EndTruncatingAccumulator();
  let stderrForShellReset = '';
  let interpretationResult: ReturnType<typeof interpretCommandResult> | undefined;
  let wasInterrupted = false;
  const isMainThread = !toolUseContext.agentId;
  const preventCwdChanges = !isMainThread;
  const { execResult } = await consumeBashCommand({
    input,
    toolUseContext,
    preventCwdChanges,
    isMainThread,
    onProgress
  });
  try {
    trackGitOperations(input.command, execResult.code, execResult.stdout);
    const isInterrupt = execResult.interrupted && abortController.signal.reason === 'interrupt';
    stdoutAccumulator.append((execResult.stdout || '').trimEnd() + EOL);
    interpretationResult = interpretCommandResult(input.command, execResult.code, execResult.stdout || '', '');
    if (execResult.stdout && execResult.stdout.includes(".git/index.lock': File exists")) {
      logEvent('tengu_git_index_lock_error', {});
    }
    if (interpretationResult.isError && !isInterrupt && execResult.code !== 0) {
      stdoutAccumulator.append(`Exit code ${execResult.code}`);
    }
    if (!preventCwdChanges) {
      const appState = getAppState();
      if (resetShellCwdIfOutsideProject(appState.toolPermissionContext)) {
        stderrForShellReset = stdErrAppendShellResetMessage('');
      }
    }
    const outputWithSbFailures = annotateShellStderrWithSandboxFailures(input.command, execResult.stdout || '');
    if (execResult.preSpawnError) {
      throw new Error(execResult.preSpawnError);
    }
    if (interpretationResult.isError && !isInterrupt) {
      throw new ShellError('', outputWithSbFailures, execResult.code, execResult.interrupted);
    }
    wasInterrupted = execResult.interrupted;
  } finally {
    if (setToolJSX) setToolJSX(null);
  }
  const stdout = stdoutAccumulator.toString();
  const persisted = await persistLargeShellOutput(execResult);
  logShellExecution(input.command, stdout, execResult.code, wasInterrupted);
  let strippedStdout = stripEmptyLines(stdout);
  const extracted = extractClaudeCodeHints(strippedStdout, input.command);
  strippedStdout = extracted.stripped;
  if (isMainThread && extracted.hints.length > 0) {
    for (const hint of extracted.hints) maybeRecordPluginHint(hint);
  }
  const imageResult = await normalizeImageOutput(strippedStdout, execResult.outputFilePath, persisted.size);
  return {
    data: {
      stdout: imageResult.stdout,
      stderr: stderrForShellReset,
      interrupted: wasInterrupted,
      isImage: imageResult.isImage,
      returnCodeInterpretation: interpretationResult?.message,
      noOutputExpected: isSilentBashCommand(input.command),
      backgroundTaskId: execResult.backgroundTaskId,
      backgroundedByUser: execResult.backgroundedByUser,
      assistantAutoBackgrounded: execResult.assistantAutoBackgrounded,
      dangerouslyDisableSandbox: 'dangerouslyDisableSandbox' in input ? input.dangerouslyDisableSandbox : undefined,
      persistedOutputPath: persisted.path,
      persistedOutputSize: persisted.size
    }
  };
}

type ConsumeInput = {
  readonly input: BashToolInput;
  readonly toolUseContext: ToolUseContext;
  readonly preventCwdChanges: boolean;
  readonly isMainThread: boolean;
  readonly onProgress?: ToolCallProgress<BashProgress>;
};

type ConsumeResult = {
  readonly execResult: ExecResult;
};

async function consumeBashCommand({
  input,
  toolUseContext,
  preventCwdChanges,
  isMainThread,
  onProgress
}: ConsumeInput): Promise<ConsumeResult> {
  const commandGenerator = runShellCommand({
    input,
    abortController: toolUseContext.abortController,
    setAppState: toolUseContext.setAppStateForTasks ?? toolUseContext.setAppState,
    setToolJSX: toolUseContext.setToolJSX,
    preventCwdChanges,
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
        toolUseID: `bash-progress-${progressCounter++}`,
        data: {
          type: 'bash_progress',
          output: progress.output,
          fullOutput: progress.fullOutput,
          elapsedTimeSeconds: progress.elapsedTimeSeconds,
          totalLines: progress.totalLines,
          totalBytes: progress.totalBytes,
          taskId: progress.taskId,
          timeoutMs: progress.timeoutMs
        }
      });
    }
  } while (!generatorResult.done);
  return {
    execResult: generatorResult.value
  };
}

function logShellExecution(command: string, stdout: string, code: number, interrupted: boolean): void {
  const commandType = command.split(' ')[0];
  logEvent('tengu_bash_tool_command_executed', {
    command_type: commandType as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS,
    stdout_length: stdout.length,
    stderr_length: 0,
    exit_code: code,
    interrupted
  });
  const codeIndexingTool = detectCodeIndexingFromCommand(command);
  if (codeIndexingTool) {
    logEvent('tengu_code_indexing_tool_used', {
      tool: codeIndexingTool as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS,
      source: 'cli' as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS,
      success: code === 0
    });
  }
}

type ImageOutput = {
  readonly stdout: string;
  readonly isImage: boolean;
};

async function normalizeImageOutput(stdout: string, outputFilePath?: string, persistedOutputSize?: number): Promise<ImageOutput> {
  if (!isImageOutput(stdout)) {
    return {
      stdout,
      isImage: false
    };
  }
  const resized = await resizeShellImageOutput(stdout, outputFilePath, persistedOutputSize);
  if (resized) {
    return {
      stdout: resized,
      isImage: true
    };
  }
  return {
    stdout,
    isImage: false
  };
}
