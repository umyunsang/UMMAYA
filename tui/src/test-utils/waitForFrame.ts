// SPDX-License-Identifier: Apache-2.0
// Spec: debug-infra-rebuild RFC § P1 (2026-05-02)
//
// Polled-with-deadline helper for ink-testing-library — replaces every
// hardcoded `Sleep <wallclock>` in .expect / .tape scripts.
//
// Pattern is the Ink port of Bubble Tea's teatest WaitFor predicate:
// https://carlosbecker.com/posts/teatest/
// https://patternmatched.substack.com/p/testing-bubble-tea-interfaces
//
// Why this exists:
//
// AGENTS.md anti-pattern #1 ("Final-state fallacy") is the user reading
// `lastFrame()` only. Spec 2521 made the deeper failure visible:
// hardcoded `Sleep 6` in expect scripts can't bound K-EXAONE on FriendliAI
// reasoning latency (30-90s natural variance). The test either
//   (a) sleeps long enough → CI is slow, or
//   (b) sleeps short → false-fail, "TUI is hung" when LLM is just slow.
//
// `waitForFrame(predicate, { deadlineMs })` polls every 10ms until either
// the predicate matches (return matchedAt) or the deadline elapses
// (throw with full diagnostic frame snapshot). The deadline is the only
// wall-clock bound — match latency is bounded by intervalMs (10ms).

import type { render } from 'ink-testing-library'

type RenderResult = ReturnType<typeof render>

export interface WaitForFrameOpts {
  /** Polling interval in ms. Default 10. */
  intervalMs?: number
  /** Wall-clock deadline in ms. Default 10_000. */
  deadlineMs?: number
  /**
   * Human-readable description of what we're waiting for. Surfaces in
   * the timeout error so failures are self-diagnosing.
   */
  describe?: string
}

export interface WaitForFrameResult {
  /** Wall-clock ms from call to predicate match. */
  matchedAt: number
  /** Total frames captured so far (cumulative since render). */
  frameCount: number
  /** The lastFrame() that satisfied the predicate. */
  lastFrame: string
  /** All frames captured so far — for sequence assertions. */
  frames: string[]
}

function getFrames(result: RenderResult): string[] {
  // ink-testing-library exposes `frames` as an array on the render result.
  // Cast through unknown because the type declaration omits the array.
  const r = result as unknown as { frames?: string[] }
  return r.frames ?? []
}

/**
 * Poll lastFrame() / frames every intervalMs until predicate matches
 * or the wall-clock deadline elapses.
 *
 * @example
 *   const r = render(<App />)
 *   r.stdin.write('부산 날씨 알려줘\r')
 *   await waitForFrame(
 *     r,
 *     (last) => /● lookup/.test(last),
 *     { describe: 'first tool_call paint', deadlineMs: 30_000 },
 *   )
 */
export async function waitForFrame(
  result: RenderResult,
  predicate: (lastFrame: string, allFrames: readonly string[]) => boolean,
  opts: WaitForFrameOpts = {},
): Promise<WaitForFrameResult> {
  const intervalMs = opts.intervalMs ?? 10
  const deadlineMs = opts.deadlineMs ?? 10_000
  const start = Date.now()
  // First check is synchronous so a predicate that's already true returns
  // matchedAt=0 instead of paying one intervalMs.
  while (true) {
    const last = result.lastFrame() ?? ''
    const all = getFrames(result)
    if (predicate(last, all)) {
      return {
        matchedAt: Date.now() - start,
        frameCount: all.length,
        lastFrame: last,
        frames: all.slice(),
      }
    }
    if (Date.now() - start >= deadlineMs) {
      throw new WaitForFrameTimeoutError({
        deadlineMs,
        describe: opts.describe ?? '(no describe given)',
        frameCount: all.length,
        lastFrame: last,
        frames: all,
      })
    }
    await new Promise((r) => setTimeout(r, intervalMs))
  }
}

/**
 * Convenience: wait for a substring (literal) in lastFrame().
 *
 * @example
 *   await waitForText(r, '● lookup', { deadlineMs: 30_000 })
 */
export async function waitForText(
  result: RenderResult,
  needle: string,
  opts: WaitForFrameOpts = {},
): Promise<WaitForFrameResult> {
  return waitForFrame(
    result,
    (last) => last.includes(needle),
    { ...opts, describe: opts.describe ?? `text "${needle}"` },
  )
}

