// SPDX-License-Identifier: Apache-2.0
// Spec 2641 — byte-copy(2641) baseline restored from
//   .references/claude-code-sourcemap/restored-src/src/services/settingsSync/index.ts
//   (CC 2.1.88, SHA-256 5ff457384f2fa4e8ead029bb8d3a8504ce0e822181b6ab57ba4430b816663f93).
// Three labeled swaps layer atop the byte-copy:
//   • swap/llm-provider(2641)      — `constants/oauth` import replaced with
//     KOSMOS-1633 inline stubs (CLAUDE_AI_INFERENCE_SCOPE/OAUTH_BETA_HEADER/
//     getOauthConfig). KOSMOS uses FriendliAI; no Anthropic OAuth tokens
//     exist.
//   • swap/anti-anthropic-1p(2641) — every entry-point that would issue an
//     axios call to claude.ai's `/api/claude_code/user_settings` endpoint
//     short-circuits via the dead-call gate below. Unlike teamMemorySync
//     (which has zero callers), settingsSync IS still imported by
//     `tui/src/cli/print.ts` (3 sites: lines ~519, ~1718, ~3078) and
//     `tui/src/commands/reload-plugins/reload-plugins.ts:28` — so the gate
//     uses *silent early-return* rather than `throw`, preserving the
//     critical boot path's fail-open behaviour. The pre-existing
//     `feature('DOWNLOAD_USER_SETTINGS')`/`feature('UPLOAD_USER_SETTINGS')`
//     flags (always `false` per `tui/src/stubs/bun-bundle.ts`) form the
//     1st gate; the env-override gate added here is the 2nd defense layer.
//   • swap/identifier-rename(2641) — none required (file uses
//     KOSMOS-neutral naming where applicable; CC settings-sync contract
//     names remain for byte-copy fidelity).
// Two callers (`cli/print.ts` + `commands/reload-plugins/`) survive but
// receive early-`false`/early-`void` from the dead-call gate; this file's
// surface is preserved for CC parity (Spec 2641).
//
// === ORIGINAL CC JSDOC (preserved for byte-copy fidelity) ===
// Settings Sync Service
//
// Syncs user settings and memory files across Claude Code environments.
//
// - Interactive CLI: Uploads local settings to remote (incremental, only changed entries)
// - CCR: Downloads remote settings to local before plugin installation
//
// Backend API: anthropic/anthropic#218817

import { feature } from 'bun:bundle'
import axios from 'axios'
import { mkdir, readFile, stat, writeFile } from 'fs/promises'
import pickBy from 'lodash-es/pickBy.js'
import { dirname } from 'path'
import { getIsInteractive } from '../../bootstrap/state.js'
// constants/oauth removed in P1+P2 (Spec 1633); KOSMOS uses FriendliAI, not Anthropic OAuth.
const CLAUDE_AI_INFERENCE_SCOPE = ''
const OAUTH_BETA_HEADER = ''
const getOauthConfig = (): { authorizationUrl: string; tokenUrl: string; clientId: string; scopes: readonly string[]; BASE_API_URL: string } => ({ authorizationUrl: '', tokenUrl: '', clientId: '', scopes: [] as readonly string[], BASE_API_URL: '' })
import {
  checkAndRefreshOAuthTokenIfNeeded,
  getClaudeAIOAuthTokens,
} from '../../utils/auth.js'
import { clearMemoryFileCaches } from '../../utils/claudemd.js'
import { getMemoryPath } from '../../utils/config.js'
import { logForDiagnosticsNoPII } from '../../utils/diagLogs.js'
import { classifyAxiosError } from '../../utils/errors.js'
import { getRepoRemoteHash } from '../../utils/git.js'
import {
  getAPIProvider,
  isFirstPartyKosmosBaseUrl,
} from '../../utils/model/providers.js'
import { markInternalWrite } from '../../utils/settings/internalWrites.js'
import { getSettingsFilePathForSource } from '../../utils/settings/settings.js'
import { resetSettingsCache } from '../../utils/settings/settingsCache.js'
import { sleep } from '../../utils/sleep.js'
import { getClaudeCodeUserAgent } from '../../utils/userAgent.js'
import { getFeatureValue_CACHED_MAY_BE_STALE } from '../analytics/growthbook.js'
import { logEvent } from '../analytics/index.js'
// KOSMOS Spec 1633 / Epic #2293 — services/api/withRetry deleted; inline stub returns 1s baseline.
const getRetryDelay = (_attempt: number): number => 1000
import {
  type SettingsSyncFetchResult,
  type SettingsSyncUploadResult,
  SYNC_KEYS,
  UserSyncDataSchema,
} from './types.js'

