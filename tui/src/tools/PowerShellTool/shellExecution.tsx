import { feature } from 'bun:bundle';
import * as React from 'react';
import { getKairosActive } from '../../bootstrap/state.js';
import { logEvent } from '../../services/analytics/index.js';
import type { SetToolJSXFn } from '../../Tool.js';
import type { AppState } from '../../state/AppState.js';
import { backgroundExistingForegroundTask, markTaskNotified, registerForeground, spawnShellTask, unregisterForeground } from '../../tasks/LocalShellTask/LocalShellTask.js';
import type { AgentId } from '../../types/ids.js';
import { errorMessage as getErrorMessage } from '../../utils/errors.js';
import { logError } from '../../utils/log.js';
import { getPlatform } from '../../utils/platform.js';
import { exec } from '../../utils/Shell.js';
import type { ExecResult } from '../../utils/ShellCommand.js';
import { getCachedPowerShellPath } from '../../utils/shell/powershellDetection.js';
import { TaskOutput } from '../../utils/task/TaskOutput.js';
import { shouldUseSandboxForShell } from '../BashTool/sandboxPolicy.js';
import { loadBashUI } from '../BashTool/uiLoader.js';
import { isAutobackgroundingAllowed, getCommandTypeForLogging } from './commandClassification.js';
import { getDefaultTimeoutMs, getMaxTimeoutMs } from './prompt.js';
import { isBackgroundTasksDisabled, type PowerShellToolInput } from './schemas.js';

const PROGRESS_THRESHOLD_MS = 2000;
const PROGRESS_INTERVAL_MS = 1000;
const ASSISTANT_BLOCKING_BUDGET_MS = 15_000;

export type PowerShellExecutionProgress = {
  readonly type: 'progress'; readonly output: string; readonly fullOutput: string;
  readonly elapsedTimeSeconds: number; readonly totalLines: number;
  readonly totalBytes: number; readonly taskId?: string; readonly timeoutMs?: number;
};

type RunPowerShellCommandInput = {
  readonly input: PowerShellToolInput; readonly abortController: AbortController;
  readonly setAppState: (f: (prev: AppState) => AppState) => void;
  readonly setToolJSX?: SetToolJSXFn; readonly preventCwdChanges?: boolean;
  readonly isMainThread?: boolean; readonly toolUseId?: string; readonly agentId?: AgentId;
};

