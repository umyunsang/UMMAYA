// SPDX-License-Identifier: Apache-2.0
// UMMAYA-original — Epic #1634 P3 · SendPrimitive.
//
// LLM-visible tool name: "send"
// Primitive wrapper over Spec 031 ummaya.primitives.send.
// Permission-gated side-effecting citizen action (application, report, etc.)
//
// Epic γ #2294 · T010/T011/T012: real validateInput + renderToolResultMessage.
//
// I/O contract: specs/1634-tool-system-wiring/contracts/primitive-envelope.md § 3

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
import { SEND_TOOL_NAME, DESCRIPTION, SEND_TOOL_PROMPT } from './prompt.js'
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
    value => normalizeRootPrimitiveAdapterEnvelope(SEND_TOOL_NAME, value),
    z.strictObject({
      tool_id: z
        .string()
        .min(1)
        .describe('Registered send adapter identifier from <available_adapters>'),
      params: z
        .record(z.string(), z.unknown())
        .describe('Adapter-defined Pydantic-validated parameter body'),
    }),
  ),
)
type InputSchema = ReturnType<typeof inputSchema>

// ---------------------------------------------------------------------------
// Output schema — discriminated union on "ok"
// ---------------------------------------------------------------------------

// Spec 2521 (2026-05-02) — ``outbound_traces`` preserved through
// safeParse so verboseRender can show the agency POST request/response.
const outputSchema = lazySchema(() =>
  z.discriminatedUnion('ok', [
    z.object({
      ok: z.literal(true),
      result: z.unknown().describe('Submit result including transaction_id, status, adapter_receipt'),
      outbound_traces: z.array(z.unknown()).optional(),
    }),
    z.object({
      ok: z.literal(false),
      error: z.object({
        kind: z.string().describe('Error classification, e.g. "permission_denied", "tool_not_found"'),
        message: z.string().describe('Human-readable error description'),
      }),
      outbound_traces: z.array(z.unknown()).optional(),
    }),
  ]),
)
type OutputSchema = ReturnType<typeof outputSchema>

export type Output = z.infer<OutputSchema>

const KOREAN_RECEIPT_NUMBER_KEY = '\uc811\uc218\ubc88\ud638'

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null
    ? (value as Record<string, unknown>)
    : null
}

function firstString(record: Record<string, unknown> | null, keys: string[]): string | null {
  if (!record) return null
  for (const key of keys) {
    const value = record[key]
    if (typeof value === 'string' && value.trim()) return value
  }
  return null
}

