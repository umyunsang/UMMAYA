// SPDX-License-Identifier: Apache-2.0

import { beforeEach, describe, expect, it } from 'bun:test'
import { mkdtempSync, rmSync } from 'node:fs'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { runWithCwdOverride } from '../../src/utils/cwd.js'
import {
  getCurrentProjectConfig,
  saveCurrentProjectConfig,
} from '../../src/utils/config.js'
import { maybeMarkProjectOnboardingComplete } from '../../src/projectOnboardingState.js'

function resetProjectOnboardingConfig(): void {
  saveCurrentProjectConfig(current => {
    const { hasCompletedProjectOnboarding: _completed, ...rest } = current
    return {
      ...rest,
      projectOnboardingSeenCount: 0,
    }
  })
}

describe('project onboarding state', () => {
  beforeEach(() => {
    process.env.NODE_ENV = 'test'
    resetProjectOnboardingConfig()
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
})
