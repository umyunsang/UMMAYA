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
import { TerminalSizeContext } from '@/ink/components/TerminalSizeContext'
import { PointCard } from '@/components/primitive/PointCard'
import { TimeseriesTable } from '@/components/primitive/TimeseriesTable'
import { CollectionList } from '@/components/primitive/CollectionList'
import { DetailView } from '@/components/primitive/DetailView'
import { ErrorBanner } from '@/components/primitive/ErrorBanner'
import { LookupPrimitive } from '@/tools/LookupPrimitive/LookupPrimitive'

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
  return (
    <ThemeProvider>
      <TerminalSizeContext.Provider value={{ columns: 100, rows: 24 }}>
        {element}
      </TerminalSizeContext.Provider>
    </ThemeProvider>
  )
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

describe('LookupPrimitive document result bridge', () => {
  test('renders wrapped document render results through the document review surface', () => {
    const ui = LookupPrimitive.renderToolResultMessage?.(
      {
        ok: true,
        result: {
          tool_id: 'document_render',
          correlation_id: 'corr-render',
          status: 'ok',
          artifact_refs: ['render-corr-render-001'],
          text_summary: 'Rendered 1 page with document diff evidence.',
          diff: {
            diff_id: 'diff-corr-render',
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
          render_artifacts: [],
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
    expect(frame).not.toContain('document_render — 1 result')
  })
})
