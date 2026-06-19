import { feature } from 'bun:bundle';
import * as React from 'react';
import type { SetToolJSXFn } from '../../Tool.js';
import { backgroundExistingForegroundTask, markTaskNotified, registerForeground, spawnShellTask, unregisterForeground } from '../../tasks/LocalShellTask/LocalShellTask.js';
import type { AgentId } from '../../types/ids.js';
import type { AppState } from '../../state/AppState.js';
import { getKairosActive } from '../../bootstrap/state.js';
import { logEvent } from '../../services/analytics/index.js';
import { exec } from '../../utils/Shell.js';
import type { ExecResult } from '../../utils/ShellCommand.js';
import { TaskOutput } from '../../utils/task/TaskOutput.js';
import { getDefaultTimeoutMs } from './prompt.js';
import { shouldUseSandboxForShell } from './sandboxPolicy.js';
import type { BashToolInput } from './schemas.js';
import { isBackgroundTasksDisabled } from './schemas.js';
import { getCommandTypeForLogging, isAutobackgroundingAllowed } from './commandClassification.js';
import { loadBashUI } from './uiLoader.js';

const PROGRESS_THRESHOLD_MS = 2000;
const ASSISTANT_BLOCKING_BUDGET_MS = 15_000;

export type BashExecutionProgress = {
  readonly type: 'progress'; readonly output: string; readonly fullOutput: string;
  readonly elapsedTimeSeconds: number; readonly totalLines: number;
  readonly totalBytes?: number; readonly taskId?: string; readonly timeoutMs?: number;
};

type RunShellCommandInput = {
  readonly input: BashToolInput; readonly abortController: AbortController;
  readonly setAppState: (f: (prev: AppState) => AppState) => void;
  readonly setToolJSX?: SetToolJSXFn; readonly preventCwdChanges?: boolean;
  readonly isMainThread?: boolean; readonly toolUseId?: string; readonly agentId?: AgentId;
};

