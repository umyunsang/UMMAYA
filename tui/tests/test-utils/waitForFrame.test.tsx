// SPDX-License-Identifier: Apache-2.0
// Spec: debug-infra-rebuild RFC § P1
//
// Verifies the waitForFrame / waitForText / waitForRegex / waitForStable
// helpers behave correctly:
//   - resolve immediately when predicate already true
//   - resolve after K state changes
//   - throw WaitForFrameTimeoutError with full diagnostic
//   - frame sequence de-dups consecutive identical states
//   - frameHash is deterministic

import { describe, expect, it } from 'bun:test'
import { render } from 'ink-testing-library'
import React, { useEffect, useState } from 'react'
import { Box, Text } from '../../src/ink.js'
import {
  WaitForFrameTimeoutError,
  frameHash,
  frameSequence,
  waitForFrame,
  waitForRegex,
  waitForStable,
  waitForText,
} from '../../src/test-utils/waitForFrame.js'

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

describe('waitForFrame helpers', () => {
  it('resolves immediately when predicate already true', async () => {
    const r = render(
      <Box>
        <Text>hello world</Text>
      </Box>,
    )
    const out = await waitForFrame(r, (f) => f.includes('hello'), {
      deadlineMs: 1000,
    })
    expect(out.matchedAt).toBeLessThan(50)
    expect(out.lastFrame).toContain('hello')
  })

  it('waits across state transitions and resolves on later frame', async () => {
    const r = render(
      <Stepper steps={['idle', 'loading', '● lookup(test)']} intervalMs={30} />,
    )
    const out = await waitForFrame(r, (f) => /● lookup/.test(f), {
      deadlineMs: 2000,
    })
    expect(out.matchedAt).toBeGreaterThan(40)
    expect(out.matchedAt).toBeLessThan(500)
    expect(out.lastFrame).toContain('● lookup')
    // Frames captured during the wait include the intermediate state(s).
    expect(out.frameCount).toBeGreaterThanOrEqual(2)
  })

  it('throws WaitForFrameTimeoutError with diagnostic on miss', async () => {
    const r = render(
      <Box>
        <Text>never matches</Text>
      </Box>,
    )
    let caught: unknown
    try {
      await waitForFrame(r, (f) => f.includes('전혀없는문자열'), {
        deadlineMs: 80,
        describe: 'unmatchable test',
      })
    } catch (e) {
      caught = e
    }
    expect(caught).toBeInstanceOf(WaitForFrameTimeoutError)
    const err = caught as WaitForFrameTimeoutError
    expect(err.deadlineMs).toBe(80)
    expect(err.describe).toBe('unmatchable test')
    expect(err.lastFrame).toContain('never matches')
    expect(err.message).toContain('80ms')
  })

  it('waitForText is sugar for substring match', async () => {
    const r = render(
      <Stepper steps={['boot', 'KOSMOS v0.1.0']} intervalMs={20} />,
    )
    const out = await waitForText(r, 'KOSMOS v0.1.0', { deadlineMs: 1000 })
    expect(out.lastFrame).toContain('KOSMOS')
  })

  it('waitForRegex matches a regex predicate', async () => {
    const r = render(<Stepper steps={['', '∴ Thinking']} intervalMs={20} />)
    const out = await waitForRegex(r, /∴ Thinking/, { deadlineMs: 1000 })
    expect(out.lastFrame).toMatch(/∴ Thinking/)
  })

  it('waitForStable resolves after stable window', async () => {
    const r = render(
      <Stepper
        steps={['t1', 't2', 't3', 'final answer paragraph']}
        intervalMs={30}
      />,
    )
    const out = await waitForStable(r, {
      stableMs: 200,
      deadlineMs: 2000,
      intervalMs: 30,
    })
    expect(out.lastFrame).toContain('final')
  })

  it('frameSequence de-dups consecutive identical states', () => {
    // Mock a render result with manually-stuffed frames array.
    const fake = {
      lastFrame: () => '',
      frames: ['a', 'a', 'a', 'b', 'b', 'c', 'a'],
    } as unknown as ReturnType<typeof render>
    const seq = frameSequence(fake)
    expect(seq.map((s) => s.preview)).toEqual(['a', 'b', 'c', 'a'])
    expect(seq[0]?.firstIndex).toBe(0)
    expect(seq[0]?.lastIndex).toBe(2)
    expect(seq[1]?.firstIndex).toBe(3)
    expect(seq[1]?.lastIndex).toBe(4)
    expect(seq[2]?.firstIndex).toBe(5)
    expect(seq[3]?.firstIndex).toBe(6)
  })

  it('frameHash is deterministic for the same input', () => {
    expect(frameHash('hello world')).toBe(frameHash('hello world'))
    expect(frameHash('a')).not.toBe(frameHash('b'))
    // 8-char hex
    expect(frameHash('test')).toMatch(/^[0-9a-f]{8}$/)
  })
})
