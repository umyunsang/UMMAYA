// SPDX-License-Identifier: Apache-2.0
// Lang ko↔en round-trip via Bun-native PTY harness.
// Runs:
//   bun scripts/bun-pty-capture.ts <out> <this scenario>
import type { Harness } from '../../../scripts/bun-pty-capture';

export default async function (h: Harness): Promise<void> {
  await h.waitForPane(/KOSMOS\s*v?0\./, 30);
  h.snapshot('boot-default-ko');

  // Stage A — open /help in default ko
  h.sendText('/help');
  await new Promise((r) => setTimeout(r, 800));
  h.sendEnter();
  await h.waitForPane(/세션|권한|도구|저장/, 10);
  h.snapshot('default-help-ko');

  // Stage B — Escape once to dismiss (after /help wiring fix routes
  // through PromptInput's setHelpOpen, the help:dismiss keybinding
  // gated by helpOpen fires on a single Esc).
  h.sendEscape();
  await new Promise((r) => setTimeout(r, 1500));
  h.snapshot('after-escape');

  // Stage C — switch to en, re-open help, must render English
  h.sendText('/lang en');
  await new Promise((r) => setTimeout(r, 800));
  h.sendEnter();
  await new Promise((r) => setTimeout(r, 1500));
  h.snapshot('after-lang-en');
  h.sendText('/help');
  await new Promise((r) => setTimeout(r, 800));
  h.sendEnter();
  await h.waitForPane(/Session|Permission|Tool|Storage/, 10);
  h.snapshot('help-en-after-switch');

  // Stage D — Escape once to dismiss, switch back to ko, re-open help
  h.sendEscape();
  await new Promise((r) => setTimeout(r, 1500));
  h.snapshot('after-escape-en');
  h.sendText('/lang ko');
  await new Promise((r) => setTimeout(r, 800));
  h.sendEnter();
  await new Promise((r) => setTimeout(r, 1500));
  h.snapshot('after-lang-ko');
  h.sendText('/help');
  await new Promise((r) => setTimeout(r, 800));
  h.sendEnter();
  await h.waitForPane(/세션|권한|도구|저장/, 15);
  h.snapshot('help-ko-roundtrip');

  // Clean exit
  h.sendCtrlC();
  await new Promise((r) => setTimeout(r, 500));
  h.sendCtrlC();
  await new Promise((r) => setTimeout(r, 1000));
  h.snapshot('exit');
}
