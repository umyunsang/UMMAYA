/**
 * Snapshot tests for send primitive renderers.
 * Uses ink-testing-library for output capture.
 * FR-026, FR-027, FR-034, FR-035.
 */
import { describe, test, expect } from 'bun:test'
import React from 'react'
import { render } from 'ink-testing-library'
import { ThemeProvider } from '@/theme/provider'
import { TerminalSizeContext } from '@/ink/components/TerminalSizeContext'
import { SubmitReceipt } from '@/components/primitive/SubmitReceipt'
import { SubmitErrorBanner } from '@/components/primitive/SubmitErrorBanner'
import { SubmitPrimitive } from '@/tools/SubmitPrimitive/SubmitPrimitive'
import { stripSnapshotAnsi } from './snapshotFrame'

import receiptFixture from '../fixtures/submit/submit-receipt.json'
import errorFixture from '../fixtures/submit/submit-error.json'

import type { SubmitSuccessPayload, SubmitErrorPayload } from '@/components/primitive/types'

function wrap(element: React.ReactElement): React.ReactElement {
  return (
    <ThemeProvider>
      <TerminalSizeContext.Provider value={{ columns: 100, rows: 24 }}>
        {element}
      </TerminalSizeContext.Provider>
    </ThemeProvider>
  )
}

describe('SubmitReceipt', () => {
  test('renders confirmation id, timestamp, and mock chip', () => {
    const payload = receiptFixture.envelope as SubmitSuccessPayload
    const { lastFrame } = render(wrap(<SubmitReceipt payload={payload} />))
    const frame = lastFrame() ?? ''
    expect(frame).toContain(payload.confirmation_id)
    expect(frame).toContain(payload.timestamp)
    // FR-026: mock_reason present → MOCK chip visible
    expect(frame).toContain(`[MOCK: ${payload.mock_reason}]`)
    expect(stripSnapshotAnsi(frame)).toMatchSnapshot()
  })
})

describe('SubmitErrorBanner', () => {
  test('renders error code, message, and retry hint', () => {
    const payload = errorFixture.envelope as SubmitErrorPayload
    const { lastFrame } = render(wrap(<SubmitErrorBanner payload={payload} />))
    const frame = lastFrame() ?? ''
    const compact = frame.replace(/\s+/g, ' ')
    expect(compact).toContain(payload.error_code)
    // Long messages wrap in terminal output; check a distinguishing prefix
    expect(compact).toContain('This application requires authenticated identity')
    expect(compact).toContain('Use /verify to authenticate')
    expect(stripSnapshotAnsi(frame)).toMatchSnapshot()
  })
})

describe('SubmitPrimitive document result bridge', () => {
  test('renders wrapped document fill results through the document review surface', () => {
    const ui = SubmitPrimitive.renderToolResultMessage?.(
      {
        ok: true,
        result: {
          tool_id: 'document_apply_fill',
          correlation_id: 'corr-fill',
          status: 'ok',
          artifact_refs: ['derivative-corr-fill'],
          text_summary: 'Applied 1 fill operation and generated a document diff.',
          diff: {
            diff_id: 'diff-corr-fill',
            source_artifact_id: 'working-doc',
            derivative_artifact_id: 'derivative-doc',
            changes: [
              {
                change_id: 'change-001',
                operation_id: 'fill-week',
                change_type: 'field',
                target_path: '/hwpx/text[2]',
                before_value: '12 주차 ',
                after_value: '13 주차 ',
              },
            ],
          },
        },
      },
      [],
      { verbose: false },
    )
    const { lastFrame } = render(wrap(ui as React.ReactElement))
    const frame = lastFrame() ?? ''

    expect(frame).toContain('Changed 1 field')
    // Inline structural diff (CC pipeline): before/after values + field path.
    expect(frame).toContain('12 주차')
    expect(frame).toContain('13 주차')
    expect(frame).toContain('text[2]')
    expect(frame).not.toContain('Submission accepted')
  })
})
