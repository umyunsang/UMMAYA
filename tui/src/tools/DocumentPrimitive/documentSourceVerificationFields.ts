// SPDX-License-Identifier: Apache-2.0

import { createHash } from 'node:crypto'
import { validatePublicWebFetchUrl } from '../WebFetchTool/urlSafety.js'

const SOURCE_VERIFICATION_TEXT_RE =
  /(근거|출처|검증|source[-\s]?support|source[-\s]?verification|citation|evidence)/iu

const SOURCE_SUPPORT_URL_FIELDS = [
  'source_url',
  'sourceUrl',
  'citation_url',
  'citationUrl',
] as const

export function recordsFrom(value: unknown): readonly Record<string, unknown>[] {
  if (!Array.isArray(value)) return []
  return value.flatMap(item => {
    const record = recordFrom(item)
    return record === null ? [] : [record]
  })
}

export function recordFrom(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? Object.fromEntries(Object.entries(value))
    : null
}

export function stringField(
  record: Record<string, unknown> | null,
  key: string,
): string | undefined {
  if (record === null) return undefined
  const value = record[key]
  return typeof value === 'string' && value.trim() !== '' ? value : undefined
}

export function sha256Hex(value: string): string {
  return createHash('sha256').update(value, 'utf8').digest('hex')
}

export function sourceVerificationRequested(
  args: Record<string, unknown>,
  userText: string | undefined,
): boolean {
  if (
    args.requires_source_verification === true ||
    args.source_verification_required === true
  ) {
    return true
  }
  const instruction = stringField(args, 'instruction')
  const text = `${instruction ?? ''}\n${userText ?? ''}`
  return SOURCE_VERIFICATION_TEXT_RE.test(text)
}

export function patchRequestsSourceSupport(
  record: Record<string, unknown> | null,
): boolean {
  if (record === null) return false
  return record.requires_source_verification === true ||
    record.source_verification_required === true ||
    record.source_support !== undefined ||
    record.sourceSupport !== undefined
}

export function sourceSupportHasUnsafeUrl(
  sourceSupport: Record<string, unknown>,
): boolean {
  for (const field of SOURCE_SUPPORT_URL_FIELDS) {
    const value = stringField(sourceSupport, field)
    if (value !== undefined && !validatePublicWebFetchUrl(value).ok) {
      return true
    }
  }
  return false
}

export function hasApprovedDraft(args: Record<string, unknown>): boolean {
  return typeof args.approved_draft_id === 'string' &&
    typeof args.approved_draft_sha256 === 'string'
}

export function withoutApprovalFields(
  args: Record<string, unknown>,
): Record<string, unknown> {
  const {
    approved_draft_id: _approvedDraftId,
    approved_draft_sha256: _approvedDraftSha256,
    ...withoutApproval
  } = args
  return withoutApproval
}

export function withoutPatches(args: Record<string, unknown>): Record<string, unknown> {
  const { patches: _patches, ...withoutPatchPayload } = args
  return withoutPatchPayload
}

export function patchTargetPath(record: Record<string, unknown> | null): string {
  return stringField(record, 'target_path') ?? 'unknown'
}
