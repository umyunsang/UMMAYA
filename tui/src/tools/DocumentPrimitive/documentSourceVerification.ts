// SPDX-License-Identifier: Apache-2.0

import { detectPromptInjection } from '../WebFetchTool/sourceVerification.js'
import {
  hasApprovedDraft,
  patchRequestsSourceSupport,
  patchTargetPath,
  recordFrom,
  recordsFrom,
  sha256Hex,
  sourceSupportHasUnsafeUrl,
  sourceVerificationRequested,
  stringField,
  withoutApprovalFields,
  withoutPatches,
} from './documentSourceVerificationFields.js'

export const DOCUMENT_SOURCE_VERIFICATION_POLICY =
  'source_supported_patch_requires_user_approval' as const

type QuestionWaitingReason =
  | 'missing_source_support'
  | 'blocked_source_support'
  | 'prompt_injection_source_support'
  | 'stale_source_support'
  | 'missing_user_approval'

type QuestionWaitingField = {
  readonly target_path: string
  readonly reason: QuestionWaitingReason
}

type SourcePatchNormalization = {
  readonly args: Record<string, unknown>
  readonly sourceGovernedPatchCount: number
  readonly sourceSupportedPatchCount: number
}

type SourceSupportEvaluation =
  | {
      readonly kind: 'supported'
      readonly sourceSupport: Record<string, unknown>
    }
  | {
      readonly kind: 'blocked'
      readonly reason: QuestionWaitingReason
    }

const SHA256_RE = /^[a-f0-9]{64}$/u

export function normalizeDocumentSourceSupportedPatchesForDispatch(
  args: Record<string, unknown>,
  userText: string | undefined,
): SourcePatchNormalization {
  if (!Array.isArray(args.patches)) {
    return {
      args,
      sourceGovernedPatchCount: 0,
      sourceSupportedPatchCount: 0,
    }
  }

  const policyRequested = sourceVerificationRequested(args, userText)
  const keptPatches: unknown[] = []
  const questionWaitingFields: QuestionWaitingField[] = []
  let sourceGovernedPatchCount = 0
  let sourceSupportedPatchCount = 0

  for (const patch of args.patches) {
    const record = recordFrom(patch)
    const patchRequiresSource = policyRequested || patchRequestsSourceSupport(record)
    if (!patchRequiresSource) {
      keptPatches.push(patch)
      continue
    }

    sourceGovernedPatchCount += 1
    const targetPath = patchTargetPath(record)
    const evaluation = evaluateSourceSupport(record)
    if (evaluation.kind === 'blocked') {
      questionWaitingFields.push({
        target_path: targetPath,
        reason: evaluation.reason,
      })
      continue
    }

    sourceSupportedPatchCount += 1
    keptPatches.push({
      ...record,
      source_support: evaluation.sourceSupport,
    })
  }

  if (sourceGovernedPatchCount === 0) {
    return {
      args,
      sourceGovernedPatchCount,
      sourceSupportedPatchCount,
    }
  }

  const nextArgs =
    keptPatches.length > 0 ? { ...args, patches: keptPatches } : withoutPatches(args)

  return {
    args: withSourceVerificationMetadata(
      nextArgs,
      sourceSupportedPatchCount,
      questionWaitingFields,
    ),
    sourceGovernedPatchCount,
    sourceSupportedPatchCount,
  }
}

export function enforceDocumentSourceApprovalForDispatch(
  args: Record<string, unknown>,
  normalization: SourcePatchNormalization,
): Record<string, unknown> {
  if (
    normalization.sourceGovernedPatchCount === 0 ||
    normalization.sourceSupportedPatchCount === 0 ||
    hasApprovedDraft(args)
  ) {
    return failClosedIfNoPatches(args, normalization.sourceGovernedPatchCount)
  }

  const blockedFields = recordsFrom(args.patches).flatMap(patch => {
    if (!patchRequestsSourceSupport(patch)) return []
    return [
      {
        target_path: patchTargetPath(patch),
        reason: 'missing_user_approval' as const,
      },
    ]
  })
  const keptPatches = recordsFrom(args.patches).filter(
    patch => !patchRequestsSourceSupport(patch),
  )
  const withoutApproval = withoutApprovalFields(args)
  const nextArgs =
    keptPatches.length > 0
      ? { ...withoutApproval, patches: keptPatches }
      : withoutPatches(withoutApproval)

  return failClosedIfNoPatches(
    withSourceVerificationMetadata(nextArgs, 0, blockedFields),
    normalization.sourceGovernedPatchCount,
  )
}