export async function* runShellCommand({
  input,
  abortController,
  setAppState,
  setToolJSX,
  preventCwdChanges,
  isMainThread,
  toolUseId,
  agentId
}: RunShellCommandInput): AsyncGenerator<BashExecutionProgress, ExecResult, void> {
  const { command, description, timeout, run_in_background } = input;
  const timeoutMs = timeout || getDefaultTimeoutMs();
  let fullOutput = '';
  let lastProgressOutput = '';
  let lastTotalLines = 0;
  let lastTotalBytes = 0;
  let backgroundShellId: string | undefined = undefined;
  let assistantAutoBackgrounded = false;
  let resolveProgress: (() => void) | null = null;
  function createProgressSignal(): Promise<null> {
    return new Promise<null>(resolve => {
      resolveProgress = () => resolve(null);
    });
  }
  const shouldAutoBackground = !isBackgroundTasksDisabled && isAutobackgroundingAllowed(command);
  const shellCommand = await exec(command, abortController.signal, 'bash', {
    timeout: timeoutMs,
    onProgress(lastLines, allLines, totalLines, totalBytes, isIncomplete) {
      lastProgressOutput = lastLines;
      fullOutput = allLines;
      lastTotalLines = totalLines;
      lastTotalBytes = isIncomplete ? totalBytes : 0;
      const resolve = resolveProgress;
      if (resolve) {
        resolveProgress = null;
        resolve();
      }
    },
    preventCwdChanges,
    shouldUseSandbox: shouldUseSandboxForShell(input),
    shouldAutoBackground
  });
  const resultPromise = shellCommand.result;
  async function spawnBackgroundTask(): Promise<string> {
    const handle = await spawnShellTask({
      command,
      description: description || command,
      shellCommand,
      toolUseId,
      agentId
    }, {
      abortController,
      getAppState: () => {
        throw new Error('getAppState not available in runShellCommand context');
      },
      setAppState
    });
    return handle.taskId;
  }
  function startBackgrounding(eventName: string, backgroundFn?: (shellId: string) => void): void {
    if (foregroundTaskId) {
      if (!backgroundExistingForegroundTask(foregroundTaskId, shellCommand, description || command, setAppState, toolUseId)) {
        return;
      }
      backgroundShellId = foregroundTaskId;
      logEvent(eventName, {
        command_type: getCommandTypeForLogging(command)
      });
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
      logEvent(eventName, {
        command_type: getCommandTypeForLogging(command)
      });
      if (backgroundFn) {
        backgroundFn(shellId);
      }
    });
  }
  if (shellCommand.onTimeout && shouldAutoBackground) {
    shellCommand.onTimeout(backgroundFn => {
      startBackgrounding('tengu_bash_command_timeout_backgrounded', backgroundFn);
    });
  }
  if (feature('KAIROS') && getKairosActive() && isMainThread && !isBackgroundTasksDisabled && run_in_background !== true) {
    setTimeout(() => {
      if (shellCommand.status === 'running' && backgroundShellId === undefined) {
        assistantAutoBackgrounded = true;
        startBackgrounding('tengu_bash_command_assistant_auto_backgrounded');
      }
    }, ASSISTANT_BLOCKING_BUDGET_MS).unref();
  }
  if (run_in_background === true && !isBackgroundTasksDisabled) {
    const shellId = await spawnBackgroundTask();
    logEvent('tengu_bash_command_explicitly_backgrounded', {
      command_type: getCommandTypeForLogging(command)
    });
    return {
      stdout: '',
      stderr: '',
      code: 0,
      interrupted: false,
      backgroundTaskId: shellId
    };
  }
  const startTime = Date.now();
  let foregroundTaskId: string | undefined = undefined;
  {
    const initialResult = await Promise.race([resultPromise, new Promise<null>(resolve => {
      const timer = setTimeout((done: (value: null) => void) => done(null), PROGRESS_THRESHOLD_MS, resolve);
      timer.unref();
    })]);
    if (initialResult !== null) {
      shellCommand.cleanup();
      return initialResult;
    }
    if (backgroundShellId) {
      return {
        stdout: '',
        stderr: '',
        code: 0,
        interrupted: false,
        backgroundTaskId: backgroundShellId,
        assistantAutoBackgrounded
      };
    }
  }
  TaskOutput.startPolling(shellCommand.taskOutput.taskId);
  try {
    while (true) {
      const progressSignal = createProgressSignal();
      const result = await Promise.race([resultPromise, progressSignal]);
      if (result !== null) {
        if (result.backgroundTaskId !== undefined) {
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
        if (foregroundTaskId) {
          unregisterForeground(foregroundTaskId, setAppState);
        }
        shellCommand.cleanup();
        return result;
      }
      if (backgroundShellId) {
        return {
          stdout: '',
          stderr: '',
          code: 0,
          interrupted: false,
          backgroundTaskId: backgroundShellId,
          assistantAutoBackgrounded
        };
      }
      if (foregroundTaskId && shellCommand.status === 'backgrounded') {
        return {
          stdout: '',
          stderr: '',
          code: 0,
          interrupted: false,
          backgroundTaskId: foregroundTaskId,
          backgroundedByUser: true
        };
      }
      const elapsedSeconds = Math.floor((Date.now() - startTime) / 1000);
      if (!isBackgroundTasksDisabled && backgroundShellId === undefined && elapsedSeconds >= PROGRESS_THRESHOLD_MS / 1000 && setToolJSX) {
        if (!foregroundTaskId) {
          foregroundTaskId = registerForeground({
            command,
            description: description || command,
            shellCommand,
            agentId
          }, setAppState, toolUseId);
        }
        const { BackgroundHint } = loadBashUI();
        setToolJSX({
          jsx: <BackgroundHint />,
          shouldHidePromptInput: false,
          shouldContinueAnimation: true,
          showSpinner: true
        });
      }
      yield {
        type: 'progress',
        fullOutput,
        output: lastProgressOutput,
        elapsedTimeSeconds: elapsedSeconds,
        totalLines: lastTotalLines,
        totalBytes: lastTotalBytes,
        taskId: shellCommand.taskOutput.taskId,
        ...(timeout ? { timeoutMs } : undefined)
      };
    }
  } finally {
    TaskOutput.stopPolling(shellCommand.taskOutput.taskId);
  }
}
