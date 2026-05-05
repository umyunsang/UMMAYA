// SPDX-License-Identifier: Apache-2.0
//
// KOSMOS-original slash command: /migrate-sessions
//
// Migrates CC-workspace JSONL sessions (leaked into `~/.claude/projects/`)
// to the KOSMOS-native memdir USER-tier sessions directory.
//
// Usage:
//   /migrate-sessions
//   /migrate-sessions --dry-run
//   /migrate-sessions --filter-cwd '.*KOSMOS.*'
//   /migrate-sessions --prune                   (destructive — requires Y confirm)
//   /migrate-sessions --prune --dry-run          (show what would be pruned)
//
// Flags:
//   --prune              Unlink source files after a successful fsync-verified
//                        copy. Any unlink failure aborts the prune phase and
//                        throws — no partial-prune state is left.
//   --filter-cwd <regex> Regex applied to the CC project-dir name (sanitized
//                        cwd). Default: .*KOSMOS.*
//   --dry-run            List what would be copied/pruned without touching disk.
//
// --prune without --dry-run requires the caller to have confirmed the
// operation. The dispatcher that wires this command into the Ink layer is
// responsible for showing the Shift+Tab / Y modal before dispatching with
// --prune. This module only validates that the confirm flag is set when
// prune is requested in interactive mode.

import type { CommandDefinition, CommandHandlerArgs, CommandResult } from './types.js'
import { migrateSessions } from '../utils/migrateSessions.js'

// ---------------------------------------------------------------------------
// Arg parser
// ---------------------------------------------------------------------------

interface ParsedFlags {
  prune: boolean
  filterCwd: string | undefined
  dryRun: boolean
  /** When true, the caller already confirmed the prune operation. */
  confirmed: boolean
  errors: string[]
}

function parseFlags(args: string): ParsedFlags {
  const tokens = args.trim().split(/\s+/).filter((t) => t.length > 0)
  const errors: string[] = []
  let prune = false
  let filterCwd: string | undefined
  let dryRun = false
  let confirmed = false

  for (let i = 0; i < tokens.length; i++) {
    const tok = tokens[i]
    if (tok === '--prune') {
      prune = true
    } else if (tok === '--dry-run') {
      dryRun = true
    } else if (tok === '--confirmed') {
      // Internal flag: set by the Y modal in the TUI before dispatching.
      confirmed = true
    } else if (tok === '--filter-cwd') {
      const next = tokens[i + 1]
      if (!next || next.startsWith('--')) {
        errors.push('--filter-cwd requires a regex argument')
      } else {
        filterCwd = next
        i += 1
      }
    } else if (!tok.startsWith('--')) {
      // Positional argument — not expected; surface as error.
      errors.push(`unexpected positional argument: ${tok}`)
    } else {
      errors.push(`unknown flag: ${tok}`)
    }
  }

  // Validate regex early so we surface parse errors before any I/O.
  if (filterCwd !== undefined) {
    try {
      new RegExp(filterCwd)
    } catch (err) {
      errors.push(`--filter-cwd: invalid regex "${filterCwd}": ${String(err)}`)
    }
  }

  return { prune, filterCwd, dryRun, confirmed, errors }
}

// ---------------------------------------------------------------------------
// Summary formatter
// ---------------------------------------------------------------------------

function formatSummary(
  summary: {
    copied: number
    skipped: number
    pruned: number
    bytes: number
    errors: string[]
  },
  dryRun: boolean,
): string {
  const prefix = dryRun ? '[dry-run] ' : ''
  const kb = (summary.bytes / 1024).toFixed(1)
  const lines: string[] = [
    `${prefix}migrate-sessions complete`,
    `  copied:  ${summary.copied} file${summary.copied !== 1 ? 's' : ''} (${kb} KB)`,
    `  skipped: ${summary.skipped} (destination already existed)`,
    `  pruned:  ${summary.pruned}`,
  ]
  if (summary.errors.length > 0) {
    lines.push(`  errors:  ${summary.errors.length}`)
    for (const e of summary.errors.slice(0, 5)) {
      lines.push(`    • ${e}`)
    }
    if (summary.errors.length > 5) {
      lines.push(`    … and ${summary.errors.length - 5} more`)
    }
  }
  return lines.join('\n')
}

// ---------------------------------------------------------------------------
// Handler
// ---------------------------------------------------------------------------

async function handle({ args }: CommandHandlerArgs): Promise<CommandResult> {
  const parsed = parseFlags(args)

  if (parsed.errors.length > 0) {
    return {
      acknowledgement: [
        '/migrate-sessions: flag parse error(s):',
        ...parsed.errors.map((e) => `  • ${e}`),
        'Usage: /migrate-sessions [--dry-run] [--filter-cwd <regex>] [--prune]',
      ].join('\n'),
    }
  }

  // Guard: --prune in non-dry-run mode requires --confirmed.
  // The Ink dispatch layer (Shift+Tab modal or Y prompt) sets --confirmed
  // before calling the handler. Without it we return a prompt hint.
  if (parsed.prune && !parsed.dryRun && !parsed.confirmed) {
    return {
      acknowledgement: [
        '/migrate-sessions --prune: source files will be deleted after copy.',
        'Re-run with --confirmed to proceed, or use --dry-run to preview.',
        '(The TUI wiring shows a Shift+Tab confirmation modal automatically.)',
      ].join('\n'),
    }
  }

  try {
    const summary = await migrateSessions({
      prune: parsed.prune,
      filterCwd: parsed.filterCwd,
      dryRun: parsed.dryRun,
    })
    return { acknowledgement: formatSummary(summary, parsed.dryRun) }
  } catch (err) {
    return {
      acknowledgement: `/migrate-sessions failed: ${String(err)}`,
    }
  }
}

// ---------------------------------------------------------------------------
// CommandDefinition export
// ---------------------------------------------------------------------------

const migrateSessionsCommand: CommandDefinition = {
  name: 'migrate-sessions',
  description:
    'Migrate CC-workspace JSONL sessions to the KOSMOS memdir sessions directory',
  argumentHint: '[--dry-run] [--filter-cwd <regex>] [--prune]',
  handle,
}

export default migrateSessionsCommand
