// SPDX-License-Identifier: Apache-2.0
/**
 * BackpressureHud tests — Spec 032 T038
 *
 * Test contract:
 * 1. Fixture frame ingestion → HUD text exact match
 *    "부처 API가 혼잡합니다. 15초 후 자동 재시도합니다."
 * 2. Countdown ticks: retry_after_ms decreases over time.
 * 3. signal="resume" → HUD not rendered.
 * 4. Null frame → HUD not rendered.
 * 5. signal="pause" → static HUD banner (no countdown).
 * 6. SC-003 render budget p95 < 16 ms (benchmark).
 *
 * Spec refs: FR-013, FR-015, SC-003, contracts/tx-dedup.contract.md § 5.1
 */

import { describe, expect, test, beforeEach, afterEach, mock } from 'bun:test'
import React from 'react'
import { render, cleanup } from 'ink-testing-library'
import { readFileSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { BackpressureHud } from '../../src/ipc/backpressure-hud.js'
import type { BackpressureSignalFrame } from '../../src/ipc/frames.generated.js'

const __dirname = dirname(fileURLToPath(import.meta.url))
const FIXTURES_DIR = join(__dirname, 'fixtures')

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function loadNdjsonFixture(filename: string): unknown[] {
  const raw = readFileSync(join(FIXTURES_DIR, filename), 'utf-8')
  return raw
    .split('\n')
    .filter(line => line.trim().length > 0)
    .map(line => JSON.parse(line))
}

function isBackpressureSignalFrame(
  value: unknown,
): value is BackpressureSignalFrame {
  if (typeof value !== 'object' || value === null) return false
  if (!('kind' in value) || value.kind !== 'backpressure') return false
  if (!('signal' in value)) return false
  return (
    value.signal === 'pause' ||
    value.signal === 'resume' ||
    value.signal === 'throttle'
  )
}

function makeThrottleFrame(retryAfterMs: number): BackpressureSignalFrame {
  return {
    version: '1.0',
    session_id: 'test-sess',
    correlation_id: 'test-corr',
    ts: '2026-04-19T12:00:00.000Z',
    role: 'backend',
    frame_seq: 1,
    transaction_id: null,
    trailer: null,
    kind: 'backpressure',
    signal: 'throttle',
    source: 'upstream_429',
    queue_depth: 48,
    hwm: 64,
    retry_after_ms: retryAfterMs,
    hud_copy_ko: `부처 API가 혼잡합니다. ${Math.ceil(retryAfterMs / 1000)}초 후 자동 재시도합니다.`,
    hud_copy_en: `Ministry API rate-limited. Retrying in ${Math.ceil(retryAfterMs / 1000)}s.`,
  } as BackpressureSignalFrame
}

function makePauseFrame(source: string = 'backend_writer'): BackpressureSignalFrame {
  return {
    version: '1.0',
    session_id: 'test-sess',
    correlation_id: 'test-corr',
    ts: '2026-04-19T12:00:00.000Z',
    role: 'backend',
    frame_seq: 2,
    transaction_id: null,
    trailer: null,
    kind: 'backpressure',
    signal: 'pause',
    source: source as BackpressureSignalFrame['source'],
    queue_depth: 64,
    hwm: 64,
    retry_after_ms: null,
    hud_copy_ko: '서비스가 일시적으로 지연됩니다. 잠시 기다려 주세요.',
    hud_copy_en: 'Backpressure detected. Pausing emission.',
  } as BackpressureSignalFrame
}

function makeResumeFrame(): BackpressureSignalFrame {
  return {
    version: '1.0',
    session_id: 'test-sess',
    correlation_id: 'test-corr',
    ts: '2026-04-19T12:00:15.000Z',
    role: 'backend',
    frame_seq: 3,
    transaction_id: null,
    trailer: null,
    kind: 'backpressure',
    signal: 'resume',
    source: 'upstream_429',
    queue_depth: 10,
    hwm: 64,
    retry_after_ms: null,
    hud_copy_ko: '서비스가 재개되었습니다.',
    hud_copy_en: 'Service resumed.',
  } as BackpressureSignalFrame
}

// ---------------------------------------------------------------------------
// Suite
// ---------------------------------------------------------------------------

describe('BackpressureHud', () => {
  afterEach(() => {
    cleanup()
  })

  // -------------------------------------------------------------------------
  // Test 1: Fixture frame ingestion — exact Korean text match
  // -------------------------------------------------------------------------

  test('renders exact Korean text from backpressure.throttle.ndjson fixture', () => {
    const lines = loadNdjsonFixture('backpressure.throttle.ndjson')
    const throttleLine = lines.find(
      (line): line is BackpressureSignalFrame =>
        isBackpressureSignalFrame(line) && line.signal === 'throttle',
    )
    expect(throttleLine).toBeDefined()
    if (throttleLine === undefined) {
      throw new Error('Expected throttle frame in fixture')
    }
    expect(throttleLine.retry_after_ms).toBe(15000)

    const { lastFrame } = render(
      React.createElement(BackpressureHud, { frame: throttleLine }),
    )
    const output = lastFrame()

    // Exact match for the canonical Korean HUD copy
    expect(output).toContain('부처 API가 혼잡합니다. 15초 후 자동 재시도합니다.')
  })

  // -------------------------------------------------------------------------
  // Test 2: Countdown ticks — initial state shows correct seconds
  // -------------------------------------------------------------------------

  test('initial countdown shows correct seconds from retry_after_ms=15000', () => {
    const frame = makeThrottleFrame(15000)
    const { lastFrame } = render(
      React.createElement(BackpressureHud, { frame }),
    )
    const output = lastFrame()
    // Should display 15초 (15 seconds rounded up)
    expect(output).toContain('15초')
  })

  test('countdown from 3000 ms shows 3초', () => {
    const frame = makeThrottleFrame(3000)
    const { lastFrame } = render(
      React.createElement(BackpressureHud, { frame }),
    )
    const output = lastFrame()
    expect(output).toContain('3초')
  })

  test('countdown from 1500 ms shows 2초 (ceiling)', () => {
    const frame = makeThrottleFrame(1500)
    const { lastFrame } = render(
      React.createElement(BackpressureHud, { frame }),
    )
    const output = lastFrame()
    // Math.ceil(1500 / 1000) = 2
    expect(output).toContain('2초')
  })

  // -------------------------------------------------------------------------
  // Test 3: signal="resume" → HUD not rendered
  // -------------------------------------------------------------------------

  test('renders nothing for signal=resume', () => {
    const frame = makeResumeFrame()
    const { lastFrame } = render(
      React.createElement(BackpressureHud, { frame }),
    )
    const output = lastFrame()
    expect(output).toBe('')
  })

  // -------------------------------------------------------------------------
  // Test 4: null frame → HUD not rendered
  // -------------------------------------------------------------------------

  test('renders nothing when frame is null', () => {
    const { lastFrame } = render(
      React.createElement(BackpressureHud, { frame: null }),
    )
    const output = lastFrame()
    expect(output).toBe('')
  })

  // -------------------------------------------------------------------------
  // Test 5: signal="pause" → static HUD banner displayed
  // -------------------------------------------------------------------------

  test('renders static Korean banner for signal=pause', () => {
    const frame = makePauseFrame('backend_writer')
    const { lastFrame } = render(
      React.createElement(BackpressureHud, { frame }),
    )
    const output = lastFrame()
    expect(output).toContain('서비스가 일시적으로 지연됩니다.')
  })

  test('pause frame with backend_writer source shows hud_copy_ko', () => {
    const frame = makePauseFrame('backend_writer')
    const { lastFrame } = render(
      React.createElement(BackpressureHud, { frame }),
    )
    // Must consume hud_copy_ko directly from frame (FR-015)
    expect(lastFrame()).toContain(frame.hud_copy_ko)
  })

  // -------------------------------------------------------------------------
  // Test 6: Dual-locale — hud_copy_ko consumed directly
  // -------------------------------------------------------------------------

  test('renders hud_copy_ko text directly from frame (FR-015)', () => {
    const frame: BackpressureSignalFrame = {
      ...makeThrottleFrame(20000),
      hud_copy_ko: '부처 API가 혼잡합니다. 20초 후 자동 재시도합니다.',
      hud_copy_en: 'Ministry rate-limited. Retry in 20s.',
      retry_after_ms: 20000,
    }
    const { lastFrame } = render(
      React.createElement(BackpressureHud, { frame }),
    )
    expect(lastFrame()).toContain('부처 API가 혼잡합니다.')
  })

  // -------------------------------------------------------------------------
  // Test 7: SC-003 render budget — p95 < 16 ms
  //
  // -------------------------------------------------------------------------

  test('SC-003: render p95 under 16 ms', () => {
    const frame = makeThrottleFrame(15000)
    const ITERATIONS = 100
    const times: number[] = []

    for (let i = 0; i < ITERATIONS; i++) {
      const start = performance.now()
      const { cleanup: c, lastFrame } = render(
        React.createElement(BackpressureHud, { frame }),
      )
      lastFrame() // force render
      const elapsed = performance.now() - start
      times.push(elapsed)
      c()
    }

    times.sort((a, b) => a - b)
    const p95 = times[Math.floor(ITERATIONS * 0.95)]
    // p95 must be under 16 ms (1 animation frame @ 60 Hz)
    expect(p95).toBeLessThan(16)
  })

  // -------------------------------------------------------------------------
  // Test 8: tui_reader source — pause frame renders correctly
  // -------------------------------------------------------------------------

  test('renders for signal=pause source=tui_reader', () => {
    const frame = makePauseFrame('tui_reader')
    const { lastFrame } = render(
      React.createElement(BackpressureHud, { frame }),
    )
    expect(lastFrame()).toContain(frame.hud_copy_ko)
  })

  // -------------------------------------------------------------------------
  // Test 9: Fixture resume line → no render
  // -------------------------------------------------------------------------

  test('resume line from fixture renders nothing', () => {
    const lines = loadNdjsonFixture('backpressure.throttle.ndjson')
    const resumeLine = lines.find(
      (line): line is BackpressureSignalFrame =>
        isBackpressureSignalFrame(line) && line.signal === 'resume',
    )
    expect(resumeLine).toBeDefined()
    if (resumeLine === undefined) {
      throw new Error('Expected resume frame in fixture')
    }

    const { lastFrame } = render(
      React.createElement(BackpressureHud, { frame: resumeLine }),
    )
    expect(lastFrame()).toBe('')
  })
})
