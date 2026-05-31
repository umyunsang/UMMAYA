// SPDX-License-Identifier: Apache-2.0
// UMMAYA-original — Epic #1634 P3 · CheckPrimitive.
//
// LLM-visible tool name: "check"
// Primitive wrapper over Spec 031 ummaya.primitives.check.
// Delegates credential verification to an auth vendor — never mints credentials.
//
// Epic γ #2294 · T013/T014/T015: real validateInput + renderToolResultMessage.
//
// I/O contract: specs/1634-tool-system-wiring/contracts/primitive-envelope.md § 4

import React from 'react'
import { z } from 'zod/v4'
import { Text } from '../../ink.js'
import { buildTool, type ToolDef, type ToolUseContext } from '../../Tool.js'
import { lazySchema } from '../../utils/lazySchema.js'
import {
  extractCitation,
  PrimitiveErrorCode,
  type AdapterCitation,
  type AdapterWithPolicy,
} from '../shared/primitiveCitation.js'
import { extractMockMeta, mockLabel } from '../shared/mockDisclaimer.js'
import { CHECK_TOOL_NAME, DESCRIPTION, CHECK_TOOL_PROMPT } from './prompt.js'
import {
  isManifestSynced,
  resolveAdapter,
} from '../../services/api/adapterManifest.js'
import { dispatchPrimitive } from '../_shared/dispatchPrimitive.js'
import {
  renderVerboseInputJson,
  renderVerboseOutputJson,
} from '../_shared/verboseRender.js'
import {
  isPrimitiveResultPreviewTruncated,
  renderCompactPrimitiveResult,
} from '../_shared/compactPrimitiveResult.js'
import { getOrCreateUmmayaBridge } from '../../ipc/bridgeSingleton.js'
import { getOrCreatePendingCallRegistry } from '../../ipc/pendingCallSingleton.js'
import {
  isRootPrimitiveToolId,
  normalizeRootPrimitiveAdapterEnvelope,
  rootPrimitiveSelfTargetMessage,
} from '../_shared/rootPrimitiveInput.js'

// ---------------------------------------------------------------------------
// UMMAYA citation extension — augments context at runtime for permission UI.
// Does NOT modify Tool.ts or ToolPermissionContext; uses a local cast to attach
// the citation so FallbackPermissionRequest can surface verbatim agency text.
// ---------------------------------------------------------------------------
type ContextWithCitation = ToolUseContext & {
  ummayaCitations?: AdapterCitation[]
}

// ---------------------------------------------------------------------------
// Input schema
// ---------------------------------------------------------------------------

const inputSchema = lazySchema(() =>
  z.preprocess(
    value => normalizeRootPrimitiveAdapterEnvelope(CHECK_TOOL_NAME, value),
    z.strictObject({
      tool_id: z
        .string()
        .min(1)
        .describe('Auth adapter identifier, e.g. "mock_verify_mobile_id"'),
      params: z
        .record(z.string(), z.unknown())
        .describe('Adapter-defined credential parameter body'),
    }),
  ),
)
type InputSchema = ReturnType<typeof inputSchema>

// ---------------------------------------------------------------------------
// Output schema — discriminated union on "ok"
// ---------------------------------------------------------------------------

// Spec 2521 (2026-05-02) — ``outbound_traces`` preserved through
// safeParse so verboseRender can show the verification vendor's HTTP
// request/response.
const outputSchema = lazySchema(() =>
  z.discriminatedUnion('ok', [
    z.object({
      ok: z.literal(true),
      result: z.unknown().describe(
        'Verify result including auth_family, auth_level, and adapter-specific verification payload',
      ),
      outbound_traces: z.array(z.unknown()).optional(),
    }),
    z.object({
      ok: z.literal(false),
      error: z.object({
        kind: z.string().describe('Error classification, e.g. "verification_failed", "tool_not_found"'),
        message: z.string().describe('Human-readable error description'),
      }),
      outbound_traces: z.array(z.unknown()).optional(),
    }),
  ]),
)
type OutputSchema = ReturnType<typeof outputSchema>

export type Output = z.infer<OutputSchema>

