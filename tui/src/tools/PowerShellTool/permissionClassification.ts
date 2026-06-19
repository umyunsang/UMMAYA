import type { ToolUseContext } from '../../Tool.js';
import type { PermissionResult } from '../../utils/permissions/PermissionResult.js';
import { getBypassImmuneShellPermissionResult } from '../BashTool/shellPermissionGauntlet.js';
import { getDestructiveCommandWarning } from './destructiveCommandWarning.js';
import { powershellToolHasPermission } from './powershellPermissions.js';
import { hasSyncSecurityConcerns, isReadOnlyCommand } from './readOnlyValidation.js';
import { POWERSHELL_TOOL_NAME } from './toolName.js';
import type { PowerShellToolInput } from './schemas.js';

export function isPowerShellReadOnly(input: PowerShellToolInput): boolean {
  if (hasSyncSecurityConcerns(input.command)) {
    return false;
  }
  return isReadOnlyCommand(input.command);
}

export async function checkPowerShellPermissions(input: PowerShellToolInput, context: ToolUseContext): Promise<PermissionResult> {
  const bypassImmuneResult = getBypassImmuneShellPermissionResult(
    input.command,
    POWERSHELL_TOOL_NAME,
    context.getAppState().toolPermissionContext,
    getDestructiveCommandWarning
  );
  if (bypassImmuneResult !== null) {
    return bypassImmuneResult;
  }
  return powershellToolHasPermission(input, context);
}
