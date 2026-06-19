// UMMAYA Epic #2112: legacy model-dispatch matrix removed; collapsed to K-EXAONE single branch.
// Public function signatures preserved per FR-006 caller-reach rule (callers in services/api/ummaya.ts,
// memdir/findRelevantMemories.ts, utils/attachments.ts, commands/insights.ts, services/tokenEstimation.ts,
// components/messages/AssistantTextMessage.tsx are bucket B — kept alive until P2 issue #2147 lands).
//
// Source-of-truth literals: this file (lines below) + src/ummaya/llm/config.py:37.
// FR-012 mandates no NEW K-EXAONE literal location; existing pre-spec sites at
// tui/src/ipc/llmClient.ts:31 and tui/src/tools/TranslateTool/TranslateTool.ts:64
// remain in place (P2 cleanup tracked under issue #2150).

import { getMainLoopModelOverride } from '../../bootstrap/state.js'
import { isClaudeAISubscriber } from '../auth.js'
import { has1mContext, modelSupports1M } from '../context.js'
import { getModelStrings, resolveOverriddenModel } from './modelStrings.js'
import { getSettings_DEPRECATED } from '../settings/settings.js'
import type { PermissionMode } from '../permissions/PermissionMode.js'
import { isModelAllowed } from './modelAllowlist.js'
import { type ModelAlias, isModelAlias } from './aliases.js'

export type ModelShortName = string
export type ModelName = string
export type ModelSetting = ModelName | ModelAlias | null

// FR-012 source-of-truth: imports from constants.ts (single declaration site
// in tui/src/utils/model/). All other callers in this subtree share the same
// constants, breaking module-init cycles cleanly.
import { UMMAYA_K_EXAONE_MODEL, UMMAYA_K_EXAONE_SHORT, UMMAYA_K_EXAONE_DISPLAY } from './constants.js'

export function getSmallFastModel(): ModelName {
  return getDefaultMainLoopModel()
}

export function isNonCustomOpusModel(_model: ModelName): boolean {
  // UMMAYA: no Opus model exists; always returns false.
  return false
}

/**
 * Helper to get the model from /model (including via /config), the --model flag, environment variable,
 * or the saved settings. The returned value can be a model alias if that's what the user specified.
 * Undefined if the user didn't configure anything, in which case we fall back to
 * the default (null).
 *
 * Priority order within this function:
 * 1. Model override during session (from /model command) - highest priority
 * 2. Model override at startup (from --model flag)
 * 3. UMMAYA_FRIENDLI_MODEL environment variable
 * 4. Settings (from user's saved settings)
 */
export function getUserSpecifiedModelSetting(): ModelSetting | undefined {
  let specifiedModel: ModelSetting | undefined

  const modelOverride = getMainLoopModelOverride()
  if (modelOverride !== undefined) {
    specifiedModel = modelOverride
  } else {
    const settings = getSettings_DEPRECATED() || {}
    specifiedModel = process.env.UMMAYA_FRIENDLI_MODEL || settings.model || undefined
  }

  if (specifiedModel && !isModelAllowed(specifiedModel)) {
    return undefined
  }

  return specifiedModel
}

export function getMainLoopModel(): ModelName {
  const model = getUserSpecifiedModelSetting()
  if (model !== undefined && model !== null) {
    return parseUserSpecifiedModel(model)
  }
  return getDefaultMainLoopModel()
}

export function getBestModel(): ModelName {
  return getDefaultMainLoopModel()
}

// [Deferred to P2 — issue #2147]: thin alias preserved for services/api/ummaya.ts
// import-graph stability. Removed together with services/api/ummaya.ts in Phase P2.
export function getDefaultOpusModel(): ModelName {
  return getDefaultMainLoopModel()
}

// [Deferred to P2 — issue #2147]: thin alias preserved for services/api/ummaya.ts
// import-graph stability.
export function getDefaultSonnetModel(): ModelName {
  return getDefaultMainLoopModel()
}

