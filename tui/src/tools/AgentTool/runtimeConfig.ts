import { feature } from 'bun:bundle'
import type { ToolUseContext } from '../../Tool.js'
import { getFeatureValue_CACHED_MAY_BE_STALE } from '../../services/analytics/growthbook.js'
import { isEnvTruthy } from '../../utils/envUtils.js'

type ProactiveModule = {
  readonly isProactiveActive: () => boolean
}

const BUILD_FLAVOR = 'external'

/* eslint-disable @typescript-eslint/no-require-imports */
const proactiveModule: ProactiveModule | null =
  feature('PROACTIVE') || feature('KAIROS')
    ? require('../../proactive/index.js')
    : null
/* eslint-enable @typescript-eslint/no-require-imports */

export const isBackgroundTasksDisabled =
  // eslint-disable-next-line custom-rules/no-process-env-top-level -- Intentional: schema must be defined at module load
  isEnvTruthy(process.env.CLAUDE_CODE_DISABLE_BACKGROUND_TASKS)

export const PROGRESS_THRESHOLD_MS = 2000

export function isAntBuild(): boolean {
  return BUILD_FLAVOR === 'ant'
}

export function getAutoBackgroundMs(): number {
  if (
    isEnvTruthy(process.env.CLAUDE_AUTO_BACKGROUND_TASKS) ||
    getFeatureValue_CACHED_MAY_BE_STALE('tengu_auto_background_agents', false)
  ) {
    return 120_000
  }
  return 0
}

export function isCoordinatorEnvMode(): boolean {
  return feature('COORDINATOR_MODE')
    ? isEnvTruthy(process.env.CLAUDE_CODE_COORDINATOR_MODE)
    : false
}

export function isProactiveAgentActive(): boolean {
  return proactiveModule?.isProactiveActive() ?? false
}

export function additionalWorkingDirectoryPaths(
  toolUseContext: Pick<ToolUseContext, 'getAppState'>,
): string[] {
  return Array.from(
    toolUseContext
      .getAppState()
      .toolPermissionContext.additionalWorkingDirectories.keys(),
  ).filter(path => typeof path === 'string')
}
