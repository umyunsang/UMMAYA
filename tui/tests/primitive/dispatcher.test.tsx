/**
 * Snapshot tests for PrimitiveDispatcher exhaustive dispatch.
 *
 * Dispatches each fixture through <PrimitiveDispatcher> and asserts that the
 * correct child renderer appeared in the rendered output.
 *
 * Also tests the UnrecognizedPayload fallback for unknown kinds.
 *
 * FR-033, FR-034, FR-035.
 */
import { describe, test, expect } from 'bun:test'
import React from 'react'
import { render } from 'ink-testing-library'
import { ThemeProvider } from '@/theme/provider'
import { PrimitiveDispatcher } from '@/components/primitive'

import pointCardFixture from '../fixtures/lookup/point-card.json'
import timeseriesFixture from '../fixtures/lookup/timeseries-table.json'
import collectionFixture from '../fixtures/lookup/collection-list.json'
import detailFixture from '../fixtures/lookup/detail-view.json'
import lookupErrorFixture from '../fixtures/lookup/error-banner.json'

import coordFixture from '../fixtures/resolve_location/coord-pill.json'
import admFixture from '../fixtures/resolve_location/adm-code-badge.json'
import addressFixture from '../fixtures/resolve_location/address-block.json'
import poiFixture from '../fixtures/resolve_location/poi-marker.json'

import receiptFixture from '../fixtures/submit/submit-receipt.json'
import submitErrorFixture from '../fixtures/submit/submit-error.json'

import authCardFixture from '../fixtures/verify/auth-context-card.json'
import authWarningFixture from '../fixtures/verify/auth-warning-banner.json'

function wrap(element: React.ReactElement): React.ReactElement {
  return <ThemeProvider>{element}</ThemeProvider>
}

// ---------------------------------------------------------------------------
// Lookup dispatches
// ---------------------------------------------------------------------------

describe('PrimitiveDispatcher — lookup', () => {
  test('dispatches point subtype to PointCard', () => {
    const { lastFrame } = render(wrap(<PrimitiveDispatcher payload={pointCardFixture.envelope} />))
    const frame = lastFrame() ?? ''
    expect(frame).toContain('Gangnam-gu Intersection Hazard Zone')
    expect(frame).toMatchSnapshot()
  })

  test('dispatches timeseries subtype to TimeseriesTable', () => {
    const { lastFrame } = render(wrap(<PrimitiveDispatcher payload={timeseriesFixture.envelope} />))
    const frame = lastFrame() ?? ''
    expect(frame).toContain('Timestamp')
    expect(frame).toMatchSnapshot()
  })

  test('dispatches collection subtype to CollectionList', () => {
    const { lastFrame } = render(wrap(<PrimitiveDispatcher payload={collectionFixture.envelope} />))
    const frame = lastFrame() ?? ''
    expect(frame).toContain('Seoul National University Hospital')
    expect(frame).toMatchSnapshot()
  })

  test('dispatches detail subtype to DetailView', () => {
    const { lastFrame } = render(wrap(<PrimitiveDispatcher payload={detailFixture.envelope} />))
    const frame = lastFrame() ?? ''
    expect(frame).toContain('Hospital Name')
    expect(frame).toMatchSnapshot()
  })

  test('dispatches error subtype to ErrorBanner', () => {
    const { lastFrame } = render(wrap(<PrimitiveDispatcher payload={lookupErrorFixture.envelope} />))
    const frame = lastFrame() ?? ''
    expect(frame).toContain('Search Failed')
    expect(frame).toMatchSnapshot()
  })
})

// ---------------------------------------------------------------------------
// Resolve location dispatches
// ---------------------------------------------------------------------------

describe('PrimitiveDispatcher — resolve_location', () => {
  test('dispatches coords slot to CoordPill', () => {
    const { lastFrame } = render(wrap(<PrimitiveDispatcher payload={coordFixture.envelope} />))
    const frame = lastFrame() ?? ''
    expect(frame).toContain('[GPS]')
    expect(frame).toMatchSnapshot()
  })

  test('dispatches adm_cd slot to AdmCodeBadge', () => {
    const { lastFrame } = render(wrap(<PrimitiveDispatcher payload={admFixture.envelope} />))
    const frame = lastFrame() ?? ''
    expect(frame).toContain('[ADM]')
    expect(frame).toMatchSnapshot()
  })

  test('dispatches address slot to AddressBlock', () => {
    const { lastFrame } = render(wrap(<PrimitiveDispatcher payload={addressFixture.envelope} />))
    const frame = lastFrame() ?? ''
    expect(frame).toContain('[Address]')
    expect(frame).toMatchSnapshot()
  })

  test('dispatches poi slot to POIMarker', () => {
    const { lastFrame } = render(wrap(<PrimitiveDispatcher payload={poiFixture.envelope} />))
    const frame = lastFrame() ?? ''
    expect(frame).toContain('강남역')
    expect(frame).toMatchSnapshot()
  })
})

// ---------------------------------------------------------------------------
// Submit dispatches
// ---------------------------------------------------------------------------

describe('PrimitiveDispatcher — submit', () => {
  test('dispatches ok=true to SubmitReceipt', () => {
    const { lastFrame } = render(wrap(<PrimitiveDispatcher payload={receiptFixture.envelope} />))
    const frame = lastFrame() ?? ''
    expect(frame).toContain('MWON-2026-0419-00001234')
    expect(frame).toMatchSnapshot()
  })

  test('dispatches ok=false to SubmitErrorBanner', () => {
    const { lastFrame } = render(wrap(<PrimitiveDispatcher payload={submitErrorFixture.envelope} />))
    const frame = lastFrame() ?? ''
    expect(frame).toContain('AUTH_REQUIRED')
    expect(frame).toMatchSnapshot()
  })
})

// ---------------------------------------------------------------------------
// Verify dispatches
// ---------------------------------------------------------------------------

describe('PrimitiveDispatcher — verify', () => {
  test('dispatches ok=true to AuthContextCard', () => {
    const { lastFrame } = render(wrap(<PrimitiveDispatcher payload={authCardFixture.envelope} />))
    const frame = lastFrame() ?? ''
    expect(frame).toContain('Verified')
    expect(frame).toMatchSnapshot()
  })

  test('dispatches ok=false to AuthWarningBanner', () => {
    const { lastFrame } = render(wrap(<PrimitiveDispatcher payload={authWarningFixture.envelope} />))
    const frame = lastFrame() ?? ''
    expect(frame).toContain('CERT_EXPIRED')
    expect(frame).toMatchSnapshot()
  })
})

// ---------------------------------------------------------------------------
// UnrecognizedPayload fallback (FR-033)
// ---------------------------------------------------------------------------

describe('PrimitiveDispatcher — unknown kind', () => {
  test('renders UnrecognizedPayload for unknown kind', () => {
    const unknownPayload = { kind: 'telepath', data: 'something' }
    const { lastFrame } = render(wrap(<PrimitiveDispatcher payload={unknownPayload} />))
    const frame = lastFrame() ?? ''
    expect(frame).toContain('Unrecognized tool result')
    expect(frame).toContain('telepath')
    expect(frame).toMatchSnapshot()
  })

  test('renders UnrecognizedPayload for missing kind', () => {
    const noKindPayload = { data: 'no kind here' }
    const { lastFrame } = render(wrap(<PrimitiveDispatcher payload={noKindPayload} />))
    const frame = lastFrame() ?? ''
    expect(frame).toContain('Unrecognized tool result')
    expect(frame).toMatchSnapshot()
  })
})