function withSourceVerificationMetadata(
  args: Record<string, unknown>,
  sourceVerifiedPatchCount: number,
  questionWaitingFields: readonly QuestionWaitingField[],
): Record<string, unknown> {
  const existingFields = Array.isArray(args.question_waiting_fields)
    ? recordsFrom(args.question_waiting_fields)
    : []
  return {
    ...args,
    source_verification_policy: DOCUMENT_SOURCE_VERIFICATION_POLICY,
    source_verified_patch_count: sourceVerifiedPatchCount,
    question_waiting_fields: [...existingFields, ...questionWaitingFields],
  }
}

function failClosedIfNoPatches(
  args: Record<string, unknown>,
  sourceGovernedPatchCount: number,
): Record<string, unknown> {
  if (sourceGovernedPatchCount === 0 || Array.isArray(args.patches)) {
    return args
  }
  const {
    approved_draft_id: _approvedDraftId,
    approved_draft_sha256: _approvedDraftSha256,
    destination_path: _destinationPath,
    destination_display_name: _destinationDisplayName,
    ...withoutMutation
  } = args
  return {
    ...withoutMutation,
    operation: 'inspect',
  }
}

function evaluateSourceSupport(
  patch: Record<string, unknown> | null,
): SourceSupportEvaluation {
  if (patch === null) return { kind: 'blocked', reason: 'missing_source_support' }
  const value = stringField(patch, 'value')
  if (value === undefined) return { kind: 'blocked', reason: 'missing_source_support' }
  const support = recordFrom(patch.source_support) ?? recordFrom(patch.sourceSupport)
  if (support === null) return { kind: 'blocked', reason: 'missing_source_support' }
  if (support.state === 'blocked' || support.blocked_or_used === 'blocked') {
    return { kind: 'blocked', reason: 'blocked_source_support' }
  }
  if (support.state !== 'source_supported') {
    return { kind: 'blocked', reason: 'missing_source_support' }
  }
  if (sourceSupportHasUnsafeUrl(support)) {
    return { kind: 'blocked', reason: 'blocked_source_support' }
  }
  if (sourceSupportHasPromptInjection(support)) {
    return { kind: 'blocked', reason: 'prompt_injection_source_support' }
  }
  const sourceSha256 = stringField(support, 'source_sha256')
  const citationHandle = stringField(support, 'citation_handle')
  if (
    sourceSha256 === undefined ||
    citationHandle === undefined ||
    !SHA256_RE.test(sourceSha256)
  ) {
    return { kind: 'blocked', reason: 'missing_source_support' }
  }
  if (sourceSha256 !== sha256Hex(value)) {
    return { kind: 'blocked', reason: 'stale_source_support' }
  }
  return {
    kind: 'supported',
    sourceSupport: sanitizeSourceSupport(support),
  }
}

function sourceSupportHasPromptInjection(
  sourceSupport: Record<string, unknown>,
): boolean {
  if (sourceSupport.prompt_injection === 'detected') return true
  const sourceText = stringField(sourceSupport, 'source_text')
  return sourceText !== undefined && detectPromptInjection(sourceText) === 'detected'
}

function sanitizeSourceSupport(
  sourceSupport: Record<string, unknown>,
): Record<string, unknown> {
  return {
    state: sourceSupport.state,
    citation_handle: sourceSupport.citation_handle,
    source_sha256: sourceSupport.source_sha256,
    observed_at: sourceSupport.observed_at,
    prompt_injection: sourceSupport.prompt_injection,
  }
}
