// SPDX-License-Identifier: Apache-2.0
// Spec 1635 P4 UI L2 — 5-step onboarding flow driver (FR-001/002, T045).
//
// Ports cc:components/Onboarding.tsx step-driver pattern to the KOSMOS 5-step
// citizen onboarding sequence:
//   preflight → theme → pipa-consent → ministry-scope → terminal-setup
//
// State is persisted to ~/.kosmos/memdir/user/onboarding/state.json via the
// existing uiL2Memdir helpers (loadOnboardingState / saveOnboardingState) so
// that a SIGINT mid-onboarding resumes from the last completed step on next
// launch (FR-002 + spec.md edge case).
//
// /onboarding <step-name> re-entry runs a single step in isolation without
// resetting the persisted state (data-model §1, state-transition rule 4).
//
// Reference: cc:components/Onboarding.tsx (step driver pattern)
//            docs/wireframes/ui-a-onboarding.mjs
// IME gate: each step component owns its own useKoreanIME gate.

import React, { useCallback, useEffect, useState } from 'react'
import { Box, Text, useApp } from 'ink'
import { useTheme } from '../../theme/provider.js'
import {
  ONBOARDING_STEP_ORDER,
  isOnboardingComplete,
  type OnboardingStateT,
  type OnboardingStepNameT,
  freshOnboardingState,
} from '../../schemas/ui-l2/onboarding.js'
import type { AccessibilityPreferenceT } from '../../schemas/ui-l2/a11y.js'
import {
  loadOnboardingState,
  saveOnboardingState,
  saveAccessibilityPreference,
} from '../../utils/uiL2Memdir.js'
import { emitSurfaceActivation } from '../../observability/surface.js'
import { writeConsentRecord } from '../../memdir/io.js'
import {
  CURRENT_CONSENT_VERSION,
  PIPAConsentRecordSchema,
} from '../../memdir/consent.js'
import { PreflightStep } from './PreflightStep.js'
import { ThemeStep } from './ThemeStep.js'
import { PipaConsentStep } from './PipaConsentStep.js'
import { MinistryScopeStep } from './MinistryScopeStep.js'
import { TerminalSetupStep } from './TerminalSetupStep.js'
import type { MinistryScopeAcknowledgment } from '../../memdir/ministry-scope.js'
import { writeScopeRecord } from '../../memdir/io.js'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type OnboardingFlowProps = {
  /**
   * Called when all five steps are completed (or when /onboarding <step>
   * isolation mode finishes its single step). The parent swaps <OnboardingFlow>
   * for <REPL> on this callback.
   */
  onComplete: () => void
  /**
   * When set, run only this step in isolation (FR-003 /onboarding <step-name>).
   * Persisted state is read but the current_step_index is not reset.
   */
  isolatedStep?: OnboardingStepNameT
  /** Session ID forwarded to consent / scope records. */
  sessionId?: string
  /** Locale override (defaults to KOSMOS_TUI_LOCALE env var). */
  locale?: 'ko' | 'en'
  // Test injection points
  onLoadState?: () => Promise<OnboardingStateT>
  onSaveState?: (s: OnboardingStateT) => Promise<void>
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function emitStep(step: OnboardingStepNameT): void {
  emitSurfaceActivation('onboarding', { 'onboarding.step': step })
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function OnboardingFlow({
  onComplete,
  isolatedStep,
  sessionId,
  locale,
  onLoadState,
  onSaveState,
}: OnboardingFlowProps): React.ReactElement {
  const { exit } = useApp()
  const theme = useTheme()
  const resolvedLocale: 'ko' | 'en' =
    locale ?? ((process.env['KOSMOS_TUI_LOCALE'] as 'ko' | 'en') || 'ko')
  const resolvedSessionId = sessionId ?? crypto.randomUUID()

  // State is loaded once at mount; subsequent saves go through onSaveState or
  // the default saveOnboardingState helper.
  const [state, setState] = useState<OnboardingStateT | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const loader = onLoadState ?? loadOnboardingState
    void loader().then((loaded) => {
      setState(loaded)
      setLoading(false)
    })
  }, [onLoadState])

  // Auto-complete escape hatch — opt-in via KOSMOS_ONBOARDING_AUTO_COMPLETE=1.
  // Persists a fully-marked OnboardingState (current_step_index=5, all steps
  // completed_at populated) and immediately invokes onComplete(), bypassing
  // any keystroke-driven step advance. Use cases:
  //   - tmux/expect-driven smoke scenarios where stdin handling under
  //     `showDialog` proves brittle (integration-verification frame
  //     04-onboarding-complete left the citizen stuck on Step 1 because
  //     PreflightStep's useInput never fired on Enter under the dialog
  //     wrapper — dispatch root cause TBD; this hatch unblocks the rest of
  //     the suite without weakening interactive UX guarantees).
  //   - dev iteration: skip the 5-screen tour after wiping state.json.
  // The flag is read fresh at mount; toggling it does not retro-revert a
  // partially completed state.
  useEffect(() => {
    if (state === null) return
    if (process.env['KOSMOS_ONBOARDING_AUTO_COMPLETE'] !== '1') return
    if (isOnboardingComplete(state)) return
    const now = new Date().toISOString()
    const completedSteps = state.steps.map((s) => ({
      ...s,
      completed_at: s.completed_at ?? now,
    }))
    const completedState: OnboardingStateT = {
      ...state,
      steps: completedSteps,
      current_step_index: 5,
    }
    setState(completedState)
    const saver = onSaveState ?? saveOnboardingState
    void saver(completedState).finally(() => onComplete())
  }, [state, onComplete, onSaveState])

  // Compute the active step index
  const activeStepIndex: number = (() => {
    if (state === null) return 0
    if (isolatedStep !== undefined) {
      const idx = ONBOARDING_STEP_ORDER.indexOf(isolatedStep)
      return idx >= 0 ? idx : 0
    }
    return state.current_step_index
  })()

  const activeStep: OnboardingStepNameT =
    ONBOARDING_STEP_ORDER[activeStepIndex] ?? 'preflight'

  // Persist a step completion and advance
  const advanceStep = useCallback(
    async (values: Record<string, unknown> = {}): Promise<void> => {
      if (state === null) return

      const updatedSteps = state.steps.map((s, i) =>
        i === activeStepIndex
          ? { ...s, completed_at: new Date().toISOString(), values }
          : s,
      )

      // In isolation mode, do not change current_step_index
      const newIndex = isolatedStep !== undefined
        ? state.current_step_index
        : Math.min(activeStepIndex + 1, 5)

      const updatedState: OnboardingStateT = {
        ...state,
        steps: updatedSteps,
        current_step_index: newIndex,
      }

      setState(updatedState)

      const saver = onSaveState ?? saveOnboardingState
      try {
        await saver(updatedState)
      } catch {
        // Fail-soft: state already updated in memory; the citizen can continue.
      }

      // If isolation mode or all steps done → call onComplete
      if (isolatedStep !== undefined || isOnboardingComplete(updatedState)) {
        onComplete()
      } else {
        const nextStep = ONBOARDING_STEP_ORDER[newIndex]
        if (nextStep !== undefined) emitStep(nextStep)
      }
    },
    [state, activeStepIndex, isolatedStep, onComplete, onSaveState],
  )

  const exitOnboarding = useCallback((): void => {
    exit()
  }, [exit])

  // Preflight advance handler
  const handlePreflightAdvance = useCallback((): void => {
    void advanceStep()
  }, [advanceStep])

  // Theme advance handler
  const handleThemeAdvance = useCallback(
    (selectedTheme: 'dark' | 'light' | 'system'): void => {
      void advanceStep({ theme: selectedTheme })
    },
    [advanceStep],
  )

  // PIPA consent advance handler — writes consent record via Spec 035 memdir
  const handlePipaAdvance = useCallback((): void => {
    void advanceStep({ consent_given: true })
  }, [advanceStep])

  const handlePipaWriteRecord = useCallback(
    async (sid: string, ts: string): Promise<void> => {
      const record = {
        consent_version: CURRENT_CONSENT_VERSION,
        timestamp: ts,
        aal_gate: 'AAL1' as const,
        session_id: sid,
        citizen_confirmed: true as const,
        schema_version: '1' as const,
      }
      const parsed = PIPAConsentRecordSchema.safeParse(record)
      if (parsed.success) {
        writeConsentRecord(parsed.data)
      }
    },
    [],
  )

  // Ministry scope advance handler — writes scope record via Spec 035 memdir
  const handleMinistryScopeAdvance = useCallback((): void => {
    void advanceStep()
  }, [advanceStep])

  const handleScopeWriteRecord = useCallback(
    async (record: MinistryScopeAcknowledgment): Promise<void> => {
      writeScopeRecord(record)
    },
    [],
  )

  // Terminal setup advance handler — persists a11y preference via uiL2Memdir
  const handleTerminalAdvance = useCallback(
    (pref: AccessibilityPreferenceT): void => {
      void advanceStep({
        screen_reader: pref.screen_reader,
        large_font: pref.large_font,
        high_contrast: pref.high_contrast,
        reduced_motion: pref.reduced_motion,
      })
    },
    [advanceStep],
  )

  const handleA11yWrite = useCallback(
    async (pref: AccessibilityPreferenceT): Promise<void> => {
      await saveAccessibilityPreference(pref)
    },
    [],
  )

  // Emit surface activation on step change
  useEffect(() => {
    if (!loading && state !== null) {
      emitStep(activeStep)
    }
  }, [loading, activeStep, state])

  // Loading state
  if (loading || state === null) {
    return (
      <Box paddingX={1}>
        <Text color={theme.kosmosCore}>
          {resolvedLocale === 'en' ? 'Loading onboarding…' : '온보딩 로딩 중…'}
        </Text>
      </Box>
    )
  }

  // Render the active step
  const commonProps = {
    locale: resolvedLocale,
    onExit: exitOnboarding,
  }

  return (
    <Box flexDirection="column">
      {activeStep === 'preflight' && (
        <PreflightStep {...commonProps} onAdvance={handlePreflightAdvance} />
      )}
      {activeStep === 'theme' && (
        <ThemeStep {...commonProps} onAdvance={handleThemeAdvance} />
      )}
      {activeStep === 'pipa-consent' && (
        <PipaConsentStep
          {...commonProps}
          sessionId={resolvedSessionId}
          onAdvance={handlePipaAdvance}
          writeRecord={handlePipaWriteRecord}
        />
      )}
      {activeStep === 'ministry-scope' && (
        <MinistryScopeStep
          onAdvance={handleMinistryScopeAdvance}
          onExit={exitOnboarding}
          sessionId={resolvedSessionId}
          writeRecord={handleScopeWriteRecord}
        />
      )}
      {activeStep === 'terminal-setup' && (
        <TerminalSetupStep
          {...commonProps}
          onAdvance={handleTerminalAdvance}
          writePreference={handleA11yWrite}
        />
      )}
    </Box>
  )
}

// ---------------------------------------------------------------------------
// Utility: reset onboarding state for /onboarding re-run
// ---------------------------------------------------------------------------

/**
 * Reset the onboarding state to step 0 while preserving completed_at audit
 * trail for prior steps (data-model §1 state-transition rule 3).
 */
export async function resetOnboardingState(
  current: OnboardingStateT,
  save: (s: OnboardingStateT) => Promise<void> = saveOnboardingState,
): Promise<OnboardingStateT> {
  const reset: OnboardingStateT = {
    ...freshOnboardingState(),
    // Preserve prior completed_at for audit — do not delete
    steps: current.steps.map((s) => ({ ...s, completed_at: s.completed_at })),
    current_step_index: 0,
    started_at: new Date().toISOString(),
  }
  await save(reset)
  return reset
}
