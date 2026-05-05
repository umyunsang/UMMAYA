// SPDX-License-Identifier: Apache-2.0
//
// KOSMOS-original Ink component: migration summary renderer.
//
// Renders the result of a /migrate-sessions operation as a coloured summary
// table. Intended to be embedded in the REPL conversation stream as a
// transient system notice (not stored in session JSONL).
//
// Props mirror MigrationSummary from utils/migrateSessions.ts.

import * as React from 'react'
import { Box, Text } from 'ink'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface MigrateSessionsResultProps {
  /** Number of files successfully copied. */
  copied: number
  /** Files skipped (destination already existed). */
  skipped: number
  /** Files unlinked from source (prune phase). */
  pruned: number
  /** Total bytes copied. */
  bytes: number
  /** Non-fatal errors encountered during migration. */
  errors: string[]
  /** When true, prefix output with "[dry-run]". */
  dryRun?: boolean
}

// ---------------------------------------------------------------------------
// Row component
// ---------------------------------------------------------------------------

interface RowProps {
  label: string
  value: string | number
  color: string
}

function Row({ label, value, color }: RowProps) {
  return (
    <Box>
      <Text color="gray">{label.padEnd(12)}</Text>
      <Text color={color}>{String(value)}</Text>
    </Box>
  )
}

// ---------------------------------------------------------------------------
// MigrateSessionsResult
// ---------------------------------------------------------------------------

export function MigrateSessionsResult({
  copied,
  skipped,
  pruned,
  bytes,
  errors,
  dryRun = false,
}: MigrateSessionsResultProps) {
  const kb = (bytes / 1024).toFixed(1)
  const hasErrors = errors.length > 0
  const headerColor = dryRun ? 'cyan' : copied > 0 ? 'green' : 'yellow'
  const headerLabel = dryRun ? '[dry-run] migrate-sessions' : 'migrate-sessions'

  return (
    <Box flexDirection="column" paddingLeft={1}>
      {/* Header */}
      <Box marginBottom={1}>
        <Text bold color={headerColor}>
          {headerLabel}
        </Text>
      </Box>

      {/* Summary table */}
      <Box flexDirection="column" paddingLeft={2}>
        <Row
          label="copied"
          value={`${copied} file${copied !== 1 ? 's' : ''} (${kb} KB)`}
          color={copied > 0 ? 'green' : 'gray'}
        />
        <Row
          label="skipped"
          value={`${skipped} (already in destination)`}
          color={skipped > 0 ? 'yellow' : 'gray'}
        />
        <Row
          label="pruned"
          value={pruned}
          color={pruned > 0 ? 'magenta' : 'gray'}
        />
      </Box>

      {/* Errors section */}
      {hasErrors && (
        <Box flexDirection="column" marginTop={1} paddingLeft={2}>
          <Text color="red" bold>
            {`errors (${errors.length})`}
          </Text>
          {errors.slice(0, 5).map((e, i) => (
            <Box key={i} paddingLeft={2}>
              <Text color="red">{'• '}</Text>
              <Text color="red" wrap="wrap">
                {e}
              </Text>
            </Box>
          ))}
          {errors.length > 5 && (
            <Box paddingLeft={2}>
              <Text color="red" dimColor>
                {`… and ${errors.length - 5} more`}
              </Text>
            </Box>
          )}
        </Box>
      )}
    </Box>
  )
}

export default MigrateSessionsResult
