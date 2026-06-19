// Source: .references/claude-code-sourcemap/restored-src/src/state/store.ts (Claude Code 2.1.88, research-use)
// createStore pattern lifted verbatim; SessionState, Action discriminated union,
// and useSessionStore hook are UMMAYA-original following data-model.md § 3.
import { useSyncExternalStore } from 'react'
import {
  setPendingPermission as _setPendingPermission,
  resolvePermissionDecision as _resolvePermissionDecision,
  getActivePermission as _getActivePermission,
  subscribeToPermissionSlot,
} from './pendingPermissionSlot.js'
export type { PendingPermissionRequest } from './pendingPermissionSlot.js'
export type { PermissionDecision } from '../ipc/codec.js'

// ---------------------------------------------------------------------------
// Generic store primitive (≈35-line pattern from restored-src/src/state/store.ts)
// ---------------------------------------------------------------------------

type Listener = () => void

type Store<T> = {
  getState: () => T
  setState: (updater: (prev: T) => T) => void
  subscribe: (listener: Listener) => () => void
  dispatch: (action: SessionAction) => void
}

function createStore<T>(
  initialState: T,
  reducer: (state: T, action: SessionAction) => T,
): Store<T> {
  let state = initialState
  const listeners = new Set<Listener>()

  return {
    getState: () => state,

    setState: (updater: (prev: T) => T) => {
      const prev = state
      const next = updater(prev)
      if (Object.is(next, prev)) return
      state = next
      for (const listener of listeners) listener()
    },

    dispatch: (action: SessionAction) => {
      const prev = state
      const next = reducer(prev, action)
      if (Object.is(next, prev)) return
      state = next
      for (const listener of listeners) listener()
    },

    subscribe: (listener: Listener) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
  }
}

// ---------------------------------------------------------------------------
// UMMAYA session state — data-model.md § 3
// ---------------------------------------------------------------------------

/** One of the four coordinator phases from Spec 031 */
export type Phase =
  | 'Research'
  | 'Synthesis'
  | 'Implementation'
  | 'Verification'

/** Per-worker status entry (worker_status IPC frame payload) */
export interface WorkerStatus {
  worker_id: string
  role_id: string
  current_primitive: string
  status: 'idle' | 'running' | 'waiting_permission' | 'error'
}

/** Pending permission request that blocks user input */
export interface PermissionRequest {
  request_id: string
  correlation_id: string
  worker_id: string
  primitive_kind: string
  description_ko: string
  description_en: string
  risk_level: 'low' | 'medium' | 'high'
}

/** One assembled message in the conversation */
export interface Message {
  id: string
  role: 'user' | 'assistant'
  /** Accumulated assistant delta strings; empty for user messages */
  chunks: string[]
  done: boolean
  tool_calls: ToolCall[]
  tool_results: ToolResult[]
}

export interface ToolCall {
  call_id: string
  name: string
  arguments: Record<string, unknown>
}

export interface ToolResult {
  call_id: string
  envelope: Record<string, unknown>
}

export interface CrashNotice {
  code: string
  message: string
  details: Record<string, unknown>
}

/** Full ephemeral render-state — data-model.md § 3.1 */
export interface SessionState {
  session_id: string
  messages: Map<string, Message>
  message_order: string[]
  coordinator_phase: Phase | null
  workers: Map<string, WorkerStatus>
  pending_permission: PermissionRequest | null
  crash: CrashNotice | null
}

// ---------------------------------------------------------------------------
// Action discriminated union — data-model.md § 3.2
// ---------------------------------------------------------------------------

export type SessionAction =
  | { type: 'USER_INPUT'; message_id: string; text: string }
  | {
      type: 'ASSISTANT_CHUNK'
      message_id: string
      delta: string
      done: boolean
    }
  | { type: 'TOOL_CALL'; message_id: string; tool_call: ToolCall }
  | { type: 'TOOL_RESULT'; call_id: string; envelope: Record<string, unknown> }
  | { type: 'COORDINATOR_PHASE'; phase: Phase }
  | { type: 'WORKER_STATUS'; status: WorkerStatus }
  | { type: 'PERMISSION_REQUEST'; request: PermissionRequest }
  | { type: 'PERMISSION_RESPONSE' }
  | {
      type: 'SESSION_EVENT'
      event: 'save' | 'load' | 'list' | 'resume' | 'new' | 'exit'
      payload: Record<string, unknown>
    }
  | { type: 'ERROR'; code: string; message: string; details: Record<string, unknown> }
  | { type: 'CRASH'; notice: CrashNotice }

