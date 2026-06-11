// SPDX-License-Identifier: Apache-2.0

import { createHash } from 'node:crypto'

const APPROVAL_TOKEN_RE = /승인|\bapprove\b/giu
const APPROVAL_WORD_RE = /승인|\bapprove\b/iu
const DECISION_SPLIT_RE =
  /[.!?。]+|\b(?:but|however|nevertheless|instead|rather|and)\b|(?:하지만|그러나|그렇지만|다만|지만)/iu
const EXPLICIT_ENGLISH_APPROVAL_SEGMENT_RE =
  /^(?:yes[,.]?\s+)?i\s+approve(?:\s+(?:this|the|that|current|revised|updated|final|draft|version|document|text|content|answer|change|changes))*[.!]?$/iu
const EXPLICIT_KOREAN_APPROVAL_SEGMENT_RE =
  /^(?:(?:지금|현재|이번|방금|수정한|이|그)\s*)?(?:(?:초안|문안|내용|답변|문서)\s*(?:은|는|을|를)?\s*)?승인(?:해|합니다|할게|하겠습니다)[.!。]?$/u
const ENGLISH_NEGATION_PREFIX_RE =
  /\b(?:do\s+not|don't|didn't|isn't|cannot|can't|won't|haven't|hasn't|hadn't|never|unable\s+to|refuse\s+to|decline\s+to|not\b)/iu
const KOREAN_NEGATION_PREFIX_RE = /(?:불\s*|미\s*)$/u
const KOREAN_NEGATION_SUFFIX_RE =
  /^\s*(?:은|을|이|가|도|만|으로)?\s*(?:하지|않|안|못|거부|거절|반려|보류|취소|처리하지|보지|간주하지|할\s*수\s*없|아님|없)/u
const EXPLICIT_REJECTION_RE =
  /(?:\bno\b|\breject(?:ed)?\b|\bdisapprove(?:d)?\b|\bunapproved\b|\bdo\s+not\s+treat\s+(?:that|this|it)\s+as\s+approval\b|아니|불\s*승인|미\s*승인|거절|거부|반려|보류|취소|승인(?:으로)?\s*처리하지)/giu

type StringPatch = {
  readonly targetPath: string
  readonly value: string
}

export function normalizeDocumentMutationPayloadsForDispatch(
  args: Record<string, unknown>,
  userText: string | undefined,
): Record<string, unknown> {
  return normalizeApprovedDraftPayloadForDispatch(
    normalizeDocumentStylePayloadsForDispatch(
      normalizeDocumentPatchPayloadsForDispatch(args),
    ),
    userText,
  )
}

function normalizeDocumentPatchPayloadsForDispatch(
  args: Record<string, unknown>,
): Record<string, unknown> {
  if (!Array.isArray(args.patches)) return args
  return {
    ...args,
    patches: args.patches.map(normalizeDocumentPatchPayloadForDispatch),
  }
}

function normalizeDocumentPatchPayloadForDispatch(patch: unknown): unknown {
  const record = recordFrom(patch)
  if (record === undefined || !Object.hasOwn(record, 'content')) return patch
  const { content, ...withoutContent } = record
  if (Object.hasOwn(withoutContent, 'value')) return withoutContent
  return {
    ...withoutContent,
    value: content,
  }
}

function normalizeDocumentStylePayloadsForDispatch(
  args: Record<string, unknown>,
): Record<string, unknown> {
  if (!Array.isArray(args.styles)) return args
  const styles = args.styles.filter(style => {
    const record = recordFrom(style)
    return record === undefined || Object.keys(record).length > 0
  })
  if (styles.length > 0) return styles.length === args.styles.length ? args : { ...args, styles }
  const { styles: _styles, ...withoutStyles } = args
  return withoutStyles
}

function normalizeApprovedDraftPayloadForDispatch(
  args: Record<string, unknown>,
  userText: string | undefined,
): Record<string, unknown> {
  const normalizedArgs = withoutApprovedDraftFields(args)
  if (userText === undefined) return normalizedArgs
  if (!hasAffirmativeApproval(userText)) return normalizedArgs
  const patches = stringPatchesFromArgs(normalizedArgs)
  if (patches === undefined || patches.length === 0) return normalizedArgs
  const approval = authoringApprovalForPatches(patches)
  return {
    ...normalizedArgs,
    approved_draft_id: approval.draftId,
    approved_draft_sha256: approval.draftSha256,
  }
}

