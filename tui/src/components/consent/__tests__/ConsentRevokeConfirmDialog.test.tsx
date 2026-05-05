// SPDX-License-Identifier: Apache-2.0
// Epic 2 — ConsentRevokeConfirmDialog unit tests.
//
// Tests are ink-testing-library (Layer 1b) snapshot tests.
// They verify:
//   1. Renders without crashing for a standard receipt.
//   2. PIPA §36 citation is present in the output.
//   3. onConfirm('once') fires on Y keypress.
//   4. onConfirm('session-all') fires on A keypress.
//   5. onCancel fires on N keypress.
//   6. onCancel fires on Esc keypress.
//   7. already-revoked notice is displayed when receipt.revoked_at is set.

import { describe, it, expect, mock } from 'bun:test'
import React from 'react'
import { render } from 'ink-testing-library'
import { ConsentRevokeConfirmDialog } from '../ConsentRevokeConfirmDialog.js'
import type { PermissionReceiptT } from '../../../schemas/ui-l2/permission.js'

// ---------------------------------------------------------------------------
// Fixture
// ---------------------------------------------------------------------------

const BASE_RECEIPT: PermissionReceiptT = {
  receipt_id: 'rcpt-abcdefgh',
  layer: 1,
  tool_name: 'kma_short_term_forecast',
  decision: 'allow_once',
  decided_at: '2026-05-04T12:00:00.000Z',
  session_id: 'sess-test-1',
  revoked_at: null,
}

const REVOKED_RECEIPT: PermissionReceiptT = {
  ...BASE_RECEIPT,
  receipt_id: 'rcpt-revoked01',
  revoked_at: '2026-05-04T13:00:00.000Z',
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ConsentRevokeConfirmDialog', () => {
  it('renders without crashing (case 1)', () => {
    const onConfirm = mock(() => {})
    const onCancel = mock(() => {})

    const { lastFrame, unmount } = render(
      React.createElement(ConsentRevokeConfirmDialog, {
        receipt: BASE_RECEIPT,
        onConfirm,
        onCancel,
        locale: 'ko',
      }),
    )

    const frame = lastFrame()
    expect(frame).toBeTruthy()
    // Title must be present.
    expect(frame).toContain('KOSMOS')
    unmount()
  })

  it('contains PIPA §36 citation text (case 2)', () => {
    const { lastFrame, unmount } = render(
      React.createElement(ConsentRevokeConfirmDialog, {
        receipt: BASE_RECEIPT,
        onConfirm: mock(() => {}),
        onCancel: mock(() => {}),
        locale: 'ko',
      }),
    )

    const frame = lastFrame() ?? ''
    expect(frame).toContain('PIPA §36')
    unmount()
  })

  it('calls onConfirm("once") on Y keypress (case 3)', () => {
    const onConfirm = mock((_scope: string) => {})
    const onCancel = mock(() => {})

    const { stdin, unmount } = render(
      React.createElement(ConsentRevokeConfirmDialog, {
        receipt: BASE_RECEIPT,
        onConfirm,
        onCancel,
        locale: 'ko',
      }),
    )

    stdin.write('y')
    expect(onConfirm).toHaveBeenCalledWith('once')
    expect(onCancel).not.toHaveBeenCalled()
    unmount()
  })

  it('calls onConfirm("session-all") on A keypress (case 4)', () => {
    const onConfirm = mock((_scope: string) => {})
    const onCancel = mock(() => {})

    const { stdin, unmount } = render(
      React.createElement(ConsentRevokeConfirmDialog, {
        receipt: BASE_RECEIPT,
        onConfirm,
        onCancel,
        locale: 'ko',
      }),
    )

    stdin.write('a')
    expect(onConfirm).toHaveBeenCalledWith('session-all')
    unmount()
  })

  it('calls onCancel on N keypress (case 5)', () => {
    const onConfirm = mock((_scope: string) => {})
    const onCancel = mock(() => {})

    const { stdin, unmount } = render(
      React.createElement(ConsentRevokeConfirmDialog, {
        receipt: BASE_RECEIPT,
        onConfirm,
        onCancel,
        locale: 'ko',
      }),
    )

    stdin.write('n')
    expect(onCancel).toHaveBeenCalled()
    expect(onConfirm).not.toHaveBeenCalled()
    unmount()
  })

  it('calls onCancel on Esc keypress (case 6)', () => {
    const onConfirm = mock((_scope: string) => {})
    const onCancel = mock(() => {})

    const { stdin, unmount } = render(
      React.createElement(ConsentRevokeConfirmDialog, {
        receipt: BASE_RECEIPT,
        onConfirm,
        onCancel,
        locale: 'ko',
      }),
    )

    // Escape key sequence
    stdin.write('\x1b')
    expect(onCancel).toHaveBeenCalled()
    unmount()
  })

  it('shows already-revoked notice when revoked_at is set (case 7)', () => {
    const { lastFrame, unmount } = render(
      React.createElement(ConsentRevokeConfirmDialog, {
        receipt: REVOKED_RECEIPT,
        onConfirm: mock((_scope: string) => {}),
        onCancel: mock(() => {}),
        locale: 'ko',
      }),
    )

    const frame = lastFrame() ?? ''
    expect(frame).toContain('이미 철회된')
    unmount()
  })
})
