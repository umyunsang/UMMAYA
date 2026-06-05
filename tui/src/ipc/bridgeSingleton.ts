// SPDX-License-Identifier: Apache-2.0
// UMMAYA-original — Epic #1633 FR-007/FR-017 bootstrap helper.
//
// Holds the lazily-spawned, process-wide IPCBridge instance. This is the
// single place `query/deps.ts::callModel` reads from to construct an
// `LLMClient` — it guarantees one Python backend per TUI process, started on
// first use, shared across every turn.
//
// The bridge is spawned lazily because cold-starting `uv run ummaya --ipc
// stdio` adds ~1–2 s to TUI boot; we don't pay that cost unless the first
// prompt is actually typed. Subsequent turns reuse the running child.

import { createBridge, type IPCBridge } from './bridge.js'
import { getSessionId } from '../bootstrap/state.js'
import {
  ingestManifestFrame,
  waitForManifestSync,
} from '../services/api/adapterManifest.js'
import {
  isAdapterManifestSync,
  isPermissionRequest,
  isToolResult,
} from './codec.js'
import { getOrCreatePendingCallRegistry } from './pendingCallSingleton.js'

let _bridge: IPCBridge | null = null
let _sessionId: string | null = null

// Spec 1979 T016 — session-scoped flag flipped when a plugin install or
// uninstall completes successfully. The flag tells the next ChatRequestFrame
// builder to set `frame.tools = []` so the backend's
// `registry.export_core_tools_openai()` fallback (stdio.py:1192-1195) re-exports
// the catalog including the freshly registered/deregistered plugin tool.
// Reset to false after a single ChatRequestFrame consumes it (per R-6 verdict
// — citizen authority remains the default for the rest of the session).
let _pluginsModifiedThisSession = false

export function getOrCreateUmmayaBridge(): IPCBridge {
  if (_bridge !== null) return _bridge
  const sessionId = getUmmayaBridgeSessionId()
  _bridge = createBridge({
    sessionId,
    // Epic ε #2296 T010 — route adapter_manifest_sync frames to the TS-side
    // manifest cache on receipt (before any LLM turn, at backend boot time).
    // FR-015: fires once per backend lifecycle; FR-016: replace-on-frame
    // semantics are enforced inside ingestManifestFrame().
    onFrame: async (frame, direction) => {
      if (direction !== 'recv') return
      if (isAdapterManifestSync(frame)) {
        ingestManifestFrame(frame)
      }
      if (isToolResult(frame)) {
        getOrCreatePendingCallRegistry().resolve(frame.call_id, frame)
      }
      if (isPermissionRequest(frame)) {
        const { pushIpcPermissionRequest } = await import(
          '../utils/permissions/ipcPermissionBridge.js'
        )
        pushIpcPermissionRequest(frame)
      }
    },
  })
  return _bridge
}

export async function ensureUmmayaAdapterManifest(
  timeoutMs = 2_500,
): Promise<boolean> {
  getOrCreateUmmayaBridge()
  return waitForManifestSync(timeoutMs)
}

export function getUmmayaBridgeSessionId(): string {
  if (_sessionId === null) {
    _sessionId = getSessionId()
  }
  return _sessionId
}

/**
 * Spec 1979 T016 — mark the session as having installed/uninstalled a plugin.
 *
 * Invoked from the IPC reader when a `plugin_op_complete` frame arrives
 * with `result === "success"` for `request_op` ∈ {install, uninstall}.
 */
export function markPluginsModified(): void {
  _pluginsModifiedThisSession = true
}

/**
 * Spec 1979 T017 — consume + reset the plugins-modified flag.
 *
 * Returns true if the next ChatRequestFrame should defer to backend
 * `registry.export_core_tools_openai()` by setting `frame.tools = []`.
 * Resets the flag so subsequent turns return false (citizen authority).
 */
export function consumePluginsModifiedFlag(): boolean {
  const wasSet = _pluginsModifiedThisSession
  _pluginsModifiedThisSession = false
  return wasSet
}

export async function closeUmmayaBridge(): Promise<void> {
  if (_bridge !== null) {
    const b = _bridge
    _bridge = null
    await b.close()
  }
  _pluginsModifiedThisSession = false
  _sessionId = null
}