const SETTINGS_SYNC_TIMEOUT_MS = 10000 // 10 seconds
const DEFAULT_MAX_RETRIES = 3
const MAX_FILE_SIZE_BYTES = 500 * 1024 // 500 KB per file (matches backend limit)

// SWAP/anti-anthropic-1p(2641): dead-call gate. Returns true only when the
// env override is the strict literal string `'1'` (caller proceeds with
// original CC behaviour); returns false otherwise (caller short-circuits
// silently). Used by all 4 entry-points below.
//
// Codex P2 (PR #2688): rejecting permissive truthy checks (`Boolean(...)`)
// prevents accidental reactivation when CI or shell environments template
// booleans as `KOSMOS_ENABLE_DEAD_SETTINGS_SYNC=0` or `=false`. Only the
// literal string `'1'` opens the gate.
function isDeadCallGateOpen(): boolean {
  return process.env.KOSMOS_ENABLE_DEAD_SETTINGS_SYNC === '1'
}

/**
 * Upload local settings to remote (interactive CLI only).
 * Called from main.tsx preAction.
 * Runs in background - caller should not await unless needed.
 */
export async function uploadUserSettingsInBackground(): Promise<void> {
  if (!isDeadCallGateOpen()) {
    // Spec 2641 dead-call gate: claude.ai settings sync is not part of the
    // L1-A K-EXAONE harness. Surface preserved for CC parity; runtime is
    // no-op. Set KOSMOS_ENABLE_DEAD_SETTINGS_SYNC=1 only for audit replay.
    return
  }
  try {
    if (
      !feature('UPLOAD_USER_SETTINGS') ||
      !getFeatureValue_CACHED_MAY_BE_STALE(
        'tengu_enable_settings_sync_push',
        false,
      ) ||
      !getIsInteractive() ||
      !isUsingOAuth()
    ) {
      logForDiagnosticsNoPII('info', 'settings_sync_upload_skipped')
      logEvent('tengu_settings_sync_upload_skipped_ineligible', {})
      return
    }

    logForDiagnosticsNoPII('info', 'settings_sync_upload_starting')
    const result = await fetchUserSettings()
    if (!result.success) {
      logForDiagnosticsNoPII('warn', 'settings_sync_upload_fetch_failed')
      logEvent('tengu_settings_sync_upload_fetch_failed', {})
      return
    }

    const projectId = await getRepoRemoteHash()
    const localEntries = await buildEntriesFromLocalFiles(projectId)
    const remoteEntries = result.isEmpty ? {} : result.data!.content.entries
    const changedEntries = pickBy(
      localEntries,
      (value, key) => remoteEntries[key] !== value,
    )

    const entryCount = Object.keys(changedEntries).length
    if (entryCount === 0) {
      logForDiagnosticsNoPII('info', 'settings_sync_upload_no_changes')
      logEvent('tengu_settings_sync_upload_skipped', {})
      return
    }

    const uploadResult = await uploadUserSettings(changedEntries)
    if (uploadResult.success) {
      logForDiagnosticsNoPII('info', 'settings_sync_upload_success')
      logEvent('tengu_settings_sync_upload_success', { entryCount })
    } else {
      logForDiagnosticsNoPII('warn', 'settings_sync_upload_failed')
      logEvent('tengu_settings_sync_upload_failed', { entryCount })
    }
  } catch {
    // Fail-open: log unexpected errors but don't block startup
    logForDiagnosticsNoPII('error', 'settings_sync_unexpected_error')
  }
}

