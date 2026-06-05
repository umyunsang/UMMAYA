// SPDX-License-Identifier: Apache-2.0
// UMMAYA document primitive LLM-observation boundary tests.

import { describe, expect, test } from 'bun:test'
import {
  DocumentPrimitive,
  normalizeDocumentPrimitiveInputForDispatch,
} from '../../src/tools/DocumentPrimitive/DocumentPrimitive'

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

  test('keeps explicitly read-only Korean inspection wording out of write display', () => {
    const message = DocumentPrimitive.renderToolUseMessage(
      {
        correlation_id: 'corr-document-read-only-korean',
        document: {
          path: '/tmp/business-registration.hwpx',
          expected_format: 'hwpx',
        },
        operation: 'inspect',
        instruction:
          '수정 없이 열람만 해줘. 양식의 문서 제목과 작성해야 할 항목명만 알려줘.',
      },
      { verbose: false },
    )

    expect(message).toBe('Inspect document: /tmp/business-registration.hwpx')
  })

  test('preserves the original autonomous-fill request for patchless dispatch', () => {
    const args = normalizeDocumentPrimitiveInputForDispatch(
      {
        correlation_id: 'corr-document-autonomous-fill',
        document: {
          path: '/tmp/business-registration.hwpx',
          expected_format: 'hwpx',
        },
        operation: 'extract',
        instruction:
          '국세청 사업자등록신청서의 모든 필드와 내용을 추출해주세요.',
      },
      '공식 국세청 사업자등록신청서 파일을 내용에 맞게 알아서 채워줘. 원본은 건드리지 말고 검토 가능한 복사본으로 만들어줘: /tmp/business-registration.hwpx',
    )

    expect(args.operation).toBe('fill')
    expect(String(args.instruction)).toContain('Original user request:')
    expect(String(args.instruction)).toContain('내용에 맞게 알아서 채워줘')
  })

  test('keeps read-only dispatch read-only even when Korean text contains 수정', () => {
    const args = normalizeDocumentPrimitiveInputForDispatch(
      {
        correlation_id: 'corr-document-readonly-dispatch',
        document: {
          path: '/tmp/business-registration.hwpx',
          expected_format: 'hwpx',
        },
        operation: 'extract',
        instruction:
          '제목과 작성해야 할 항목명만 추출해주세요. 수정 없이 읽기 전용으로 처리해 주세요.',
      },
      '수정 없이 열람만 해줘. 양식의 문서 제목과 작성해야 할 항목명만 알려줘: /tmp/business-registration.hwpx',
    )

    expect(args.operation).toBe('extract')
    expect(String(args.instruction)).toContain('Original user request:')
  })

  test('downgrades model fill calls to inspect when the user explicitly requested read-only', () => {
    const args = normalizeDocumentPrimitiveInputForDispatch(
      {
        correlation_id: 'corr-document-readonly-fill',
        document: {
          path: '/tmp/business-registration.hwp',
          expected_format: 'hwp',
        },
        operation: 'fill',
        instruction:
          '문서 제목과 작성해야 할 항목명만 알려주세요. 수정 없이 열람만 처리해 주세요.',
        destination_path: '/tmp/model-invented-review-copy.hwp',
      },
      '수정 없이 열람만 해줘. 이 공식 국세청 사업자등록신청서 파일의 문서 제목과 작성해야 할 항목명만 알려줘: /tmp/business-registration.hwp',
    )

    expect(args.operation).toBe('inspect')
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
