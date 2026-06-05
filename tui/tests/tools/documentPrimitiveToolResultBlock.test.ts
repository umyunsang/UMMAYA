// SPDX-License-Identifier: Apache-2.0
// UMMAYA document primitive LLM-observation boundary tests.

import { describe, expect, test } from 'bun:test'
import { DocumentPrimitive } from '../../src/tools/DocumentPrimitive/DocumentPrimitive'

describe('DocumentPrimitive tool_result block', () => {
  test('renders provider inspect attempts with write intent as document edits', () => {
    const message = DocumentPrimitive.renderToolUseMessage(
      {
        correlation_id: 'corr-document-write-intent',
        document: {
          path: '/tmp/seoul-culture-application-plan.docx',
          expected_format: 'docx',
        },
        operation: 'inspect',
        instruction:
          '접수번호 옆 빈칸에 UMMAYA-G011-2026을 넣고 Malgun Gothic 12pt 굵게 저장해줘.',
        destination_path: '/tmp/g011-seoul-culture-application-plan.docx',
      },
      { verbose: false },
    )

    expect(message).toBe('Write document: /tmp/seoul-culture-application-plan.docx')
  })

  test('uses observable display operation when query repaired a provider inspect tool_use', () => {
    const message = DocumentPrimitive.renderToolUseMessage(
      {
        correlation_id: 'corr-document-observable-write',
        document: {
          path: '/tmp/seoul-culture-application-plan.docx',
          expected_format: 'docx',
        },
        operation: 'inspect',
        instruction: '접수번호 위치를 확인합니다.',
        __ummaya_display_operation: 'fill',
      },
      { verbose: false },
    )

    expect(message).toBe('Write document: /tmp/seoul-culture-application-plan.docx')
  })

  test('uses display labels instead of native document paths for model-visible diff lines', () => {
    const block = DocumentPrimitive.mapToolResultToToolResultBlockParam(
      {
        ok: true,
        result: {
          tool_id: 'document',
          correlation_id: 'corr-document-label',
          status: 'ok',
          text_summary: 'Document edit completed.',
          diff: {
            source_artifact_id: 'source-001',
            derivative_artifact_id: 'derivative-001',
            changes: [
              {
                change_id: 'change-001',
                operation_id: 'operation-001',
                change_type: 'table_cell',
                target_path: 'Contents/section0.xml#table[1]/r4c2',
                display_label: '접수번호',
                before_value: '',
                after_value: 'UMMAYA-2026-0007',
              },
            ],
          },
        },
      },
      'toolu-document-label',
    )

    const parsed = JSON.parse(block.content)
    const [change] = parsed.result.diff.changes

    expect(change.target_path).toBe('접수번호')
    expect(change.display_label).toBe('접수번호')
    expect(JSON.stringify(parsed)).not.toContain('Contents/section0.xml')
  })
})
