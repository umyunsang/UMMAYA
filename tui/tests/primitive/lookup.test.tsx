/**
 * Snapshot tests for find primitive renderers.
 * Each renderer is exercised against its corresponding fixture JSON.
 * Uses ink-testing-library for output capture.
 * FR-034, FR-035.
 */
import { describe, test, expect } from 'bun:test'
import React from 'react'
import { render } from 'ink-testing-library'
import { ThemeProvider } from '@/theme/provider'
import { PointCard } from '@/components/primitive/PointCard'
import { TimeseriesTable } from '@/components/primitive/TimeseriesTable'
import { CollectionList } from '@/components/primitive/CollectionList'
import { DetailView } from '@/components/primitive/DetailView'
import { ErrorBanner } from '@/components/primitive/ErrorBanner'

import pointCardFixture from '../fixtures/lookup/point-card.json'
import timeseriesFixture from '../fixtures/lookup/timeseries-table.json'
import collectionFixture from '../fixtures/lookup/collection-list.json'
import detailFixture from '../fixtures/lookup/detail-view.json'
import errorFixture from '../fixtures/lookup/error-banner.json'

import type {
  LookupPointPayload,
  LookupTimeseriesPayload,
  LookupCollectionPayload,
  LookupDetailPayload,
  LookupErrorPayload,
} from '@/components/primitive/types'

function wrap(element: React.ReactElement): React.ReactElement {
  return <ThemeProvider>{element}</ThemeProvider>
}

describe('PointCard', () => {
  test('renders title, subtitle, and fields', () => {
    const payload = pointCardFixture.envelope as LookupPointPayload
    const { lastFrame } = render(wrap(<PointCard payload={payload} />))
    const frame = lastFrame() ?? ''
    expect(frame).toContain(payload.title)
    expect(frame).toContain(payload.subtitle ?? '')
    expect(frame).toContain(payload.fields[0]?.label ?? '')
    expect(frame).toMatchSnapshot()
  })
})

describe('TimeseriesTable', () => {
  test('renders header and data rows', () => {
    const payload = timeseriesFixture.envelope as LookupTimeseriesPayload
    const { lastFrame } = render(wrap(<TimeseriesTable payload={payload} />))
    const frame = lastFrame() ?? ''
    expect(frame).toContain('Timestamp')
    expect(frame).toContain(payload.unit ?? '')
    expect(frame).toContain(payload.rows[0]?.ts ?? '')
    expect(frame).toMatchSnapshot()
  })
})

describe('CollectionList', () => {
  test('renders indexed items with metadata', () => {
    const payload = collectionFixture.envelope as LookupCollectionPayload
    const { lastFrame } = render(wrap(<CollectionList payload={payload} />))
    const frame = lastFrame() ?? ''
    expect(frame).toContain(payload.items[0]?.title ?? '')
    expect(frame).toMatchSnapshot()
  })
})

describe('DetailView', () => {
  test('renders all key/value pairs', () => {
    const payload = detailFixture.envelope as LookupDetailPayload
    const { lastFrame } = render(wrap(<DetailView payload={payload} />))
    const frame = lastFrame() ?? ''
    expect(frame).toContain(payload.fields[0]?.label ?? '')
    expect(frame).toContain(payload.fields[0]?.value ?? '')
    expect(frame).toMatchSnapshot()
  })
})

describe('ErrorBanner (lookup)', () => {
  test('renders error title, description, and retry hint', () => {
    const payload = errorFixture.envelope as LookupErrorPayload
    const { lastFrame } = render(wrap(<ErrorBanner payload={payload} />))
    const frame = lastFrame() ?? ''
    expect(frame).toContain(payload.title)
    expect(frame).toContain(payload.description)
    expect(frame).toContain(payload.retry_hint ?? '')
    expect(frame).toMatchSnapshot()
  })
})
