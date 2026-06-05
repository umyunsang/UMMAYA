// SPDX-License-Identifier: Apache-2.0
// UMMAYA — migration-boundary adapter test.
//
// documentChangeToPatch routes document field-level changes INTO the
// already-ported Claude Code diff pipeline (StructuredPatchHunk → StructuredDiff).
// Deep-research-migration note: specs/2802-public-doc-harness/
// deep-research-migration-document-render.md (selected approach D).

import { describe, expect, it } from 'bun:test'
import { documentChangeToPatch } from '../../src/tools/_shared/documentChangeToPatch'
import type { DocumentDiffPayload } from '../../src/components/primitive/types'

function diffOf(
  changes: DocumentDiffPayload['changes'],
  extra: Partial<DocumentDiffPayload> = {},
): DocumentDiffPayload {
  return {
    source_artifact_id: 'working-001',
    derivative_artifact_id: 'derivative-001',
    changes,
    ...extra,
  }
}

describe('documentChangeToPatch', () => {
  it('renders a blank→value fill as a removed/added diff line for the field', () => {
    const result = documentChangeToPatch(
      diffOf([
        {
          change_id: 'c1',
          operation_id: 'op1',
          change_type: 'field',
          target_path: '/hwpx/text[12]',
          before_value: '',
          after_value: '홍길동',
        },
      ]),
      { documentName: '주민등록등본.hwpx' },
    )

    expect(result.filePath).toBe('주민등록등본.hwpx')
    expect(result.changeCount).toBe(1)
    expect(result.truncated).toBe(false)
    expect(result.hunks.length).toBeGreaterThan(0)

    const lines = result.hunks.flatMap((hunk) => hunk.lines)
    // The after value must appear on an added (+) line.
    expect(lines.some((line) => line.startsWith('+') && line.includes('홍길동'))).toBe(true)
    // The field label (humanized target_path) must be visible.
    expect(lines.some((line) => line.includes('text[12]'))).toBe(true)
  })

  it('keeps all changed fields together and collapses newlines in values', () => {
    const result = documentChangeToPatch(
      diffOf([
        {
          change_id: 'c1',
          operation_id: 'op1',
          change_type: 'field',
          target_path: '성명',
          before_value: null,
          after_value: '홍길동',
        },
        {
          change_id: 'c2',
          operation_id: 'op2',
          change_type: 'table_cell',
          target_path: '주소',
          before_value: '서울',
          after_value: '서울특별시\n종로구',
        },
      ]),
    )

    expect(result.changeCount).toBe(2)
    const lines = result.hunks.flatMap((hunk) => hunk.lines)
    // Multi-line value is collapsed to a single visible line (no raw newline).
    expect(lines.some((line) => line.includes('서울특별시') && line.includes('종로구'))).toBe(true)
    expect(lines.every((line) => !line.includes('\n'))).toBe(true)
  })

  it('uses backend display labels before native document paths', () => {
    const result = documentChangeToPatch(
      diffOf([
        {
          change_id: 'c1',
          operation_id: 'op1',
          change_type: 'table_cell',
          target_path: 'Contents/section0.xml#table[1]/r4c2',
          display_label: '접수번호',
          before_value: '',
          after_value: 'UMMAYA-2026-0003',
        },
      ]),
    )

    const lines = result.hunks.flatMap((hunk) => hunk.lines)
    expect(lines.some((line) => line.includes('접수번호'))).toBe(true)
    expect(lines.some((line) => line.includes('Contents/section0.xml'))).toBe(false)
  })

  it('filters no-op changes so the TUI shows only actual document changes', () => {
    const result = documentChangeToPatch(
      diffOf([
        {
          change_id: 'c1',
          operation_id: 'op1',
          change_type: 'field',
          target_path: '/hwpx/text[16]',
          before_value: '1705817 엄윤상',
          after_value: '1705817 엄윤상',
        },
        {
          change_id: 'c2',
          operation_id: 'op2',
          change_type: 'field',
          target_path: '/hwpx/text[18]',
          before_value: '진행 중임.',
          after_value: '진행 중입니다.',
        },
      ]),
    )

    expect(result.changeCount).toBe(1)
    expect(result.renderedChangeCount).toBe(1)
    const lines = result.hunks.flatMap((hunk) => hunk.lines)
    expect(lines.some((line) => line.includes('1705817 엄윤상'))).toBe(false)
    expect(lines.some((line) => line.startsWith('-') && line.includes('진행 중임.'))).toBe(true)
    expect(lines.some((line) => line.startsWith('+') && line.includes('진행 중입니다.'))).toBe(true)
  })

  it('reports truncation when change count exceeds the inline cap', () => {
    const many = Array.from({ length: 30 }, (_, index) => ({
      change_id: `c${index}`,
      operation_id: `op${index}`,
      change_type: 'field' as const,
      target_path: `field_${index}`,
      before_value: '',
      after_value: `value_${index}`,
    }))

    const result = documentChangeToPatch(diffOf(many), { maxChanges: 10 })

    expect(result.changeCount).toBe(30)
    expect(result.renderedChangeCount).toBe(10)
    expect(result.truncated).toBe(true)
  })

  it('returns an empty patch with no changes (no crash on empty diff)', () => {
    const result = documentChangeToPatch(diffOf([]))
    expect(result.changeCount).toBe(0)
    expect(result.hunks).toEqual([])
    expect(result.truncated).toBe(false)
  })
})
