// SPDX-License-Identifier: Apache-2.0

import { describe, expect, test } from 'bun:test'
import { normalizeDocumentMutationPayloadsForDispatch } from '../../src/tools/DocumentPrimitive/documentPatchNormalization'

const PATCH_ARGS = {
  patches: [
    {
      target_path: 'engine://python-docx/self-introduction-form.docx/table/1/r1c2',
      value: 'Supported revised motivation draft.',
    },
  ],
} as const

function mintsApprovalToken(userText: string): boolean {
  const args = normalizeDocumentMutationPayloadsForDispatch(PATCH_ARGS, userText)
  return args.approved_draft_id !== undefined &&
    args.approved_draft_sha256 !== undefined
}

describe('DocumentPrimitive mixed approval normalization', () => {
  test('mints approved draft tokens from decisive approval after prior rejection context', () => {
    const approvedTexts = [
      'I do not approve the earlier draft, but I approve this revised draft.',
      'I do not approve the earlier draft and I approve this revised draft.',
      '이전 초안은 승인하지 않았지만 지금 초안은 승인해.',
      'I approve this draft and want the document to include the phrase not approved as an example.',
      'Please include the phrase not approved as an example, and I approve this draft.',
    ]

    expect(approvedTexts.filter(text => !mintsApprovalToken(text))).toEqual([])
  })

  test('does not mint approved draft tokens when the latest contrast rejects the draft', () => {
    const negatedTexts = [
      'I approved the earlier draft, but I do not approve this revised draft.',
      '이전 초안은 승인했지만 지금 초안은 승인하지 않아.',
    ]

    expect(negatedTexts.filter(mintsApprovalToken)).toEqual([])
  })

  test('does not mint approved draft tokens when same-segment current rejection follows stale approval', () => {
    const negatedTexts = [
      'I approved the earlier draft and I do not approve this revised draft.',
      'I approved the earlier draft and I reject this revised draft.',
      'I approve this draft. No.',
      'I approve this draft. I reject it.',
      'I approve this draft and reject it.',
      '초안 승인해. 아니, 거부해.',
      '초안 승인해. 취소해.',
      '이전 초안은 승인했고 지금 초안은 승인하지 않아.',
      'This draft is not yet approved.',
      "This draft isn't approved.",
      "I haven't approved this draft.",
      "I hadn't approved this draft.",
      'I cannot approve this draft.',
      'I am unable to approve this draft.',
      "I won't approve this draft.",
      "I didn't approve this draft.",
      'This draft was never approved.',
      'I do not want to approve this draft.',
      'I do not think this is approved.',
      "I don't want to approve this draft.",
      "I don't think this is approved.",
      "I don't want this approved.",
      'I do not want this approved.',
      "I don't think this should be approved.",
      'I do not think this should be approved.',
      'I refuse to approve this draft.',
      'I decline to approve this draft.',
      'I will not approve this draft.',
      'I am not going to approve this draft.',
      'Do you approve this draft? No.',
      'Approve this draft? No.',
      'This draft should not be approved.',
      'This draft must not be approved.',
      'This draft cannot be approved.',
      "This draft can't be approved.",
      'I am not ready to approve this draft.',
      '이 초안은 승인할 수 없어.',
      '이 초안은 승인 아님.',
      '이 초안은 승인이 없어.',
    ]

    expect(negatedTexts.filter(mintsApprovalToken)).toEqual([])
  })

  test('does not mint approved draft tokens from approval wording requested as document content', () => {
    const contentOnlyTexts = [
      'Please include the sentence I approve this draft in the document, but do not treat that as approval.',
      'Please include I approve this draft as a sentence in the document.',
      'Set the document text to: "I approve this draft."',
      'Write: I approve this draft.',
      'The sentence should be: I approve this draft.',
      '문서에 "이 초안을 승인합니다"라는 문장을 예시로 넣어줘. 이걸 승인으로 처리하지는 마.',
    ]

    expect(contentOnlyTexts.filter(mintsApprovalToken)).toEqual([])
  })

  test('does not mint approved draft tokens from passive approval status wording', () => {
    const ambiguousTexts = [
      'I think this draft is approved.',
      'Please add the approved draft to the document.',
      'Please include the approved draft in the document.',
      '승인된 초안을 문서에 넣어줘.',
      '이 초안은 승인된 상태야.',
    ]

    expect(ambiguousTexts.filter(mintsApprovalToken)).toEqual([])
  })

  test('does not mint approved draft tokens when any patch is outside the approval hash', () => {
    const args = normalizeDocumentMutationPayloadsForDispatch(
      {
        patches: [
          {
            target_path: 'engine://python-docx/self-introduction-form.docx/body',
            value: 'Covered draft.',
          },
          {
            target_path: 'engine://python-docx/self-introduction-form.docx/extra',
            value: 42,
          },
        ],
      },
      'I approve this draft.',
    )

    expect(args.approved_draft_id).toBeUndefined()
    expect(args.approved_draft_sha256).toBeUndefined()
  })

  test('strips caller-supplied approval tokens when latest user text rejects the draft', () => {
    const args = normalizeDocumentMutationPayloadsForDispatch(
      {
        ...PATCH_ARGS,
        approved_draft_id: 'draft-stale',
        approved_draft_sha256: '0'.repeat(64),
      },
      'I do not approve this revised draft.',
    )

    expect(args.approved_draft_id).toBeUndefined()
    expect(args.approved_draft_sha256).toBeUndefined()
  })

  test('strips caller-supplied approval tokens when approval text is unavailable', () => {
    const args = normalizeDocumentMutationPayloadsForDispatch(
      {
        ...PATCH_ARGS,
        approved_draft_id: 'draft-stale',
        approved_draft_sha256: '0'.repeat(64),
      },
      undefined,
    )

    expect(args.approved_draft_id).toBeUndefined()
    expect(args.approved_draft_sha256).toBeUndefined()
  })

  test('recomputes caller-supplied approval tokens from current patches on approval', () => {
    const args = normalizeDocumentMutationPayloadsForDispatch(
      {
        ...PATCH_ARGS,
        approved_draft_id: 'draft-stale',
        approved_draft_sha256: '0'.repeat(64),
      },
      'I approve this revised draft.',
    )

    expect(String(args.approved_draft_id)).toMatch(/^draft-[a-f0-9]{24}$/)
    expect(String(args.approved_draft_id)).not.toBe('draft-stale')
    expect(String(args.approved_draft_sha256)).toMatch(/^[a-f0-9]{64}$/)
    expect(String(args.approved_draft_sha256)).not.toBe('0'.repeat(64))
  })

  test('preserves issued approval tokens for mixed narrative and ordinary string patches', () => {
    const issuedDraftId = 'draft-1234567890abcdef12345678'
    const issuedDraftSha256 = 'f'.repeat(64)
    const args = normalizeDocumentMutationPayloadsForDispatch(
      {
        approved_draft_id: issuedDraftId,
        approved_draft_sha256: issuedDraftSha256,
        patches: [
          {
            target_path: 'engine://python-docx/self-introduction-form.docx/table/1/r1c2',
            value: 'Supported revised motivation draft.',
          },
          {
            target_path: 'engine://python-docx/self-introduction-form.docx/table/1/r3c2',
            value: 'Hong Gil-dong',
          },
        ],
      },
      'I approve this revised draft.',
    )

    expect(args.approved_draft_id).toBe(issuedDraftId)
    expect(args.approved_draft_sha256).toBe(issuedDraftSha256)
  })
})
