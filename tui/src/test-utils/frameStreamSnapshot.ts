// SPDX-License-Identifier: Apache-2.0
// KOSMOS-original — observability/spec(debug-infra-rebuild RFC § P3 + § P4 2026-05-02)
//
// frameStreamSnapshot — per-render Ink snapshot stream helpers.
//
// Permanently retires AGENTS.md anti-pattern #1 ("Final-state fallacy") at the
// test-helper layer. Every distinct frame hash in the render sequence is
// asserted, not just `lastFrame()`.
//
// Pattern source:
//   react-render-stream-testing-library "takeSnapshot after every render"
//   https://github.com/testing-library/react-render-stream-testing-library
//   Adapted for ink-testing-library's `frames` array.
//
// Exports:
//   assertFrameSequence(result, expected, opts?) — sequence hash assertion
//   takeStreamSnapshot(result)                   — capture hashes + previews

import type { render } from 'ink-testing-library'
import { frameHash, frameSequence, type FrameSequenceEntry } from './waitForFrame.js'

type RenderResult = ReturnType<typeof render>

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

export interface AssertFrameSequenceOpts {
  /**
   * When true the de-duplicated sequence length must EXACTLY equal expected.
   * When false (default) the sequence must CONTAIN the expected hashes as a
   * contiguous subsequence — trailing frames not in expected are ignored.
   * Use strict=false for async tests where extra settle frames may appear.
   */
  strict?: boolean
}

export interface StreamSnapshot {
  /** FNV-1a hash per de-duplicated frame (in order). */
  hashes: string[]
  /** First 80 chars of each de-duplicated frame (in order). */
  previews: string[]
  /** Full FrameSequenceEntry entries (includes firstIndex, lastIndex). */
  sequence: FrameSequenceEntry[]
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/**
 * Build a human-readable diff-like diagnostic for two string sequences.
 * Produces "+ actual" / "- expected" lines similar to unified diff.
 */
function buildDiff(actual: string[], expected: Array<string | RegExp>): string {
  const maxLen = Math.max(actual.length, expected.length)
  const lines: string[] = ['  Sequence mismatch (actual vs expected):']
  for (let i = 0; i < maxLen; i++) {
    const a = actual[i] ?? '(missing)'
    const e = expected[i]
    if (e === undefined) {
      lines.push(`  [${i}] + ${a}  (extra actual frame)`)
    } else if (typeof e === 'string') {
      const match = a === e
      lines.push(`  [${i}] ${match ? '=' : '!'} actual="${a}" expected="${e}"`)
    } else {
      const match = e.test(a)
      lines.push(`  [${i}] ${match ? '=' : '!'} actual="${a}" expected=${e}`)
    }
  }
  return lines.join('\n')
}

// ---------------------------------------------------------------------------
// Exported helpers
// ---------------------------------------------------------------------------

/**
 * Assert that the de-duplicated frame hash sequence of a rendered Ink
 * component matches `expected`.
 *
 * Each element of `expected` may be:
 *   - a string hash (8-char hex from `frameHash()`) — exact match
 *   - a RegExp — tested against the 8-char hash string
 *
 * By default (strict=false) the sequence must START WITH the expected
 * entries; additional trailing frames are allowed.
 *
 * @example
 *   const r = render(<Stepper steps={['idle', 'loading', 'done']} />)
 *   await waitForText(r, 'done')
 *   assertFrameSequence(r, [
 *     frameHash('idle'),
 *     frameHash('loading'),
 *     frameHash('done'),
 *   ])
 */
export function assertFrameSequence(
  result: RenderResult,
  expected: Array<string | RegExp>,
  opts: AssertFrameSequenceOpts = {},
): void {
  const seq = frameSequence(result)
  const actualHashes = seq.map((e) => e.hash)
  const strict = opts.strict ?? false

  const compareLen = strict ? Math.max(actualHashes.length, expected.length) : expected.length
  const mismatches: number[] = []

  for (let i = 0; i < compareLen; i++) {
    const a = actualHashes[i]
    const e = expected[i]
    if (e === undefined) {
      // strict mode: extra actual frames are a mismatch
      if (strict) mismatches.push(i)
      continue
    }
    if (a === undefined) {
      mismatches.push(i)
      continue
    }
    if (typeof e === 'string') {
      if (a !== e) mismatches.push(i)
    } else {
      if (!e.test(a)) mismatches.push(i)
    }
  }

  if (mismatches.length > 0) {
    const diff = buildDiff(actualHashes, expected)
    const previews = seq.map((e, i) => `  [${i}] hash=${e.hash} preview="${e.preview}"`).join('\n')
    throw new Error(
      `assertFrameSequence failed — ${mismatches.length} mismatch(es) at index [${mismatches.join(', ')}].\n` +
        diff +
        '\n\nActual frame previews:\n' +
        previews,
    )
  }
}

/**
 * Capture the current render stream as hashes + previews for deferred
 * assertion. Useful in incremental tests that want to inspect intermediate
 * states before calling `assertFrameSequence`.
 *
 * @example
 *   const r = render(<App />)
 *   await waitForText(r, '● lookup')
 *   const snap = takeStreamSnapshot(r)
 *   expect(snap.hashes).toHaveLength(3)
 *   expect(snap.previews[0]).toContain('KOSMOS')
 */
export function takeStreamSnapshot(result: RenderResult): StreamSnapshot {
  const seq = frameSequence(result)
  return {
    hashes: seq.map((e) => e.hash),
    previews: seq.map((e) => e.preview),
    sequence: seq,
  }
}

// Re-export frameHash so callers can build expected arrays without a second
// import from waitForFrame.
export { frameHash } from './waitForFrame.js'
