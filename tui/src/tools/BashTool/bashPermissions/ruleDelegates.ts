import {
  parsePermissionRule,
  type ShellPermissionRule,
  matchWildcardPattern as sharedMatchWildcardPattern,
  permissionRuleExtractPrefix as sharedPermissionRuleExtractPrefix,
} from '../../../utils/permissions/shellRuleMatching.js'

export const permissionRuleExtractPrefix = sharedPermissionRuleExtractPrefix

export function matchWildcardPattern(
  pattern: string,
  command: string,
): boolean {
  return sharedMatchWildcardPattern(pattern, command)
}

export const bashPermissionRule: (
  permissionRule: string,
) => ShellPermissionRule = parsePermissionRule