/**
 * Convenience: wait for a regex match in lastFrame().
 *
 * @example
 *   await waitForRegex(r, /⏿ Thinking/, { deadlineMs: 60_000 })
 */
export async function waitForRegex(
  result: RenderResult,
  pattern: RegExp,
  opts: WaitForFrameOpts = {},
): Promise<WaitForFrameResult> {
  return waitForFrame(
    result,
    (last) => pattern.test(last),
    { ...opts, describe: opts.describe ?? `regex ${pattern}` },
  )
}

/**
 * Wait until the screen has been STABLE for `stableMs` consecutive ms
 * (no new distinct frames). Useful as the final settle before a full
 * snapshot assertion — replaces `Sleep 8` for "let the answer settle".
 *
 * @example
 *   await waitForStable(r, { stableMs: 1500, deadlineMs: 60_000 })
 */
export async function waitForStable(
  result: RenderResult,
  opts: { stableMs?: number; deadlineMs?: number; intervalMs?: number } = {},
): Promise<WaitForFrameResult> {
  const stableMs = opts.stableMs ?? 1000
  const deadlineMs = opts.deadlineMs ?? 30_000
  const intervalMs = opts.intervalMs ?? 50
  const start = Date.now()
  let lastSnapshot = result.lastFrame() ?? ''
  let lastChangeAt = Date.now()
  while (Date.now() - start < deadlineMs) {
    await new Promise((r) => setTimeout(r, intervalMs))
    const cur = result.lastFrame() ?? ''
    if (cur !== lastSnapshot) {
      lastSnapshot = cur
      lastChangeAt = Date.now()
      continue
    }
    if (Date.now() - lastChangeAt >= stableMs) {
      const all = getFrames(result)
      return {
        matchedAt: Date.now() - start,
        frameCount: all.length,
        lastFrame: cur,
        frames: all.slice(),
      }
    }
  }
  const all = getFrames(result)
  throw new WaitForFrameTimeoutError({
    deadlineMs,
    describe: `stable for ${stableMs}ms`,
    frameCount: all.length,
    lastFrame: lastSnapshot,
    frames: all,
  })
}

/**
 * Hash a frame to a 12-char prefix for snapshot-stream assertions.
 * Bun's stdlib subtle.digest is overkill here — a simple FNV-1a is
 * sufficient for de-dup keys and reads obvious in test failures.
 */
export function frameHash(frame: string): string {
  let h = 0x811c9dc5
  for (let i = 0; i < frame.length; i++) {
    h ^= frame.charCodeAt(i)
    h = Math.imul(h, 0x01000193) >>> 0
  }
  return h.toString(16).padStart(8, '0')
}

/**
 * Per-render snapshot stream — the AGENTS.md anti-pattern #1
 * (Final-state fallacy) cure. Returns one entry per *distinct* frame
 * with hash + first/last index of each unique state.
 */
export interface FrameSequenceEntry {
  hash: string
  firstIndex: number
  lastIndex: number
  preview: string // first 80 chars of the frame
}

export function frameSequence(result: RenderResult): FrameSequenceEntry[] {
  const all = getFrames(result)
  const seq: FrameSequenceEntry[] = []
  for (let i = 0; i < all.length; i++) {
    const f = all[i] ?? ''
    const h = frameHash(f)
    const last = seq[seq.length - 1]
    if (last && last.hash === h) {
      last.lastIndex = i
      continue
    }
    seq.push({
      hash: h,
      firstIndex: i,
      lastIndex: i,
      preview: f.replace(/\s+/g, ' ').slice(0, 80),
    })
  }
  return seq
}

export class WaitForFrameTimeoutError extends Error {
  readonly deadlineMs: number
  readonly describe: string
  readonly frameCount: number
  readonly lastFrame: string
  readonly frames: readonly string[]
  constructor(args: {
    deadlineMs: number
    describe: string
    frameCount: number
    lastFrame: string
    frames: readonly string[]
  }) {
    super(
      `waitForFrame timeout after ${args.deadlineMs}ms ` +
        `(${args.describe}). Captured ${args.frameCount} frames. ` +
        `Last frame:\n${args.lastFrame}`,
    )
    this.name = 'WaitForFrameTimeoutError'
    this.deadlineMs = args.deadlineMs
    this.describe = args.describe
    this.frameCount = args.frameCount
    this.lastFrame = args.lastFrame
    this.frames = args.frames
  }
}
