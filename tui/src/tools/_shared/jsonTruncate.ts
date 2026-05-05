// SPDX-License-Identifier: Apache-2.0
// KOSMOS-original — Wave-2 G5 (Spec realuse-audit-2026-05-05).
//
// JSON-aware truncation helper for ⎿ tool-result preview rows.
//
// F-known criterion #2 / F-beta-05 universal regression: the LookupPrimitive
// tool-result summary path was using bare ``s.slice(0, N)`` which produces
// invalid mid-key JSON without any indicator. Citizens see fragments like
//   {"timestamp_iso":"2026-05-05T12:00:00",...,"sky_code":"1","interval
// with no closing brace and no ellipsis. This helper appends an explicit
// ``…`` (U+2026) ellipsis so the citizen always knows the row is truncated.
//
// CC-side analog: ``utils/terminal.ts:renderTruncatedContent`` already does
// this for free-form text (``… +N lines``). The Lookup primitive renders
// each item as its own row, not a single content blob, so we keep the
// per-row helper rather than reusing renderTruncatedContent.

/**
 * Truncate a string to ``max`` columns, appending a single-codepoint ``…``
 * indicator (U+2026, 1 visible cell) when truncation occurs.
 *
 * - Returns the input unchanged when ``s.length <= max``.
 * - Reserves 1 character for the ellipsis when the input must be cut, so
 *   the visible width never exceeds ``max``.
 * - When ``max <= 1`` returns ``"…"`` (degenerate case).
 *
 * @param s   Plain-text or JSON-serialized string.
 * @param max Maximum visible width in characters (must be a positive integer).
 */
export function truncateJson(s: string, max: number): string {
  if (max <= 0) return ''
  if (s.length <= max) return s
  if (max === 1) return '…'
  return s.slice(0, max - 1) + '…'
}