// Cached so the fire-and-forget at runHeadless entry and the await in
// installPluginsAndApplyMcpInBackground share one fetch.
let downloadPromise: Promise<boolean> | null = null

/** Test-only: clear the cached download promise between tests. */
export function _resetDownloadPromiseForTesting(): void {
  downloadPromise = null
}

/**
 * Download settings from remote for CCR mode.
 * Fired fire-and-forget at the top of print.ts runHeadless(); awaited in
 * installPluginsAndApplyMcpInBackground before plugin install. First call
 * starts the fetch; subsequent calls join it.
 * Returns true if settings were applied, false otherwise.
 */
export function downloadUserSettings(): Promise<boolean> {
  if (!isDeadCallGateOpen()) {
    // Spec 2641 dead-call gate: silent early-return so cli/print.ts boot
    // path receives `false` (the same answer it currently gets when
    // `feature('DOWNLOAD_USER_SETTINGS')` is `false`). No axios traffic.
    return Promise.resolve(false)
  }
  if (downloadPromise) {
    return downloadPromise
  }
  downloadPromise = doDownloadUserSettings()
  return downloadPromise
}

/**
 * Force a fresh download, bypassing the cached startup promise.
 * Called by /reload-plugins in CCR so mid-session settings changes
 * (enabledPlugins, extraKnownMarketplaces) pushed from the user's local
 * CLI are picked up before the plugin-cache sweep.
 *
 * No retries: user-initiated command, one attempt + fail-open. The user
 * can re-run /reload-plugins to retry. Startup path keeps DEFAULT_MAX_RETRIES.
 *
 * Caller is responsible for firing settingsChangeDetector.notifyChange
 * when this returns true — applyRemoteEntriesToLocal uses markInternalWrite
 * to suppress detection (correct for startup, but mid-session needs
 * applySettingsChange to run). Kept out of this module to avoid the
 * settingsSync → changeDetector cycle edge.
 */
export function redownloadUserSettings(): Promise<boolean> {
  if (!isDeadCallGateOpen()) {
    // Spec 2641 dead-call gate: silent early-return. /reload-plugins user
    // command receives `false` and continues with local-only state.
    return Promise.resolve(false)
  }
  downloadPromise = doDownloadUserSettings(0)
  return downloadPromise
}

async function doDownloadUserSettings(
  maxRetries = DEFAULT_MAX_RETRIES,
): Promise<boolean> {
  if (!isDeadCallGateOpen()) {
    // Spec 2641 dead-call gate: defense-in-depth. The two public callers
    // (downloadUserSettings/redownloadUserSettings) already short-circuit,
    // but if a future refactor invokes this private helper directly the
    // gate still blocks any axios traffic.
    return false
  }
  if (feature('DOWNLOAD_USER_SETTINGS')) {
    try {
      if (
        !getFeatureValue_CACHED_MAY_BE_STALE('tengu_strap_foyer', false) ||
        !isUsingOAuth()
      ) {
        logForDiagnosticsNoPII('info', 'settings_sync_download_skipped')
        logEvent('tengu_settings_sync_download_skipped', {})
        return false
      }

      logForDiagnosticsNoPII('info', 'settings_sync_download_starting')
      const result = await fetchUserSettings(maxRetries)
      if (!result.success) {
        logForDiagnosticsNoPII('warn', 'settings_sync_download_fetch_failed')
        logEvent('tengu_settings_sync_download_fetch_failed', {})
        return false
      }

      if (result.isEmpty) {
        logForDiagnosticsNoPII('info', 'settings_sync_download_empty')
        logEvent('tengu_settings_sync_download_empty', {})
        return false
      }

      const entries = result.data!.content.entries
      const projectId = await getRepoRemoteHash()
      const entryCount = Object.keys(entries).length
      logForDiagnosticsNoPII('info', 'settings_sync_download_applying', {
        entryCount,
      })
      await applyRemoteEntriesToLocal(entries, projectId)
      logEvent('tengu_settings_sync_download_success', { entryCount })
      return true
    } catch {
      // Fail-open: log error but don't block CCR startup
      logForDiagnosticsNoPII('error', 'settings_sync_download_error')
      logEvent('tengu_settings_sync_download_error', {})
      return false
    }
  }
  return false
}