function buildVerifySuccessRows(output: Extract<Output, { ok: true }>): React.ReactNode[] {
  const result = output.result as Record<string, unknown> | null | undefined
  const rawStatus =
    result && typeof result === 'object' ? result['status'] : undefined
  const rawAuthority =
    result && typeof result === 'object' ? result['policy_authority'] : undefined
  const rawFamily =
    result && typeof result === 'object' ? result['family'] : undefined
  const rawReason =
    result && typeof result === 'object' ? result['reason'] : undefined

  const isMismatchHere =
    rawFamily === 'mismatch_error' || rawReason === 'family_mismatch'
  if (isMismatchHere) {
    const message =
      (result && typeof result === 'object' && typeof result['message'] === 'string'
        ? (result['message'] as string)
        : null) ?? 'The auth module rejected the request.'
    return [
      React.createElement(
        Text,
        { key: 'mismatch', color: 'red' as never },
        `Authentication module rejected: ${message}`,
      ),
    ]
  }

  let statusLabel: string
  let statusColor: string
  if (rawStatus === 'verified' || rawStatus === true) {
    statusLabel = 'Verification complete'
    statusColor = 'green'
  } else if (rawStatus === 'pending') {
    statusLabel = 'Verification pending'
    statusColor = 'yellow'
  } else if (rawStatus === 'failed' || rawStatus === false) {
    statusLabel = 'Verification failed'
    statusColor = 'red'
  } else {
    statusLabel = String(rawStatus ?? 'Result received')
    statusColor = 'white'
  }

  const authorityText = rawAuthority
    ? `Source: ${String(rawAuthority)}`
    : undefined
  const mockMeta = extractMockMeta(output)
  const isMock = mockMeta.isMock
  const verifyLabel = isMock ? mockLabel(statusLabel) : statusLabel
  const verifyColor = isMock ? ('cyan' as never) : (statusColor as never)

  return [
    React.createElement(
      Text,
      { key: 'heading' },
      React.createElement(Text, { bold: true }, 'Verification result: '),
      React.createElement(Text, { color: verifyColor, dimColor: isMock }, verifyLabel),
    ),
    ...(isMock
      ? [
          React.createElement(
            Text,
            { key: 'mock-disclaimer', dimColor: true },
            'Demo-only result. No real administrative action was taken.',
          ),
        ]
      : []),
    ...(authorityText
      ? [
          React.createElement(
            Text,
            { key: 'authority', dimColor: true },
            authorityText,
          ),
        ]
      : []),
    ...(isMock && mockMeta.actualEndpointWhenLive
      ? [
          React.createElement(
            Text,
            { key: 'mock-live-endpoint', dimColor: true },
            `Live endpoint: ${mockMeta.actualEndpointWhenLive}`,
          ),
        ]
      : []),
  ]
}

function buildVerifyErrorRows(output: Extract<Output, { ok: false }>): React.ReactNode[] {
  const errorMsg = output.error?.message ?? 'The verification request was rejected.'
  const errorKind = output.error?.kind
  const isMismatchKind = errorKind === 'mismatch_error' || errorKind === 'family_mismatch'
  return [
    React.createElement(
      Text,
      { key: 'error', color: 'red' as never },
      isMismatchKind
        ? `Authentication module rejected: ${errorMsg}`
        : `Authentication rejected: ${errorMsg}`,
    ),
  ]
}

// ---------------------------------------------------------------------------
// Tool definition
// ---------------------------------------------------------------------------