export async function* runPowerShellCommand({
  input,
  abortController,
  setAppState,
  setToolJSX,
  preventCwdChanges,
  isMainThread,
  toolUseId,
  agentId
}: RunPowerShellCommandInput): AsyncGenerator<PowerShellExecutionProgress, ExecResult, void> {
  const { command, description, timeout, run_in_background, dangerouslyDisableSandbox } = input;
  const timeoutMs = Math.min(timeout || getDefaultTimeoutMs(), getMaxTimeoutMs());
  let fullOutput = '';
  let lastProgressOutput = '';
  let lastTotalLines = 0;
  let lastTotalBytes = 0;
  const updateProgress = (lastLines: string, allLines: string, totalLines: number, totalBytes: number, isIncomplete: boolean): void => {
    lastProgressOutput = lastLines;
    fullOutput = allLines;
    lastTotalLines = totalLines;
    lastTotalBytes = isIncomplete ? totalBytes : 0;
  };
  const powershellPath = await getCachedPowerShellPath();
  if (!powershellPath) {
    return {
      stdout: '',
      stderr: 'PowerShell is not available on this system.',
      code: 0,
      interrupted: false
    };
  }
  const shellCommand = await createShellCommand({ command, abortController, timeoutMs, preventCwdChanges, dangerouslyDisableSandbox, onProgress: updateProgress });
  if (shellCommand.kind === 'preflight') {
    return shellCommand.result;
  }
  const execution = shellCommand.value;
  const resultPromise = execution.result;
  let backgroundShellId: string | undefined = undefined;
  let interruptBackgroundingStarted = false;
  let assistantAutoBackgrounded = false;
  let resolveProgress: (() => void) | null = null;
  function createProgressSignal(): Promise<null> {
    return new Promise<null>(resolve => {
      resolveProgress = () => resolve(null);
    });
  }
  async function spawnBackgroundTask(): Promise<string> {
    const handle = await spawnShellTask({
      command,
      description: description || command,
      shellCommand: execution,
      toolUseId,
      agentId
    }, {
      abortController,
      getAppState: () => {
        throw new Error('getAppState not available in runPowerShellCommand context');
      },
      setAppState
    });
    return handle.taskId;
  }
  function startBackgrounding(eventName: string, backgroundFn?: (shellId: string) => void): void {
    if (foregroundTaskId) {
      if (!backgroundExistingForegroundTask(foregroundTaskId, execution, description || command, setAppState, toolUseId)) {
        return;
      }
      backgroundShellId = foregroundTaskId;
      logEvent(eventName, { command_type: getCommandTypeForLogging(command) });
      backgroundFn?.(foregroundTaskId);
      return;
    }
    void spawnBackgroundTask().then(shellId => {
      backgroundShellId = shellId;
      const resolve = resolveProgress;
      if (resolve) {
        resolveProgress = null;
        resolve();
      }
      logEvent(eventName, { command_type: getCommandTypeForLogging(command) });
      backgroundFn?.(shellId);
    });
  }
  const shouldAutoBackground = !isBackgroundTasksDisabled && isAutobackgroundingAllowed(command);
  if (execution.onTimeout && shouldAutoBackground) {
    execution.onTimeout(backgroundFn => startBackgrounding('tengu_powershell_command_timeout_backgrounded', backgroundFn));
  }
  if (feature('KAIROS') && getKairosActive() && isMainThread && !isBackgroundTasksDisabled && run_in_background !== true) {
    setTimeout(() => {
      if (execution.status === 'running' && backgroundShellId === undefined) {
        assistantAutoBackgrounded = true;
        startBackgrounding('tengu_powershell_command_assistant_auto_backgrounded');
      }
    }, ASSISTANT_BLOCKING_BUDGET_MS).unref();
  }
  if (run_in_background === true && !isBackgroundTasksDisabled) {
    const shellId = await spawnBackgroundTask();
    logEvent('tengu_powershell_command_explicitly_backgrounded', { command_type: getCommandTypeForLogging(command) });
    return { stdout: '', stderr: '', code: 0, interrupted: false, backgroundTaskId: shellId };
  }
  TaskOutput.startPolling(execution.taskOutput.taskId);
  const startTime = Date.now();
  let nextProgressTime = startTime + PROGRESS_THRESHOLD_MS;
  let foregroundTaskId: string | undefined = undefined;
  try {
    while (true) {
      const result = await Promise.race([resultPromise, progressDelay(nextProgressTime), createProgressSignal()]);
      if (result !== null) {
        return finishCompletedPowerShellResult(result, execution, setAppState);
      }
      if (backgroundShellId) {
        return { stdout: interruptBackgroundingStarted ? fullOutput : '', stderr: '', code: 0, interrupted: false, backgroundTaskId: backgroundShellId, assistantAutoBackgrounded };
      }
      if (abortController.signal.aborted && abortController.signal.reason === 'interrupt' && !interruptBackgroundingStarted) {
        interruptBackgroundingStarted = true;
        if (!isBackgroundTasksDisabled) {
          startBackgrounding('tengu_powershell_command_interrupt_backgrounded');
          continue;
        }
        execution.kill();
      }
      if (foregroundTaskId && execution.status === 'backgrounded') {
        return { stdout: '', stderr: '', code: 0, interrupted: false, backgroundTaskId: foregroundTaskId, backgroundedByUser: true };
      }
      const elapsedSeconds = Math.floor((Date.now() - startTime) / 1000);
      foregroundTaskId = maybeShowBackgroundHint({ command, description, execution, agentId, setAppState, setToolJSX, toolUseId, foregroundTaskId, backgroundShellId, elapsedSeconds });
      yield { type: 'progress', fullOutput, output: lastProgressOutput, elapsedTimeSeconds: elapsedSeconds, totalLines: lastTotalLines, totalBytes: lastTotalBytes, taskId: execution.taskOutput.taskId, ...(timeout ? { timeoutMs } : undefined) };
      nextProgressTime = Date.now() + PROGRESS_INTERVAL_MS;
    }
  } finally {
    TaskOutput.stopPolling(execution.taskOutput.taskId);
    if (!backgroundShellId && execution.status !== 'backgrounded') {
      if (foregroundTaskId) unregisterForeground(foregroundTaskId, setAppState);
      execution.cleanup();
    }
  }
}