/**
 * Check if user is authenticated with first-party OAuth.
 * Required for settings sync in both CLI (upload) and CCR (download) modes.
 *
 * Only checks user:inference (not user:profile) — CCR's file-descriptor token
 * hardcodes scopes to ['user:inference'] only, so requiring profile would make
 * download a no-op there. Upload is independently guarded by getIsInteractive().
 */
function isUsingOAuth(): boolean {
  if (getAPIProvider() !== 'firstParty' || !isFirstPartyKosmosBaseUrl()) {
    return false
  }

  const tokens = getClaudeAIOAuthTokens()
  return Boolean(
    tokens?.accessToken && tokens.scopes?.includes(CLAUDE_AI_INFERENCE_SCOPE),
  )
}

function getSettingsSyncEndpoint(): string {
  return `${getOauthConfig().BASE_API_URL}/api/claude_code/user_settings`
}

function getSettingsSyncAuthHeaders(): {
  headers: Record<string, string>
  error?: string
} {
  const oauthTokens = getClaudeAIOAuthTokens()
  if (oauthTokens?.accessToken) {
    return {
      headers: {
        Authorization: `Bearer ${oauthTokens.accessToken}`,
        'anthropic-beta': OAUTH_BETA_HEADER,
      },
    }
  }

  return {
    headers: {},
    error: 'No OAuth token available',
  }
}

async function fetchUserSettingsOnce(): Promise<SettingsSyncFetchResult> {
  try {
    await checkAndRefreshOAuthTokenIfNeeded()

    const authHeaders = getSettingsSyncAuthHeaders()
    if (authHeaders.error) {
      return {
        success: false,
        error: authHeaders.error,
        skipRetry: true,
      }
    }

    const headers: Record<string, string> = {
      ...authHeaders.headers,
      'User-Agent': getClaudeCodeUserAgent(),
    }

    const endpoint = getSettingsSyncEndpoint()
    const response = await axios.get(endpoint, {
      headers,
      timeout: SETTINGS_SYNC_TIMEOUT_MS,
      validateStatus: status => status === 200 || status === 404,
    })

    // 404 means no settings exist yet
    if (response.status === 404) {
      logForDiagnosticsNoPII('info', 'settings_sync_fetch_empty')
      return {
        success: true,
        isEmpty: true,
      }
    }

    const parsed = UserSyncDataSchema().safeParse(response.data)
    if (!parsed.success) {
      logForDiagnosticsNoPII('warn', 'settings_sync_fetch_invalid_format')
      return {
        success: false,
        error: 'Invalid settings sync response format',
      }
    }

    logForDiagnosticsNoPII('info', 'settings_sync_fetch_success')
    return {
      success: true,
      data: parsed.data,
      isEmpty: false,
    }
  } catch (error) {
    const { kind, message } = classifyAxiosError(error)
    switch (kind) {
      case 'auth':
        return {
          success: false,
          error: 'Not authorized for settings sync',
          skipRetry: true,
        }
      case 'timeout':
        return { success: false, error: 'Settings sync request timeout' }
      case 'network':
        return { success: false, error: 'Cannot connect to server' }
      default:
        return { success: false, error: message }
    }
  }
}

