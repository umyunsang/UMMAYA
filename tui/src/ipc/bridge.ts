// SPDX-License-Identifier: Apache-2.0
// KOSMOS-original — no upstream analog (Claude Code uses HTTP SSE, not stdio JSONL).
//
// IPC Bridge: spawns the Python backend and exposes a typed async interface.
//
// Design decisions:
//   - Uses Bun.spawn() with { stdin: "pipe", stdout: "pipe", stderr: "pipe" }
//     because Bun#4670 blocks extra fds; all IPC must fit on stdin/stdout/stderr.
//   - stdout frames are pushed into a FIFO async queue (no reordering).
//   - DEBUG-level frame logging controlled by KOSMOS_TUI_LOG_LEVEL (FR-010).
//   - crashDetector is wired via crash-detector.ts; this module only exposes
//     the send/close/frames API surface.
//
// FR-054 (fire-and-forget telemetry hook):
//   - Callers may attach bridge.onFrame to observe frame events with latency.
//   - Implementations MUST return synchronously and MUST NOT throw.
//   - If an implementation throws or returns a rejected Promise the bridge
//     swallows the error via a queueMicrotask wrapper so the frame-dispatch
//     loop is never blocked.
//   - OTEL span emission lives in the Python backend (Spec 031 / T121).
//     The TUI surfaces metrics only through this hook + the store subscriber
//     pattern; no opentelemetry-sdk dependency is added to the TUI package.
//
// US1 (T025) Reconnect loop:
//   - EOF / EPIPE on stdout triggers exponential-backoff reconnect.
//   - On reconnect, emits ResumeRequestFrame(frame_seq=0) as the first frame.
//   - Incoming replayed frames are de-duplicated via applied_frame_seqs Set.
//   - crash-detector.ts signals drops via onDrop() callback (T026).

import { decodeFrames, encodeFrame } from './codec'
import { startCrashDetector } from './crash-detector'
import type { IPCFrame, ResumeRequestFrame } from './frames.generated'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/**
 * FR-054 telemetry hook.
 *
 * Called fire-and-forget after every frame is pushed to the dispatch queue.
 * Implementations MUST:
 *   - return synchronously (or return void — a resolved Promise is fine)
 *   - never throw (errors are caught and logged at WARN level)
 *
 * The hook is invoked inside a queueMicrotask() wrapper so it cannot block
 * the frame-dispatch loop under any circumstances.
 */
export type FrameHook = (
  frame: IPCFrame,
  direction: 'recv' | 'send',
  latencyMs: number,
) => void

export interface BridgeOptions {
  /**
   * Command to spawn.  Defaults to ['uv', 'run', 'kosmos', '--ipc', 'stdio'].
   * Override via KOSMOS_BACKEND_CMD env var (space-split) or this option.
   */
  cmd?: string[]
  /**
   * Milliseconds to wait for the backend process to start before considering
   * it as having crashed.  Default: 5000.
   */
  startupTimeoutMs?: number
  /**
   * Called whenever a crash is detected (non-zero exit or fatal stderr).
   * The bridge emits a synthetic error frame to the store separately via the
   * crash-detector; this hook is for callers who need additional side-effects.
   */
  onCrash?: (notice: CrashNotice) => void
  /**
   * FR-054 fire-and-forget telemetry hook.
   * Invoked in a queueMicrotask after each frame is dispatched or sent.
   * Must not throw; errors are caught and logged at WARN level.
   */
  onFrame?: FrameHook

  // ------------------------------------------------------------------
  // US1 reconnect options (T025)
  // ------------------------------------------------------------------

  /**
   * Session ID for resume handshake. Must be set by caller once a session
   * is established; bridged into ResumeRequestFrame.session_id.
   */
  sessionId?: string
  /**
   * Opaque TUI session token minted by the backend on initial handshake.
   * Required in ResumeRequestFrame.tui_session_token (FR-019).
   */
  tuiSessionToken?: string
  /**
   * Maximum number of reconnect attempts before giving up (default: 5).
   */
  maxReconnectAttempts?: number
  /**
   * Initial backoff delay in ms (default: 500).  Doubles each retry up to
   * maxBackoffMs.
   */
  initialBackoffMs?: number
  /**
   * Cap for exponential backoff (default: 30000).
   */
  maxBackoffMs?: number
  /**
   * Called when a reconnect attempt is made (for UI feedback).
   */
  onReconnect?: (attempt: number, delayMs: number) => void
  /**
   * Called after all reconnect attempts are exhausted without success.
   */
  onReconnectFailed?: () => void

