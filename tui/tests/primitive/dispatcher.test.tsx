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
import { DocumentToolResultCard, PrimitiveDispatcher } from '@/components/primitive'
import { TerminalSizeContext } from '@/ink/components/TerminalSizeContext'
import { stringWidth } from '@/ink/stringWidth'

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
  return (
    <ThemeProvider>
      <TerminalSizeContext.Provider value={{ columns: 100, rows: 24 }}>
        {element}
      </TerminalSizeContext.Provider>
    </ThemeProvider>
  )
}

function wrapNarrow(element: React.ReactElement, columns: number): React.ReactElement {
  return (
    <ThemeProvider>
      <TerminalSizeContext.Provider value={{ columns, rows: 24 }}>
        {element}
      </TerminalSizeContext.Provider>
    </ThemeProvider>
  )
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
// Document harness dispatches
// ---------------------------------------------------------------------------

describe('PrimitiveDispatcher — document harness', () => {
  // Inline-image escape signatures that must never appear (approach D drops all
  // terminal-graphics / browser-viewer rendering — structural text only).
  const KITTY_ESC = '_G'
  const ITERM_ESC = ']1337;File='
  const SIXEL_ESC = 'Pq'

  function assertNoImageEscapes(frame: string): void {
    expect(frame.includes(KITTY_ESC)).toBe(false)
    expect(frame.includes(ITERM_ESC)).toBe(false)
    expect(frame.includes(SIXEL_ESC)).toBe(false)
  }

  function assertNoBrowserViewer(frame: string): void {
    expect(frame).not.toContain('Document viewer')
    expect(frame).not.toContain('document review opened')
    expect(frame).not.toContain('viewer.html')
    expect(frame).not.toContain('diff rail')
  }

  function assertNoRoundedCardFrame(frame: string): void {
    for (const glyph of ['╭', '╮', '╰', '╯']) {
      expect(frame).not.toContain(glyph)
    }
  }

  function assertNoRevdiffStatus(frame: string): void {
    expect(frame).not.toContain('hunk 1/')
    expect(frame).not.toContain('⊂ compact')
    expect(frame).not.toContain('± word-diff')
  }

  test('renders blocked document results as a concise non-card tool result surface', () => {
    const payload = {
      tool_id: 'document_render',
      correlation_id: 'corr-doc-render',
      status: 'blocked',
      artifact_refs: ['working-corr003'],
      text_summary: 'No render-capable engine is registered for hwpx.',
      blocked_reason: 'unsupported_operation',
      promotion_gate_result: {
        capability: 'render',
        promotion_state: 'blocked',
        hard_gate_failures: ['hwpx_render_engine_unpromoted'],
      },
    }
    const { lastFrame } = render(wrap(<PrimitiveDispatcher payload={payload} />))
    const frame = lastFrame() ?? ''

    expect(frame).toContain('Document blocked')
    expect(frame).toContain('unsupported_operation')
    expect(frame).toContain('No render-capable engine is registered for hwpx.')
    expect(frame).toContain('Gate: render blocked')
    expect(frame).toContain('hwpx_render_engine_unpromoted')
    expect(frame).not.toContain('Submitted')
    expect(frame).not.toContain('Unrecognized tool result')
    assertNoRoundedCardFrame(frame)
    assertNoBrowserViewer(frame)
    assertNoImageEscapes(frame)
  })

  test('renders a document mutation as an inline structural field diff (per-mutation)', () => {
    const payload = {
      tool_id: 'document_apply_fill',
      correlation_id: 'corr-doc-fill',
      status: 'ok',
      artifact_refs: ['working-corr002', 'derivative-corr003'],
      text_summary: 'Applied 1 document patch operation through flow-docx-engine.',
      diff: {
        diff_id: 'diff-1111222233334444',
        source_artifact_id: 'working-corr002',
        derivative_artifact_id: 'derivative-corr003',
        changes: [
          {
            change_id: 'change-001',
            operation_id: 'fill-applicant-name',
            change_type: 'field',
            target_path: '/word/document.xml/field[applicant_name]',
            before_value: null,
            after_value: 'Kim',
          },
        ],
      },
    }
    const { lastFrame } = render(wrap(<PrimitiveDispatcher payload={payload} />))
    const frame = lastFrame() ?? ''

    // CC-style inline diff: a compact change summary plus the diff body.
    expect(frame).toContain('Changed 1 field')
    expect(frame).not.toContain('Document OK')
    expect(frame).not.toContain('document_apply_fill')
    expect(frame).not.toContain('Applied 1 document patch operation through flow-docx-engine.')
    expect(frame).toContain('field[applicant_name]')
    expect(frame).toContain('Kim')
    assertNoRevdiffStatus(frame)
    // The mutation result is shown immediately, without a separate render call.
    assertNoRoundedCardFrame(frame)
    assertNoBrowserViewer(frame)
    assertNoImageEscapes(frame)
  })

  test('renders document_render changes inline without opening a browser viewer', () => {
    const payload = {
      tool_id: 'document_render',
      correlation_id: 'corr-doc-render-ok',
      status: 'ok',
      artifact_refs: ['render-corr-doc-render-001'],
      text_summary: '주민등록등본.hwpx 의 변경을 렌더링했습니다.',
      render_artifacts: [
        {
          render_artifact_id: 'render-corr-doc-render-001',
          render_path: '/tmp/ummaya/renders/render-corr-doc-render-001.svg',
          render_mime_type: 'image/svg+xml',
          page_number: 1,
          engine_id: 'rhwp-node-wasm',
        },
      ],
      diff: {
        diff_id: 'diff-render-aaaa',
        source_artifact_id: 'working-corr-doc-render',
        derivative_artifact_id: 'derivative-corr-doc-render',
        changes: [
          {
            change_id: 'change-001',
            operation_id: 'fill-week',
            change_type: 'field',
            target_path: '근무주차',
            before_value: '12 주차',
            after_value: '13 주차',
          },
        ],
      },
    }
    const { lastFrame } = render(wrap(<PrimitiveDispatcher payload={payload} />))
    const frame = lastFrame() ?? ''

    expect(frame).toContain('Changed 1 field')
    expect(frame).not.toContain('Document OK')
    expect(frame).not.toContain('document_render')
    expect(frame).not.toContain('주민등록등본.hwpx 의 변경을 렌더링했습니다.')
    // Before/after values are both visible inline (structural diff).
    expect(frame).toContain('12 주차')
    expect(frame).toContain('13 주차')
    expect(frame).toContain('근무주차')
    assertNoRevdiffStatus(frame)
    // Render artifacts stay evidence-only — never a browser viewer surface.
    assertNoRoundedCardFrame(frame)
    assertNoBrowserViewer(frame)
    assertNoImageEscapes(frame)
  })

  test('renders saved export paths only when saved_exports is present', () => {
    const basePayload = {
      tool_id: 'document',
      correlation_id: 'corr-doc-style-save',
      status: 'ok',
      text_summary: 'Styled and saved application.docx.',
      diff: {
        diff_id: 'diff-style-save',
        source_artifact_id: 'working-style-save',
        derivative_artifact_id: 'derivative-style-save',
        changes: [
          {
            change_id: 'change-style',
            operation_id: 'style-receipt',
            change_type: 'style',
            target_path: '/word/document.xml/table[1]/cell[2]/style',
            display_label: '접수번호 서식',
            before_value: '맑은 고딕 10pt',
            after_value: 'Malgun Gothic 12pt bold',
          },
        ],
      },
    }

    const withoutSave = render(wrap(<PrimitiveDispatcher payload={basePayload} />))
    const withoutSaveFrame = withoutSave.lastFrame() ?? ''
    expect(withoutSaveFrame).toContain('Changed 1 field')
    expect(withoutSaveFrame).not.toContain('Saved:')
    expect(withoutSaveFrame).not.toContain('/tmp/ummaya/tui-exports/application.docx')

    const withSave = render(wrap(
      <PrimitiveDispatcher
        payload={{
          ...basePayload,
          saved_exports: [
            {
              local_path: '/tmp/ummaya/tui-exports/application.docx',
              sha256: 'b'.repeat(64),
            },
          ],
        }}
      />,
    ))
    const withSaveFrame = withSave.lastFrame() ?? ''
    expect(withSaveFrame).toContain('Changed 1 field')
    expect(withSaveFrame).toContain('Saved: /tmp/ummaya/tui-exports/application.docx')
    expect(withSaveFrame).not.toContain('bbbbbbbb')
  })

  test('caps changes in compact mode and reveals all when expanded', () => {
    const changes = Array.from({ length: 10 }, (_, index) => ({
      change_id: `change-${index}`,
      operation_id: `op-${index}`,
      change_type: 'field' as const,
      target_path: `필드_${index}`,
      before_value: null,
      after_value: `값_${index}`,
    }))
    const payload = {
      tool_id: 'document_apply_fill',
      correlation_id: 'corr-doc-many',
      status: 'ok',
      text_summary: '10건의 변경을 적용했습니다.',
      diff: {
        diff_id: 'diff-many',
        source_artifact_id: 'working-many',
        derivative_artifact_id: 'derivative-many',
        changes,
      },
    }

    const compact = render(wrap(<DocumentToolResultCard payload={payload} />))
    const compactFrame = compact.lastFrame() ?? ''
    expect(compactFrame).toContain('Changed 10 fields')
    expect(compactFrame).toContain('more')
    expect(compactFrame).toContain('Ctrl+O')
    assertNoRevdiffStatus(compactFrame)
    // The last change is hidden in compact mode.
    expect(compactFrame).not.toContain('값_9')
    assertNoRoundedCardFrame(compactFrame)

    const expanded = render(wrap(<DocumentToolResultCard payload={payload} expanded />))
    const expandedFrame = expanded.lastFrame() ?? ''
    // All changes visible when expanded; no truncation affordance.
    expect(expandedFrame).toContain('Changed 10 fields')
    expect(expandedFrame).toContain('값_9')
    expect(expandedFrame).not.toContain('Ctrl+O')
    assertNoRevdiffStatus(expandedFrame)
    assertNoRoundedCardFrame(expandedFrame)
  })

  test('renders a render with no changes as a non-card summary surface without crashing', () => {
    const payload = {
      tool_id: 'document_render',
      correlation_id: 'corr-doc-nochange',
      status: 'ok',
      text_summary: '변경 없이 문서를 렌더링했습니다.',
    }
    const { lastFrame } = render(wrap(<PrimitiveDispatcher payload={payload} />))
    const frame = lastFrame() ?? ''

    expect(frame).toContain('Document OK')
    expect(frame).toContain('변경 없이 문서를 렌더링했습니다.')
    assertNoRoundedCardFrame(frame)
    assertNoBrowserViewer(frame)
    assertNoImageEscapes(frame)
  })

  test('keeps document diff surfaces within terminal width at narrow columns', () => {
    const payload = {
      tool_id: 'document_apply_fill',
      correlation_id: 'corr-doc-narrow',
      status: 'ok',
      text_summary: '좁은 터미널에서도 폭을 넘지 않아야 합니다 — 주민등록등본 성명 칸을 채웠습니다.',
      diff: {
        diff_id: 'diff-narrow',
        source_artifact_id: 'working-narrow',
        derivative_artifact_id: 'derivative-narrow',
        changes: [
          {
            change_id: 'change-001',
            operation_id: 'fill-name',
            change_type: 'field',
            target_path: '성명',
            before_value: null,
            after_value: '홍길동',
          },
        ],
      },
    }
    const columns = 40
    const { lastFrame } = render(wrapNarrow(<PrimitiveDispatcher payload={payload} />, columns))
    const frame = lastFrame() ?? ''
    for (const line of frame.split('\n')) {
      expect(stringWidth(line)).toBeLessThanOrEqual(columns)
    }
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
