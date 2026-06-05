// SPDX-License-Identifier: Apache-2.0

import { describe, expect, test } from 'bun:test'
import { getSessionId, switchSession } from '../../src/bootstrap/state.js'
import {
  closeUmmayaBridge,
  getUmmayaBridgeSessionId,
} from '../../src/ipc/bridgeSingleton.js'

describe('UMMAYA bridge session identity', () => {
  test('uses the active TUI session id for IPC frames and resets after bridge close', async () => {
    const originalSessionId = getSessionId()

    try {
      switchSession('44444444-4444-4444-8444-444444444444')
      await closeUmmayaBridge()
      expect(getUmmayaBridgeSessionId()).toBe('44444444-4444-4444-8444-444444444444')

      switchSession('55555555-5555-4555-8555-555555555555')
      await closeUmmayaBridge()
      expect(getUmmayaBridgeSessionId()).toBe('55555555-5555-4555-8555-555555555555')
    } finally {
      switchSession(originalSessionId)
      await closeUmmayaBridge()
    }
  })
})
