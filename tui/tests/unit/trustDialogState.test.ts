// SPDX-License-Identifier: Apache-2.0

import { beforeEach, describe, expect, it } from 'bun:test'
import { homedir } from 'node:os'
import { persistTrustDialogAcceptanceForCurrentWorkspace } from '../../src/components/TrustDialog/TrustDialog.js'
import {
  getCurrentProjectConfig,
  saveCurrentProjectConfig,
} from '../../src/utils/config.js'
import { runWithCwdOverride } from '../../src/utils/cwd.js'

function resetTrustDialogConfig(): void {
  saveCurrentProjectConfig(current => {
    const { hasTrustDialogAccepted: _accepted, ...rest } = current
    return {
      ...rest,
      hasTrustDialogAccepted: undefined,
    }
  })
}

describe('trust dialog state', () => {
  beforeEach(() => {
    process.env.NODE_ENV = 'test'
    resetTrustDialogConfig()
  })

  it('persists trust acceptance when launched from the user home directory', () => {
    runWithCwdOverride(homedir(), () => {
      persistTrustDialogAcceptanceForCurrentWorkspace()
    })

    expect(getCurrentProjectConfig().hasTrustDialogAccepted).toBe(true)
  })
})
