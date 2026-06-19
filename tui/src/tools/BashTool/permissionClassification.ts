import { feature } from 'bun:bundle';
import type { ToolUseContext, ValidationResult } from '../../Tool.js';
import type { PermissionResult } from '../../utils/permissions/PermissionResult.js';
import { parseForSecurity } from '../../utils/bash/ast.js';
import { bashToolHasPermission, commandHasAnyCd, matchWildcardPattern, permissionRuleExtractPrefix } from './bashPermissions.js';
import { checkReadOnlyConstraints } from './readOnlyValidation.js';
import { getDestructiveCommandWarning } from './destructiveCommandWarning.js';
import { getBypassImmuneShellPermissionResult } from './shellPermissionGauntlet.js';
import { BASH_TOOL_NAME } from './toolName.js';
import { detectBlockedSleepPattern } from './commandClassification.js';
import { isBackgroundTasksDisabled } from './schemas.js';
import type { BashToolInput } from './schemas.js';

export async function validateBashInput(input: BashToolInput): Promise<ValidationResult> {
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

export function isBashReadOnly(input: BashToolInput): boolean {
  const compoundCommandHasCd = commandHasAnyCd(input.command);
  const result = checkReadOnlyConstraints(input, compoundCommandHasCd);
  return result.behavior === 'allow';
}

export async function prepareBashPermissionMatcher({
  command
}: BashToolInput): Promise<(pattern: string) => boolean> {
  const parsed = await parseForSecurity(command);
  if (parsed.kind !== 'simple') {
    return () => true;
  }
  const subcommands = parsed.commands.map(c => c.argv.join(' '));
  return pattern => {
    const prefix = permissionRuleExtractPrefix(pattern);
    return subcommands.some(cmd => {
      if (prefix !== null) {
        return cmd === prefix || cmd.startsWith(`${prefix} `);
      }
      return matchWildcardPattern(pattern, cmd);
    });
  };
}

export async function checkBashPermissions(input: BashToolInput, context: ToolUseContext): Promise<PermissionResult> {
  const bypassImmuneResult = getBypassImmuneShellPermissionResult(
    input.command,
    BASH_TOOL_NAME,
    context.getAppState().toolPermissionContext,
    getDestructiveCommandWarning
  );
  if (bypassImmuneResult !== null) {
    return bypassImmuneResult;
  }
  return bashToolHasPermission(input, context);
}