// ---------------------------------------------------------------------------
// Reducer
// ---------------------------------------------------------------------------

function getOrCreateAssistantMessage(
  state: SessionState,
  message_id: string,
): Message {
  return (
    state.messages.get(message_id) ?? {
      id: message_id,
      role: 'assistant',
      chunks: [],
      done: false,
      tool_calls: [],
      tool_results: [],
    }
  )
}

function sessionReducer(
  state: SessionState,
  action: SessionAction,
): SessionState {
  switch (action.type) {
    case 'USER_INPUT': {
      const msg: Message = {
        id: action.message_id,
        role: 'user',
        chunks: [action.text],
        done: true,
        tool_calls: [],
        tool_results: [],
      }
      const messages = new Map(state.messages)
      messages.set(msg.id, msg)
      return {
        ...state,
        messages,
        message_order: [...state.message_order, msg.id],
      }
    }

    case 'ASSISTANT_CHUNK': {
      const existing = getOrCreateAssistantMessage(state, action.message_id)
      if (existing.done) return state // discard post-done chunks
      const updated: Message = {
        ...existing,
        chunks: [...existing.chunks, action.delta],
        done: action.done,
      }
      const messages = new Map(state.messages)
      messages.set(action.message_id, updated)
      const message_order = state.messages.has(action.message_id)
        ? state.message_order
        : [...state.message_order, action.message_id]
      return { ...state, messages, message_order }
    }

    case 'TOOL_CALL': {
      const existing = getOrCreateAssistantMessage(state, action.message_id)
      const updated: Message = {
        ...existing,
        tool_calls: [...existing.tool_calls, action.tool_call],
      }
      const messages = new Map(state.messages)
      messages.set(action.message_id, updated)
      return { ...state, messages, message_order: state.messages.has(action.message_id) ? state.message_order : [...state.message_order, action.message_id] }
    }

    case 'TOOL_RESULT': {
      // Attach result to the message that owns the matching call_id
      const messages = new Map(state.messages)
      for (const [id, msg] of messages) {
        if (msg.tool_calls.some(tc => tc.call_id === action.call_id)) {
          messages.set(id, {
            ...msg,
            tool_results: [
              ...msg.tool_results,
              { call_id: action.call_id, envelope: action.envelope },
            ],
          })
          break
        }
      }
      return { ...state, messages }
    }

    case 'COORDINATOR_PHASE':
      return { ...state, coordinator_phase: action.phase }

    case 'WORKER_STATUS': {
      const workers = new Map(state.workers)
      workers.set(action.status.worker_id, action.status)
      return { ...state, workers }
    }

    case 'PERMISSION_REQUEST':
      return { ...state, pending_permission: action.request }

    case 'PERMISSION_RESPONSE':
      return { ...state, pending_permission: null }

    case 'SESSION_EVENT': {
      if (action.event === 'new') {
        return {
          ...initialSessionState(state.session_id),
        }
      }
      if (action.event === 'load') {
        // FR-052: replay persisted messages directly with done:true so
        // MessageList does not animate them as streaming content.
        const rawMessages = action.payload['messages']
        if (!Array.isArray(rawMessages)) {
          console.warn('[session-store] SESSION_EVENT load: payload.messages is not an array — ignoring')
          return state
        }
        const messages = new Map<string, Message>()
        const message_order: string[] = []
        for (const raw of rawMessages) {
          if (
            raw === null ||
            typeof raw !== 'object' ||
            typeof (raw as Record<string, unknown>)['id'] !== 'string'
          ) {
            console.warn('[session-store] SESSION_EVENT load: skipping entry missing required id field', raw)
            continue
          }
          const entry = raw as Record<string, unknown>
          const msg: Message = {
            id: entry['id'] as string,
            role: (entry['role'] === 'user' || entry['role'] === 'assistant') ? entry['role'] : 'assistant',
            chunks: Array.isArray(entry['chunks'])
              ? (entry['chunks'] as unknown[]).map(String)
              : [],
            done: true, // always mark done — no streaming animation (FR-052)
            tool_calls: Array.isArray(entry['tool_calls'])
              ? (entry['tool_calls'] as ToolCall[])
              : [],
            tool_results: Array.isArray(entry['tool_results'])
              ? (entry['tool_results'] as ToolResult[])
              : [],
          }
          messages.set(msg.id, msg)
          message_order.push(msg.id)
        }
        const session_id =
          typeof action.payload['session_id'] === 'string'
            ? action.payload['session_id']
            : state.session_id
        return {
          ...state,
          session_id,
          messages,
          message_order,
        }
      }
      // Other session events (save, list, resume, exit) are handled
      // as side-effects by the IPC bridge; reducer leaves state intact.
      return state
    }

    case 'ERROR': {
      const errId = `error-${Date.now()}-${Math.random().toString(36).slice(2)}`
      const errMsg: Message = {
        id: errId,
        role: 'assistant',
        chunks: [`[ERROR ${action.code}] ${action.message}`],
        done: true,
        tool_calls: [],
        tool_results: [],
      }
      const messages = new Map(state.messages)
      messages.set(errId, errMsg)
      return {
        ...state,
        messages,
        message_order: [...state.message_order, errId],
      }
    }

    case 'CRASH':
      return { ...state, crash: action.notice }

    default:
      return state
  }
}

