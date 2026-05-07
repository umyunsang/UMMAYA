// SPDX-License-Identifier: Apache-2.0
// Spec 1635 P4 UI L2 — Onboarding step 1: Preflight (FR-001 step 1, T040).
//
// Runs environment checks synchronously at mount (Bun version, terminal graphics
// protocol presence, required KOSMOS_* env vars) and renders ✓/✗ per item.
// The citizen can advance to step 2 regardless of soft-fail items; a hard-fail
// (Bun version below 1.2) shows a warning but does not block advancing.
//
// Reference: docs/wireframes/ui-a-onboarding.mjs § Step1_Preflight
// IME gate: useKoreanIME per vision.md § Keyboard-shortcut migration

import React, { useEffect, useMemo } from 'react'
import { Box, Text, useInput } from 'ink'
import { useTheme } from '../../theme/provider.js'
import { useKoreanIME } from '../../hooks/useKoreanIME.js'
import { getUiL2I18n } from '../../i18n/uiL2.js'
import { emitSurfaceActivation } from '../../observability/surface.js'

// ---------------------------------------------------------------------------
// Preflight check items
// ---------------------------------------------------------------------------

export type PreflightCheckResult = {
  label: string
  passed: boolean
  note?: string
}

function detectGraphicsProtocol(): 'kitty' | 'iterm2' | 'none' {
  const term = process.env['TERM'] ?? ''
  const termProgram = process.env['TERM_PROGRAM'] ?? ''
  if (term === 'xterm-kitty') return 'kitty'
  if (termProgram === 'iTerm.app') return 'iterm2'
  return 'none'
}

function checkBunVersion(): PreflightCheckResult {
  // Bun exposes its version via Bun.version global when running in Bun.
  // In Node/test environments it is absent; treat absence as passing for tests.
  const bunVersion: string | undefined =
    typeof (globalThis as Record<string, unknown>)['Bun'] === 'object' &&
    (globalThis as Record<string, unknown>)['Bun'] !== null
      ? String(
          ((globalThis as Record<string, unknown>)['Bun'] as Record<string, unknown>)[
            'version'
          ] ?? '',
        )
      : undefined

  if (bunVersion === undefined || bunVersion === '') {
    return { label: 'Bun ≥ 1.2', passed: true, note: 'runtime check skipped in test mode' }
  }

  const [major, minor] = bunVersion.split('.').map(Number)
  const passed = (major ?? 0) > 1 || ((major ?? 0) === 1 && (minor ?? 0) >= 2)
  return {
    label: `Bun ${bunVersion}`,
    passed,
    note: passed ? undefined : 'Bun 1.2+ required — run `bun upgrade`',
  }
}

function checkGraphicsProtocol(): PreflightCheckResult {
  const proto = detectGraphicsProtocol()
  const labels: Record<typeof proto, string> = {
    kitty: 'Kitty graphics protocol ✓',
    iterm2: 'iTerm2 graphics protocol ✓',
    none: 'Terminal graphics protocol (not detected — PDF inline preview unavailable)',
  }
  return {
    label: labels[proto],
    passed: proto !== 'none',
    note: proto === 'none' ? 'PDF attachments will open in external viewer' : undefined,
  }
}

function checkRequiredEnvVars(): PreflightCheckResult[] {
  const optional: { keys: string[]; label: string; mockNote: string }[] = [
    {
      keys: ['KOSMOS_DATA_GO_KR_API_KEY', 'KOSMOS_DATA_GO_KR_KEY'],
      label: 'KOSMOS_DATA_GO_KR_API_KEY',
      mockNote: 'absent — Mock mode (no live data.go.kr calls)',
    },
  ]

  const results: PreflightCheckResult[] = []

  for (const { keys, label, mockNote } of optional) {
    const present = keys.some((k) => Boolean(process.env[k]))
    results.push({
      label,
      passed: true, // optional — never blocks advancing
      note: present ? undefined : mockNote,
    })
  }

  return results
}

export function runPreflightChecks(): PreflightCheckResult[] {
  return [
    checkBunVersion(),
    checkGraphicsProtocol(),
    ...checkRequiredEnvVars(),
  ]
}

// ---------------------------------------------------------------------------
// Step header (progress dots)
// ---------------------------------------------------------------------------

function StepProgressDots({
  current,
  total,
}: {
  current: number
  total: number
}) {
  const theme = useTheme()
  const dots = Array.from({ length: total }, (_, i) =>
    i < current ? '●' : i === current ? '◉' : '○',
  ).join(' ')
  return (
    <Text color={theme.subtle}>
      {dots}{'     '}{current + 1} / {total}
    </Text>
  )
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export type PreflightStepProps = {
  onAdvance: () => void
  onExit: () => void
  /** Locale used for UI strings; defaults to KOSMOS_TUI_LOCALE env var. */
  locale?: 'ko' | 'en'
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function PreflightStep({
  onAdvance,
  onExit,
  locale,
}: PreflightStepProps): React.ReactElement {
  const theme = useTheme()
  const { isComposing } = useKoreanIME()
  const i18n = getUiL2I18n(
    locale ?? ((process.env['KOSMOS_TUI_LOCALE'] as 'ko' | 'en') || 'ko'),
  )

  const checks = useMemo(() => runPreflightChecks(), [])
  const allPassed = checks.every((c) => c.passed)

  useEffect(() => {
    emitSurfaceActivation('onboarding', { 'onboarding.step': 'preflight' })
  }, [])

  useInput((input, key) => {
    if (isComposing) return
    if (key.ctrl && (input === 'c' || input === 'd')) {
      onExit()
      return
    }
    if (key.escape) {
      onExit()
      return
    }
    if (key.return) {
      onAdvance()
    }
  })

  return (
    <Box flexDirection="column" paddingX={1}>
      <Box flexDirection="column">
        <Text bold color={theme.wordmark}>
          {i18n.preflightTitle}
        </Text>
        <StepProgressDots current={0} total={5} />
      </Box>

      <Box marginTop={1} flexDirection="column">
        {checks.map((check, idx) => (
          <Box key={idx} flexDirection="column">
            <Box flexDirection="row">
              <Text color={check.passed ? theme.success : theme.warning}>
                {check.passed
                  ? i18n.preflightOk(check.label)
                  : i18n.preflightFail(check.label)}
              </Text>
            </Box>
            {check.note !== undefined && (
              <Box paddingLeft={2}>
                <Text color={theme.subtle} dimColor>
                  {check.note}
                </Text>
              </Box>
            )}
          </Box>
        ))}
      </Box>

      {!allPassed && (
        <Box marginTop={1}>
          <Text color={theme.warning}>
            ⚠ 일부 항목이 설정되지 않았습니다. 계속 진행할 수 있지만 일부 기능이 제한될 수 있습니다.
          </Text>
        </Box>
      )}

      <Box marginTop={1}>
        <Text color={theme.kosmosCore}>
          {i18n.onboardingNext}{'  ·  '}
          <Text color={theme.subtle}>{i18n.onboardingBack}</Text>
        </Text>
      </Box>
    </Box>
  )
}
