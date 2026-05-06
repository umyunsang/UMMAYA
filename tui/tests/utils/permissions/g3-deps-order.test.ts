// SPDX-License-Identifier: Apache-2.0
// Regression for the IPC permission fast-Enter race.
//
// The deps.ts permission_request branch must arm pendingPermissionSlot before
// it mounts CC's PermissionRequest. Otherwise a fast Enter can resolve an
// unknown request_id, leaving deps.ts blocked until permission_timeout.

import { describe, expect, it } from 'bun:test'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'

describe('G3 — deps.ts permission_request ordering', () => {
  it('arms pendingPermissionSlot before pushing the modal', () => {
    const depsPath = join(import.meta.dir, '../../../src/query/deps.ts')
    const text = readFileSync(depsPath, 'utf8')
    const permissionBlockStart = text.indexOf("fa.kind === 'permission_request'")
    expect(permissionBlockStart).toBeGreaterThanOrEqual(0)

    const block = text.slice(permissionBlockStart)
    const armIndex = block.indexOf('const permissionPromise = setPendingPermission')
    const pushIndex = block.indexOf('pushIpcPermissionRequest(requestFrame)')

    expect(armIndex).toBeGreaterThanOrEqual(0)
    expect(pushIndex).toBeGreaterThanOrEqual(0)
    expect(armIndex).toBeLessThan(pushIndex)
  })
})
