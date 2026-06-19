import { describe, expect, test } from 'bun:test'
import { render } from 'ink-testing-library'
import { DocumentToolResultCard, PrimitiveDispatcher } from '@/components/primitive'
import { stringWidth } from '@/ink/stringWidth'
import {
  assertNoBrowserViewer,
  assertNoImageEscapes,
  assertNoRevdiffStatus,
  assertNoRoundedCardFrame,
  wrap,
  wrapNarrow,
} from './dispatcher.helpers.js'

describe('PrimitiveDispatcher — document harness', () => {
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
    const frame = render(wrap(<PrimitiveDispatcher payload={payload} />)).lastFrame() ?? ''
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

  test('renders a document mutation as an inline structural field diff', () => {
    const payload = documentPayload('document_apply_fill', 'corr-doc-fill')
    const frame = render(wrap(<PrimitiveDispatcher payload={payload} />)).lastFrame() ?? ''
    expect(frame).toContain('Changed 1 field')
    expect(frame).not.toContain('Document OK')
    expect(frame).not.toContain('document_apply_fill')
    expect(frame).toContain('field[applicant_name]')
    expect(frame).toContain('Kim')
    assertNoRevdiffStatus(frame)
    assertNoRoundedCardFrame(frame)
    assertNoBrowserViewer(frame)
    assertNoImageEscapes(frame)
  })

  test('renders document_render changes inline without opening a browser viewer', () => {
    const payload = documentPayload('document_render', 'corr-doc-render-ok')
    const frame = render(wrap(<PrimitiveDispatcher payload={payload} />)).lastFrame() ?? ''
    expect(frame).toContain('Changed 1 field')
    expect(frame).not.toContain('Document OK')
    expect(frame).not.toContain('document_render')
    expect(frame).toContain('Kim')
    assertNoRoundedCardFrame(frame)
    assertNoBrowserViewer(frame)
    assertNoImageEscapes(frame)
  })

  test('renders saved export paths only when saved_exports is present', () => {
    const basePayload = documentPayload('document', 'corr-doc-style-save')
    const withoutSave = render(wrap(<PrimitiveDispatcher payload={basePayload} />))
    expect(withoutSave.lastFrame() ?? '').not.toContain('Saved:')
    const withSave = render(wrap(<PrimitiveDispatcher payload={{
      ...basePayload,
      saved_exports: [{ local_path: '/tmp/ummaya/tui-exports/application.docx', sha256: 'b'.repeat(64) }],
    }} />))
    const frame = withSave.lastFrame() ?? ''
    expect(frame).toContain('Saved: /tmp/ummaya/tui-exports/application.docx')
    expect(frame).not.toContain('bbbbbbbb')
  })

  test('caps changes in compact mode and reveals all when expanded', () => {
    const changes = Array.from({ length: 10 }, (_, index) => ({
      change_id: `change-${index}`,
      operation_id: `op-${index}`,
      change_type: 'field',
      target_path: `필드_${index}`,
      before_value: null,
      after_value: `값_${index}`,
    }))
    const payload = { ...documentPayload('document_apply_fill', 'corr-doc-many'), diff: { diff_id: 'diff-many', changes } }
    const compactFrame = render(wrap(<DocumentToolResultCard payload={payload} />)).lastFrame() ?? ''
    expect(compactFrame).toContain('Changed 10 fields')
    expect(compactFrame).toContain('Ctrl+O')
    expect(compactFrame).not.toContain('값_9')
    const expandedFrame = render(wrap(<DocumentToolResultCard payload={payload} expanded />)).lastFrame() ?? ''
    expect(expandedFrame).toContain('값_9')
    expect(expandedFrame).not.toContain('Ctrl+O')
  })

  test('renders a render with no changes as a non-card summary surface', () => {
    const payload = {
      tool_id: 'document_render',
      correlation_id: 'corr-doc-nochange',
      status: 'ok',
      text_summary: '변경 없이 문서를 렌더링했습니다.',
    }
    const frame = render(wrap(<PrimitiveDispatcher payload={payload} />)).lastFrame() ?? ''
    expect(frame).toContain('Document OK')
    expect(frame).toContain('변경 없이 문서를 렌더링했습니다.')
    assertNoRoundedCardFrame(frame)
  })

  test('keeps document diff surfaces within terminal width at narrow columns', () => {
    const columns = 40
    const frame = render(wrapNarrow(<PrimitiveDispatcher payload={documentPayload('document_apply_fill', 'corr-doc-narrow')} />, columns)).lastFrame() ?? ''
    for (const line of frame.split('\n')) {
      expect(stringWidth(line)).toBeLessThanOrEqual(columns)
    }
  })
})

function documentPayload(toolId: string, correlationId: string): Record<string, unknown> {
  return {
    tool_id: toolId,
    correlation_id: correlationId,
    status: 'ok',
    text_summary: 'Applied 1 document patch operation through flow-docx-engine.',
    diff: {
      diff_id: `diff-${correlationId}`,
      changes: [{
        change_id: 'change-001',
        operation_id: 'fill-applicant-name',
        change_type: 'field',
        target_path: '/word/document.xml/field[applicant_name]',
        before_value: null,
        after_value: 'Kim',
      }],
    },
  }
}