  /**
   * Additional env vars to merge onto the backend subprocess environment
   * (on top of the inherited process env). Used primarily by tests to select
   * the `echo` handler via `{ KOSMOS_IPC_HANDLER: 'echo' }` without needing
   * a FriendliAI session on the CI runner.
   */
  env?: Record<string, string>
}

export interface CrashNotice {
  exitCode: number | null
  stderrTail: string
  redactedStderrTail: string
}

export interface IPCBridge {
  /**
   * Send a frame to the Python backend via stdin.
   * Returns false if the backend has already exited.
   */
  send(frame: IPCFrame): boolean
  /**
   * Async iterable of decoded frames from the backend.
   * Yields until the bridge is closed or the process exits.
   */
  frames(): AsyncIterable<IPCFrame>
  /** Gracefully close the bridge (SIGTERM → 3 s → SIGKILL). */
  close(): Promise<void>
  /** Underlying Bun subprocess (for crash detector, tests, etc.) */
  readonly proc: ReturnType<typeof Bun.spawn>
  /**
   * FR-054 fire-and-forget telemetry hook.
   * May be set or replaced at any time after bridge creation.
   * Invoked in a queueMicrotask after each dispatched/sent frame.
   */
  onFrame?: FrameHook

  // ------------------------------------------------------------------
  // US1 extensions (T025)
  // ------------------------------------------------------------------

  /**
   * Set of (session_id + ':' + frame_seq) strings already applied by the TUI.
   * Populated during replay; callers check this set to skip duplicate frames.
   * Exposed for test assertions in T031.
   */
  readonly applied_frame_seqs: Set<string>

  /**
   * Update session credentials for future ResumeRequestFrame emissions.
   * Should be called when the backend sends a session_event(kind="started").
   */
  setSessionCredentials(sessionId: string, tuiSessionToken: string): void

  /**
   * Last seen correlation_id and frame_seq — tracked across reconnects for
   * populating ResumeRequestFrame fields.
   */
  readonly lastSeenCorrelationId: string | null
  readonly lastSeenFrameSeq: number | null

  /**
   * Signal an EOF/EPIPE drop to the bridge so it can initiate reconnect.
   * Called by crash-detector.ts on stdin EOF (T026 coupling).
   */
  signalDrop(): void
}

// ---------------------------------------------------------------------------
// Log helper (FR-010: KOSMOS_TUI_LOG_LEVEL)
// ---------------------------------------------------------------------------

type LogLevel = 'DEBUG' | 'INFO' | 'WARN' | 'ERROR'

const _levelOrder: Record<LogLevel, number> = {
  DEBUG: 0, INFO: 1, WARN: 2, ERROR: 3,
}

function _getLogLevel(): LogLevel {
  const raw = (process.env['KOSMOS_TUI_LOG_LEVEL'] ?? 'WARN').toUpperCase()
  if (raw in _levelOrder) return raw as LogLevel
  return 'WARN'
}

function _log(level: LogLevel, ...args: unknown[]): void {
  if (_levelOrder[level] >= _levelOrder[_getLogLevel()]) {
    // CRITICAL: writes go to stderr only — the stdout channel carries pure
    // NDJSON IPC frames consumed by the parent harness. Mixing log output
    // into stdout corrupts the frame parser (Spec 032 FR-035 fail-closed
    // drop-and-log) and breaks PTY scenarios (Spec 1978 T002 regression
    // guard — see docs/spec-1978/B1-root-cause-trace.md). Do NOT switch to
    // console.log here even temporarily.
    process.stderr.write(`[KOSMOS IPC ${level}] ${args.map(String).join(' ')}\n`)
  }
}

// ---------------------------------------------------------------------------
// Async FIFO queue (single-producer, single-consumer)
// ---------------------------------------------------------------------------

class AsyncQueue<T> {
  private _queue: T[] = []
  private _resolve: ((value: IteratorResult<T>) => void) | null = null
  private _closed = false

  push(item: T): void {
    if (this._closed) return
    if (this._resolve) {
      const r = this._resolve
      this._resolve = null
      r({ value: item, done: false })
    } else {
      this._queue.push(item)
    }
  }

  close(): void {
    this._closed = true
    if (this._resolve) {
      this._resolve({ value: undefined as unknown as T, done: true })
      this._resolve = null
    }
  }

  get closed(): boolean {
    return this._closed
  }

  [Symbol.asyncIterator](): AsyncIterator<T> {
    return {
      next: (): Promise<IteratorResult<T>> => {
        if (this._queue.length > 0) {
          return Promise.resolve({ value: this._queue.shift()!, done: false })
        }
        if (this._closed) {
          return Promise.resolve({ value: undefined as unknown as T, done: true })
        }
        return new Promise((resolve) => {
          this._resolve = resolve
        })
      },
    }
  }
}

