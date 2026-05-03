#!/usr/bin/env bun
// SPDX-License-Identifier: Apache-2.0
//
// KOSMOS-original — Bun-native PTY harness for end-to-end TUI verification.
//
// Replaces the tmux send-keys path for scenarios where keystroke delivery
// timing is critical. The tmux harness suffers from two unfixable
// limitations (deep research 2026-05-04):
//   1. tmux escape-time (default 500 ms) batches Escape with subsequent
//      bytes into Meta-/function-key sequences before delivery.
//   2. The Ink App-level handler intercepts Escape globally (clears
//      activeFocusId) before component-level useInput hooks ever see it.
//      Setting `escape-time 0` did not bypass this in production.
//
// This harness uses Bun.spawn({terminal: ...}) (Bun ≥ 1.3.5) to attach a
// real PTY, then writes raw escape bytes (\x1b) directly to the child's
// terminal. That mirrors what an interactive human keystroke produces and
// gives Ink's stdin reader an unambiguous Escape byte with no batching.
//
// API mirrors scripts/tui-tmux-capture.sh helpers:
//   waitForPane(pattern, deadlineSec)
//   snapshot(label)
//   sendText(text)         — literal bytes (incl. spaces)
//   sendEnter()
//   sendEscape()           — raw 0x1b
//   sendCtrlC()
//   sendKey('Up' | 'Down' | ...)
//
// Usage:
//   bun scripts/bun-pty-capture.ts <out-dir> <scenario.ts>
//
// The scenario.ts module must export a default async function:
//   export default async (h: Harness) => { await h.waitForPane(...); ... }

import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve as pathResolve } from 'node:path';

type SpecialKey =
  | 'Enter'
  | 'Tab'
  | 'BackTab'
  | 'Backspace'
  | 'Escape'
  | 'Up'
  | 'Down'
  | 'Left'
  | 'Right'
  | 'Home'
  | 'End'
  | 'PageUp'
  | 'PageDown'
  | 'C-c'
  | 'C-d'
  | 'C-q'
  | 'C-z';

const SPECIAL_KEY_MAP: Record<SpecialKey, string> = {
  Enter: '\r',
  Tab: '\t',
  BackTab: '\x1b[Z',
  Backspace: '\x7f',
  Escape: '\x1b',
  Up: '\x1b[A',
  Down: '\x1b[B',
  Right: '\x1b[C',
  Left: '\x1b[D',
  Home: '\x1b[H',
  End: '\x1b[F',
  PageUp: '\x1b[5~',
  PageDown: '\x1b[6~',
  'C-c': '\x03',
  'C-d': '\x04',
  'C-q': '\x11',
  'C-z': '\x1a',
};