type ShellCommand = Awaited<ReturnType<typeof exec>>;
type ShellCommandResult =
  | { readonly kind: 'ok'; readonly value: ShellCommand }
  | { readonly kind: 'preflight'; readonly result: ExecResult };

async function createShellCommand(input: {
  readonly command: string;
  readonly abortController: AbortController;
  readonly timeoutMs: number;
  readonly preventCwdChanges?: boolean;
  readonly dangerouslyDisableSandbox?: boolean;
  readonly onProgress: (lastLines: string, allLines: string, totalLines: number, totalBytes: number, isIncomplete: boolean) => void;
}): Promise<ShellCommandResult> {
  try {
    const value = await exec(input.command, input.abortController.signal, 'powershell', {
      timeout: input.timeoutMs,
      onProgress: input.onProgress,
      preventCwdChanges: input.preventCwdChanges,
      shouldUseSandbox: getPlatform() === 'windows' ? false : shouldUseSandboxForShell(input),
      shouldAutoBackground: !isBackgroundTasksDisabled && isAutobackgroundingAllowed(input.command)
    });
    return { kind: 'ok', value };
  } catch (error) {
    if (error instanceof Error) {
      logError(error);
      return { kind: 'preflight', result: { stdout: '', stderr: `Failed to execute PowerShell command: ${getErrorMessage(error)}`, code: 0, interrupted: false } };
    }
    throw error;
  }
}

function progressDelay(nextProgressTime: number): Promise<null> {
  const delayMs = Math.max(0, nextProgressTime - Date.now());
  return new Promise<null>(resolve => setTimeout(done => done(null), delayMs, resolve).unref());
}

function finishCompletedPowerShellResult(result: ExecResult, shellCommand: ShellCommand, setAppState: (f: (prev: AppState) => AppState) => void): ExecResult {
  if (result.backgroundTaskId === undefined) {
    return result;
  }
  markTaskNotified(result.backgroundTaskId, setAppState);
  const fixedResult: ExecResult = { ...result, backgroundTaskId: undefined };
  const { taskOutput } = shellCommand;
  if (taskOutput.stdoutToFile && !taskOutput.outputFileRedundant) {
    fixedResult.outputFilePath = taskOutput.path;
    fixedResult.outputFileSize = taskOutput.outputFileSize;
    fixedResult.outputTaskId = taskOutput.taskId;
  }
  shellCommand.cleanup();
  return fixedResult;
}

function maybeShowBackgroundHint(input: {
  readonly command: string;
  readonly description?: string;
  readonly execution: ShellCommand;
  readonly agentId?: AgentId;
  readonly setAppState: (f: (prev: AppState) => AppState) => void;
  readonly setToolJSX?: SetToolJSXFn;
  readonly toolUseId?: string;
  readonly foregroundTaskId?: string;
  readonly backgroundShellId?: string;
  readonly elapsedSeconds: number;
}): string | undefined {
  if (isBackgroundTasksDisabled || input.backgroundShellId !== undefined || input.elapsedSeconds < PROGRESS_THRESHOLD_MS / 1000 || !input.setToolJSX) {
    return input.foregroundTaskId;
  }
  const foregroundTaskId = input.foregroundTaskId ?? registerForeground({
    command: input.command,
    description: input.description || input.command,
    shellCommand: input.execution,
    agentId: input.agentId
  }, input.setAppState, input.toolUseId);
  const { BackgroundHint } = loadBashUI();
  input.setToolJSX({
    jsx: <BackgroundHint />,
    shouldHidePromptInput: false,
    shouldContinueAnimation: true,
    showSpinner: true
  });
  return foregroundTaskId;
}
