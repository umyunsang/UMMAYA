// SPDX-License-Identifier: Apache-2.0
// Layer 3/5 PTY scenario for FriendliAI session auth.

export default async function run(h: {
  waitForPane(pattern: RegExp | string, deadlineSec?: number): Promise<void>
  waitForPaneSince(
    mark: number,
    pattern: RegExp | string,
    deadlineSec?: number,
  ): Promise<void>
  snapshot(label: string): string
  mark(): number
  sendText(text: string): void
  sendEnter(): void
  sendCtrlC(): void
}): Promise<void> {
  const sleep = async (ms: number): Promise<void> => {
    await new Promise<void>((resolve) => setTimeout(resolve, ms))
  }

  await h.waitForPane(/Not logged in · Run \/login/, 20)
  h.snapshot('boot-no-friendli-key')

  const loginMark = h.mark()
  h.sendText('/login')
  await h.waitForPaneSince(loginMark, /\/login/, 5)
  await sleep(500)
  h.sendEnter()
  await h.waitForPane(/Login/, 10)
  h.snapshot('login-dialog')

  await sleep(500)
  h.sendText('friendli-pty-placeholder')
  await h.waitForPane(/\*{8}/, 5)
  h.snapshot('login-input-masked')

  h.sendEnter()
  await h.waitForPane(/Login successful/, 10)
  h.snapshot('login-success')

  const logoutMark = h.mark()
  h.sendText('/logout')
  await h.waitForPaneSince(logoutMark, /\/logout/, 5)
  await sleep(500)
  h.sendEnter()
  await h.waitForPane(/Successfully logged out/, 10)
  h.snapshot('logout-success')
}