// ---------------------------------------------------------------------------
// ANSI strip — produce greppable plain text from xterm output.
//
// Cursor-right (CSI n C) is replaced with a single space so words separated
// by `\x1b[1C` (cursor right one column) do not collapse to a single token
// after the catch-all CSI strip.  All other CSI / OSC / DCS / single-char
// escape sequences are removed entirely.
// ---------------------------------------------------------------------------
const CURSOR_RE = /\x1b\[\d+[ABCD]/g;
const CSI_RE = /\x1b\[[\d;?]*[A-Za-z]/g;
const OSC_RE = /\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)/g;
const DCS_RE = /\x1bP[^\x07\x1b]*\x1b\\/g;
const ESC_SHORT_RE = /\x1b[=>()#0-9?\\]/g;

function stripAnsi(s: string): string {
  return s
    .replace(CURSOR_RE, ' ')
    .replace(CSI_RE, '')
    .replace(OSC_RE, '')
    .replace(DCS_RE, '')
    .replace(ESC_SHORT_RE, '');
}

export interface Harness {
  cols: number;
  rows: number;
  outDir: string;
  buffer: string; // raw stream (with ANSI)
  plain: () => string; // ANSI-stripped buffer
  write(data: string): void;
  sendText(s: string): void;
  sendEnter(): void;
  sendEscape(): void;
  sendCtrlC(): void;
  sendKey(name: SpecialKey): void;
  waitForPane(pattern: RegExp | string, deadlineSec?: number): Promise<void>;
  snapshot(label: string): string;
  resize(cols: number, rows: number): void;
}

async function sleep(ms: number): Promise<void> {
  await new Promise((r) => setTimeout(r, ms));
}

async function run(): Promise<void> {
  const [, , outDir, scenarioPath] = process.argv;
  if (!outDir || !scenarioPath) {
    process.stderr.write(
      'usage: bun bun-pty-capture.ts <out-dir> <scenario.ts>\n',
    );
    process.exit(2);
  }

  const cols = Number(process.env.KOSMOS_DEBUG_COLS ?? 180);
  const rows = Number(process.env.KOSMOS_DEBUG_ROWS ?? 60);

  mkdirSync(outDir, { recursive: true });
  const absOut = pathResolve(outDir);

  const repoRoot = pathResolve(import.meta.dir, '..');
  const tuiDir = pathResolve(repoRoot, 'tui');

  const harnessBuf = { value: '' };
  const snapSeqRef = { value: 0 };

  const proc = Bun.spawn(['bun', 'run', 'tui'], {
    cwd: tuiDir,
    env: { ...process.env },
    terminal: {
      cols,
      rows,
      data(_terminal: unknown, data: Uint8Array | string) {
        const text =
          typeof data === 'string' ? data : new TextDecoder().decode(data);
        harnessBuf.value += text;
        // Mirror to stderr so a developer running the harness interactively
        // can see what the TUI is doing without polluting our snapshot files
        // (which only contain stripped plain text).
        process.stderr.write(text);
      },
    },
  } as any);

  const writeRaw = (data: string): void => {
    (proc as any).terminal.write(data);
  };

  const harness: Harness = {
    cols,
    rows,
    outDir: absOut,
    get buffer() {
      return harnessBuf.value;
    },
    plain() {
      return stripAnsi(harnessBuf.value);
    },
    write: writeRaw,
    sendText(s: string) {
      writeRaw(s);
    },
    sendEnter() {
      writeRaw(SPECIAL_KEY_MAP.Enter);
    },
    sendEscape() {
      writeRaw(SPECIAL_KEY_MAP.Escape);
    },
    sendCtrlC() {
      writeRaw(SPECIAL_KEY_MAP['C-c']);
    },
    sendKey(name: SpecialKey) {
      const seq = SPECIAL_KEY_MAP[name];
      if (seq === undefined) throw new Error(`Unknown special key: ${name}`);
      writeRaw(seq);
    },
    async waitForPane(pattern: RegExp | string, deadlineSec = 30) {
      const re = typeof pattern === 'string' ? new RegExp(pattern) : pattern;
      const start = Date.now();
      const deadline = start + deadlineSec * 1000;
      while (Date.now() < deadline) {
        const stripped = stripAnsi(harnessBuf.value);
        if (re.test(stripped)) {
          const elapsed = ((Date.now() - start) / 1000).toFixed(1);
          process.stderr.write(
            `\n[waitForPane MATCH ${re} after ${elapsed}s]\n`,
          );
          return;
        }
        await sleep(120);
      }
      const elapsed = ((Date.now() - start) / 1000).toFixed(1);
      process.stderr.write(
        `\n[waitForPane TIMEOUT ${re} after ${elapsed}s]\n`,
      );
      const file = pathResolve(absOut, `timeout-${Date.now()}.txt`);
      writeFileSync(file, stripAnsi(harnessBuf.value));
      throw new Error(`waitForPane timeout: ${re}`);
    },
    snapshot(label: string) {
      const seq = String(snapSeqRef.value++).padStart(3, '0');
      const file = pathResolve(absOut, `snap-${seq}-${label}.txt`);
      writeFileSync(file, stripAnsi(harnessBuf.value));
      process.stderr.write(`[snapshot ${file}]\n`);
      return file;
    },
    resize(cols2: number, rows2: number) {
      (proc as any).terminal.resize(cols2, rows2);
      harness.cols = cols2;
      harness.rows = rows2;
    },
  };

  // Allow some boot time before the scenario's first read.
  await sleep(500);

  let scenarioErr: Error | null = null;
  try {
    const scenario = await import(pathResolve(scenarioPath));
    if (typeof scenario.default !== 'function') {
      throw new Error(
        `scenario ${scenarioPath} must export a default async function`,
      );
    }
    await scenario.default(harness);
  } catch (err) {
    scenarioErr = err as Error;
    process.stderr.write(`\n[scenario ERROR] ${(err as Error).message}\n`);
  } finally {
    // Always write final state for postmortem.
    const finalFile = pathResolve(absOut, 'final.txt');
    writeFileSync(finalFile, stripAnsi(harnessBuf.value));
    const rawFile = pathResolve(absOut, 'final.raw.txt');
    writeFileSync(rawFile, harnessBuf.value);
    try {
      (proc as any).terminal.close();
    } catch {
      /* already closed */
    }
    proc.kill();
  }

  process.stderr.write(`\n=== captures saved to ${absOut} ===\n`);
  if (scenarioErr) process.exit(1);
}

void run();