// ---------------------------------------------------------------------------
// Store singleton + exported hook — data-model.md § 3.3
// ---------------------------------------------------------------------------

function initialSessionState(session_id: string): SessionState {
  return {
    session_id,
    messages: new Map(),
    message_order: [],
    coordinator_phase: null,
    workers: new Map(),
    pending_permission: null,
    crash: null,
  }
}

/** Module-level singleton.  Reset via SESSION_EVENT new. */
const sessionStore = createStore<SessionState>(
  initialSessionState(''),
  sessionReducer,
)

// ---------------------------------------------------------------------------
// SessionStoreActions — the full capability surface (session state + permission
// slot).  Non-React callers access this via useSessionStore.getState().
// ---------------------------------------------------------------------------

export interface SessionStoreActions {
  /** Read the current session state snapshot. */
  getState: () => SessionState
  /** Enqueue a permission request; returns a Promise that resolves when the
   *  citizen responds or the 5-minute timeout fires. */
  setPendingPermission: (request: import('./pendingPermissionSlot.js').PendingPermissionRequest) => Promise<import('../ipc/codec.js').PermissionDecision>
  /** Resolve a pending permission request by id.  No-op for unknown ids. */
  resolvePermissionDecision: (request_id: string, decision: import('../ipc/codec.js').PermissionDecision) => void
  /** Snapshot accessor for the currently active request (null when empty). */
  getActivePermission: () => import('./pendingPermissionSlot.js').PendingPermissionRequest | null
}

/**
 * Subscribe to a slice of SessionState via useSyncExternalStore.
 * Only components whose selector result changes (Object.is) re-render.
 *
 * Also exposes `.getState()` for non-React callers (mirrors Zustand API shape
 * so the contract caller pattern `useSessionStore.getState().setPendingPermission(…)`
 * works outside React component trees).
 *
 * @example
 *   const phase = useSessionStore(s => s.coordinator_phase)
 *   const msgs  = useSessionStore(s => s.message_order)
 */
export function useSessionStore<T>(selector: (state: SessionState) => T): T {
  return useSyncExternalStore(
    (listener) => {
      // Subscribe to both the reducer store AND the permission slot so that
      // selectors that read activePermission via getActivePermission() trigger
      // re-renders when the slot changes.
      const unsubReducer = sessionStore.subscribe(listener)
      const unsubSlot = subscribeToPermissionSlot(listener)
      return () => {
        unsubReducer()
        unsubSlot()
      }
    },
    () => selector(sessionStore.getState()),
    () => selector(sessionStore.getState()),
  )
}

