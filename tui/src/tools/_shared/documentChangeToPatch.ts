// SPDX-License-Identifier: Apache-2.0
/**
 * UMMAYA — document-change → Claude Code diff-pipeline migration boundary.
 *
 * Deep-research-migration note (selected approach D):
 *   specs/2802-public-doc-harness/deep-research-migration-document-render.md
 *
 * Document work renders in the TUI the same way Claude Code renders a code
 * edit: automatically, inline, per-mutation, via `renderToolResultMessage`.
 * Rather than invent a renderer, this module routes structural field-level
 * document changes INTO the already-ported CC diff pipeline by representing the
 * changed form as `label: value` text and producing the `StructuredPatchHunk[]`
 * shape that `StructuredDiffList` already consumes byte-identically. The
 * "structural" choice (difftastic / json-diff / daff convergence) is that the
 * text is built from semantic fields, not from raw document bytes.
 */
import type { StructuredPatchHunk } from 'diff'
import { getPatchFromContents } from '../../utils/diff.js'
import type {
  DocumentChangePayload,
  DocumentDiffPayload,
} from '../../components/primitive/types.js'

/** Default inline cap; beyond this the inline view shows a "+N more" affordance. */
export const DEFAULT_INLINE_CHANGE_CAP = 20

export interface DocumentPatchResult {
  /** Hunks ready for `<StructuredDiffList hunks={...} />` (CC pipeline). */
  hunks: StructuredPatchHunk[]
  /** Synthetic file path = document name; drives CC language detection. */
  filePath: string
  /** Actual visible changes after no-op entries are removed. */
  changeCount: number
  /** Changes actually rendered into the patch (≤ cap). */
  renderedChangeCount: number
  /** True when changes were dropped from the inline view, or the backend
   *  already flagged inline truncation. */
  truncated: boolean
}

interface DocumentChangeToPatchOptions {
  documentName?: string
  maxChanges?: number
}

export function documentChangeToPatch(
  diff: DocumentDiffPayload,
  options: DocumentChangeToPatchOptions = {},
): DocumentPatchResult {
  const filePath = nonEmpty(options.documentName) ?? 'document'
  const cap = Math.max(0, options.maxChanges ?? DEFAULT_INLINE_CHANGE_CAP)
  const changes = documentVisibleChanges(diff)
  const changeCount = changes.length
  const rendered = changes.slice(0, cap)
  const renderedChangeCount = rendered.length
  const truncated =
    changeCount > renderedChangeCount || diff.inline_truncated === true

  if (renderedChangeCount === 0) {
    return { hunks: [], filePath, changeCount, renderedChangeCount, truncated }
  }

  // Trailing newline on both sides so the `diff` package does not emit a
  // "\ No newline at end of file" marker — that marker would also break the
  // fallback renderer's remove/add adjacency pairing (and thus its word-level
  // value highlighting).
  const before = `${rendered.map((change) => fieldLine(change, 'before')).join('\n')}\n`
  const after = `${rendered.map((change) => fieldLine(change, 'after')).join('\n')}\n`
  const hunks = getPatchFromContents({
    filePath,
    oldContent: before,
    newContent: after,
    singleHunk: true,
  })
  return { hunks, filePath, changeCount, renderedChangeCount, truncated }
}

function fieldLine(change: DocumentChangePayload, side: 'before' | 'after'): string {
  const fallbackLabel = humanizeDocumentTargetPath(change.target_path) || change.change_type
  const label = nonEmpty(change.display_label) ?? fallbackLabel
  const value = sanitizeValue(
    side === 'before' ? change.before_value : change.after_value,
  )
  return `${label}: ${value}`
}

export function documentVisibleChanges(
  diff: DocumentDiffPayload,
): DocumentChangePayload[] {
  return diff.changes.filter(hasVisibleChange)
}

function hasVisibleChange(change: DocumentChangePayload): boolean {
  return sanitizeValue(change.before_value) !== sanitizeValue(change.after_value)
}

/**
 * Structural path is the location (difftastic philosophy). Strip the leading
 * slash and render nested segments with a breadcrumb separator so
 * `/hwpx/text[12]` reads as `hwpx › text[12]`. No pixel coordinates — the field
 * path is honest and precise about where the change lives.
 */
export function humanizeDocumentTargetPath(path: string): string {
  const trimmed = path.trim().replace(/^\/+/u, '')
  if (trimmed === '') {
    return ''
  }
  return trimmed.replace(/\/+/gu, ' › ')
}

/** Collapse newlines so one field change stays one diff line. */
function sanitizeValue(value: string | null | undefined): string {
  if (value === null || value === undefined) {
    return ''
  }
  return value.replace(/\r?\n/gu, ' ')
}

function nonEmpty(value: string | null | undefined): string | undefined {
  if (value === null || value === undefined) {
    return undefined
  }
  const trimmed = value.trim()
  return trimmed === '' ? undefined : trimmed
}
