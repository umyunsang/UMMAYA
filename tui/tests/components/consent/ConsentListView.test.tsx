// SPDX-License-Identifier: Apache-2.0
// KOSMOS — ConsentListView component tests (FR-019).
//
// Pins the /consent list overlay contract:
//   - mount with receipts → table contains receipt_id / layer / tool / decision
//   - mount with empty receipts → "아직 발급된 영수증이 없습니다" empty-state
//   - Esc keypress → onExit fires (defense-in-depth useInput fallback,
//     AGENTS.md "Infrastructure insights" #3 + #4)
//   - revoked receipt renders [REVOKED] suffix
//   - reverse-chronological order (FR-019) is preserved by buildConsentListRows()
//   - renderConsentListPlain helper is symmetric to the Ink view
//
// Test harness pattern matches tests/components/onboarding/PreflightStep.test.tsx
// (ink-testing-library + ThemeProvider).

import React from 'react';
import { describe, expect, it } from 'bun:test';
import { render } from 'ink-testing-library';
import { ThemeProvider } from '../../../src/theme/provider';
import {
  ConsentListView,
  renderConsentListPlain,
} from '../../../src/components/consent/ConsentListView';
import type { PermissionReceiptT } from '../../../src/schemas/ui-l2/permission';

function makeReceipt(
  id: string,
  ts: string,
  opts: {
    layer?: 1 | 2 | 3;
    tool_name?: string;
    decision?: PermissionReceiptT['decision'];
    revoked_at?: string | null;
  } = {},
): PermissionReceiptT {
  return {
    receipt_id: id,
    layer: opts.layer ?? 2,
    tool_name: opts.tool_name ?? 'test_tool',
    decision: opts.decision ?? 'allow_once',
    decided_at: ts,
    session_id: 'sess-test',
    revoked_at: opts.revoked_at ?? null,
  };
}

function tick(ms = 20): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ---------------------------------------------------------------------------
// Empty-state
// ---------------------------------------------------------------------------

describe('ConsentListView — empty receipts', () => {
  it('renders the bilingual empty-state message', () => {
    const { lastFrame } = render(
      <ThemeProvider>
        <ConsentListView receipts={[]} onExit={() => {}} />
      </ThemeProvider>,
    );
    const frame = lastFrame() ?? '';
    expect(frame).toContain('아직 발급된 영수증이 없습니다');
    expect(frame).toContain('No receipts issued yet');
    expect(frame).toContain('총 0건');
  });
});

// ---------------------------------------------------------------------------
// Populated table
// ---------------------------------------------------------------------------

describe('ConsentListView — non-empty receipts', () => {
  it('renders receipt_id / layer / tool / decision columns for each row', () => {
    const receipts = [
      makeReceipt('rcpt-aaaaaaaa', '2026-04-25T09:00:00.000Z', {
        layer: 1,
        tool_name: 'kma_forecast',
        decision: 'allow_once',
      }),
      makeReceipt('rcpt-bbbbbbbb', '2026-04-25T10:00:00.000Z', {
        layer: 3,
        tool_name: 'hira_lookup',
        decision: 'allow_session',
      }),
    ];

    const { lastFrame } = render(
      <ThemeProvider>
        <ConsentListView receipts={receipts} onExit={() => {}} />
      </ThemeProvider>,
    );
    const frame = lastFrame() ?? '';
    expect(frame).toContain('권한 영수증');
    expect(frame).toContain('rcpt-aaaaaaaa');
    expect(frame).toContain('rcpt-bbbbbbbb');
    expect(frame).toContain('kma_forecast');
    expect(frame).toContain('hira_lookup');
    expect(frame).toContain('allow_once');
    expect(frame).toContain('allow_session');
    expect(frame).toContain('총 2건');
  });

  it('renders newest receipt first (FR-019 reverse chronological)', () => {
    // Pass in chronological order; expect the newer one to render above.
    const older = makeReceipt('rcpt-oldoldoo', '2026-04-25T08:00:00.000Z');
    const newer = makeReceipt('rcpt-newnewnn', '2026-04-25T11:00:00.000Z');
    const { lastFrame } = render(
      <ThemeProvider>
        <ConsentListView receipts={[older, newer]} onExit={() => {}} />
      </ThemeProvider>,
    );
    const frame = lastFrame() ?? '';
    const newerIdx = frame.indexOf('rcpt-newnewnn');
    const olderIdx = frame.indexOf('rcpt-oldoldoo');
    expect(newerIdx).toBeGreaterThan(-1);
    expect(olderIdx).toBeGreaterThan(-1);
    expect(newerIdx).toBeLessThan(olderIdx);
  });

  it('renders [REVOKED] suffix for revoked receipts', () => {
    const revoked = makeReceipt('rcpt-revoked1', '2026-04-25T10:00:00.000Z', {
      revoked_at: '2026-04-25T11:00:00.000Z',
    });
    const { lastFrame } = render(
      <ThemeProvider>
        <ConsentListView receipts={[revoked]} onExit={() => {}} />
      </ThemeProvider>,
    );
    const frame = lastFrame() ?? '';
    expect(frame).toContain('rcpt-revoked1');
    expect(frame).toContain('[REVOKED]');
  });
});

// ---------------------------------------------------------------------------
// Esc → onExit (defense-in-depth, AGENTS.md insight #3 + #4)
// ---------------------------------------------------------------------------

describe('ConsentListView — Esc dismisses', () => {
  it('invokes onExit when the citizen presses Escape', async () => {
    let exited = false;
    const { stdin } = render(
      <ThemeProvider>
        <ConsentListView receipts={[]} onExit={() => { exited = true; }} />
      </ThemeProvider>,
    );
    // Drain initial render.
    await tick();
    // Raw ESC byte — same as a real PTY keystroke.
    stdin.write('');
    await tick();
    expect(exited).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// renderConsentListPlain helper
// ---------------------------------------------------------------------------

describe('renderConsentListPlain', () => {
  it('returns the empty-state string when no receipts', () => {
    expect(renderConsentListPlain([])).toContain('아직 발급된 영수증이 없습니다');
  });

  it('joins formatted rows with newlines, newest first', () => {
    const older = makeReceipt('rcpt-aaaaaaaa', '2026-04-25T08:00:00.000Z');
    const newer = makeReceipt('rcpt-bbbbbbbb', '2026-04-25T10:00:00.000Z');
    const out = renderConsentListPlain([older, newer]);
    const lines = out.split('\n');
    expect(lines).toHaveLength(2);
    expect(lines[0]).toContain('rcpt-bbbbbbbb');
    expect(lines[1]).toContain('rcpt-aaaaaaaa');
  });
});
