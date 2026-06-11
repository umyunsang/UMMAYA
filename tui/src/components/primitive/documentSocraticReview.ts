// SPDX-License-Identifier: Apache-2.0

const REVIEW_STATUSES = ['pass', 'failed', 'blocked'] as const
const INTERNAL_TOKEN_PATTERN =
  /\b(?:document_[A-Za-z0-9_]+|[A-Za-z0-9_-]*fixture[A-Za-z0-9_-]*)\b/gu

export type RenderComparisonStatus = (typeof REVIEW_STATUSES)[number]

export type DocumentSocraticRenderComparison = {
  readonly status: RenderComparisonStatus
  readonly changedRegionCount: number
  readonly detail?: string
}

export type DocumentSocraticReviewState = {
  readonly missingQuestions: readonly string[]
  readonly collectedAnswers: readonly string[]
  readonly draftPreview?: string
  readonly approvalLabel?: string
  readonly renderComparison?: DocumentSocraticRenderComparison
}

type ParsedQuestion = {
  readonly questionId?: string
  readonly prompt: string
  readonly required: boolean
}

type ParsedAnswer = {
  readonly questionId?: string
  readonly summary: string
}

export function extractDocumentSocraticReview(
  payload: unknown,
): DocumentSocraticReviewState | null {
  const payloadRecord = asRecord(payload)
  if (payloadRecord === null) {
    return null
  }

  const authoring = asRecord(payloadRecord.authoring)
  const renderComparison = parseRenderComparison(payloadRecord.render_comparison)
  if (authoring === null && renderComparison === undefined) {
    return null
  }

  const questions = parseQuestions(authoring?.questions)
  const answers = parseAnswers(authoring?.answers)
  const missingQuestions = missingRequiredQuestions(questions, answers)
  const collectedAnswers = collectedAnswerSummaries(answers, authoring)
  const draftPreview = parseDraftPreview(authoring?.draft)
  const approvalLabel = parseApprovalLabel(authoring)

  const review = {
    missingQuestions,
    collectedAnswers,
    ...(draftPreview !== undefined ? { draftPreview } : {}),
    ...(approvalLabel !== undefined ? { approvalLabel } : {}),
    ...(renderComparison !== undefined ? { renderComparison } : {}),
  } satisfies DocumentSocraticReviewState

  return hasReviewContent(review) ? review : null
}

function parseQuestions(value: unknown): readonly ParsedQuestion[] {
  return recordsFrom(value)
    .map((record): ParsedQuestion | null => {
      const prompt = cleanDisplayText(readString(record.prompt))
      if (prompt === undefined) {
        return null
      }
      const questionId = readString(record.question_id)
      const required = record.required === true
      return {
        ...(questionId !== undefined ? { questionId } : {}),
        prompt,
        required,
      }
    })
    .filter((question): question is ParsedQuestion => question !== null)
}

function parseAnswers(value: unknown): readonly ParsedAnswer[] {
  return recordsFrom(value)
    .map((record): ParsedAnswer | null => {
      const summary = cleanDisplayText(readString(record.response_summary))
      if (summary === undefined) {
        return null
      }
      const questionId = readString(record.question_id)
      return {
        ...(questionId !== undefined ? { questionId } : {}),
        summary,
      }
    })
    .filter((answer): answer is ParsedAnswer => answer !== null)
}

function missingRequiredQuestions(
  questions: readonly ParsedQuestion[],
  answers: readonly ParsedAnswer[],
): readonly string[] {
  const answeredIds = new Set(
    answers
      .map(answer => answer.questionId)
      .filter((questionId): questionId is string => questionId !== undefined),
  )
  return questions
    .filter(question => question.required)
    .filter(question => question.questionId === undefined || !answeredIds.has(question.questionId))
    .map(question => question.prompt)
}

function collectedAnswerSummaries(
  answers: readonly ParsedAnswer[],
  authoring: Readonly<Record<string, unknown>> | null,
): readonly string[] {
  if (answers.length > 0) {
    return answers.map(answer => answer.summary)
  }
  return recordsFrom(authoring?.evidence_items)
    .map(record => cleanDisplayText(readString(record.summary)))
    .filter((summary): summary is string => summary !== undefined)
}

function parseDraftPreview(value: unknown): string | undefined {
  const draft = asRecord(value)
  return draft === null ? undefined : cleanDisplayText(readString(draft.draft_text))
}

function parseApprovalLabel(
  authoring: Readonly<Record<string, unknown>> | null,
): string | undefined {
  if (authoring === null) {
    return undefined
  }
  const approval = asRecord(authoring.approval)
  const decision = approval === null ? undefined : readString(approval.decision)
  if (decision !== undefined) {
    return approvalDecisionLabel(decision)
  }
  if (parseDraftPreview(authoring.draft) !== undefined) {
    return 'awaiting approval'
  }
  const state = readString(authoring.state)
  return state === 'needs_input' || state === 'blocked_missing_evidence' ? 'not ready' : undefined
}

function approvalDecisionLabel(decision: string): string {
  switch (decision) {
    case 'approved':
      return 'approved'
    case 'edited':
      return 'approved with edits'
    case 'leave_blank':
      return 'leave blank'
    case 'cancel':
      return 'cancelled'
    default:
      return 'unknown'
  }
}

function parseRenderComparison(value: unknown): DocumentSocraticRenderComparison | undefined {
  const record = asRecord(value)
  if (record === null) {
    return undefined
  }
  const rawStatus = readString(record.status) ?? readString(record.threshold_status)
  if (rawStatus === undefined || !isRenderComparisonStatus(rawStatus)) {
    return undefined
  }
  const changedRegionCount = recordsFrom(record.changed_regions).length
  const detail = cleanDisplayText(readString(record.failure_reason))
  return {
    status: rawStatus,
    changedRegionCount,
    ...(detail !== undefined ? { detail } : {}),
  }
}

function hasReviewContent(review: DocumentSocraticReviewState): boolean {
  return (
    review.missingQuestions.length > 0 ||
    review.collectedAnswers.length > 0 ||
    review.draftPreview !== undefined ||
    review.approvalLabel !== undefined ||
    review.renderComparison !== undefined
  )
}

function isRenderComparisonStatus(value: string): value is RenderComparisonStatus {
  return REVIEW_STATUSES.some(status => status === value)
}

function recordsFrom(value: unknown): readonly Readonly<Record<string, unknown>>[] {
  return Array.isArray(value) ? value.filter(isRecord) : []
}

function asRecord(value: unknown): Readonly<Record<string, unknown>> | null {
  return isRecord(value) ? value : null
}

function isRecord(value: unknown): value is Readonly<Record<string, unknown>> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function readString(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim().length > 0 ? value.trim() : undefined
}

function cleanDisplayText(value: string | undefined): string | undefined {
  return value?.replace(INTERNAL_TOKEN_PATTERN, 'internal step')
}
