// SPDX-License-Identifier: Apache-2.0

import React from 'react'
import { Box, Text } from '../../ink.js'
import { truncateToWidth } from '../../utils/format.js'
import { useTheme } from '@/theme/provider'
import type { DocumentSocraticReviewState, RenderComparisonStatus } from './documentSocraticReview'

export type DocumentSocraticReviewBlockProps = {
  readonly review: DocumentSocraticReviewState | null
  readonly width: number
}

export function DocumentSocraticReviewBlock({
  review,
  width,
}: DocumentSocraticReviewBlockProps): React.JSX.Element | null {
  const theme = useTheme()
  if (review === null) {
    return null
  }
  return (
    <Box flexDirection="column" marginTop={1} width={width}>
      {review.missingQuestions.length > 0 && (
        <ReviewList
          title="Questions needed"
          items={review.missingQuestions}
          width={width}
          titleColor={theme.warning}
        />
      )}
      {review.collectedAnswers.length > 0 && (
        <ReviewList
          title="Collected answers"
          items={review.collectedAnswers}
          width={width}
          titleColor={theme.success}
        />
      )}
      {review.draftPreview !== undefined && (
        <Box flexDirection="column">
          <Text color={theme.text} bold>Draft preview</Text>
          <Text color={theme.text} wrap="wrap">
            {truncateToWidth(review.draftPreview, width)}
          </Text>
        </Box>
      )}
      {review.approvalLabel !== undefined && (
        <Text color={approvalColor(review.approvalLabel, theme)}>
          {truncateToWidth(`Approval: ${review.approvalLabel}`, width)}
        </Text>
      )}
      {review.renderComparison !== undefined && (
        <Box flexDirection="column">
          <Text color={renderComparisonColor(review.renderComparison.status, theme)}>
            {truncateToWidth(
              `Render comparison: ${review.renderComparison.status}${changedRegionText(review.renderComparison.changedRegionCount)}`,
              width,
            )}
          </Text>
          {review.renderComparison.detail !== undefined && (
            <Text color={theme.warning} wrap="wrap">
              {truncateToWidth(review.renderComparison.detail, width)}
            </Text>
          )}
        </Box>
      )}
    </Box>
  )
}

type ReviewListProps = {
  readonly title: string
  readonly items: readonly string[]
  readonly width: number
  readonly titleColor: string
}

function ReviewList({
  title,
  items,
  width,
  titleColor,
}: ReviewListProps): React.JSX.Element {
  return (
    <Box flexDirection="column">
      <Text color={titleColor} bold>{title}</Text>
      {items.map((item, index) => (
        <Text key={`${title}-${index}`} color="white" wrap="wrap">
          {truncateToWidth(`- ${item}`, width)}
        </Text>
      ))}
    </Box>
  )
}

function changedRegionText(count: number): string {
  if (count <= 0) {
    return ''
  }
  return ` · ${count} changed ${count === 1 ? 'region' : 'regions'}`
}

function approvalColor(
  label: string,
  theme: ReturnType<typeof useTheme>,
): string {
  if (label === 'approved' || label === 'approved with edits') {
    return theme.success
  }
  if (label === 'awaiting approval' || label === 'not ready') {
    return theme.warning
  }
  return theme.inactive
}

function renderComparisonColor(
  status: RenderComparisonStatus,
  theme: ReturnType<typeof useTheme>,
): string {
  switch (status) {
    case 'pass':
      return theme.success
    case 'blocked':
      return theme.warning
    case 'failed':
      return theme.error
  }
}
