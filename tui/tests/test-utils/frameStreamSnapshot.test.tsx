// SPDX-License-Identifier: Apache-2.0
// Spec: debug-infra-rebuild RFC § P3 + § P4 (2026-05-02)
//
// Unit tests for:
//   - assertFrameSequence (sequence hash assertion)
//   - takeStreamSnapshot  (capture hashes + previews)
//   - useFrameCommitTracker (OTEL hook no-op in uninitialised env)

import { describe, expect, it, beforeEach } from 'bun:test'
import { render } from 'ink-testing-library'
import React, { useEffect, useState } from 'react'
import { Box, Text } from '../../src/ink.js'
import {
  assertFrameSequence,
  takeStreamSnapshot,
  frameHash,
} from '../../src/test-utils/frameStreamSnapshot.js'
import { waitForText } from '../../src/test-utils/waitForFrame.js'
import { useFrameCommitTracker, _resetSeqCounters } from '../../src/utils/frameCommitOtel.js'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Simple stepping component used across multiple tests. */
function Stepper({ steps, intervalMs }: { steps: string[]; intervalMs: number }) {
  const [idx, setIdx] = useState(0)
  useEffect(() => {
    if (idx >= steps.length - 1) return
    const t = setTimeout(() => setIdx(idx + 1), intervalMs)
    return () => clearTimeout(t)
  }, [idx, steps.length, intervalMs])
  return (
    <Box>
      <Text>{steps[idx]}</Text>
    </Box>
  )
}

/** Fake render result with pre-set frames — lets us unit-test without real Ink renders. */
function fakeResult(frames: string[]) {
  return {
    lastFrame: () => frames[frames.length - 1] ?? '',
    frames,
  } as unknown as ReturnType<typeof render>
}

beforeEach(() => {
  _resetSeqCounters()
})

// ---------------------------------------------------------------------------
// assertFrameSequence
// ---------------------------------------------------------------------------

describe('assertFrameSequence', () => {
  it('passes for matching sequence (exact hashes)', () => {
    const fake = fakeResult(['idle', 'loading', 'done'])
    // Build expected from the same frames
    const expected = ['idle', 'loading', 'done'].map(frameHash)
    // Should not throw
    assertFrameSequence(fake, expected)
  })

  it('passes for matching sequence using RegExp per slot', () => {
    const fake = fakeResult(['boot', 'ready'])
    // All 8-char hex hashes match the regex
    assertFrameSequence(fake, [/^[0-9a-f]{8}$/, /^[0-9a-f]{8}$/])
  })

  it('fails with diff diagnostic on hash mismatch', () => {
    const fake = fakeResult(['idle', 'loading', 'done'])
    const wrong = ['wrong-a', 'wrong-b', 'wrong-c'].map(frameHash)
    let thrown: Error | undefined
    try {
      assertFrameSequence(fake, wrong, { strict: true })
    } catch (e) {
      thrown = e as Error
    }
    expect(thrown).toBeDefined()
    expect(thrown?.message).toContain('assertFrameSequence failed')
    // Diagnostic must include both actual and expected hash values
    expect(thrown?.message).toContain('actual=')
    expect(thrown?.message).toContain('expected=')
    // Must show the mismatched index count
    expect(thrown?.message).toContain('mismatch')
  })

  it('fails with preview lines in diagnostic for debugging', () => {
    const fake = fakeResult(['KOSMOS boot', 'KOSMOS thinking', 'KOSMOS result'])
    const wrong = [frameHash('different-a'), frameHash('different-b')]
    let thrown: Error | undefined
    try {
      assertFrameSequence(fake, wrong)
    } catch (e) {
      thrown = e as Error
    }
    expect(thrown?.message).toContain('frame previews')
    // The actual frame content should appear in the diagnostic
    expect(thrown?.message).toContain('KOSMOS')
  })

  it('dedup of consecutive identical frames — de-duplicated sequence is asserted', () => {
    // [a, a, a, b, b, c] de-dupes to [a, b, c]
    const fake = fakeResult(['alpha', 'alpha', 'alpha', 'beta', 'beta', 'gamma'])
    const expected = ['alpha', 'beta', 'gamma'].map(frameHash)
    // strict: sequence length must be exactly 3 after dedup
    assertFrameSequence(fake, expected, { strict: true })
  })

  it('non-strict (default) allows extra trailing frames after expected', () => {
    // render produced 4 de-duped frames but we only care about first 2
    const fake = fakeResult(['first', 'second', 'third', 'fourth'])
    const expected = ['first', 'second'].map(frameHash)
    // default strict=false → should pass
    assertFrameSequence(fake, expected)
  })

  it('strict mode fails when actual has extra frames beyond expected', () => {
    const fake = fakeResult(['first', 'second', 'third'])
    const expected = ['first', 'second'].map(frameHash)
    let thrown: Error | undefined
    try {
      assertFrameSequence(fake, expected, { strict: true })
    } catch (e) {
      thrown = e as Error
    }
    expect(thrown).toBeDefined()
    expect(thrown?.message).toContain('extra actual frame')
  })

  it('works end-to-end with a real Ink render + waitForText', async () => {
    const r = render(
      <Stepper steps={['idle', 'loading', '● lookup']} intervalMs={20} />,
    )
    await waitForText(r, '● lookup', { deadlineMs: 2000 })
    const expected = ['idle', 'loading', '● lookup'].map(frameHash)
    // non-strict: extra settle frames may appear
    assertFrameSequence(r, expected)
  })
})

