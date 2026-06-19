import { feature } from 'bun:bundle';
import type { ValidationResult } from '../../Tool.js';
import { getPlatform } from '../../utils/platform.js';
import {
  areUnsandboxedShellCommandsAllowed,
  isShellSandboxEnabledInSettings
} from '../BashTool/sandboxPolicy.js';
import { detectBlockedSleepPattern } from './commandClassification.js';
import { isBackgroundTasksDisabled } from './schemas.js';
import type { PowerShellToolInput } from './schemas.js';

export const WINDOWS_SANDBOX_POLICY_REFUSAL = 'Enterprise policy requires sandboxing, but sandboxing is not available on native Windows. Shell command execution is blocked on this platform by policy.';

export function isWindowsSandboxPolicyViolation(): boolean {
  return getPlatform() === 'windows' && isShellSandboxEnabledInSettings() && !areUnsandboxedShellCommandsAllowed();
}

export async function validatePowerShellInput(input: PowerShellToolInput): Promise<ValidationResult> {
  if (isWindowsSandboxPolicyViolation()) {
    return {
      result: false,
      message: WINDOWS_SANDBOX_POLICY_REFUSAL,
      errorCode: 11
    };
  }
  if (feature('MONITOR_TOOL') && !isBackgroundTasksDisabled && !input.run_in_background) {
    const sleepPattern = detectBlockedSleepPattern(input.command);
    if (sleepPattern !== null) {
      return {
        result: false,
        message: `Blocked: ${sleepPattern}. Run blocking commands in the background with run_in_background: true — you'll get a completion notification when done. For streaming events (watching logs, polling APIs), use the Monitor tool. If you genuinely need a delay (rate limiting, deliberate pacing), keep it under 2 seconds.`,
        errorCode: 10
      };
    }
  }
  return {
    result: true
  };
}
