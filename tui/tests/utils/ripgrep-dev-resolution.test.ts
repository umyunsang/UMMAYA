import { describe, expect, test } from 'bun:test'
import { existsSync } from 'node:fs'
import { spawnSync } from 'node:child_process'
import { join } from 'node:path'

const TUI_ROOT = join(import.meta.dir, '../..')
const { USE_BUILTIN_RIPGREP: _unusedRipgrepEnv, ...DEFAULT_ENV } = process.env

function systemRgExists(): boolean {
  return spawnSync('sh', ['-lc', 'command -v rg'], {
    cwd: TUI_ROOT,
    encoding: 'utf8',
  }).status === 0
}

describe('ripgrep development resolution', () => {
  test('does not select a missing vendored rg when system rg is available', () => {
    if (!systemRgExists()) return

    const result = spawnSync(
      'bun',
      [
        '-e',
        [
          "import { ripgrepCommand, getRipgrepStatus } from './src/utils/ripgrep.ts'",
          'const command = ripgrepCommand()',
          'const status = getRipgrepStatus()',
          'console.log(JSON.stringify({ command, status }))',
        ].join('; '),
      ],
      {
        cwd: TUI_ROOT,
        encoding: 'utf8',
        env: DEFAULT_ENV,
      },
    )

    expect(result.status).toBe(0)
    const parsed = JSON.parse(result.stdout) as {
      command: { rgPath: string }
      status: { mode: string; path: string }
    }
    expect(parsed.status.mode).toBe('system')
    expect(parsed.command.rgPath).toBe('rg')
    expect(existsSync(parsed.status.path)).toBe(false)
  })
})
