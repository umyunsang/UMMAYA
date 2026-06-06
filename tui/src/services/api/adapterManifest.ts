// SPDX-License-Identifier: Apache-2.0
// Epic ε #2296 · T009 — Adapter manifest singleton cache (TS side).
//
// FR-015: TS-side manifest cache populated once per backend boot.
// FR-016: cache is REPLACED on each new frame (NOT merged).
// FR-019: isManifestSynced() guards cold-boot race.
//
// Contract: specs/2296-ax-mock-adapters/contracts/ipc-adapter-manifest-frame.md § 5.2

import type { AdapterManifestEntry, AdapterManifestSyncFrame } from '../../ipc/frames.generated.js'

// Re-export AdapterManifestEntry so consumers import from one place.
export type { AdapterManifestEntry }

// ---------------------------------------------------------------------------
// Internal cache type
// ---------------------------------------------------------------------------

interface AdapterManifestCache {
  /** Map from tool_id → AdapterManifestEntry for O(1) resolution. */
  entries: Map<string, AdapterManifestEntry>
  /** SHA-256 hex of the canonical JSON entries (wire verification). */
  manifestHash: string
  /** Python backend PID at boot (for OTEL cross-correlation). */
  emitterPid: number
  /** Wall-clock time when this manifest was ingested. */
  ingestedAt: Date
}

// ---------------------------------------------------------------------------
// Module-level singleton (replace-on-frame, never merged per FR-016)
// ---------------------------------------------------------------------------

let _cache: AdapterManifestCache | null = null
const _waiters = new Set<(synced: boolean) => void>()
let _version = 0
const _subscribers = new Set<() => void>()

function publishManifestChange(): void {
  _version += 1
  for (const subscriber of _subscribers) {
    subscriber()
  }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Ingest a backend-emitted ``AdapterManifestSyncFrame``.
 *
 * Replaces the module-level cache wholesale (FR-016 — do NOT merge).
 * Called by the IPC frame router when it receives a frame with
 * ``kind === 'adapter_manifest_sync'``.
 */
export function ingestManifestFrame(frame: AdapterManifestSyncFrame): void {
  _cache = {
    entries: new Map(frame.entries.map((e) => [e.tool_id, e])),
    manifestHash: frame.manifest_hash,
    emitterPid: frame.emitter_pid,
    ingestedAt: new Date(),
  }
  publishManifestChange()
  for (const resolve of _waiters) {
    resolve(true)
  }
  _waiters.clear()
}

/**
 * Resolve an adapter by its backend-registered ``tool_id``.
 *
 * Returns ``undefined`` when the manifest has not yet been ingested (cold-boot
 * race) or when the ``tool_id`` is absent from the synced manifest.
 *
 * Callers MUST check {@link isManifestSynced} first to distinguish the
 * cold-boot race (manifest not arrived yet) from a genuine AdapterNotFound.
 */
export function resolveAdapter(tool_id: string): AdapterManifestEntry | undefined {
  return _cache?.entries.get(tool_id)
}

/**
 * Return the currently synced adapter entries in deterministic tool_id order.
 *
 * Dynamic adapter Tool objects are rebuilt from this snapshot when the CC query
 * loop refreshes its tool pool for a model-emitted concrete adapter call.
 */
export function listAdapters(): AdapterManifestEntry[] {
  if (_cache === null) return []
  return [..._cache.entries.values()].sort((a, b) =>
    a.tool_id.localeCompare(b.tool_id),
  )
}

export function getAdapterManifestHash(): string | null {
  return _cache?.manifestHash ?? null
}

/**
 * Returns ``true`` when at least one manifest frame has been ingested.
 *
 * Used by primitive ``validateInput`` to enforce the cold-boot fail-closed
 * invariant (FR-019): if the manifest has not yet synced, reject the call
 * with a retry hint rather than silently returning AdapterNotFound.
 */
export function isManifestSynced(): boolean {
  return _cache !== null
}

export function getManifestVersion(): number {
  return _version
}

export function subscribeAdapterManifest(listener: () => void): () => void {
  _subscribers.add(listener)
  return () => {
    _subscribers.delete(listener)
  }
}

export function waitForManifestSync(timeoutMs = 2_500): Promise<boolean> {
  if (isManifestSynced()) {
    return Promise.resolve(true)
  }

  return new Promise(resolve => {
    let settled = false
    let timeout: ReturnType<typeof setTimeout>
    const done = (synced: boolean) => {
      if (settled) return
      settled = true
      clearTimeout(timeout)
      _waiters.delete(done)
      resolve(synced)
    }
    timeout = setTimeout(() => done(false), timeoutMs)
    _waiters.add(done)
  })
}

/**
 * Clear the manifest cache.
 *
 * **FOR TESTING ONLY.** Do not call from production code.
 * Allows tests to reset the singleton between test cases.
 */
export function clearManifestCache(): void {
  _cache = null
  publishManifestChange()
  for (const resolve of _waiters) {
    resolve(false)
  }
  _waiters.clear()
}