// ---------------------------------------------------------------------------
// UUIDv7 helper (no external deps — Bun stdlib crypto)
// ---------------------------------------------------------------------------

function _uuidv7(): string {
  // Construct a UUIDv7: 48-bit ms timestamp + 4-bit version(7) + 12-bit rand
  //                   + 2-bit variant(10) + 62-bit rand
  const now = Date.now()
  const tsHex = now.toString(16).padStart(12, '0')
  const rand = crypto.getRandomValues(new Uint8Array(10))
  const randHex = Array.from(rand).map(b => b.toString(16).padStart(2, '0')).join('')
  // version bits: 7 → 0111; variant bits: 10 → 10xx
  const ver = '7'
  const varByte = ((rand[0]! & 0x3f) | 0x80).toString(16).padStart(2, '0')
  const remaining = randHex.slice(2)
  return `${tsHex.slice(0, 8)}-${tsHex.slice(8, 12)}-${ver}${randHex.slice(0, 3)}-${varByte}${randHex.slice(3, 5)}-${remaining.slice(0, 12)}`
}

// ---------------------------------------------------------------------------
// createBridge
// ---------------------------------------------------------------------------

/**
 * Spawn the Python backend and return an {@link IPCBridge}.
 *
 * The bridge:
 * 1. Resolves the backend command (option > env var > default).
 * 2. Spawns the process with stdio pipes.
 * 3. Starts a stdout reader that splits on `\n` and decodes frames into the
 *    internal FIFO queue.
 * 4. Wires the crash-detector to watch for non-zero exit / fatal stderr.
 * 5. Exposes `send()`, `frames()`, and `close()`.
 * 6. (US1 T025) On EOF/EPIPE, initiates exponential-backoff reconnect loop
 *    and emits ResumeRequestFrame as first frame after reconnect.
 */
