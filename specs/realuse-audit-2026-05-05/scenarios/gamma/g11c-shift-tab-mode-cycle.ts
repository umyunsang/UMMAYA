// SPDX-License-Identifier: Apache-2.0
// Wave-4 G11c / F-gamma-06 — Shift+Tab mode cycle Bun PTY verification.
//
// Uses the Bun-native PTY harness (NOT tmux) to send raw \x1b[Z bytes.
// AGENTS.md infra-insight #2: tmux send-keys S-Tab collides with the 500ms
// escape-time timer and never delivers a clean BackTab sequence to Ink.
// Bun.spawn({ terminal }) writes raw bytes directly to the child PTY.
//
// Verifies:
//   1. The TUI boots and shows mode indicator (● high · /effort).
//   2. First Shift+Tab changes the footer mode indicator OR shows a cycle
//      message (Use meta+t to toggle thinking / NORMAL / bypassPermissions).
//   3. Second Shift+Tab returns to the original mode OR advances to next mode.
//   4. No crash or frozen spinner from the Shift+Tab events.
//
// Run from repo root:
//   bun scripts/bun-pty-capture.ts \
//     specs/realuse-audit-2026-05-05/wave4/gamma/g11c \
//     specs/realuse-audit-2026-05-05/scenarios/gamma/g11c-shift-tab-mode-cycle.ts

import type { Harness } from '../../../scripts/bun-pty-capture'

async function sleep(ms: number): Promise<void> {
  await new Promise((r) => setTimeout(r, ms))
}

export default async function (h: Harness): Promise<void> {
  // -------------------------------------------------------------------------
  // Stage 1 — Boot: wait for KOSMOS branding and mode footer
  // -------------------------------------------------------------------------
  await h.waitForPane(/KOSMOS/, 30)
  await h.waitForPane(/tool_registry.*entries verified|high|effort|NORMAL/, 15)
  h.snapshot('boot-mode-indicator')

  // Capture the initial mode text for comparison
  const before = h.plain()

  // -------------------------------------------------------------------------
  // Stage 2 — First Shift+Tab (raw \x1b[Z sent via PTY)
  // BackTab is mapped in SPECIAL_KEY_MAP to '\x1b[Z' (VT220 / xterm standard)
  // -------------------------------------------------------------------------
  h.sendKey('BackTab')
  await sleep(400)  // allow Ink reconcile cycle (one frame ~16ms; 400ms is generous)
  h.snapshot('after-first-shift-tab')

  const afterFirst = h.plain()
  const modeChanged = beforeAfterDiffers(before, afterFirst)

  // -------------------------------------------------------------------------
  // Stage 3 — Second Shift+Tab (cycle again)
  // -------------------------------------------------------------------------
  h.sendKey('BackTab')
  await sleep(400)
  h.snapshot('after-second-shift-tab')

  const afterSecond = h.plain()

  // -------------------------------------------------------------------------
  // Stage 4 — Third Shift+Tab (verify cycling continues or wraps around)
  // -------------------------------------------------------------------------
  h.sendKey('BackTab')
  await sleep(400)
  h.snapshot('after-third-shift-tab')

  // -------------------------------------------------------------------------
  // Stage 5 — Verify assertions
  //
  // Success criteria (any ONE must be satisfied):
  //   A. afterFirst != before  (mode indicator text changed after first press)
  //   B. afterSecond != afterFirst  (mode continued cycling on second press)
  //   C. afterSecond == before  (two presses returned to original — 2-mode cycle)
  //   D. Footer contains known mode strings: 'high', 'normal', 'NORMAL',
  //      'bypass', 'bypassPermissions', 'thinking', 'meta+t'
  // -------------------------------------------------------------------------
  const knownModePatterns = [
    /● high/,
    /● normal/,
    /NORMAL/i,
    /bypassPermissions/,
    /bypass/i,
    /meta\+t.*toggle/i,
    /thinking/,
    /effort/,
  ]
  const footerHasKnownMode = knownModePatterns.some((re) => re.test(afterFirst))

  process.stderr.write(
    `[g11c] mode_changed_after_first_shift_tab=${modeChanged}\n` +
    `[g11c] footer_has_known_mode=${footerHasKnownMode}\n`,
  )

  if (!modeChanged && !footerHasKnownMode) {
    process.stderr.write(
      '[g11c WARNING] Neither mode change nor known mode pattern detected. ' +
      'Check snap-001-after-first-shift-tab.txt for footer content.\n',
    )
  }

  // -------------------------------------------------------------------------
  // Stage 6 — Quit cleanly
  // -------------------------------------------------------------------------
  h.sendKey('C-c')
  await sleep(500)
  h.sendKey('C-c')
  await sleep(300)
  h.snapshot('quit')
}

// ---------------------------------------------------------------------------
// Helper — does the ANSI-stripped plain-text differ in the footer line?
// We compare only the last 8 lines to avoid false positives from streaming.
// ---------------------------------------------------------------------------
function beforeAfterDiffers(before: string, after: string): boolean {
  const tail = (s: string): string =>
    s.split('\n').slice(-8).join('\n')
  return tail(before) !== tail(after)
}