function buildSubmitSuccessRows(output: Extract<Output, { ok: true }>): React.ReactNode[] {
  const result = asRecord(output.result)
  const adapterReceipt = asRecord(result?.adapter_receipt)
  const receiptId =
    firstString(adapterReceipt, [
      'receipt_id',
      'receipt_number',
      'confirmation_id',
      KOREAN_RECEIPT_NUMBER_KEY,
    ]) ?? firstString(result, ['receipt_id', 'receipt_number', 'confirmation_id'])
  const ministry =
    typeof result?.ministry === 'string' ? result.ministry : null
  const status =
    typeof result?.status === 'string' ? result.status : null
  const handoffUrl =
    typeof result?.agency_handoff_url === 'string'
      ? result.agency_handoff_url
      : null

  const statusLabel =
    status === 'accepted'
      ? 'accepted'
      : status === 'succeeded'
        ? 'completed'
        : status === 'pending'
          ? 'pending'
          : status === 'rejected'
            ? 'rejected'
            : status

  const mockMeta = extractMockMeta(output)
  const isMock = mockMeta.isMock
  const successLabel = isMock
    ? mockLabel('Submission accepted')
    : `✓ ${ministry ? `[${ministry}] ` : ''}Submission accepted.`
  const successColor = isMock ? ('cyan' as const) : ('green' as const)

  return [
    React.createElement(
      Text,
      { key: 'heading', color: successColor, dimColor: isMock },
      isMock
        ? `${successLabel}${ministry ? ` — [${ministry}]` : ''}`
        : successLabel,
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
    ...(receiptId
      ? [React.createElement(Text, { key: 'receipt', dimColor: true }, `Receipt ID: ${receiptId}`)]
      : []),
    ...(status
      ? [React.createElement(Text, { key: 'status', dimColor: true }, `Status: ${statusLabel}`)]
      : []),
    ...(handoffUrl
      ? [React.createElement(Text, { key: 'handoff', dimColor: true }, `Agency confirmation: ${handoffUrl}`)]
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

function buildSubmitErrorRows(output: Extract<Output, { ok: false }>): React.ReactNode[] {
  const handoffUrl =
    typeof (output.error as Record<string, unknown>)?.agency_handoff_url ===
    'string'
      ? ((output.error as Record<string, unknown>).agency_handoff_url as string)
      : null

  return [
    React.createElement(Text, { key: 'error', color: 'red' }, `✗ ${output.error.message}`),
    ...(handoffUrl
      ? [React.createElement(Text, { key: 'handoff', dimColor: true }, `Agency contact: ${handoffUrl}`)]
      : []),
  ]
}

// ---------------------------------------------------------------------------
// Tool definition
// ---------------------------------------------------------------------------

export const SubmitPrimitive = buildTool({
  name: SEND_TOOL_NAME,

  /** English keyword hint for ToolSearch deferred-tool discovery. */
  searchHint: 'submit application report send apply public service side effect',

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
    // send is side-effecting — not concurrency safe.
    return false
  },

  isReadOnly() {
    return false
  },

  isDestructive() {
    // send can be irreversible (e.g., form submission, report filing).
    return true
  },

  async description() {
    return DESCRIPTION
  },

  async prompt() {
    return SEND_TOOL_PROMPT
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
    input: { tool_id?: string; params?: unknown },
    options: { verbose: boolean },
  ) {
    // Spec 2521 (2026-05-01 evening) — verbose flag surfaces the full
    // request body the LLM submitted (CC BashTool parity).
    if (options.verbose) {
      return renderVerboseInputJson(input)
    }
    return input.tool_id ?? ''
  },

  // Epic γ #2294 · T010/T011 · real validateInput + renderToolResultMessage.
  isMcp: false,

  async validateInput(
    input: { tool_id: string; params: Record<string, unknown> },
    context: ToolUseContext,
  ) {
    // Epic ε #2296 T012 — two-tier resolution (FR-017 / FR-018 / FR-019 / FR-020).
    // Spec 2521 (2026-05-01) — citation-missing branch added so the
    // 1002 contract (Spec 024 invariant: every adapter cites the agency
    // policy URL) is enforced at the primitive surface.

    if (isRootPrimitiveToolId(input.tool_id)) {
      return {
        result: false as const,
        message: rootPrimitiveSelfTargetMessage(input.tool_id, 'send'),
        errorCode: PrimitiveErrorCode.AdapterNotFound,
      }
    }

    // Tier 1 — synced backend manifest (FR-017).
    if (isManifestSynced()) {
      const backendEntry = resolveAdapter(input.tool_id)
      if (backendEntry) {
        // Internal-mode adapters (find/send/check primitives
        // themselves, locate, etc.) are not citizen-facing
        // agency calls and are exempt from the citation invariant.
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
      (t): t is typeof t & AdapterWithPolicy => t.name === input.tool_id,
    ) as (AdapterWithPolicy & { name: string }) | undefined

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
    // the full envelope JSON. CC BashTool/UI.tsx:renderToolResultMessage
    // pattern.
    if (options.verbose || options.isTranscriptMode) {
      return renderVerboseOutputJson(output)
    }
    // NOTE: This file is `.ts` (not `.tsx`); Bun runtime cannot parse JSX in
    // `.ts`. Use `React.createElement` for parity with the other 3 primitives.
    //
    // UMMAYA hotfix #2519 — after dispatchPrimitive register-and-await
    // rewrite, output.result is the actual send primitive output
    // (transaction_id / ministry / status / agency_handoff_url) unwrapped
    // from ToolResultEnvelope.result.
    if (output.ok) {
      return renderCompactPrimitiveResult(buildSubmitSuccessRows(output))
    }

    return renderCompactPrimitiveResult(buildSubmitErrorRows(output))
  },

  isResultTruncated(output: Output): boolean {
    return isPrimitiveResultPreviewTruncated(
      output.ok
        ? buildSubmitSuccessRows(output)
        : buildSubmitErrorRows(output),
    )
  },

  /**
   * send is a side-effecting citizen action (application, report, etc.) that may
   * be irreversible. Always ask for citizen permission before proceeding.
   * Spec 024 invariant: adapters cite agency policy; the permission gauntlet
   * surfaces that citation via context.ummayaCitations (set in validateInput).
   */
  async checkPermissions(_input) {
    return {
      behavior: 'ask' as const,
      message: 'Permission delegation required: send a submission request to the agency. Continue?',
    }
  },

  /**
   * Dispatch send call via real IPC bridge (T011 — stub replaced).
   */
  async call(input, context) {
    return dispatchPrimitive<Output>({
      primitive: 'send',
      args: input as Record<string, unknown>,
      context,
      registry: getOrCreatePendingCallRegistry(),
      bridge: getOrCreateUmmayaBridge(),
    })
  },
} satisfies ToolDef<InputSchema, Output>)