// ---------------------------------------------------------------------------
// takeStreamSnapshot
// ---------------------------------------------------------------------------

describe('takeStreamSnapshot', () => {
  it('returns hashes and previews arrays of equal length', () => {
    const fake = fakeResult(['alpha', 'beta', 'gamma'])
    const snap = takeStreamSnapshot(fake)
    expect(snap.hashes).toHaveLength(3)
    expect(snap.previews).toHaveLength(3)
    expect(snap.sequence).toHaveLength(3)
    expect(snap.hashes.length).toBe(snap.previews.length)
  })

  it('de-dups consecutive identical frames in the snapshot', () => {
    const fake = fakeResult(['a', 'a', 'b', 'b', 'b', 'c'])
    const snap = takeStreamSnapshot(fake)
    expect(snap.hashes).toHaveLength(3)
    expect(snap.previews).toHaveLength(3)
  })

  it('hashes match frameHash of each preview text', () => {
    const frames = ['KOSMOS boot', 'KOSMOS thinking', 'KOSMOS done']
    const fake = fakeResult(frames)
    const snap = takeStreamSnapshot(fake)
    for (let i = 0; i < frames.length; i++) {
      expect(snap.hashes[i]).toBe(frameHash(frames[i]!))
    }
  })

  it('previews are truncated to 80 chars', () => {
    const longFrame = 'x'.repeat(200)
    const fake = fakeResult([longFrame])
    const snap = takeStreamSnapshot(fake)
    expect(snap.previews[0]?.length).toBeLessThanOrEqual(80)
  })

  it('sequence entries carry firstIndex + lastIndex span', () => {
    const fake = fakeResult(['same', 'same', 'diff'])
    const snap = takeStreamSnapshot(fake)
    expect(snap.sequence[0]?.firstIndex).toBe(0)
    expect(snap.sequence[0]?.lastIndex).toBe(1)
    expect(snap.sequence[1]?.firstIndex).toBe(2)
    expect(snap.sequence[1]?.lastIndex).toBe(2)
  })
})

// ---------------------------------------------------------------------------
// useFrameCommitTracker — no-op when OTEL uninitialised
// ---------------------------------------------------------------------------

describe('useFrameCommitTracker', () => {
  it('is a no-op when OTEL is uninitialised (test env) — does not throw', () => {
    // In Bun test env, @opentelemetry/api is loaded but not initialised
    // (no SDK provider). trace.getTracer() returns a no-op tracer.
    // This test confirms the hook mounts + renders without throwing.
    function Fixture() {
      useFrameCommitTracker('test-correlation-id')
      return (
        <Box>
          <Text>otel fixture</Text>
        </Box>
      )
    }
    const r = render(<Fixture />)
    expect(r.lastFrame()).toContain('otel fixture')
  })

  it('does not throw when correlationId is undefined', () => {
    function Fixture() {
      useFrameCommitTracker()
      return (
        <Box>
          <Text>no cid</Text>
        </Box>
      )
    }
    const r = render(<Fixture />)
    expect(r.lastFrame()).toContain('no cid')
  })

  it('emits per-render — renders multiple times without error', async () => {
    function Counter({ n }: { n: number }) {
      useFrameCommitTracker('multi-render-test')
      return (
        <Box>
          <Text>count={n}</Text>
        </Box>
      )
    }
    // Render with different props to force multiple re-renders
    const r = render(<Counter n={1} />)
    expect(r.lastFrame()).toContain('count=1')
    r.rerender(<Counter n={2} />)
    expect(r.lastFrame()).toContain('count=2')
    r.rerender(<Counter n={3} />)
    expect(r.lastFrame()).toContain('count=3')
  })
})
