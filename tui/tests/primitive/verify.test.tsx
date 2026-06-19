/**
 * Snapshot tests for check primitive renderers.
 * Uses ink-testing-library for output capture.
 * FR-030, FR-031, FR-032, FR-034, FR-035.
 */
import { describe, test, expect } from 'bun:test'
import React from 'react'
import { render } from 'ink-testing-library'
import { ThemeProvider } from '@/theme/provider'
import { AuthContextCard } from '@/components/primitive/AuthContextCard'
import { AuthWarningBanner } from '@/components/primitive/AuthWarningBanner'
import { stripSnapshotAnsi } from './snapshotFrame'

import authCardFixture from '../fixtures/verify/auth-context-card.json'
import authWarningFixture from '../fixtures/verify/auth-warning-banner.json'

import type { VerifySuccessPayload, VerifyFailPayload } from '@/components/primitive/types'

function wrap(element: React.ReactElement): React.ReactElement {
  return <ThemeProvider>{element}</ThemeProvider>
}

describe('AuthContextCard', () => {
  test('renders identity label, korea_tier as primary label, and NIST hint', () => {
    const payload = authCardFixture.envelope as VerifySuccessPayload
    const { lastFrame } = render(wrap(<AuthContextCard payload={payload} />))
    const frame = lastFrame() ?? ''
    // FR-030: korea_tier MUST be the primary level label
    expect(frame).toContain(payload.korea_tier)
    expect(frame).toContain(payload.identity_label)
    expect(frame).toContain(payload.nist_aal_hint ?? '')
    expect(stripSnapshotAnsi(frame)).toMatchSnapshot()
  })
})

describe('AuthWarningBanner', () => {
  test('renders korea_tier, error code, message, and remediation', () => {
    const payload = authWarningFixture.envelope as VerifyFailPayload
    const { lastFrame } = render(wrap(<AuthWarningBanner payload={payload} />))
    const frame = lastFrame() ?? ''
    const compact = frame.replace(/\s+/g, ' ')
    // FR-030: korea_tier MUST be present even for failure
    expect(compact).toContain(payload.korea_tier)
    expect(compact).toContain(payload.error_code)
    expect(compact).toContain(payload.message)
    // Remediation text may wrap; check a distinguishing prefix
    expect(compact).toContain('Renew your GongdongInjeungseo')
    expect(stripSnapshotAnsi(frame)).toMatchSnapshot()
  })
})
