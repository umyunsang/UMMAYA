/**
 * Snapshot tests for resolve_location primitive renderers.
 * Each slot renderer is exercised against its corresponding fixture JSON.
 * Uses ink-testing-library for output capture.
 * FR-034, FR-035.
 */
import { describe, test, expect } from 'bun:test'
import React from 'react'
import { render } from 'ink-testing-library'
import { ThemeProvider } from '@/theme/provider'
import { CoordPill } from '@/components/primitive/CoordPill'
import { AdmCodeBadge } from '@/components/primitive/AdmCodeBadge'
import { AddressBlock } from '@/components/primitive/AddressBlock'
import { POIMarker } from '@/components/primitive/POIMarker'
import { stripSnapshotAnsi } from './snapshotFrame'

import coordFixture from '../fixtures/resolve_location/coord-pill.json'
import admFixture from '../fixtures/resolve_location/adm-code-badge.json'
import addressFixture from '../fixtures/resolve_location/address-block.json'
import poiFixture from '../fixtures/resolve_location/poi-marker.json'

import type { ResolveLocationPayload } from '@/components/primitive/types'

function wrap(element: React.ReactElement): React.ReactElement {
  return <ThemeProvider>{element}</ThemeProvider>
}

describe('CoordPill', () => {
  test('renders lat/lon with degree symbols', () => {
    const payload = coordFixture.envelope as ResolveLocationPayload
    const coords = payload.slots.coords!
    const { lastFrame } = render(wrap(<CoordPill coords={coords} />))
    const frame = lastFrame() ?? ''
    expect(frame).toContain('[GPS]')
    expect(frame).toContain('37.566826')
    expect(frame).toContain('126.978656')
    expect(stripSnapshotAnsi(frame)).toMatchSnapshot()
  })
})

describe('AdmCodeBadge', () => {
  test('renders ADM code and name', () => {
    const payload = admFixture.envelope as ResolveLocationPayload
    const admCode = payload.slots.adm_cd!
    const { lastFrame } = render(wrap(<AdmCodeBadge admCode={admCode} />))
    const frame = lastFrame() ?? ''
    expect(frame).toContain('[ADM]')
    expect(frame).toContain(admCode.code)
    expect(frame).toContain(admCode.name)
    expect(stripSnapshotAnsi(frame)).toMatchSnapshot()
  })
})

describe('AddressBlock', () => {
  test('renders road, parcel, detail, and zip', () => {
    const payload = addressFixture.envelope as ResolveLocationPayload
    const address = payload.slots.address!
    const { lastFrame } = render(wrap(<AddressBlock address={address} />))
    const frame = lastFrame() ?? ''
    expect(frame).toContain('[Address]')
    expect(frame).toContain(address.road ?? '')
    expect(frame).toContain(address.zip ?? '')
    expect(stripSnapshotAnsi(frame)).toMatchSnapshot()
  })
})

describe('POIMarker', () => {
  test('renders POI name, category, and source', () => {
    const payload = poiFixture.envelope as ResolveLocationPayload
    const poi = payload.slots.poi!
    const { lastFrame } = render(wrap(<POIMarker poi={poi} />))
    const frame = lastFrame() ?? ''
    expect(frame).toContain(poi.name)
    expect(frame).toContain(poi.category ?? '')
    expect(stripSnapshotAnsi(frame)).toMatchSnapshot()
  })
})
