/**
 * UMMAYA — document harness result renderer.
 *
 * Renders document mutations through the Claude Code edit-result shape:
 * a concise change summary followed immediately by the structured diff body.
 * There is deliberately no rounded card frame, browser/graphics viewer, tool-id
 * header, artifact summary, or revdiff status rail in the compact success path.
 */
import React, { useContext } from 'react'
import { Box, Text } from '../../ink.js'
import { TerminalSizeContext } from '../../ink/components/TerminalSizeContext.js'
import { truncateToWidth } from '../../utils/format.js'
import { useTheme } from '@/theme/provider'
import { MessageResponse } from '../MessageResponse.js'
import { StructuredDiffFallback } from '../StructuredDiff/Fallback.js'
import { DocumentSocraticReviewBlock } from './DocumentSocraticReviewBlock.js'
import {
  documentChangeToPatch,
  documentVisibleChanges,
} from '../../tools/_shared/documentChangeToPatch.js'
import { extractDocumentSocraticReview } from './documentSocraticReview.js'
import type {
  DocumentDiffPayload,
  DocumentToolResultPayload,
  DocumentToolStatus,
} from './types'

export interface DocumentToolResultCardProps {
  payload: DocumentToolResultPayload
  expanded?: boolean
}

/** Compact inline view caps the change list; Ctrl+O / verbose expands to all. */
const COMPACT_CHANGE_CAP = 6
const EXPANDED_CHANGE_CAP = 256

export function DocumentToolResultCard({
  payload,
  expanded = false,
}: DocumentToolResultCardProps): React.JSX.Element {
  const theme = useTheme()
  const terminalSize = useContext(TerminalSizeContext)
  const surfaceWidth = Math.max(24, terminalSize?.columns ?? 100)

  const diff = payload.diff ?? undefined
  const statusColor = colorForStatus(payload.status, theme)
  const statusLabel = labelForStatus(payload.status)
  const promotionGate = payload.promotion_gate_result ?? undefined
  const promotionChecklistCount = promotionGate?.promotion_checklist?.length ?? 0
  const visibleChanges = diff === undefined ? [] : documentVisibleChanges(diff)
  const changeCap = expanded ? EXPANDED_CHANGE_CAP : COMPACT_CHANGE_CAP
  const reviewDocumentName =
    diff === undefined ? payload.tool_id : documentNameFor(payload, diff)
  const savedExportPaths = savedExportPathsFor(payload)
  const socraticReview = extractDocumentSocraticReview(payload)

  const patch =
    diff !== undefined && visibleChanges.length > 0
      ? documentChangeToPatch(diff, {
          documentName: reviewDocumentName,
          maxChanges: changeCap,
        })
      : undefined
  const omittedChangeCount = patch === undefined ? 0 : patch.changeCount - patch.renderedChangeCount
  const diffWidth = Math.max(20, surfaceWidth - 12)

  if (payload.status === 'ok' && patch !== undefined && patch.hunks.length > 0) {
    return (
      <MessageResponse>
        <Box flexDirection="column" width={surfaceWidth}>
          <Text>{changedFieldsSummary(patch.changeCount)}</Text>
          {patch.hunks.map((hunk, index) => (
            <React.Fragment key={`${hunk.oldStart}-${hunk.newStart}-${index}`}>
              {index > 0 && <Text dimColor>...</Text>}
              <StructuredDiffFallback
                patch={hunk}
                dim={false}
                width={diffWidth}
              />
            </React.Fragment>
          ))}
          {patch.truncated && omittedChangeCount > 0 && (
            <Text color={theme.inactive}>
              {truncateToWidth(
                `… +${omittedChangeCount} more ${omittedChangeCount === 1 ? 'change' : 'changes'} · Ctrl+O to expand`,
                surfaceWidth,
              )}
            </Text>
          )}
          {savedExportPaths.map((localPath) => (
            <Text key={localPath} color={theme.success}>
              {truncateToWidth(`Saved: ${localPath}`, surfaceWidth)}
            </Text>
          ))}
          <DocumentSocraticReviewBlock review={socraticReview} width={surfaceWidth} />
        </Box>
      </MessageResponse>
    )
  }

  return (
    <Box flexDirection="column" width={surfaceWidth}>
      <Box flexDirection="row" gap={1} width={surfaceWidth}>
        <Text bold color={statusColor}>{statusLabel}</Text>
      </Box>
      <Text color={theme.text} wrap="wrap">
        {truncateToWidth(summaryForDisplay(payload, expanded), surfaceWidth)}
      </Text>
      {payload.blocked_reason !== undefined && payload.blocked_reason !== null && (
        <Text color={theme.warning}>{`Reason: ${payload.blocked_reason}`}</Text>
      )}
      <DocumentSocraticReviewBlock review={socraticReview} width={surfaceWidth} />
      {promotionGate !== undefined && (
        <Box flexDirection="column" marginTop={1}>
          <Text color={theme.warning} wrap="wrap">
            {truncateToWidth(
              `Gate: ${promotionGate.capability ?? 'capability'} ${promotionGate.promotion_state ?? 'unknown'}`,
              surfaceWidth,
            )}
          </Text>
          {(promotionGate.hard_gate_failures ?? []).length > 0 && (
            <Text color={theme.warning} wrap="wrap">
              {truncateToWidth(
                `Hard gates: ${(promotionGate.hard_gate_failures ?? []).join(', ')}`,
                surfaceWidth,
              )}
            </Text>
          )}
          {promotionChecklistCount > 0 && (
            <Text color={theme.inactive} wrap="wrap">
              {truncateToWidth(
                `Checklist: ${promotionChecklistCount} render promotion evidence item(s) required`,
                surfaceWidth,
              )}
            </Text>
          )}
        </Box>
      )}
      {expanded && diff !== undefined && (diff.diff_id !== undefined || diff.derivative_artifact_id !== undefined) && (
        <Text color={theme.inactive} wrap="wrap">
          {truncateToWidth(
            `Evidence: ${diff.diff_id ?? 'untracked'} · ${diff.source_artifact_id} -> ${diff.derivative_artifact_id}`,
            surfaceWidth,
          )}
        </Text>
      )}
      {savedExportPaths.map((localPath) => (
        <Text key={localPath} color={theme.success}>
          {truncateToWidth(`Saved: ${localPath}`, surfaceWidth)}
        </Text>
      ))}
    </Box>
  )
}