async function fetchUserSettings(
  maxRetries = DEFAULT_MAX_RETRIES,
): Promise<SettingsSyncFetchResult> {
  let lastResult: SettingsSyncFetchResult | null = null

  for (let attempt = 1; attempt <= maxRetries + 1; attempt++) {
    lastResult = await fetchUserSettingsOnce()

    if (lastResult.success) {
      return lastResult
    }

    if (lastResult.skipRetry) {
      return lastResult
    }

    if (attempt > maxRetries) {
      return lastResult
    }

    const delayMs = getRetryDelay(attempt)
    logForDiagnosticsNoPII('info', 'settings_sync_retry', {
      attempt,
      maxRetries,
      delayMs,
    })
    await sleep(delayMs)
  }

  return lastResult!
}

async function uploadUserSettings(
  entries: Record<string, string>,
): Promise<SettingsSyncUploadResult> {
  try {
    await checkAndRefreshOAuthTokenIfNeeded()

    const authHeaders = getSettingsSyncAuthHeaders()
    if (authHeaders.error) {
      return {
        success: false,
        error: authHeaders.error,
      }
    }

    const headers: Record<string, string> = {
      ...authHeaders.headers,
      'User-Agent': getClaudeCodeUserAgent(),
      'Content-Type': 'application/json',
    }

    const endpoint = getSettingsSyncEndpoint()
    const response = await axios.put(
      endpoint,
      { entries },
      {
        headers,
        timeout: SETTINGS_SYNC_TIMEOUT_MS,
      },
    )

    logForDiagnosticsNoPII('info', 'settings_sync_uploaded', {
      entryCount: Object.keys(entries).length,
    })
    return {
      success: true,
      checksum: response.data?.checksum,
      lastModified: response.data?.lastModified,
    }
  } catch (error) {
    logForDiagnosticsNoPII('warn', 'settings_sync_upload_error')
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    }
  }
}

/**
 * Try to read a file for sync, with size limit and error handling.
 * Returns null if file doesn't exist, is empty, or exceeds size limit.
 */
async function tryReadFileForSync(filePath: string): Promise<string | null> {
  try {
    const stats = await stat(filePath)
    if (stats.size > MAX_FILE_SIZE_BYTES) {
      logForDiagnosticsNoPII('info', 'settings_sync_file_too_large')
      return null
    }

    const content = await readFile(filePath, 'utf8')
    // Check for empty/whitespace-only without allocating a trimmed copy
    if (!content || /^\s*$/.test(content)) {
      return null
    }

    return content
  } catch {
    return null
  }
}

async function buildEntriesFromLocalFiles(
  projectId: string | null,
): Promise<Record<string, string>> {
  const entries: Record<string, string> = {}

  // Global user settings
  const userSettingsPath = getSettingsFilePathForSource('userSettings')
  if (userSettingsPath) {
    const content = await tryReadFileForSync(userSettingsPath)
    if (content) {
      entries[SYNC_KEYS.USER_SETTINGS] = content
    }
  }

  // Global user memory
  const userMemoryPath = getMemoryPath('User')
  const userMemoryContent = await tryReadFileForSync(userMemoryPath)
  if (userMemoryContent) {
    entries[SYNC_KEYS.USER_MEMORY] = userMemoryContent
  }

  // Project-specific files (only if we have a project ID from git remote)
  if (projectId) {
    // Project local settings
    const localSettingsPath = getSettingsFilePathForSource('localSettings')
    if (localSettingsPath) {
      const content = await tryReadFileForSync(localSettingsPath)
      if (content) {
        entries[SYNC_KEYS.projectSettings(projectId)] = content
      }
    }

    // Project local memory
    const localMemoryPath = getMemoryPath('Local')
    const localMemoryContent = await tryReadFileForSync(localMemoryPath)
    if (localMemoryContent) {
      entries[SYNC_KEYS.projectMemory(projectId)] = localMemoryContent
    }
  }

  return entries
}