// Attach Zustand-compatible getState + actions to the hook function so that
// non-React callers can do:
//   useSessionStore.getState().setPendingPermission(...)
//   useSessionStore.getState().resolvePermissionDecision(...)
//   useSessionStore.getState().getActivePermission()
// This avoids coupling the smoke-check / deps.ts callers to the internal
// sessionStore singleton.
Object.assign(useSessionStore, {
  getState: (): SessionStoreActions & SessionState => ({
    ...sessionStore.getState(),
    getState: () => sessionStore.getState(),
    setPendingPermission: _setPendingPermission,
    resolvePermissionDecision: _resolvePermissionDecision,
    getActivePermission: _getActivePermission,
  }),
})

/** Dispatch an action to the session store */
export function dispatchSessionAction(action: SessionAction): void {
  sessionStore.dispatch(action)
}

/** Direct snapshot access for non-React code (IPC bridge, tests) */
export function getSessionSnapshot(): SessionState {
  return sessionStore.getState()
}

// ---------------------------------------------------------------------------
// Pending permission slot — re-exported for direct import by non-React code.
//
// Use these when you don't need the Zustand-compat getState() pattern:
//   import { setPendingPermission, resolvePermissionDecision } from './session-store.js'
// ---------------------------------------------------------------------------

/** @see pendingPermissionSlot.ts */
export const setPendingPermission = _setPendingPermission

/** @see pendingPermissionSlot.ts */
export const resolvePermissionDecision = _resolvePermissionDecision

/** @see pendingPermissionSlot.ts */
export const getActivePermission = _getActivePermission

// ---------------------------------------------------------------------------
// Derived agent-loop probes — keep liveness tied to actual message state, not
// only render order, so cancellation/exit checks keep working if ordering and
// execution state ever diverge again.
// ---------------------------------------------------------------------------

/**
 * Returns true when any assistant message in `state.messages` represents
 * in-flight agent work — either an assistant message that has not been marked
 * `done: true`, or a tool call whose matching `tool_result` has not yet
 * arrived.  Ignores `message_order` entirely: a `TOOL_CALL`-only message is
 * visible to this probe even when no `ASSISTANT_CHUNK` has pushed its id into
 * the order array.
 *
 * Intentionally scans the full map (O(n) in message count). Session size is
 * bounded in practice, and each call site runs on a citizen keystroke rather
 * than every render.
 */
export function computeIsAgentLoopActive(
  messages: ReadonlyMap<string, Message>,
): boolean {
  for (const [, msg] of messages) {
    if (msg.role !== 'assistant') continue
    if (!msg.done) return true
    // Tool calls with no matching result — the streamed deltas can legitimately
    // be `done:true` while a tool round-trip is still pending.  Treat the
    // outstanding tool call as the loop continuation.
    for (const call of msg.tool_calls) {
      const hasResult = msg.tool_results.some(
        (r) => r.call_id === call.call_id,
      )
      if (!hasResult) return true
    }
  }
  return false
}

/**
 * Returns the `call_id` of the most recently registered tool call that has no
 * matching `tool_result`, or null when no tool call is in flight.
 *
 * Uses `messages` map insertion order, which appends for a fresh key and
 * preserves position for an existing key (JS `Map` contract). That matches the
 * intent of "most recent" without depending on render ordering.
 */
export function computeCurrentToolCallId(
  messages: ReadonlyMap<string, Message>,
): string | null {
  // Iterate in reverse so the most recent in-flight tool call wins.  `Map`
  // does not expose a reverse iterator directly; materialise entries once.
  const entries = Array.from(messages)
  for (let i = entries.length - 1; i >= 0; i--) {
    const entry = entries[i]
    if (entry === undefined) continue
    const msg = entry[1]
    if (msg.role !== 'assistant') continue
    for (let j = msg.tool_calls.length - 1; j >= 0; j--) {
      const call = msg.tool_calls[j]
      if (call === undefined) continue
      const hasResult = msg.tool_results.some(
        (r) => r.call_id === call.call_id,
      )
      if (!hasResult) return call.call_id
    }
  }
  return null
}

export { sessionStore }
