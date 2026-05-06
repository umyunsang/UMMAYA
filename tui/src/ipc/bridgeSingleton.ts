// SPDX-License-Identifier: Apache-2.0
// KOSMOS-original — Epic #1633 FR-007/FR-017 bootstrap helper.
//
// Holds the lazily-spawned, process-wide IPCBridge instance. This is the
// single place `query/deps.ts::callModel` reads from to construct an
// `LLMClient` — it guarantees one Python backend per TUI process, started on
// first use, shared across every turn.
//
// The bridge is spawned lazily because cold-starting `uv run kosmos --ipc
// stdio` adds ~1–2 s to TUI boot; we don't pay that cost unless the first
// prompt is actually typed. Subsequent turns reuse the running child.

import { createBridge, type IPCBridge } from './bridge.js'
import { ingestManifestFrame } from '../services/api/adapterManifest.js'
import { isAdapterManifestSync } from './codec.js'
import { appendFileSync } from 'node:fs'

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

export function getOrCreateKosmosBridge(): IPCBridge {
  if (_bridge !== null) return _bridge
  _bridge = createBridge({
    // Epic ε #2296 T010 — route adapter_manifest_sync frames to the TS-side
    // manifest cache on receipt (before any LLM turn, at backend boot time).
    // FR-015: fires once per backend lifecycle; FR-016: replace-on-frame
    // semantics are enforced inside ingestManifestFrame().
    onFrame: (frame, direction) => {
      const tracePath = process.env['KOSMOS_IPC_TRACE_FILE']
      if (tracePath) {
        try {
          appendFileSync(
            tracePath,
            JSON.stringify({
              ts: new Date().toISOString(),
              direction,
              frame,
            }) + '\n',
            'utf8',
          )
        } catch {
          // Best-effort diagnostics only. Never break the citizen flow because
          // a local trace path is unavailable or full.
        }
      }
      if (direction === 'recv' && isAdapterManifestSync(frame)) {
        ingestManifestFrame(frame)
      }
    },
  })
  return _bridge
}

export function getKosmosBridgeSessionId(): string {
  if (_sessionId === null) {
    _sessionId = crypto.randomUUID()
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

export async function closeKosmosBridge(): Promise<void> {
  if (_bridge !== null) {
    const b = _bridge
    _bridge = null
    await b.close()
  }
  _pluginsModifiedThisSession = false
}