function withoutApprovedDraftFields(args: Record<string, unknown>): Record<string, unknown> {
  const {
    approved_draft_id: _approvedDraftId,
    approved_draft_sha256: _approvedDraftSha256,
    ...withoutApproval
  } = args
  return withoutApproval
}

function hasAffirmativeApproval(userText: string): boolean {
  const decisions = decisionSegments(userText).flatMap(approvalDecisionFromSegment)
  return decisions.at(-1) === true
}

function decisionSegments(userText: string): readonly string[] {
  return userText
    .split(DECISION_SPLIT_RE)
    .map(segment => segment.trim())
    .filter(segment => segment !== '')
}

function approvalDecisionFromSegment(segment: string): readonly boolean[] {
  const decisions: Array<{ readonly index: number; readonly approved: boolean }> = []
  for (const match of segment.matchAll(APPROVAL_TOKEN_RE)) {
    const approvalToken = match[0]
    const index = match.index
    if (index !== undefined && isNegatedApprovalToken(segment, index, approvalToken.length)) {
      decisions.push({ index, approved: false })
    }
  }
  for (const match of segment.matchAll(EXPLICIT_REJECTION_RE)) {
    const index = match.index
    if (index !== undefined) {
      decisions.push({ index, approved: false })
    }
  }
  if (decisions.length === 0 && isExplicitApprovalSegment(segment)) {
    decisions.push({ index: 0, approved: true })
  }
  return decisions
    .sort((left, right) => left.index - right.index)
    .map(decision => decision.approved)
}

function isExplicitApprovalSegment(segment: string): boolean {
  const trimmedSegment = segment.trim()
  return EXPLICIT_ENGLISH_APPROVAL_SEGMENT_RE.test(trimmedSegment) ||
    EXPLICIT_KOREAN_APPROVAL_SEGMENT_RE.test(trimmedSegment)
}

function isNegatedApprovalToken(
  segment: string,
  index: number,
  tokenLength: number,
): boolean {
  const beforeToken = segment.slice(0, index)
  const afterToken = segment.slice(index + tokenLength)
  return ENGLISH_NEGATION_PREFIX_RE.test(beforeToken) ||
    KOREAN_NEGATION_PREFIX_RE.test(beforeToken) ||
    KOREAN_NEGATION_SUFFIX_RE.test(afterToken)
}

function stringPatchesFromArgs(args: Record<string, unknown>): readonly StringPatch[] | undefined {
  if (!Array.isArray(args.patches)) return []
  const patches: StringPatch[] = []
  for (const patch of args.patches) {
    const record = recordFrom(patch)
    if (record === undefined) return undefined
    const targetPath = stringField(record, 'target_path')
    const value = stringField(record, 'value')
    if (targetPath === undefined || value === undefined) return undefined
    patches.push({ targetPath, value })
  }
  return patches
}

function authoringApprovalForPatches(
  patches: readonly StringPatch[],
): { readonly draftId: string; readonly draftSha256: string } {
  if (patches.length === 1) {
    const patch = patches[0]
    if (patch !== undefined) {
      const draftSha256 = sha256Hex(patch.value)
      return {
        draftId: issuedAuthoringDraftId(patch.targetPath, draftSha256),
        draftSha256,
      }
    }
  }
  const draftSha256 = sha256Hex(
    patches
      .map(patch => `${patch.targetPath}\0${sha256Hex(patch.value)}`)
      .join('\0'),
  )
  return {
    draftId: issuedAuthoringDraftId(authoringBundleTargetPath(patches), draftSha256),
    draftSha256,
  }
}

function issuedAuthoringDraftId(targetPath: string, draftSha256: string): string {
  return `draft-${sha256Hex(`${targetPath}\0${draftSha256}`).slice(0, 24)}`
}

function authoringBundleTargetPath(patches: readonly StringPatch[]): string {
  const targetPaths = patches.map(patch => patch.targetPath).join('\0')
  return `bundle:${sha256Hex(targetPaths).slice(0, 24)}`
}

function stringField(
  record: Record<string, unknown>,
  key: string,
): string | undefined {
  const value = record[key]
  return typeof value === 'string' && value.trim() !== '' ? value : undefined
}

function sha256Hex(value: string): string {
  return createHash('sha256').update(value, 'utf8').digest('hex')
}

function recordFrom(value: unknown): Record<string, unknown> | undefined {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? Object.fromEntries(Object.entries(value))
    : undefined
}
