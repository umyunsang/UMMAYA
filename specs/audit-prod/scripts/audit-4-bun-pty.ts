// SPDX-License-Identifier: Apache-2.0
// audit-4-bun-pty — Permission Gauntlet via Bun-native PTY (bypasses tmux escape-time)
//
// Run from repo root:
//   KOSMOS_BACKEND_LOG_FILE=/tmp/audit-4-bun.log \
//     bun scripts/bun-pty-capture.ts \
//       specs/audit-prod/audit-4-bun-pty \
//       specs/audit-prod/scripts/audit-4-bun-pty.ts
//
// Purpose:
//   1. Confirm whether the Y/A/N selector is functionally responsive when
//      input bytes arrive via a real PTY (the tmux scenario showed the
//      modal frozen on the first option; we need to disambiguate
//      tmux-routing vs modal-bug).
//   2. Confirm the wire decision sent on A vs Y (allow_session vs allow_once).
//      The TUI's pushIpcPermissionRequest._sendPermissionResponse always
//      sends 'granted' / 'denied' — never 'allow_session'.  We capture
//      stderr (which mirrors the raw PTY) for the wire bytes.

import type { Harness } from '../../../scripts/bun-pty-capture.ts'

export default async function (h: Harness): Promise<void> {
  // -------------------- Stage 0 — boot --------------------
  await h.waitForPane(/tool_registry: \d+ entries verified/, 90)
  h.snapshot('00-boot')

  // -------------------- Stage 1 — verify primitive Y --------------------
  h.sendText('모바일 신분증으로 신원 확인을 진행해 주세요')
  h.sendEnter()
  // Modal title.
  await h.waitForPane(/신원 확인 권한 요청/, 120)
  h.snapshot('01-verify-modal')

  // Press Enter — first option (Y allow_once) is default focus.
  h.sendEnter()
  await new Promise((r) => setTimeout(r, 2000))
  h.snapshot('02-after-Y-enter')

  // Wait for tool dispatch to complete (or LLM to react).
  await new Promise((r) => setTimeout(r, 8000))
  h.snapshot('03-after-Y-dispatch')

  // -------------------- Stage 2 — /consent list --------------------
  h.sendText('/consent list')
  h.sendEnter()
  await new Promise((r) => setTimeout(r, 2000))
  h.snapshot('04-consent-list-after-Y')
  h.sendEscape()
  await new Promise((r) => setTimeout(r, 500))

  // -------------------- Stage 3 — submit primitive A --------------------
  h.sendText('복지 급여 신청을 제출해 주세요')
  h.sendEnter()
  await h.waitForPane(/(제출 권한 요청|신원 확인 권한 요청)/, 120)
  h.snapshot('05-submit-modal-mounted')

  // Press DownArrow once to move from Y to A, then Enter.
  h.sendKey('Down')
  await new Promise((r) => setTimeout(r, 400))
  h.snapshot('06-submit-modal-A-focus')

  h.sendEnter()
  await new Promise((r) => setTimeout(r, 2000))
  h.snapshot('07-after-A-enter')

  await new Promise((r) => setTimeout(r, 8000))
  h.snapshot('08-after-A-dispatch')

  // -------------------- Stage 4 — second submit (test session-grant cache) --------------------
  h.sendText('같은 복지 급여 신청을 다시 제출해 주세요')
  h.sendEnter()
  // If allow_session caching worked, NO modal should mount.  If broken,
  // the same modal mounts again (proving cache miss).
  await new Promise((r) => setTimeout(r, 12000))
  h.snapshot('09-submit-second-call')

  // -------------------- Stage 5 — exit --------------------
  h.sendCtrlC()
  h.sendCtrlC()
  await new Promise((r) => setTimeout(r, 1000))
  h.snapshot('10-exit')
}
