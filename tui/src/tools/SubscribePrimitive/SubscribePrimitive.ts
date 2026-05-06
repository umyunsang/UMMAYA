// SPDX-License-Identifier: Apache-2.0
// KOSMOS-original — Epic #1634 P3 · SubscribePrimitive.
//
// LLM-visible tool name: "subscribe"
// Primitive wrapper over Spec 031 kosmos.primitives.subscribe.
// Returns a SubscriptionHandle with session-lifetime; stream delivered out-of-band.
//
// Epic γ #2294 · T016/T017/T018: real validateInput + renderToolResultMessage.
//
// I/O contract: specs/1634-tool-system-wiring/contracts/primitive-envelope.md § 5

import React from 'react'
import { z } from 'zod/v4'
import { Box, Text } from '../../ink.js'
import { MessageResponse } from '../../components/MessageResponse.js'
import { buildTool, type ToolDef, type ToolUseContext } from '../../Tool.js'
import { lazySchema } from '../../utils/lazySchema.js'
import {
  extractCitation,
  PrimitiveErrorCode,
  type AdapterCitation,
  type AdapterWithPolicy,
} from '../shared/primitiveCitation.js'
import { extractMockMeta, mockLabel } from '../shared/mockDisclaimer.js'
import { SUBSCRIBE_TOOL_NAME, DESCRIPTION, SUBSCRIBE_TOOL_PROMPT } from './prompt.js'
import {
  isManifestSynced,
  resolveAdapter,
} from '../../services/api/adapterManifest.js'
import { dispatchPrimitive } from '../_shared/dispatchPrimitive.js'
import {
  renderVerboseInputJson,
  renderVerboseOutputJson,
} from '../_shared/verboseRender.js'
import { getOrCreateKosmosBridge } from '../../ipc/bridgeSingleton.js'
import { getOrCreatePendingCallRegistry } from '../../ipc/pendingCallSingleton.js'

// ---------------------------------------------------------------------------
// KOSMOS citation extension — augments context at runtime for permission UI.
// Does NOT modify Tool.ts or ToolPermissionContext; uses a local cast to attach
// the citation so FallbackPermissionRequest can surface verbatim agency text.
// ---------------------------------------------------------------------------
type ContextWithCitation = ToolUseContext & {
  kosmosCitations?: AdapterCitation[]
}

// ---------------------------------------------------------------------------
// Input schema
// ---------------------------------------------------------------------------

const inputSchema = lazySchema(() =>
  z.strictObject({
    tool_id: z
      .string()
      .min(1)
      .describe('Streaming adapter identifier (obtain via lookup mode=search)'),
    params: z
      .record(z.string(), z.unknown())
      .describe('Adapter-defined Pydantic-validated subscription parameter body'),
    lifetime_seconds: z
      .number()
      .int()
      .min(1)
      .max(31_536_000)
      .optional()
      .describe(
        'Bounded subscription lifetime in seconds. Ceiling = 365 days.',
      ),
  }),
)
type InputSchema = ReturnType<typeof inputSchema>

// ---------------------------------------------------------------------------
// Output schema — discriminated union on "ok"
// ---------------------------------------------------------------------------

// Spec 2521 (2026-05-02) — ``outbound_traces`` preserved through
// safeParse so verboseRender can show the subscription handshake's
// outbound HTTP if the adapter pulls before yielding.
const outputSchema = lazySchema(() =>
  z.discriminatedUnion('ok', [
    z.object({
      ok: z.literal(true),
      result: z.unknown().describe(
        'SubscriptionHandle: { handle_id, lifetime, kind } — stream delivered out-of-band via TUI ⎿ prefix',
      ),
      outbound_traces: z.array(z.unknown()).optional(),
    }),
    z.object({
      ok: z.literal(false),
      error: z.object({
        kind: z.string().describe('Error classification, e.g. "tool_not_found", "permission_denied"'),
        message: z.string().describe('Human-readable error description'),
      }),
      outbound_traces: z.array(z.unknown()).optional(),
    }),
  ]),
)
type OutputSchema = ReturnType<typeof outputSchema>

export type Output = z.infer<OutputSchema>

// ---------------------------------------------------------------------------
// Tool definition
// ---------------------------------------------------------------------------

