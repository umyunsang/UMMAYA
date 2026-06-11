// SPDX-License-Identifier: Apache-2.0

import { describe, expect, mock, test } from 'bun:test'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const TUI_ROOT = join(__dirname, '../..')
const execaCalls: Array<Record<string, unknown>> = []

mock.module('execa', () => ({
  execa: async (
    _file: string,
    _args: readonly string[],
    options: Record<string, unknown>,
  ) => {
    execaCalls.push(options)
    return {
      failed: false,
      stdout: 'ok',
      stderr: '',
    }
  },
  execaSync: () => ({
    stdout: '',
    stderr: '',
    exitCode: 0,
  }),
}))

const { execFileNoThrowWithCwd } = await import(
  join(TUI_ROOT, 'src/utils/execFileNoThrow.js')
)

describe('execFileNoThrow execa compatibility', () => {
  test('passes AbortSignal through execa cancelSignal, not the removed signal option', async () => {
    execaCalls.length = 0
    const controller = new AbortController()

    const result = await execFileNoThrowWithCwd('echo', ['ok'], {
      abortSignal: controller.signal,
      cwd: TUI_ROOT,
    })

    expect(result).toEqual({ stdout: 'ok', stderr: '', code: 0 })
    expect(execaCalls).toHaveLength(1)
    expect(execaCalls[0]).not.toHaveProperty('signal')
    expect(execaCalls[0]?.cancelSignal).toBe(controller.signal)
  })
})
