import type { ToolPermissionContext } from '../../Tool.js'
import type { PermissionResult } from '../../utils/permissions/PermissionResult.js'

type ShellRiskClass = {
  readonly kind: 'destructive' | 'protected-ax'
  readonly reason: string
}

type DestructiveWarningFn = (command: string) => string | null

const PROTECTED_AX_PATTERNS: readonly { readonly pattern: RegExp; readonly reason: string }[] = [
  {
    pattern:
      /\b(?:curl|wget|http|https|invoke-webrequest|invoke-restmethod|iwr|irm)\b[\s\S]*(?:data\.go\.kr|www\.gov\.kr|gov\.kr|hometax\.go\.kr|wetax\.go\.kr|openbanking|kftc|mobileid|omnidid|omni[-_ ]?one)/iu,
    reason:
      'Shell command appears to call Korean public-service, identity, payment, or government infrastructure',
  },
  {
    pattern:
      /\b(?:hometax|government24|gov24|wetax|openbanking|kftc|mobile[-_ ]?id|certificate|public[-_ ]?certificate|identity|payment|pipa|정부24|홈택스|위택스|모바일신분증|공동인증서|금융인증서)\b/iu,
    reason:
      'Shell command references protected national AX, identity, certificate, or payment surfaces',
  },
  {
    pattern:
      /\bUMMAYA_[A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|CERT|CERTIFICATE|API_KEY|AUTH_KEY|SERVICE_KEY)\b/u,
    reason:
      'Shell command references UMMAYA credential material for protected infrastructure access',
  },
]

function shouldTreatModeAsBypass(toolPermissionContext: ToolPermissionContext): boolean {
  return (
    toolPermissionContext.mode === 'bypassPermissions' ||
    (toolPermissionContext.mode === 'plan' &&
      toolPermissionContext.isBypassPermissionsModeAvailable)
  )
}

export function classifyShellRiskForPermissionGauntlet(
  command: string,
  getDestructiveWarning: DestructiveWarningFn,
): ShellRiskClass | null {
  const destructiveWarning = getDestructiveWarning(command)
  if (destructiveWarning !== null) {
    return {
      kind: 'destructive',
      reason: destructiveWarning,
    }
  }

  for (const { pattern, reason } of PROTECTED_AX_PATTERNS) {
    if (pattern.test(command)) {
      return {
        kind: 'protected-ax',
        reason,
      }
    }
  }

  return null
}

export function getBypassImmuneShellPermissionResult(
  command: string,
  toolName: string,
  toolPermissionContext: ToolPermissionContext,
  getDestructiveWarning: DestructiveWarningFn,
): PermissionResult | null {
  if (!shouldTreatModeAsBypass(toolPermissionContext)) {
    return null
  }

  const risk = classifyShellRiskForPermissionGauntlet(
    command,
    getDestructiveWarning,
  )
  if (risk === null) {
    return null
  }

  const reason =
    risk.kind === 'destructive'
      ? `Destructive shell command requires explicit approval even in bypassPermissions mode: ${risk.reason}`
      : `Protected AX-adjacent shell command requires explicit approval even in bypassPermissions mode: ${risk.reason}`

  return {
    behavior: 'ask',
    message: `${toolName} command requires explicit approval. ${reason}`,
    decisionReason: {
      type: 'safetyCheck',
      reason,
      classifierApprovable: false,
    },
    suggestions: [],
  }
}
