#!/usr/bin/env bun
// SPDX-License-Identifier: Apache-2.0
// KOSMOS-original — boot smoke gate.
//
// Purpose
// -------
// Catch regressions that only manifest when the TUI boots against a real TTY:
//   - React 19 "getSnapshot should be cached to avoid an infinite loop"
//     (unstable selector identity → Object.is cache miss → render storm).
//   - Ink "Encountered two children with the same key" (duplicate React keys).
//   - Main entrypoint missing / wrong script wiring ("Module not found").
//   - Backend bridge not draining stdout → crash detector false positive.
//   - SIGTERM handler regression (process fails to exit within 3 s).
//
// Strategy
// --------
// 1. Spawn `bun run tui` inside a PTY via `script` (BSD on macOS, util-linux on
//    Linux/CI). Without a TTY, Ink's `useInput` throws "Raw mode not supported"
//    and masks the bugs we're actually hunting.
// 2. Set `KOSMOS_BACKEND_CMD=sleep 60` — the bridge's default is
//    `uv run kosmos --ipc stdio`, which may not be installed on the CI runner
//    before the Python deps are synced.  `sleep` is a POSIX-guaranteed no-op
//    that holds the bridge's stdin open exactly like a real backend would.
// 3. Let the TUI boot for 3 s, then send SIGTERM.
// 4. Assert:
//      exit ∈ {0, 143}                         (143 = 128 + SIGTERM)
//      stdout+stderr do NOT contain the forbidden strings below.
//
// Exit codes
// ----------
// 0 — smoke passed.
// 1 — anything else (forbidden string found, timeout, wrong exit code).
//
// Runs locally via `bun run tui:smoke` and in CI (.github/workflows/tui-smoke.yml).

import { spawn } from 'node:child_process'
import { platform } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const FORBIDDEN_STRINGS: ReadonlyArray<string> = [
  'getSnapshot should be cached',
  'two children with the same key',
  'Module not found',
  'Cannot find module',
  'Raw mode is not supported', // TTY harness failure — defence in depth
]

// Boot window tuned per platform — macOS pty init is ~200 ms; ubuntu-latest
// under GitHub Actions is slower (~800 ms cold-start overhead).
const BOOT_MS = Number(process.env['KOSMOS_TUI_SMOKE_BOOT_MS'] ?? 3_000)
const SHUTDOWN_GRACE_MS = 5_000
const ACCEPTABLE_EXIT_CODES = new Set([0, 143])

function withoutFriendliCredential(env: NodeJS.ProcessEnv): NodeJS.ProcessEnv {
  const next = { ...env }
  delete next.KOSMOS_FRIENDLI_TOKEN
  delete next.KOSMOS_FRIENDLI_SESSION_ACTIVE
  return next
}

interface SmokeResult {
  exitCode: number | null
  signal: NodeJS.Signals | null
  output: string
  timedOut: boolean
}

function resolveTuiDir(): string {
  // scripts/tui-smoke.ts → <repo>/tui
  const here = fileURLToPath(import.meta.url)
  return join(here, '..', '..')
}

function buildScriptInvocation(cmd: string, args: readonly string[]): {
  bin: string
  argv: string[]
} {
  // Run the target under `script` so the child has a real PTY.
  const tuiCmd = [cmd, ...args].join(' ')
  if (platform() === 'darwin') {
    // BSD script: script [-q] file [cmd ...]
    return { bin: 'script', argv: ['-q', '/dev/null', cmd, ...args] }
  }
  // util-linux script: script -q -c "<cmd>" /dev/null
  return { bin: 'script', argv: ['-q', '-c', tuiCmd, '/dev/null'] }
}