export function createBridge(opts: BridgeOptions = {}): IPCBridge {
  // Resolve command
  const envCmd = process.env['KOSMOS_BACKEND_CMD']
  const defaultCmd = ['uv', 'run', 'kosmos', '--ipc', 'stdio']
  const cmd: string[] = opts.cmd ?? (envCmd ? envCmd.split(' ') : defaultCmd)

  // Reconnect config
  const maxReconnectAttempts = opts.maxReconnectAttempts ?? 5
  const initialBackoffMs = opts.initialBackoffMs ?? 500
  const maxBackoffMs = opts.maxBackoffMs ?? 30_000

  _log('INFO', `Spawning backend: ${cmd.join(' ')}`)

  // ------------------------------------------------------------------
  // Mutable session state (shared across reconnects — US1)
  // ------------------------------------------------------------------
  let _sessionId: string | null = opts.sessionId ?? null
  let _tuiSessionToken: string | null = opts.tuiSessionToken ?? null
  let _lastSeenCorrelationId: string | null = null
  let _lastSeenFrameSeq: number | null = null
  // Bounded ring of applied (session_id, frame_seq) keys for replay-dedup.
  // Cap mirrors the backend SessionRingBuffer size (Spec 032: 256 frames);
  // oldest entries are evicted via FIFO replacement so the Set cannot grow
  // unbounded across long sessions.
  const _APPLIED_FRAME_SEQS_CAP = 256
  const _appliedFrameSeqs = new Set<string>()
  const _appliedFrameSeqsOrder: string[] = []

  // ------------------------------------------------------------------
  // Spawn first process
  // ------------------------------------------------------------------
  const spawnEnv = opts.env
    ? ({ ...process.env, ...opts.env } as Record<string, string>)
    : (process.env as Record<string, string>)
  let proc = Bun.spawn(cmd, {
    stdin: 'pipe',
    stdout: 'pipe',
    stderr: 'pipe',
    env: spawnEnv,
  })

  const frameQueue = new AsyncQueue<IPCFrame>()
  let _remainder = ''
  let _closed = false
  let _reconnecting = false
  let _reconnectAttempt = 0

  // ---- FR-054 fire-and-forget hook dispatcher ----
  function _dispatchHook(
    frame: IPCFrame,
    direction: 'recv' | 'send',
    latencyMs: number,
  ): void {
    if (!bridge.onFrame) return
    const hook = bridge.onFrame
    queueMicrotask(() => {
      try {
        const result = hook(frame, direction, latencyMs) as unknown
        if (result instanceof Promise) {
          result.catch((e: unknown) => {
            _log('WARN', `onFrame hook rejected: ${e}`)
          })
        }
      } catch (e: unknown) {
        _log('WARN', `onFrame hook threw: ${e}`)
      }
    })
  }

  // ------------------------------------------------------------------
  // Reconnect loop (US1 T025)
  // ------------------------------------------------------------------

  /**
   * Build and emit a ResumeRequestFrame on the current proc.stdin.
   * frame_seq is always 0 (fresh outbound counter after reconnect).
   */
  function _emitResumeRequest(): void {
    // Fresh bridge that never handshaked has nothing to resume — skip silently.
    if (!_sessionId) {
      _log('DEBUG', 'Skipping ResumeRequestFrame — no session_id assigned yet')
      return
    }
    // session_id is set but token is missing → programmer error (likely
    // session_event path skipped setSessionCredentials). Log loud so the
    // invariant break is visible; the bridge will fall back to a fresh session.
    if (!_tuiSessionToken) {
      _log(
        'ERROR',
        `Cannot emit ResumeRequestFrame — session=${_sessionId} has no tui_session_token; falling back to fresh session`,
      )
      _sessionId = null
      _lastSeenFrameSeq = null
      _lastSeenCorrelationId = null
      return
    }
    const frame: ResumeRequestFrame = {
      kind: 'resume_request' as const,
      role: 'tui',
      version: '1.0',
      session_id: _sessionId,
      correlation_id: _uuidv7(),
      ts: new Date().toISOString(),
      frame_seq: 0,
      last_seen_correlation_id: _lastSeenCorrelationId ?? undefined,
      last_seen_frame_seq: _lastSeenFrameSeq ?? undefined,
      tui_session_token: _tuiSessionToken,
    } as ResumeRequestFrame
    try {
      proc.stdin.write(encodeFrame(frame))
      _log('INFO', `Emitted ResumeRequestFrame last_seen_frame_seq=${_lastSeenFrameSeq}`)
    } catch (e: unknown) {
      _log('WARN', `Failed to write ResumeRequestFrame: ${e}`)
    }
  }

  async function _doReconnect(): Promise<void> {
    if (_closed || _reconnecting) return
    _reconnecting = true

    let delay = initialBackoffMs
    while (_reconnectAttempt < maxReconnectAttempts && !_closed) {
      _reconnectAttempt++
      _log(
        'INFO',
        `Reconnect attempt ${_reconnectAttempt}/${maxReconnectAttempts} in ${delay}ms`,
      )
      opts.onReconnect?.(_reconnectAttempt, delay)

      await new Promise<void>((resolve) => setTimeout(resolve, delay))
      delay = Math.min(delay * 2, maxBackoffMs)

      if (_closed) break

      try {
        _log('INFO', `Re-spawning backend: ${cmd.join(' ')}`)
        proc = Bun.spawn(cmd, {
          stdin: 'pipe',
          stdout: 'pipe',
          stderr: 'pipe',
        })
        _remainder = ''

        // Wire new process into crash-detector
        startCrashDetector(proc, {
          onCrash: (notice) => {
            _log('ERROR', `Backend crashed on reconnect: exitCode=${notice.exitCode}`)
            opts.onCrash?.(notice)
            if (!_closed && !_reconnecting) {
              _doReconnect()
            }
          },
          onDrop: () => {
            if (!_closed) {
              _doReconnect()
            }
          },
        })

        // Start new stdout reader
        _startStdoutReader()

        // Emit ResumeRequestFrame as first frame (fresh frame_seq=0)
        _emitResumeRequest()

        _reconnecting = false
        _reconnectAttempt = 0
        return
      } catch (e: unknown) {
        _log('WARN', `Reconnect attempt ${_reconnectAttempt} failed: ${e}`)
      }
    }

    _reconnecting = false
    if (!_closed) {
      _log('ERROR', `All ${maxReconnectAttempts} reconnect attempts exhausted`)
      opts.onReconnectFailed?.()
      frameQueue.close()
    }
  }

  // ------------------------------------------------------------------
  // Stdout reader (extracted for reuse across reconnects)
  // ------------------------------------------------------------------

  function _startStdoutReader(): void {
    ;(async () => {
      const reader = proc.stdout.getReader()
      const decoder = new TextDecoder('utf-8')
      try {
        while (true) {
          const { value, done } = await reader.read()
          if (done) break
          const t0 = Date.now()
          const chunk = decoder.decode(value, { stream: true })
          const buffered = _remainder + chunk
          const { frames, remainder } = decodeFrames(buffered)
          _remainder = remainder
          for (const result of frames) {
            if (result.ok) {
              const frame = result.frame

              // Track last-seen for resume requests — only advance forward so
              // heartbeats (frame_seq=0) never regress the watermark.
              if (
                frame.frame_seq != null &&
                (_lastSeenFrameSeq == null || frame.frame_seq > _lastSeenFrameSeq)
              ) {
                _lastSeenFrameSeq = frame.frame_seq
              }
              if (frame.correlation_id) {
                _lastSeenCorrelationId = frame.correlation_id
              }

              // De-duplicate replayed frames (applied_frame_seqs set)
              if (_sessionId && frame.frame_seq != null) {
                const key = `${frame.session_id ?? _sessionId}:${frame.frame_seq}`
                if (_appliedFrameSeqs.has(key)) {
                  _log(
                    'DEBUG',
                    `Skipping duplicate replay frame session=${frame.session_id} frame_seq=${frame.frame_seq}`,
                  )
                  continue
                }
                _appliedFrameSeqs.add(key)
                _appliedFrameSeqsOrder.push(key)
                if (_appliedFrameSeqsOrder.length > _APPLIED_FRAME_SEQS_CAP) {
                  const evicted = _appliedFrameSeqsOrder.shift()
                  if (evicted !== undefined) _appliedFrameSeqs.delete(evicted)
                }
              }

              _log('DEBUG', `recv kind=${frame.kind} session=${frame.session_id}`)
              frameQueue.push(frame)
              _dispatchHook(frame, 'recv', Date.now() - t0)
            } else {
              _log(
                'ERROR',
                `decode error: ${result.error} | raw=${result.raw.slice(0, 200)}`,
              )
            }
          }
        }
      } catch (e: unknown) {
        _log('WARN', `stdout reader error: ${e}`)
        // EOF / EPIPE — trigger reconnect (US1 T025)
        if (!_closed) {
          _doReconnect()
        }
      } finally {
        // Only close the queue if we are not going to reconnect
        if (_closed || _reconnectAttempt >= maxReconnectAttempts) {
          frameQueue.close()
        }
      }
    })()
  }

  // ---- stdout reader (initial process) ----
  _startStdoutReader()

  // ---- crash detector (initial process) ----
  startCrashDetector(proc, {
    onCrash: (notice) => {
      _log('ERROR', `Backend crashed: exitCode=${notice.exitCode}`)
      opts.onCrash?.(notice)
      // Attempt reconnect if crash was unintentional (non-zero exit)
      if (!_closed) {
        _doReconnect()
      }
    },
    onDrop: () => {
      // stdin EOF / EPIPE signaled by crash-detector (T026)
      if (!_closed) {
        _doReconnect()
      }
    },
  })

  // ---- bridge implementation ----
  const bridge: IPCBridge = {
    get proc() {
      return proc
    },
    onFrame: opts.onFrame,
    applied_frame_seqs: _appliedFrameSeqs,

    get lastSeenCorrelationId() {
      return _lastSeenCorrelationId
    },
    get lastSeenFrameSeq() {
      return _lastSeenFrameSeq
    },

    setSessionCredentials(sessionId: string, tuiSessionToken: string): void {
      _sessionId = sessionId
      _tuiSessionToken = tuiSessionToken
    },

    signalDrop(): void {
      if (!_closed) {
        _log('INFO', 'Drop signaled externally — initiating reconnect')
        _doReconnect()
      }
    },

    send(frame: IPCFrame): boolean {
      if (_closed || proc.killed) return false
      try {
        const t0 = Date.now()
        const encoded = encodeFrame(frame)
        _log('DEBUG', `send kind=${frame.kind} session=${frame.session_id}`)
        proc.stdin.write(encoded)
        _dispatchHook(frame, 'send', Date.now() - t0)
        return true
      } catch (e: unknown) {
        _log('WARN', `send error: ${e}`)
        return false
      }
    },

    frames(): AsyncIterable<IPCFrame> {
      return frameQueue
    },

    async close(): Promise<void> {
      if (_closed) return
      _closed = true
      _log('INFO', 'Closing bridge — sending SIGTERM')
      try {
        proc.stdin.end()
        proc.kill('SIGTERM')
        // Wait up to 3 s for graceful exit, then SIGKILL (FR-009)
        const exitPromise = proc.exited
        const timeoutPromise = new Promise<void>((_, reject) =>
          setTimeout(() => reject(new Error('timeout')), 3000),
        )
        await Promise.race([exitPromise, timeoutPromise]).catch(() => {
          _log('WARN', 'Backend did not exit within 3 s — sending SIGKILL')
          proc.kill('SIGKILL')
        })
      } catch (e: unknown) {
        _log('WARN', `close error: ${e}`)
      }
      frameQueue.close()
    },
  }

  return bridge
}