function changedFieldsSummary(changeCount: number): string {
  return `Changed ${changeCount} ${changeCount === 1 ? 'field' : 'fields'}`
}

function summaryForDisplay(
  payload: DocumentToolResultPayload,
  expanded: boolean,
): string {
  if (expanded) {
    return payload.text_summary
  }
  const [firstLine] = payload.text_summary.split(/\r?\n/u)
  const candidateCount = payload.text_summary
    .split(/\r?\n/u)
    .filter(line => line.trim().startsWith('- ')).length
  if (candidateCount > 0) {
    return `${firstLine} ${candidateCount} matching candidate${candidateCount === 1 ? '' : 's'} available · Ctrl+O to expand.`
  }
  return firstLine ?? payload.text_summary
}

function savedExportPathsFor(payload: DocumentToolResultPayload): string[] {
  return (payload.saved_exports ?? [])
    .map(savedExport => savedExport.local_path?.trim())
    .filter((localPath): localPath is string => localPath !== undefined && localPath.length > 0)
}

/**
 * Synthetic file name for the diff. Only used by CC's language detection; for
 * documents it falls back to plain-text rendering, which is what we want for
 * `label: value` field lines. Prefer a real filename sniffed from the summary.
 */
function documentNameFor(
  payload: DocumentToolResultPayload,
  diff: DocumentDiffPayload,
): string {
  const sniffed = /([^\s/\\]+\.(?:hwpx|hwp|docx|pdf|xlsx|pptx))/iu.exec(
    payload.text_summary,
  )?.[1]
  return sniffed ?? diff.derivative_artifact_id ?? payload.tool_id
}

function labelForStatus(status: DocumentToolStatus): string {
  switch (status) {
    case 'ok':
      return 'Document OK'
    case 'blocked':
      return 'Document blocked'
    case 'failed':
      return 'Document failed'
    case 'needs_input':
      return 'Document needs input'
  }
}

function colorForStatus(
  status: DocumentToolStatus,
  theme: ReturnType<typeof useTheme>,
): string {
  switch (status) {
    case 'ok':
      return theme.success
    case 'blocked':
    case 'needs_input':
      return theme.warning
    case 'failed':
      return theme.error
  }
}