async function runSmoke(): Promise<SmokeResult> {
  const tuiDir = resolveTuiDir()
  const { bin, argv } = buildScriptInvocation('bun', ['run', 'tui'])

  // eslint-disable-next-line no-console
  console.log(`[tui-smoke] cwd=${tuiDir}`)
  // eslint-disable-next-line no-console
  console.log(`[tui-smoke] exec: ${bin} ${argv.join(' ')}`)

  const child = spawn(bin, argv, {
    cwd: tuiDir,
    env: {
      ...withoutFriendliCredential(process.env),
      // Fake backend that stays alive until SIGTERMed — tests the bridge
      // spawn path without requiring the Python harness on the runner.
      KOSMOS_BACKEND_CMD: 'sleep 60',
      // Surface every decode / send / recv line in case the boot path fails.
      KOSMOS_TUI_LOG_LEVEL: 'DEBUG',
      // Disable colour codes where possible to keep forbidden-string matching
      // insensitive to ANSI reset sequences. Ink still emits some; we match
      // substrings anyway.
      NO_COLOR: '1',
      FORCE_COLOR: '0',
      // Enables macro-preload's bun:bundle runtime mock for local source runs.
      // Packaged builds inline this module; source smoke runs do not.
      NODE_ENV: 'test',
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  })

  let output = ''
  child.stdout?.on('data', (chunk: Buffer) => {
    output += chunk.toString('utf8')
  })
  child.stderr?.on('data', (chunk: Buffer) => {
    output += chunk.toString('utf8')
  })

  const exitPromise = new Promise<{
    exitCode: number | null
    signal: NodeJS.Signals | null
  }>((resolve) => {
    child.once('exit', (code, signal) => {
      resolve({ exitCode: code, signal })
    })
  })

  // Let the TUI boot, then send SIGTERM.
  await new Promise((r) => setTimeout(r, BOOT_MS))
  // eslint-disable-next-line no-console
  console.log(`[tui-smoke] sending SIGTERM after ${BOOT_MS} ms boot window`)
  child.kill('SIGTERM')

  // Race exit against a hard timeout so the CI job never hangs.
  const timedOut = await Promise.race([
    exitPromise.then(() => false),
    new Promise<boolean>((r) =>
      setTimeout(() => {
        // eslint-disable-next-line no-console
        console.error('[tui-smoke] SIGTERM grace expired — sending SIGKILL')
        child.kill('SIGKILL')
        r(true)
      }, SHUTDOWN_GRACE_MS),
    ),
  ])

  const { exitCode, signal } = await exitPromise
  return { exitCode, signal, output, timedOut }
}

async function main(): Promise<void> {
  const result = await runSmoke()

  const hitForbidden = FORBIDDEN_STRINGS.filter((s) =>
    result.output.includes(s),
  )

  // eslint-disable-next-line no-console
  console.log(
    `[tui-smoke] exit=${result.exitCode} signal=${result.signal ?? 'null'} timedOut=${result.timedOut}`,
  )
  // eslint-disable-next-line no-console
  console.log(`[tui-smoke] captured ${result.output.length} bytes`)

  const failures: string[] = []
  if (result.timedOut) {
    failures.push('process did not exit within SIGTERM grace window')
  }
  if (
    result.exitCode !== null &&
    !ACCEPTABLE_EXIT_CODES.has(result.exitCode)
  ) {
    failures.push(
      `exit code ${result.exitCode} not in {${[...ACCEPTABLE_EXIT_CODES].join(', ')}}`,
    )
  }
  if (hitForbidden.length > 0) {
    failures.push(`forbidden strings observed: ${hitForbidden.join(' | ')}`)
  }

  if (failures.length > 0) {
    // eslint-disable-next-line no-console
    console.error('[tui-smoke] FAIL')
    for (const f of failures) {
      // eslint-disable-next-line no-console
      console.error(`  - ${f}`)
    }
    // Dump output tail (last 4 KiB) to help debug CI failures without bloating logs.
    const tail = result.output.slice(-4096)
    // eslint-disable-next-line no-console
    console.error('--- output tail ---')
    // eslint-disable-next-line no-console
    console.error(tail)
    // eslint-disable-next-line no-console
    console.error('--- end tail ---')
    process.exit(1)
  }

  // eslint-disable-next-line no-console
  console.log('[tui-smoke] PASS')
  process.exit(0)
}

main().catch((e: unknown) => {
  // eslint-disable-next-line no-console
  console.error('[tui-smoke] unhandled error:', e)
  process.exit(1)
})
