import { feature } from 'bun:bundle'
import { getIsNonInteractiveSession } from '../../bootstrap/state.js'
import { isCoordinatorMode } from '../../coordinator/coordinatorMode.js'
import {
  isEnvDefinedFalsy,
  isEnvTruthy,
} from '../../utils/envUtils.js'

function readFeatureBoolean(value: string | undefined): boolean | undefined {
  if (isEnvTruthy(value)) return true
  if (isEnvDefinedFalsy(value)) return false
  return undefined
}

function isForkSubagentFeatureEnabled(): boolean {
  const ummayaOverride = readFeatureBoolean(
    process.env.UMMAYA_FEATURE_FORK_SUBAGENT,
  )
  if (ummayaOverride !== undefined) return ummayaOverride

  const claudeOverride = readFeatureBoolean(
    process.env.CLAUDE_CODE_FEATURE_FORK_SUBAGENT,
  )
  return claudeOverride ?? (feature('FORK_SUBAGENT') ? true : false)
}

export function isForkSubagentEnabled(): boolean {
  if (isForkSubagentFeatureEnabled()) {
    if (isCoordinatorMode()) return false
    if (getIsNonInteractiveSession()) return false
    return true
  }
  return false
}
