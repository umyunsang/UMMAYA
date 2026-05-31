import * as React from 'react'
import { useAppState, useSetAppState } from '../../state/AppState.js'
import type { LocalJSXCommandOnDone } from '../../types/command.js'
import {
  getReasoningModeDescription,
  isReasoningMode,
  resolveKExaoneReasoningPolicy,
  type ReasoningMode,
} from '../../utils/kExaoneReasoning.js'
import { updateSettingsForSource } from '../../utils/settings/settings.js'

const COMMON_HELP_ARGS = ['help', '-h', '--help']
const REASONING_STATUS_MAX_CHARS = 220
const REASONING_STATUS_RE =
  /(추론|reasoning|thinking|think\s*mode)/iu
const STATUS_RE =
  /(지금|현재|current|status|어떻게\s*설정|설정(?:돼|되어|되어\s*있는|값|상태)|모드|mode|configured|확인)/iu
const MUTATION_RE =
  /(켜줘|꺼줘|바꿔|설정해|변경|set\s+reasoning|enable|disable|turn\s+(?:on|off)|deep으로|fast로|balanced로|diagnostic으로|auto로)/iu

type ReasoningCommandResult = {
  message: string
  reasoningUpdate?: {
    value: ReasoningMode | undefined
  }
}

export function isReasoningStatusQuestion(input: string): boolean {
  const normalized = input.trim()
  if (
    !normalized ||
    normalized.startsWith('/') ||
    normalized.length > REASONING_STATUS_MAX_CHARS
  ) {
    return false
  }
  return (
    REASONING_STATUS_RE.test(normalized) &&
    STATUS_RE.test(normalized) &&
    !MUTATION_RE.test(normalized)
  )
}

export function showCurrentReasoning(
  appStateMode: ReasoningMode | undefined,
  env: Record<string, string | undefined> = process.env,
): ReasoningCommandResult {
  const policy = resolveKExaoneReasoningPolicy({
    explicitSessionMode: appStateMode,
    env,
  })
  return {
    message:
      `Reasoning mode: ${policy.mode} (source: ${policy.source}) - ` +
      getReasoningModeDescription(policy.mode),
  }
}

export function executeReasoning(args: string): ReasoningCommandResult {
  const normalized = args.toLowerCase()
  if (normalized === 'unset') {
    return unsetReasoningMode()
  }
  if (!isReasoningMode(normalized)) {
    return {
      message:
        `Invalid argument: ${args}. Valid options are: ` +
        'fast, balanced, deep, diagnostic, auto, unset',
    }
  }
  return setReasoningMode(normalized)
}

function setReasoningMode(mode: ReasoningMode): ReasoningCommandResult {
  const result = updateSettingsForSource('userSettings', {
    reasoningMode: mode,
  })
  if (result.error) {
    return {
      message: `Failed to set reasoning mode: ${result.error.message}`,
    }
  }

  const envOverride = process.env.UMMAYA_K_EXAONE_REASONING_MODE
  const policy = resolveKExaoneReasoningPolicy({
    explicitSessionMode: mode,
  })
  if (policy.source === 'env' && policy.mode !== mode) {
    return {
      message:
        `UMMAYA_K_EXAONE_REASONING_MODE=${envOverride} overrides this session; ` +
        `saved ${mode} for sessions without the env override`,
      reasoningUpdate: { value: mode },
    }
  }

  return {
    message: `Set reasoning mode to ${mode}: ${getReasoningModeDescription(mode)}`,
    reasoningUpdate: { value: mode },
  }
}

function unsetReasoningMode(): ReasoningCommandResult {
  const result = updateSettingsForSource('userSettings', {
    reasoningMode: undefined,
  })
  if (result.error) {
    return {
      message: `Failed to clear reasoning mode: ${result.error.message}`,
    }
  }
  return {
    message: 'Reasoning mode cleared; default balanced policy is active',
    reasoningUpdate: { value: undefined },
  }
}

function ShowCurrentReasoning({
  onDone,
}: {
  onDone: (result: string) => void
}): React.ReactNode {
  const reasoningMode = useAppState(s => s.reasoningMode)
  const { message } = showCurrentReasoning(reasoningMode)
  onDone(message)
  return null
}

function ApplyReasoningAndClose({
  result,
  onDone,
}: {
  result: ReasoningCommandResult
  onDone: (result: string) => void
}): React.ReactNode {
  const setAppState = useSetAppState()
  const { reasoningUpdate, message } = result
  React.useEffect(() => {
    if (reasoningUpdate) {
      setAppState(prev => ({
        ...prev,
        reasoningMode: reasoningUpdate.value,
      }))
    }
    onDone(message)
  }, [setAppState, reasoningUpdate, message, onDone])
  return null
}

export async function call(
  onDone: LocalJSXCommandOnDone,
  _context: unknown,
  args?: string,
): Promise<React.ReactNode> {
  args = args?.trim() || ''

  if (COMMON_HELP_ARGS.includes(args)) {
    onDone(
      'Usage: /reasoning [fast|balanced|deep|diagnostic|auto|unset]\n\n' +
        'Modes:\n' +
        '- fast: latency-first answers with deterministic progress painting\n' +
        '- balanced: default production policy with reasoning parsing but no raw trace\n' +
        '- deep: provider thinking enabled and streamed when K-EXAONE emits it\n' +
        '- diagnostic: deep provider thinking for local diagnostic inspection\n' +
        '- auto: adaptive placeholder; currently resolves to the balanced payload\n' +
        '- unset: clear saved mode and use the default balanced policy',
    )
    return
  }

  if (!args || args === 'current' || args === 'status') {
    return <ShowCurrentReasoning onDone={onDone} />
  }

  const result = executeReasoning(args)
  return <ApplyReasoningAndClose result={result} onDone={onDone} />
}
