import { describe, expect, test } from 'bun:test'
import { render } from 'ink-testing-library'
import { PrimitiveDispatcher } from '@/components/primitive'
import { stripSnapshotAnsi } from './snapshotFrame.js'
import { wrap } from './dispatcher.helpers.js'
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

function assertFrame(payload: unknown, expected: string): void {
  const { lastFrame } = render(wrap(<PrimitiveDispatcher payload={payload} />))
  const frame = lastFrame() ?? ''
  expect(frame).toContain(expected)
  expect(stripSnapshotAnsi(frame)).toMatchSnapshot()
}

describe('PrimitiveDispatcher — lookup', () => {
  test('dispatches point subtype to PointCard', () => {
    assertFrame(pointCardFixture.envelope, 'Gangnam-gu Intersection Hazard Zone')
  })

  test('dispatches timeseries subtype to TimeseriesTable', () => {
    assertFrame(timeseriesFixture.envelope, 'Timestamp')
  })

  test('dispatches collection subtype to CollectionList', () => {
    assertFrame(collectionFixture.envelope, 'Seoul National University Hospital')
  })

  test('dispatches detail subtype to DetailView', () => {
    assertFrame(detailFixture.envelope, 'Hospital Name')
  })

  test('dispatches error subtype to ErrorBanner', () => {
    assertFrame(lookupErrorFixture.envelope, 'Search Failed')
  })
})

describe('PrimitiveDispatcher — resolve_location', () => {
  test('dispatches coords slot to CoordPill', () => {
    assertFrame(coordFixture.envelope, '[GPS]')
  })

  test('dispatches adm_cd slot to AdmCodeBadge', () => {
    assertFrame(admFixture.envelope, '[ADM]')
  })

  test('dispatches address slot to AddressBlock', () => {
    assertFrame(addressFixture.envelope, '[Address]')
  })

  test('dispatches poi slot to POIMarker', () => {
    assertFrame(poiFixture.envelope, '강남역')
  })
})

describe('PrimitiveDispatcher — submit', () => {
  test('dispatches ok=true to SubmitReceipt', () => {
    assertFrame(receiptFixture.envelope, 'MWON-2026-0419-00001234')
  })

  test('dispatches ok=false to SubmitErrorBanner', () => {
    assertFrame(submitErrorFixture.envelope, 'AUTH_REQUIRED')
  })
})

describe('PrimitiveDispatcher — verify', () => {
  test('dispatches ok=true to AuthContextCard', () => {
    assertFrame(authCardFixture.envelope, 'Verified')
  })

  test('dispatches ok=false to AuthWarningBanner', () => {
    assertFrame(authWarningFixture.envelope, 'CERT_EXPIRED')
  })
})
