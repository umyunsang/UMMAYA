// SPDX-License-Identifier: Apache-2.0
// Sanity check: does Bun PTY raw write actually reach the Ink TUI stdin?
// Type the literal text "abc" and confirm it appears in the prompt.
import type { Harness } from '../../../scripts/bun-pty-capture';

export default async function (h: Harness): Promise<void> {
  await h.waitForPane(/KOSMOS\s*v?0\./, 30);
  h.snapshot('boot');
  // Type characters and check the prompt buffer reflects them.
  h.sendText('abc');
  await new Promise((r) => setTimeout(r, 1500));
  h.snapshot('after-typed-abc');
  // Send Esc — should clear the buffer or at least be observable.
  h.sendEscape();
  await new Promise((r) => setTimeout(r, 1500));
  h.snapshot('after-esc');
  // One more text after esc to see if input still routed to prompt.
  h.sendText('xyz');
  await new Promise((r) => setTimeout(r, 1500));
  h.snapshot('after-typed-xyz');
  h.sendCtrlC();
  await new Promise((r) => setTimeout(r, 500));
  h.sendCtrlC();
  await new Promise((r) => setTimeout(r, 1000));
  h.snapshot('exit');
}