export const VerifyPrimitive = buildTool({
  name: CHECK_TOOL_NAME,

  /** English keyword hint for ToolSearch deferred-tool discovery. */
  searchHint: 'verify credential check authentication certificate simple auth mobile ID identity',

  maxResultSizeChars: 50_000,

  get inputSchema(): InputSchema {
    return inputSchema()
  },

  get outputSchema(): OutputSchema {
    return outputSchema()
  },

  isEnabled() {
    return true
  },

  isConcurrencySafe() {
    // check is read-only (delegates, never mints) — concurrency safe.
    return true
  },

  isReadOnly() {
    return true
  },

  async description() {
    return DESCRIPTION
  },

  async prompt() {
    return CHECK_TOOL_PROMPT
  },

  mapToolResultToToolResultBlockParam(output, toolUseID) {
    // Spec 2521 (2026-05-02) — outbound_traces is UI-only (see Lookup).
    const llmContent =
      typeof output === 'object' && output !== null
        ? Object.fromEntries(
            Object.entries(output as Record<string, unknown>).filter(
              ([k]) => k !== 'outbound_traces',
            ),
          )
        : output
    return {
      tool_use_id: toolUseID,
      type: 'tool_result',
      content: JSON.stringify(llmContent),
    }
  },

  renderToolUseMessage(
    input: { tool_id?: string; family_hint?: string; params?: unknown },
    options: { verbose: boolean },
  ) {
    // Spec 2521 (2026-05-01 evening) — verbose surfaces full request JSON.
    if (options.verbose) {
      return renderVerboseInputJson(input)
    }
    return input.tool_id ?? input.family_hint ?? ''
  },

  // Epic γ #2294 · T013/T014 · real validateInput + renderToolResultMessage.
  isMcp: false,

  async validateInput(
    input: z.infer<ReturnType<typeof inputSchema>>,
    context: ToolUseContext,
  ) {
    // Epic ε #2296 T013 — two-tier resolution (FR-017 / FR-018 / FR-019 / FR-020).
    // Spec 2521 (2026-05-01) — citation-missing branch added (1002).

    if (isRootPrimitiveToolId(input.tool_id)) {
      return {
        result: false as const,
        message: rootPrimitiveSelfTargetMessage(input.tool_id, 'check'),
        errorCode: PrimitiveErrorCode.AdapterNotFound,
      }
    }

    // Tier 1 — synced backend manifest (FR-017).
    if (isManifestSynced()) {
      const backendEntry = resolveAdapter(input.tool_id)
      if (backendEntry) {
        if (backendEntry.source_mode === 'internal') {
          ;(context as ContextWithCitation).ummayaCitations = []
          return { result: true as const }
        }
        if (!backendEntry.policy_authority_url) {
          return {
            result: false as const,
            message: `Adapter '${input.tool_id}' is missing a policy citation (Spec 024 invariant violation).`,
            errorCode: PrimitiveErrorCode.CitationMissing,
          }
        }
        const citation: AdapterCitation = {
          real_classification_url: backendEntry.policy_authority_url,
          policy_authority: backendEntry.name,
        }
        ;(context as ContextWithCitation).ummayaCitations = [citation]
        return { result: true as const }
      }
    }

    // Tier 2 — TS-side internal tools fallback (FR-018 / existing path).
    const adapter = context.options.tools.find(
      (t) => t.name === input.tool_id,
    ) as AdapterWithPolicy | undefined

    if (adapter) {
      const citation = extractCitation(adapter)
      if (!citation) {
        return {
          result: false as const,
          message: `Adapter '${input.tool_id}' is missing a policy citation (Spec 024 invariant violation).`,
          errorCode: PrimitiveErrorCode.CitationMissing,
        }
      }
      ;(context as ContextWithCitation).ummayaCitations = [citation]
      return { result: true as const }
    }

    // Tier 0 — fail closed if manifest not yet synced AND no internal hit.
    if (!isManifestSynced()) {
      return {
        result: false as const,
        message: 'Adapter manifest not yet synced from backend; retry once boot completes.',
        errorCode: PrimitiveErrorCode.AdapterNotFound,
      }
    }

    // Fail closed (FR-020).
    return {
      result: false as const,
      message: `AdapterNotFound: '${input.tool_id}' is not in the synced backend manifest or the internal tools list.`,
      errorCode: PrimitiveErrorCode.AdapterNotFound,
    }
  },

  renderToolResultMessage(
    output: Output,
    _progress: unknown,
    options: { verbose: boolean; isTranscriptMode?: boolean } = { verbose: false },
  ) {
    // Spec 2521 (2026-05-01 evening) — verbose / transcript mode surface
    // the full envelope JSON. CC BashTool/UI.tsx parity.
    if (options.verbose || options.isTranscriptMode) {
      return renderVerboseOutputJson(output)
    }
    // UMMAYA hotfix #2519 — after dispatchPrimitive register-and-await
    // rewrite, output.result is the actual check primitive output
    // unwrapped from ToolResultEnvelope.result.
    if (output.ok === true) {
      return renderCompactPrimitiveResult(buildVerifySuccessRows(output))
    }

    return renderCompactPrimitiveResult(buildVerifyErrorRows(output))
  },

  isResultTruncated(output: Output): boolean {
    return isPrimitiveResultPreviewTruncated(
      output.ok
        ? buildVerifySuccessRows(output)
        : buildVerifyErrorRows(output),
    )
  },

  /**
   * check delegates to an external auth vendor. Always ask for citizen
   * permission before proceeding.
   * Spec 024 invariant: adapters cite agency policy; the permission gauntlet
   * surfaces that citation via context.ummayaCitations (set in validateInput).
   */
  async checkPermissions(_input) {
    return {
      behavior: 'ask' as const,
      message: 'Permission delegation required: send identity information to the auth provider. Continue?',
    }
  },

  /**
   * Dispatch check call via real IPC bridge (T010 — stub replaced).
   *
   * I-D8 / FR-009: args forwarded verbatim — NO tool_id→family_hint translation
   * at TUI side. The backend's _VerifyInputForLLM pre-validator owns translation.
   */
  async call(input, context) {
    return dispatchPrimitive<Output>({
      primitive: 'check',
      args: input as Record<string, unknown>,  // forwarded verbatim (I-D8)
      context,
      registry: getOrCreatePendingCallRegistry(),
      bridge: getOrCreateUmmayaBridge(),
    })
  },
} satisfies ToolDef<InputSchema, Output>)