export const SubscribePrimitive = buildTool({
  name: SUBSCRIBE_TOOL_NAME,

  /** Bilingual keyword hint for ToolSearch deferred-tool discovery. */
  searchHint: '구독 스트리밍 subscribe streaming 재난 알림 실시간 alert realtime',

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
    // subscribe is session-scoped and side-effecting — not concurrency safe.
    return false
  },

  isReadOnly() {
    return false
  },

  userFacingName() {
    return 'watch'
  },

  async description() {
    return DESCRIPTION
  },

  async prompt() {
    return SUBSCRIBE_TOOL_PROMPT
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
    // Spec 2521 (2026-05-01 evening) — verbose surfaces full request JSON.
    if (options.verbose) {
      return renderVerboseInputJson(input)
    }
    return input.tool_id ?? ''
  },

  // Epic γ #2294 · T016/T017 · real validateInput + renderToolResultMessage.
  isMcp: false,

  async validateInput(
    input: z.infer<ReturnType<typeof inputSchema>>,
    context: ToolUseContext,
  ) {
    // Epic ε #2296 T014 — two-tier resolution (FR-017 / FR-018 / FR-019 / FR-020).
    // Spec 2521 (2026-05-01) — citation-missing branch added (1002).

    // Tier 1 — synced backend manifest (FR-017).
    if (isManifestSynced()) {
      const backendEntry = resolveAdapter(input.tool_id)
      if (backendEntry) {
        if (backendEntry.source_mode === 'internal') {
          ;(context as ContextWithCitation).kosmosCitations = []
          return { result: true as const }
        }
        if (!backendEntry.policy_authority_url) {
          return {
            result: false as const,
            message: `'${input.tool_id}' 어댑터 정책 인용이 누락되었습니다 (Spec 024 invariant 위반).`,
            errorCode: PrimitiveErrorCode.CitationMissing,
          }
        }
        const citation: AdapterCitation = {
          real_classification_url: backendEntry.policy_authority_url,
          policy_authority: backendEntry.name,
        }
        ;(context as ContextWithCitation).kosmosCitations = [citation]
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
          message: `'${input.tool_id}' 어댑터 정책 인용이 누락되었습니다 (Spec 024 invariant 위반).`,
          errorCode: PrimitiveErrorCode.CitationMissing,
        }
      }
      ;(context as ContextWithCitation).kosmosCitations = [citation]
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
    // KOSMOS hotfix #2519 — after dispatchPrimitive register-and-await
    // rewrite, output.result is the actual subscribe primitive output
    // (handle_id / lifetime / kind) unwrapped from ToolResultEnvelope.result.
    if (output.ok === true) {
      // Extract handle metadata from the result payload.
      const result = output.result as Record<string, unknown> | null | undefined
      const handleId =
        result && typeof result === 'object' ? result['handle_id'] : undefined
      const lifetime =
        result && typeof result === 'object' ? result['lifetime'] : undefined
      const kind =
        result && typeof result === 'object' ? result['kind'] : undefined

      const handleLabel = handleId
        ? String(handleId)
        : '핸들 ID 없음'
      const kindLabel = kind ? `(${String(kind)})` : ''
      const lifetimeLabel = lifetime
        ? `유지 시간: ${String(lifetime)}`
        : undefined

      // Audit-2 P0: check _mode === 'mock' from transparency stamp (Spec 024).
      const mockMeta = extractMockMeta(output)
      const isMock = mockMeta.isMock

      const subscribeHeading = isMock ? mockLabel('구독 시작') : '구독 완료:'
      const subscribeColor = isMock ? ('cyan' as never) : (undefined as never)

      // KOSMOS hotfix #2519 — wrap in <MessageResponse> for the CC ⎿ prefix.
      // Drop the explicit "⎿ 실시간 스트림은…" line since MessageResponse now
      // owns the leading "  ⎿  " glyph; restating it produced a doubled tree.
      return React.createElement(
        MessageResponse,
        null,
        React.createElement(
          Box,
          { flexDirection: 'column' },
          React.createElement(
            Text,
            null,
            React.createElement(
              Text,
              { bold: true, color: subscribeColor, dimColor: isMock },
              subscribeHeading + ' ',
            ),
            React.createElement(Text, null, `${handleLabel} ${kindLabel}`.trim()),
          ),
          isMock
            ? React.createElement(
                Text,
                { dimColor: true },
                '실제 행정 영향 없는 시연 결과입니다.',
              )
            : null,
          lifetimeLabel
            ? React.createElement(Text, { dimColor: true }, lifetimeLabel)
            : null,
          React.createElement(
            Text,
            { dimColor: true },
            '실시간 스트림은 대화창에서 별도 ⎿ 인용으로 전달됩니다.',
          ),
          isMock && mockMeta.actualEndpointWhenLive
            ? React.createElement(
                Text,
                { dimColor: true },
                `실제 엔드포인트 (운영 시): ${mockMeta.actualEndpointWhenLive}`,
              )
            : null,
        ),
      )
    }

    // output.ok === false: render error message in Korean.
    const errorMsg = output.error?.message ?? '구독 요청이 실패하였습니다.'
    return React.createElement(
      MessageResponse,
      { height: 1 },
      React.createElement(
        Text,
        { color: 'red' as never },
        `구독 실패: ${errorMsg}`,
      ),
    )
  },

  /**
   * Backend owns the KOSMOS permission gauntlet for backend-dispatched
   * primitives. Subscribe opens a persistent channel and remains gated in
   * Python GATED_PRIMITIVES; the stdio dispatcher emits the canonical
   * PermissionRequestFrame before adapter invocation. Keeping a separate
   * client-side prompt here duplicates the gauntlet and can block stream
   * consumption.
   */
  async checkPermissions(input) {
    return { behavior: 'allow' as const, updatedInput: input }
  },

  /**
   * Dispatch subscribe call via real IPC bridge (T012 — stub replaced).
   *
   * I-D9: returns the first tool_result frame's envelope as a
   * "subscription opened" acknowledgment. Subsequent stream events
   * are deferred (spec.md Deferred Items — out of scope for Phase 0).
   */
  async call(input, context) {
    const result = await dispatchPrimitive<Output>({
      primitive: 'subscribe',
      args: input as Record<string, unknown>,
      context,
      registry: getOrCreatePendingCallRegistry(),
      bridge: getOrCreateKosmosBridge(),
    })

    return result
  },
} satisfies ToolDef<InputSchema, Output>)