// [Deferred to P2 — issue #2147]: thin alias preserved for services/api/ummaya.ts
// import-graph stability.
export function getDefaultHaikuModel(): ModelName {
  return getDefaultMainLoopModel()
}

/**
 * Get the model to use for runtime, depending on the runtime context.
 * UMMAYA: always returns the K-EXAONE main-loop model; permission-mode-driven
 * model swap is dead under the single-fixed provider invariant.
 */
export function getRuntimeMainLoopModel(_params: {
  permissionMode: PermissionMode
  mainLoopModel: string
  exceeds200kTokens?: boolean
}): ModelName {
  return getDefaultMainLoopModel()
}

/**
 * Get the default main loop model setting.
 *
 * UMMAYA always uses the canonical K-EXAONE model via FriendliAI Serverless.
 */
export function getDefaultMainLoopModelSetting(): ModelName | ModelAlias {
  return UMMAYA_K_EXAONE_MODEL
}

/**
 * Synchronous operation to get the default main loop model to use
 * (bypassing any user-specified values).
 */
export function getDefaultMainLoopModel(): ModelName {
  return UMMAYA_K_EXAONE_MODEL as ModelName
}

/**
 * UMMAYA Epic #2112: legacy name-pattern dispatch (15+ branches) collapsed to a
 * fail-safe single branch keyed on K-EXAONE detection.
 *
 * [Deferred to P2 — issue #2147]: this function is preserved as an export for
 * services/api/ummaya.ts callers; removed together with that file in Phase P2.
 */
export function firstPartyNameToCanonical(name: ModelName): ModelShortName {
  const lowered = name.toLowerCase()
  if (lowered.includes('k-exaone')) {
    return UMMAYA_K_EXAONE_SHORT as ModelShortName
  }
  // Fall back to the original name unchanged. Pre-P2 callers that pass
  // legacy-shaped strings receive them back as-is — the dispatch table
  // they depended on is dead, but the call site does not crash.
  return name as ModelShortName
}

/**
 * Maps a full model string to a shorter canonical version.
 * UMMAYA routes everything through firstPartyNameToCanonical's K-EXAONE branch.
 */
export function getCanonicalName(fullModelName: ModelName): ModelShortName {
  return firstPartyNameToCanonical(resolveOverriddenModel(fullModelName))
}

export function getClaudeAiUserDefaultModelDescription(_fastMode = false): string {
  return `${UMMAYA_K_EXAONE_DISPLAY} · UMMAYA default`
}

export function renderDefaultModelSetting(setting: ModelName | ModelAlias): string {
  return renderModelName(parseUserSpecifiedModel(setting))
}

export function getOpus46PricingSuffix(_fastMode: boolean): string {
  // UMMAYA: no Opus pricing tier; returns empty.
  return ''
}

export function isOpus1mMergeEnabled(): boolean {
  // UMMAYA: no Opus 1M merge — single-fixed K-EXAONE 256K context.
  return false
}

export function renderModelSetting(setting: ModelName | ModelAlias): string {
  if (isModelAlias(setting)) {
    return UMMAYA_K_EXAONE_DISPLAY
  }
  return renderModelName(setting)
}

/**
 * Returns a human-readable display name for known public models, or null
 * if the model is not recognized as a public model.
 *
 * UMMAYA: only the canonical K-EXAONE identifier is recognised; everything else returns null.
 */
export function getPublicModelDisplayName(model: ModelName): string | null {
  if (model === UMMAYA_K_EXAONE_MODEL) {
    return UMMAYA_K_EXAONE_DISPLAY
  }
  // modelStrings still exposes legacy keys for the bucket-B callers; if they
  // happen to match one of those keys at runtime, fall through to null so the
  // caller can apply its own fallback.
  return null
}

export function renderModelName(model: ModelName): string {
  return getPublicModelDisplayName(model) ?? model
}

/**
 * Returns a safe author name for public display (e.g., in git commit trailers).
 * UMMAYA: returns "K-EXAONE" branding instead of "Claude".
 */
