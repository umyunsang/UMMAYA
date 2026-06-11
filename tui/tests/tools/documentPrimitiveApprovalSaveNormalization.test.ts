// SPDX-License-Identifier: Apache-2.0

import { describe, expect, test } from 'bun:test'
import { normalizeDocumentPrimitiveInputForDispatch } from '../../src/tools/DocumentPrimitive/DocumentPrimitive'
import { normalizeDocumentMutationPayloadsForDispatch } from '../../src/tools/DocumentPrimitive/documentPatchNormalization'

describe('DocumentPrimitive approval-save normalization', () => {
  test('keeps draft-preview protected-slot wording read-only before approval', () => {
    const args = normalizeDocumentPrimitiveInputForDispatch(
      {
        correlation_id: 'corr-document-task2-pin',
        document: {
          path: '/tmp/seoul-culture-application-plan.docx',
          expected_format: 'docx',
        },
        operation: 'extract',
        instruction: '문서의 빈칸과 문항 구조를 확인하고 초안을 준비합니다.',
      },
      '개인정보, 연락처, 동의, 서명은 근거가 없으니 작성하지 마. 이 근거만 사용해서 초안을 먼저 보여줘. 아직 문서에는 쓰지 마.',
    )

    expect(args.operation).toBe('extract')
    expect(args.destination_path).toBeUndefined()
  })

  test('keeps approved derivative save mutable when protected fields are excluded', () => {
    const args = normalizeDocumentPrimitiveInputForDispatch(
      {
        correlation_id: 'corr-document-task2-approved-save',
        document: {
          path: '/tmp/seoul-culture-application-plan.docx',
          expected_format: 'docx',
        },
        operation: 'extract',
        instruction: '승인된 근거만 사용해서 검토용 복사본을 저장합니다.',
        destination_path: '/tmp/ummaya-goal-form-public.docx',
      },
      '승인해. 원본은 건드리지 말고 검토용 복사본을 /tmp/ummaya-goal-form-public.docx 로 저장해줘. 기업 및 브랜드명은 "UMMAYA 문서작성 안전성 검증"만 넣어. 개인정보, 연락처, 동의, 서명은 작성하지 마.',
    )

    expect(args.operation).toBe('fill')
    expect(args.destination_path).toBe('/tmp/ummaya-goal-form-public.docx')
    expect(String(args.instruction)).toContain('Original user request:')
  })

  test('derives approved derivative save destination when the provider omits it', () => {
    const args = normalizeDocumentPrimitiveInputForDispatch(
      {
        correlation_id: 'corr-document-task2-approved-save-omitted-destination',
        document: {
          path: '/tmp/seoul-culture-application-plan.docx',
          expected_format: 'docx',
        },
        operation: 'save',
        instruction:
          '검토용 복사본을 /tmp/ummaya-goal-form-public.docx 에 저장하세요. 원본 파일은 수정하지 마세요.',
      },
      '승인해. 원본은 건드리지 말고 검토용 복사본을 /tmp/ummaya-goal-form-public.docx 로 저장해줘. 기업 및 브랜드명은 "UMMAYA 문서작성 안전성 검증"만 넣어.',
    )

    expect(args.operation).toBe('save')
    expect(args.destination_path).toBe('/tmp/ummaya-goal-form-public.docx')
    expect(String(args.instruction)).toContain('Original user request:')
  })

  test('normalizes provider patch content aliases before dispatch', () => {
    const args = normalizeDocumentPrimitiveInputForDispatch(
      {
        correlation_id: 'corr-document-task3-approved-draft-patches',
        document: {
          path: '/tmp/self-introduction-form.docx',
          expected_format: 'docx',
        },
        operation: 'fill',
        instruction: '승인된 자기소개서 초안을 각 문항에 반영합니다.',
        patches: [
          {
            target_path: 'engine://python-docx/self-introduction-form.docx/table/1/r1c2',
            content: '승인된 지원동기 초안입니다.',
          },
        ],
        destination_path: '/tmp/self-introduction-form-derivative.docx',
      },
      '초안 승인해. 원본은 건드리지 말고 파생 문서로 저장해줘.',
    )

    expect(args.patches).toEqual([
      {
        target_path: 'engine://python-docx/self-introduction-form.docx/table/1/r1c2',
        value: '승인된 지원동기 초안입니다.',
      },
    ])
  })

  test('adds approved draft token fields for approved narrative patches', () => {
    const args = normalizeDocumentPrimitiveInputForDispatch(
      {
        correlation_id: 'corr-document-task3-approved-draft-token',
        document: {
          path: '/tmp/self-introduction-form.docx',
          expected_format: 'docx',
        },
        operation: 'save',
        instruction: '승인된 자기소개서 초안을 각 문항에 반영합니다.',
        patches: [
          {
            target_path: 'engine://python-docx/self-introduction-form.docx/table/1/r1c2',
            value: '승인된 지원동기 초안입니다.',
          },
          {
            target_path: 'engine://python-docx/self-introduction-form.docx/table/1/r2c2',
            value: '승인된 성장과정 초안입니다.',
          },
        ],
        styles: [{}, {}],
        destination_path: '/tmp/self-introduction-form-derivative.docx',
      },
      '초안 승인해. 원본은 건드리지 말고 파생 문서로 저장해줘.',
    )

    expect(String(args.approved_draft_id)).toMatch(/^draft-[a-f0-9]{24}$/)
    expect(String(args.approved_draft_sha256)).toMatch(/^[a-f0-9]{64}$/)
    expect(args.styles).toBeUndefined()
  })

  test('does not add approved draft tokens when the user rejects a narrative draft', () => {
    const args = normalizeDocumentPrimitiveInputForDispatch(
      {
        correlation_id: 'corr-document-task3-rejected-draft-token',
        document: {
          path: '/tmp/self-introduction-form.docx',
          expected_format: 'docx',
        },
        operation: 'save',
        instruction: '자기소개서 초안을 각 문항에 반영합니다.',
        patches: [
          {
            target_path: 'engine://python-docx/self-introduction-form.docx/table/1/r1c2',
            value: '근거 없는 지원동기 초안입니다.',
          },
          {
            target_path: 'engine://python-docx/self-introduction-form.docx/table/1/r2c2',
            value: '근거 없는 성장과정 초안입니다.',
          },
        ],
        destination_path: '/tmp/self-introduction-form-derivative.docx',
      },
      '방금 초안은 승인하지 않아. 내가 제공하지 않은 사실이 들어갔으니 아직 문서에는 쓰거나 저장하지 마.',
    )

    expect(args.approved_draft_id).toBeUndefined()
    expect(args.approved_draft_sha256).toBeUndefined()
  })

  test('does not mint approved draft tokens from negated Korean approval text', () => {
    const args = normalizeDocumentMutationPayloadsForDispatch(
      {
        patches: [
          {
            target_path: 'engine://python-docx/self-introduction-form.docx/table/1/r1c2',
            value: '근거 없는 지원동기 초안입니다.',
          },
        ],
      },
      '방금 초안은 승인하지 않아.',
    )

    expect(args.approved_draft_id).toBeUndefined()
    expect(args.approved_draft_sha256).toBeUndefined()
  })

  test('does not mint approved draft tokens from Korean rejection approval words', () => {
    const negatedTexts = [
      '방금 초안은 불승인입니다. 문서에는 쓰지 마.',
      '방금 초안은 미승인 상태야.',
      '이 초안은 승인 거절이야.',
      '이 초안은 승인 반려해.',
      '이 초안은 승인 보류야.',
      '아까 승인은 취소해.',
    ]
    const mintedTexts = negatedTexts.filter(userText => {
      const args = normalizeDocumentMutationPayloadsForDispatch(
        {
          patches: [
            {
              target_path: 'engine://python-docx/self-introduction-form.docx/table/1/r1c2',
              value: '근거 없는 지원동기 초안입니다.',
            },
          ],
        },
        userText,
      )
      return args.approved_draft_id !== undefined ||
        args.approved_draft_sha256 !== undefined
    })

    expect(mintedTexts).toEqual([])
  })

  test('adds approved draft token fields from affirmative English approval text', () => {
    const args = normalizeDocumentMutationPayloadsForDispatch(
      {
        patches: [
          {
            target_path: 'engine://python-docx/self-introduction-form.docx/table/1/r1c2',
            value: 'Approved motivation draft.',
          },
        ],
      },
      'I approve this draft.',
    )

    expect(String(args.approved_draft_id)).toMatch(/^draft-[a-f0-9]{24}$/)
    expect(String(args.approved_draft_sha256)).toMatch(/^[a-f0-9]{64}$/)
  })

  test('does not mint approved draft tokens from negated English approval text', () => {
    const negatedTexts = [
      'I do not approve this draft.',
      "I don't approve this draft.",
      'This draft is not approved.',
      'I reject this draft.',
      'I disapprove this draft.',
      'This draft is unapproved.',
    ]
    const mintedTexts = negatedTexts.filter(userText => {
      const args = normalizeDocumentMutationPayloadsForDispatch(
        {
          patches: [
            {
              target_path: 'engine://python-docx/self-introduction-form.docx/table/1/r1c2',
              value: 'Unsupported motivation draft.',
            },
          ],
        },
        userText,
      )
      return args.approved_draft_id !== undefined ||
        args.approved_draft_sha256 !== undefined
    })

    expect(mintedTexts).toEqual([])
  })

})
