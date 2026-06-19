// SPDX-License-Identifier: Apache-2.0

import { beforeEach, describe, expect, it } from 'bun:test'
import { mkdtempSync, rmSync } from 'node:fs'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { runWithCwdOverride } from '../../src/utils/cwd.js'
import {
  getCurrentProjectConfig,
  getGlobalConfig,
  isProjectConfigKey,
  saveCurrentProjectConfig,
  saveGlobalConfig,
} from '../../src/utils/config.js'
import { ensureStartupOnboardingComplete } from '../../src/interactiveHelpers.js'
import {
  maybeMarkProjectOnboardingComplete,
  resetProjectOnboardingMemoForTesting,
  shouldShowProjectOnboarding,
} from '../../src/projectOnboardingState.js'

function resetProjectOnboardingConfig(): void {
  saveCurrentProjectConfig(current => {
    const { hasCompletedProjectOnboarding: _completed, ...rest } = current
    return {
      ...rest,
      hasCompletedProjectOnboarding: undefined,
      projectOnboardingSeenCount: 0,
    }
  })
}

function resetStartupOnboardingConfig(): void {
  saveGlobalConfig(current => ({
    ...current,
    hasCompletedOnboarding: undefined,
    lastOnboardingVersion: undefined,
    theme: undefined,
  }))
}

describe('project onboarding state', () => {
  beforeEach(() => {
    process.env.NODE_ENV = 'test'
    resetProjectOnboardingConfig()
    resetStartupOnboardingConfig()
    resetProjectOnboardingMemoForTesting()
  })

  it('marks onboarding complete when the first prompt is sent from an empty workspace', () => {
    // Given: a clean demo-style workspace has no files and no project onboarding flag.
    const workspace = mkdtempSync(join(tmpdir(), 'ummaya-onboarding-empty-'))

    try {
      expect(getCurrentProjectConfig().hasCompletedProjectOnboarding).toBeUndefined()

      // When: REPL submits the first real user message and marks project onboarding.
      runWithCwdOverride(workspace, () => {
        maybeMarkProjectOnboardingComplete()
      })

      // Then: the next launch suppresses the full project onboarding feed.
      expect(getCurrentProjectConfig().hasCompletedProjectOnboarding).toBe(true)
    } finally {
      rmSync(workspace, { force: true, recursive: true })
    }
  })

  it('does not show project onboarding on clean startup', () => {
    const workspace = mkdtempSync(join(tmpdir(), 'ummaya-onboarding-seen-'))

    try {
      runWithCwdOverride(workspace, () => {
        expect(shouldShowProjectOnboarding()).toBe(false)
      })
    } finally {
      rmSync(workspace, { force: true, recursive: true })
    }
  })

  it('recognizes the onboarding seen count as project configuration', () => {
    expect(isProjectConfigKey('projectOnboardingSeenCount')).toBe(true)
  })

  it('completes startup onboarding without rendering the welcome setup flow', () => {
    ensureStartupOnboardingComplete()

    const config = getGlobalConfig()
    expect(config.hasCompletedOnboarding).toBe(true)
    expect(config.theme).toBe('dark')
    expect(config.lastOnboardingVersion).toBeTruthy()
  })
})
