// SPDX-License-Identifier: Apache-2.0

import { describe, expect, spyOn, test } from 'bun:test'
import { CHUNK_MS, FileIndex } from '../../src/native-ts/file-index/index.js'

describe('FileIndex async rebuild concurrency', () => {
  test('older async builds stop cleanly after a newer rebuild resets paths', async () => {
    const performanceNow = spyOn(performance, 'now')
    let now = 0
    performanceNow.mockImplementation(() => {
      now += CHUNK_MS + 1
      return now
    })
    const index = new FileIndex()
    const firstFiles = Array.from(
      { length: 1024 },
      (_value, i) => `first-file-${i}.ts`,
    )

    const first = index.loadFromFileListAsync(firstFiles)
    await first.queryable
    const second = index.loadFromFileListAsync(['final-target.ts'])

    await expect(first.done).resolves.toBeUndefined()
    await expect(second.done).resolves.toBeUndefined()
    expect(index.search('final', 5)[0]?.path).toBe('final-target.ts')
    performanceNow.mockRestore()
  })

  test('newer async builds win while an older rebuild is still collecting paths', async () => {
    const performanceNow = spyOn(performance, 'now')
    let now = 0
    performanceNow.mockImplementation(() => {
      now += CHUNK_MS + 1
      return now
    })
    const index = new FileIndex()
    const firstFiles = Array.from(
      { length: 1024 },
      (_value, i) => `first-file-${i}.ts`,
    )

    const first = index.loadFromFileListAsync(firstFiles)
    const second = index.loadFromFileListAsync(['final-target.ts'])

    await expect(second.done).resolves.toBeUndefined()
    await expect(first.done).resolves.toBeUndefined()
    expect(index.search('final', 5)[0]?.path).toBe('final-target.ts')
    performanceNow.mockRestore()
  })
})