async function writeFileForSync(
  filePath: string,
  content: string,
): Promise<boolean> {
  try {
    const parentDir = dirname(filePath)
    if (parentDir) {
      await mkdir(parentDir, { recursive: true })
    }

    await writeFile(filePath, content, 'utf8')
    logForDiagnosticsNoPII('info', 'settings_sync_file_written')
    return true
  } catch {
    logForDiagnosticsNoPII('warn', 'settings_sync_file_write_failed')
    return false
  }
}

/**
 * Apply remote entries to local files (CCR pull pattern).
 * Only writes files that match expected keys.
 *
 * After writing, invalidates relevant caches:
 * - resetSettingsCache() for settings files
 * - clearMemoryFileCaches() for memory files (CLAUDE.md)
 */
async function applyRemoteEntriesToLocal(
  entries: Record<string, string>,
  projectId: string | null,
): Promise<void> {
  let appliedCount = 0
  let settingsWritten = false
  let memoryWritten = false

  // Helper to check size limit (defense-in-depth, matches backend limit)
  const exceedsSizeLimit = (content: string, _path: string): boolean => {
    const sizeBytes = Buffer.byteLength(content, 'utf8')
    if (sizeBytes > MAX_FILE_SIZE_BYTES) {
      logForDiagnosticsNoPII('info', 'settings_sync_file_too_large', {
        sizeBytes,
        maxBytes: MAX_FILE_SIZE_BYTES,
      })
      return true
    }
    return false
  }

  // Apply global user settings
  const userSettingsContent = entries[SYNC_KEYS.USER_SETTINGS]
  if (userSettingsContent) {
    const userSettingsPath = getSettingsFilePathForSource('userSettings')
    if (
      userSettingsPath &&
      !exceedsSizeLimit(userSettingsContent, userSettingsPath)
    ) {
      // Mark as internal write to prevent spurious change detection
      markInternalWrite(userSettingsPath)
      if (await writeFileForSync(userSettingsPath, userSettingsContent)) {
        appliedCount++
        settingsWritten = true
      }
    }
  }

  // Apply global user memory
  const userMemoryContent = entries[SYNC_KEYS.USER_MEMORY]
  if (userMemoryContent) {
    const userMemoryPath = getMemoryPath('User')
    if (!exceedsSizeLimit(userMemoryContent, userMemoryPath)) {
      if (await writeFileForSync(userMemoryPath, userMemoryContent)) {
        appliedCount++
        memoryWritten = true
      }
    }
  }

  // Apply project-specific files (only if project ID matches)
  if (projectId) {
    const projectSettingsKey = SYNC_KEYS.projectSettings(projectId)
    const projectSettingsContent = entries[projectSettingsKey]
    if (projectSettingsContent) {
      const localSettingsPath = getSettingsFilePathForSource('localSettings')
      if (
        localSettingsPath &&
        !exceedsSizeLimit(projectSettingsContent, localSettingsPath)
      ) {
        // Mark as internal write to prevent spurious change detection
        markInternalWrite(localSettingsPath)
        if (await writeFileForSync(localSettingsPath, projectSettingsContent)) {
          appliedCount++
          settingsWritten = true
        }
      }
    }

    const projectMemoryKey = SYNC_KEYS.projectMemory(projectId)
    const projectMemoryContent = entries[projectMemoryKey]
    if (projectMemoryContent) {
      const localMemoryPath = getMemoryPath('Local')
      if (!exceedsSizeLimit(projectMemoryContent, localMemoryPath)) {
        if (await writeFileForSync(localMemoryPath, projectMemoryContent)) {
          appliedCount++
          memoryWritten = true
        }
      }
    }
  }

  // Invalidate caches so subsequent reads pick up new content
  if (settingsWritten) {
    resetSettingsCache()
  }
  if (memoryWritten) {
    clearMemoryFileCaches()
  }

  logForDiagnosticsNoPII('info', 'settings_sync_applied', {
    appliedCount,
  })
}
