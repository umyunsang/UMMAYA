// SPDX-License-Identifier: Apache-2.0

import { describe, expect, test } from 'bun:test'
import React from 'react'
import { render } from 'ink-testing-library'
import { DocumentToolResultCard } from '@/components/primitive'
import { TerminalSizeContext } from '@/ink/components/TerminalSizeContext'
import { ThemeProvider } from '@/theme/provider'
import type { DocumentToolResultPayload } from '@/components/primitive'

type AuthoringQuestion = {
  readonly question_id: string
  readonly target_id: string
  readonly prompt: string
  readonly required: boolean
}

type AuthoringAnswer = {
  readonly answer_id: string
  readonly question_id: string
  readonly response_summary: string
  readonly evidence_refs: readonly string[]
}

type AuthoringDraft = {
  readonly draft_id: string
  readonly target_id: string
  readonly draft_text: string
  readonly draft_sha256: string
}

type AuthoringApproval = {
  readonly approval_id: string
  readonly draft_id: string
  readonly decision: 'approved' | 'edited' | 'leave_blank' | 'cancel'
  readonly draft_sha256: string
  readonly approved_text_sha256?: string
}

type AuthoringReview = {
  readonly state:
    | 'needs_input'
    | 'draft_ready_for_approval'
    | 'approved_for_mutation'
    | 'blocked_missing_evidence'
  readonly target_id: string
  readonly questions: readonly AuthoringQuestion[]
  readonly answers: readonly AuthoringAnswer[]
  readonly draft?: AuthoringDraft
  readonly approval?: AuthoringApproval
}

type RenderComparisonReview = {
  readonly status: 'pass' | 'failed' | 'blocked'
  readonly threshold_status: 'pass' | 'failed' | 'blocked'
  readonly changed_regions: readonly Record<string, unknown>[]
  readonly failure_reason?: string
}

type ReviewPayload = DocumentToolResultPayload & {
  readonly authoring: AuthoringReview
  readonly render_comparison: RenderComparisonReview
}

function wrap(element: React.ReactElement): React.ReactElement {
  return (
    <ThemeProvider>
      <TerminalSizeContext.Provider value={{ columns: 180, rows: 30 }}>
        {element}
      </TerminalSizeContext.Provider>
    </ThemeProvider>
  )
}

describe('DocumentToolResultCard Socratic authoring review', () => {
  test('renders missing questions, collected answers, draft, approval wait, and blocked render comparison', () => {
    const payload: ReviewPayload = {
      tool_id: 'document',
      correlation_id: 'corr-socratic-review',
      status: 'needs_input',
      text_summary: 'Draft is ready for review, but one required answer is still missing.',
      authoring: {
        state: 'draft_ready_for_approval',
        target_id: 'self_intro.motivation',
        questions: [
          {
            question_id: 'question-team-leadership',
            target_id: 'self_intro.motivation',
            prompt: '지원동기를 뒷받침할 구체적인 경험은 무엇인가요?',
            required: true,
          },
          {
            question_id: 'question-result-metric',
            target_id: 'self_intro.motivation',
            prompt: '그 경험에서 확인 가능한 결과나 수치는 무엇인가요?',
            required: true,
          },
        ],
        answers: [
          {
            answer_id: 'answer-team-leadership',
            question_id: 'question-team-leadership',
            response_summary: '공모전에서 팀 리더로 일정과 역할을 조율했습니다.',
            evidence_refs: ['evidence-team-leadership'],
          },
        ],
        draft: {
          draft_id: 'draft-self-intro',
          target_id: 'self_intro.motivation',
          draft_text: '사용자가 제공한 팀 리더 경험을 바탕으로 지원 동기를 작성합니다.',
          draft_sha256: 'a'.repeat(64),
        },
      },
      render_comparison: {
        status: 'blocked',
        threshold_status: 'blocked',
        changed_regions: [],
        failure_reason: 'source-to-derivative render comparison is missing',
      },
    }

    const { lastFrame } = render(wrap(<DocumentToolResultCard payload={payload} />))
    const frame = lastFrame() ?? ''

    expect(frame).toContain('Questions needed')
    expect(frame).toContain('그 경험에서 확인 가능한 결과나 수치는 무엇인가요?')
    expect(frame).toContain('Collected answers')
    expect(frame).toContain('공모전에서 팀 리더로 일정과 역할을 조율했습니다.')
    expect(frame).toContain('Draft preview')
    expect(frame).toContain('사용자가 제공한 팀 리더 경험을 바탕으로 지원 동기를 작성합니다.')
    expect(frame).toContain('Approval: awaiting approval')
    expect(frame).toContain('Render comparison: blocked')
    expect(frame).toContain('source-to-derivative render comparison is missing')
    expect(frame).not.toContain('document_apply')
    expect(frame).not.toContain('question-team-leadership')
    expect(frame).not.toContain('fixture')
  })

  test('keeps approved mutations visible with changed fields and render comparison status', () => {
    const payload: ReviewPayload = {
      tool_id: 'document',
      correlation_id: 'corr-socratic-approved',
      status: 'ok',
      text_summary: 'Approved self-introduction draft was written to the derivative.',
      authoring: {
        state: 'approved_for_mutation',
        target_id: 'self_intro.motivation',
        questions: [
          {
            question_id: 'question-team-leadership',
            target_id: 'self_intro.motivation',
            prompt: '지원동기를 뒷받침할 구체적인 경험은 무엇인가요?',
            required: true,
          },
        ],
        answers: [
          {
            answer_id: 'answer-team-leadership',
            question_id: 'question-team-leadership',
            response_summary: '공모전에서 팀 리더로 일정과 역할을 조율했습니다.',
            evidence_refs: ['evidence-team-leadership'],
          },
        ],
        draft: {
          draft_id: 'draft-self-intro',
          target_id: 'self_intro.motivation',
          draft_text: '사용자가 제공한 팀 리더 경험을 바탕으로 지원 동기를 작성합니다.',
          draft_sha256: 'a'.repeat(64),
        },
        approval: {
          approval_id: 'approval-self-intro',
          draft_id: 'draft-self-intro',
          decision: 'approved',
          draft_sha256: 'a'.repeat(64),
          approved_text_sha256: 'a'.repeat(64),
        },
      },
      render_comparison: {
        status: 'pass',
        threshold_status: 'pass',
        changed_regions: [{ region: 'visible' }],
      },
      diff: {
        diff_id: 'diff-approved',
        source_artifact_id: 'source-approved',
        derivative_artifact_id: 'derivative-approved',
        changes: [
          {
            change_id: 'change-approved',
            operation_id: 'operation-approved',
            change_type: 'field',
            target_path: '/word/document.xml/field[self_intro_motivation]',
            display_label: '지원동기',
            before_value: '',
            after_value: '사용자가 제공한 팀 리더 경험을 바탕으로 지원 동기를 작성합니다.',
          },
        ],
      },
    }

    const { lastFrame } = render(wrap(<DocumentToolResultCard payload={payload} />))
    const frame = lastFrame() ?? ''

    expect(frame).toContain('Changed 1 field')
    expect(frame).toContain('지원동기')
    expect(frame).toContain('Approval: approved')
    expect(frame).toContain('Render comparison: pass')
    expect(frame).toContain('1 changed region')
    expect(frame).not.toContain('document_apply')
    expect(frame).not.toContain('approval-self-intro')
    expect(frame).not.toContain('fixture')
  })
})