export function getPublicModelName(model: ModelName): string {
  const publicName = getPublicModelDisplayName(model)
  if (publicName) {
    return publicName
  }
  return `UMMAYA (${model})`
}

/**
 * Returns a full model name for use in this session, possibly after resolving
 * a model alias.
 *
 * UMMAYA: every alias and unknown name resolves to the canonical K-EXAONE model;
 * the [1m] suffix path is dead (K-EXAONE supports 256K natively).
 */
export function parseUserSpecifiedModel(modelInput: ModelName | ModelAlias): ModelName {
  const trimmed = modelInput.trim()
  if (trimmed.length === 0) {
    return getDefaultMainLoopModel()
  }
  const normalised = trimmed.toLowerCase()
  if (isModelAlias(normalised)) {
    return getDefaultMainLoopModel()
  }
  if (normalised === UMMAYA_K_EXAONE_MODEL.toLowerCase()) {
    return UMMAYA_K_EXAONE_MODEL
  }
  // Codex P1 (PR #2151): legacy alias values (`sonnet`, `opus`, `haiku`, `best`,
  // `opusplan`, plus `[1m]` variants) may still flow in from existing configs,
  // settings.json, or agent definitions. The narrow `isModelAlias` table only
  // recognises `default` post-Spec 2112, so without remapping these legacy
  // strings would be returned as literal model IDs and routed to FriendliAI,
  // which rejects them. Map any token containing one of those legacy family
  // names to the canonical K-EXAONE model so backward-compatibility holds
  // until the Spec 2147 cleanup migrates configs forward.
  if (
    normalised === 'sonnet' || normalised === 'opus' || normalised === 'haiku' ||
    normalised === 'best' || normalised === 'opusplan' ||
    normalised === 'sonnet[1m]' || normalised === 'opus[1m]' ||
    normalised === 'haiku[1m]'
  ) {
    return getDefaultMainLoopModel()
  }
  // Preserve the original case for custom model names (e.g. Azure Foundry deployment IDs).
  return trimmed
}

/**
 * Resolves a skill's `model:` frontmatter against the current model.
 * UMMAYA: K-EXAONE has a single context window (256K native); the [1m] carry-over
 * logic is dead. Pass the skill model through unchanged when it does not already
 * carry a [1m] tag, otherwise honour the explicit tag.
 */
export function resolveSkillModelOverride(skillModel: string, currentModel: string): string {
  if (has1mContext(skillModel) || !has1mContext(currentModel)) {
    return skillModel
  }
  if (modelSupports1M(parseUserSpecifiedModel(skillModel))) {
    return skillModel + '[1m]'
  }
  return skillModel
}

export function isLegacyModelRemapEnabled(): boolean {
  // UMMAYA: no legacy remap; helper preserved for caller import-graph.
  return false
}

export function modelDisplayString(model: ModelSetting): string {
  if (model === null) {
    if (isClaudeAISubscriber()) {
      return `Default (${getClaudeAiUserDefaultModelDescription()})`
    }
    return `Default (${getDefaultMainLoopModel()})`
  }
  const resolvedModel = parseUserSpecifiedModel(model)
  return model === resolvedModel ? resolvedModel : `${model} (${resolvedModel})`
}

/**
 * UMMAYA: returns the K-EXAONE marketing name for the canonical identifier;
 * undefined for everything else. Bucket-B callers that pass legacy-shaped
 * strings receive undefined and apply their own fallback.
 */
export function getMarketingNameForModel(modelId: string): string | undefined {
  if (modelId === UMMAYA_K_EXAONE_MODEL) {
    return UMMAYA_K_EXAONE_DISPLAY
  }
  return undefined
}

export function normalizeModelStringForAPI(model: string): string {
  return model.replace(/\[(1|2)m\]/gi, '')
}

// modelStrings is preserved as a re-exported helper because legacy callers
// (Bucket B) still consume it. See modelStrings.ts for the K-EXAONE collapse.
export { getModelStrings }
