/**
 * Snapshot tests for send primitive renderers.
 * Uses ink-testing-library for output capture.
 * FR-026, FR-027, FR-034, FR-035.
 */
import { describe, test, expect } from 'bun:test'
import React from 'react'
import { render } from 'ink-testing-library'
import { ThemeProvider } from '@/theme/provider'
import { SubmitReceipt } from '@/components/primitive/SubmitReceipt'
import { SubmitErrorBanner } from '@/components/primitive/SubmitErrorBanner'

import receiptFixture from '../fixtures/submit/submit-receipt.json'
import errorFixture from '../fixtures/submit/submit-error.json'

import type { SubmitSuccessPayload, SubmitErrorPayload } from '@/components/primitive/types'

function wrap(element: React.ReactElement): React.ReactElement {
  return <ThemeProvider>{element}</ThemeProvider>
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
    expect(frame).toMatchSnapshot()
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
    expect(frame).toMatchSnapshot()
  })
})
