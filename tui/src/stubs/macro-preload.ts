/// <reference types="bun-types" />
// [P0 reconstructed · Bun MACRO shim + TTY shim]
// CC 2.1.88 uses `MACRO.*` build-time constants that Bun's bundler would
// normally inline. Without a build step, those references throw
// `ReferenceError: MACRO is not defined`. This preload script injects a
// global `MACRO` object and a TTY detection shim so the module-load phase
// succeeds and the splash renders.
//
// Referenced from `bunfig.toml` `preload = ["./src/stubs/macro-preload.ts"]`.

type ProcessExit = typeof process.exit

declare global {
  namespace NodeJS {
    interface Process {
      _origExit?: ProcessExit
    }
  }
}

// ═══════════════════════════════════════════════════════════════════════
// bun:bundle virtual module plugin
// Bun's default resolver treats `bun:` as a reserved built-in namespace and
// ignores tsconfig paths for it. We register a Bun plugin that intercepts
// imports of `bun:bundle` at runtime and routes them to the local runtime
// implementation when the bundler path supports plugin-time resolution.
// ═══════════════════════════════════════════════════════════════════════
try {
  if (typeof Bun !== 'undefined' && typeof Bun.plugin === 'function') {
    Bun.plugin({
      name: 'ummaya-bun-bundle-shim',
      setup(build: {
        onResolve: (
          opts: { filter: RegExp },
          cb: (args: { path: string }) => { path: string } | undefined,
        ) => void
      }) {
        build.onResolve({ filter: /^bun:bundle$/ }, () => ({
          path: new URL('../runtime/bun-bundle.ts', import.meta.url).pathname,
        }))
      },
    })
  }
} catch {
  /* Bun plugin API not available — tsconfig paths will still cover tsc */
}

// ═══════════════════════════════════════════════════════════════════════
// Bun MACRO.* build-time constants
// ═══════════════════════════════════════════════════════════════════════
// UMMAYA's user-visible TUI version is sourced from tui/package.json.
// Release bumps must keep root package.json, pyproject.toml, and this TUI
// package version in sync; otherwise the npm tarball can publish one version
// while `ummaya --version` prints another. The previous "2.1.88-ummaya"
// hardcode was a residue of the CC 2.1.88 source-map import; UMMAYA is a
// separate project with its own release cadence (github.com/umyunsang/UMMAYA).
// npm release smoke also checks `ummaya --help` to catch commander option
// parse errors that happen after the fast --version path.
//
// BUILD_TIME is injected from the env var UMMAYA_BUILD_TIME at runtime
// (set by the packaging step). When unset (e.g. local dev) we fall back to
// the deterministic epoch-zero ISO string so reproducible builds stay
// byte-stable across machines.
import pkg from '../../package.json' with { type: 'json' }

const runtimeMacro = {
  VERSION: pkg.version,
  VERSION_CHANGELOG: 'https://github.com/umyunsang/UMMAYA/releases',
  BUILD_TIME: process.env.UMMAYA_BUILD_TIME ?? new Date(0).toISOString(),
  FEEDBACK_CHANNEL: 'https://github.com/umyunsang/UMMAYA/issues',
  ISSUES_EXPLAINER:
    'Please open a GitHub issue at https://github.com/umyunsang/UMMAYA/issues',
  PACKAGE_URL: 'https://github.com/umyunsang/UMMAYA',
  NATIVE_PACKAGE_URL: 'https://github.com/umyunsang/UMMAYA',
} satisfies typeof MACRO

Reflect.set(globalThis, 'MACRO', runtimeMacro)

// ═══════════════════════════════════════════════════════════════════════
// TTY detection shim
// Bun v1.3 reports `process.{stdin,stdout,stderr}.isTTY === undefined` by
// default, which makes CC evaluate `!process.stdout.isTTY` as `true` and
// switch to `--print` mode even inside iTerm2. We check the real signal
// (`tty.isatty(fd)`) and force the flag so CC routes to the interactive REPL.
// ═══════════════════════════════════════════════════════════════════════
try {
  const tty = require('node:tty')
  for (const fd of [0, 1, 2]) {
    if (tty.isatty(fd)) {
      const stream =
        fd === 0 ? process.stdin : fd === 1 ? process.stdout : process.stderr
      try {
        Object.defineProperty(stream, 'isTTY', {
          value: true,
          configurable: true,
        })
      } catch {
        /* stream's isTTY is frozen; fallback accepted */
      }
    }
  }
} catch {
  /* node:tty not available; fall through */
}

// ═══════════════════════════════════════════════════════════════════════
// Debug hooks — OFF by default. Enable with `UMMAYA_DEBUG_PRELOAD=1`.
// ═══════════════════════════════════════════════════════════════════════
if (process.env.UMMAYA_DEBUG_PRELOAD === '1') {
  process.stderr.write(
    `[UMMAYA/PRELOAD] loaded, pid=${process.pid}\n` +
      `[UMMAYA/TTY] stdin=${process.stdin.isTTY} stdout=${process.stdout.isTTY} stderr=${process.stderr.isTTY}\n`,
  )
  process.on('unhandledRejection', (reason: unknown) => {
    try {
      require('fs').writeSync(
        2,
        `[UMMAYA/DEBUG] unhandledRejection: ${
          reason instanceof Error ? reason.stack || reason.message : String(reason)
        }\n`,
      )
    } catch {
      /* stderr torn down */
    }
  })
  process.on('uncaughtException', (err: Error) => {
    try {
      require('fs').writeSync(
        2,
        `[UMMAYA/DEBUG] uncaughtException: ${err.stack || err.message}\n`,
      )
    } catch {
      /* stderr torn down */
    }
  })
  process.on('beforeExit', (code: number) => {
    try {
      require('fs').writeSync(2, `[UMMAYA/DEBUG] beforeExit(${code})\n`)
    } catch {
      /* stderr torn down */
    }
  })
  process.on('exit', (code: number) => {
    try {
      require('fs').writeSync(
        2,
        `[UMMAYA/DEBUG] exit(${code}) exitCode=${process.exitCode}\n`,
      )
    } catch {
      /* stderr torn down */
    }
  })

  // Patch process.exit so we can see WHO is calling it before the process
  // dies (boot crashes were silent — UMMAYA_FORCE_INTERACTIVE=1 prevents
  // the documented isTTY exit but a downstream caller is still firing
  // process.exit(1) without a stack trace). Wraps once per process; the
  // original is preserved on `process._origExit`.
  if (!process._origExit) {
    const originalExit: ProcessExit = process.exit.bind(process)
    process._origExit = originalExit
    const patchedExit: ProcessExit = code => {
      try {
        const stack = new Error('process.exit caller').stack ?? ''
        require('fs').writeSync(
          2,
          `[UMMAYA/DEBUG] process.exit(${code}) called\n${stack}\n`,
        )
      } catch {
        /* stderr torn down */
      }
      return originalExit(code)
    }
    process.exit = patchedExit
  }
}
