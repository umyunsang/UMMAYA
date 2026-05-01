// SPDX-License-Identifier: Apache-2.0
// KOSMOS-original — Epic #1634 P3 · VerifyPrimitive.
//
// LLM-visible tool name: "verify"
// Primitive wrapper over Spec 031 kosmos.primitives.verify.
// Delegates credential verification to an auth vendor — never mints credentials.
//
// Epic γ #2294 · T013/T014/T015: real validateInput + renderToolResultMessage.
//
// I/O contract: specs/1634-tool-system-wiring/contracts/primitive-envelope.md § 4

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
import { VERIFY_TOOL_NAME, DESCRIPTION, VERIFY_TOOL_PROMPT } from './prompt.js'
import {
  isManifestSynced,
  resolveAdapter,
} from '../../services/api/adapterManifest.js'
import { dispatchPrimitive } from '../_shared/dispatchPrimitive.js'
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
      .describe('Auth adapter identifier, e.g. "gongdong_injeungseo", "mobile_id"'),
    params: z
      .record(z.string(), z.unknown())
      .describe('Adapter-defined credential parameter body'),
  }),
)
type InputSchema = ReturnType<typeof inputSchema>

// ---------------------------------------------------------------------------
// Output schema — discriminated union on "ok"
// ---------------------------------------------------------------------------

const outputSchema = lazySchema(() =>
  z.discriminatedUnion('ok', [
    z.object({
      ok: z.literal(true),
      result: z.unknown().describe(
        'Verify result including auth_family, auth_level, and adapter-specific verification payload',
      ),
    }),
    z.object({
      ok: z.literal(false),
      error: z.object({
        kind: z.string().describe('Error classification, e.g. "verification_failed", "tool_not_found"'),
        message: z.string().describe('Human-readable error description'),
      }),
    }),
  ]),
)
type OutputSchema = ReturnType<typeof outputSchema>

export type Output = z.infer<OutputSchema>

// ---------------------------------------------------------------------------
// Tool definition
// ---------------------------------------------------------------------------

export const VerifyPrimitive = buildTool({
  name: VERIFY_TOOL_NAME,

  /** Bilingual keyword hint for ToolSearch deferred-tool discovery. */
  searchHint: '인증 검증 verify credential auth 공인인증서 간편인증 본인확인',

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
    // verify is read-only (delegates, never mints) — concurrency safe.
    return true
  },

  isReadOnly() {
    return true
  },

  async description() {
    return DESCRIPTION
  },

  async prompt() {
    return VERIFY_TOOL_PROMPT
  },

  mapToolResultToToolResultBlockParam(output, toolUseID) {
    return {
      tool_use_id: toolUseID,
      type: 'tool_result',
      content: JSON.stringify(output),
    }
  },

  renderToolUseMessage(input: { tool_id?: string; family_hint?: string }) {
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

  renderToolResultMessage(output: Output) {
    // KOSMOS hotfix #2519 — after dispatchPrimitive register-and-await
    // rewrite, output.result is the actual verify primitive output
    // unwrapped from ToolResultEnvelope.result.
    if (output.ok === true) {
      // Extract verification status from the result payload.
      const result = output.result as Record<string, unknown> | null | undefined
      const rawStatus =
        result && typeof result === 'object' ? result['status'] : undefined
      const rawAuthority =
        result && typeof result === 'object' ? result['policy_authority'] : undefined

      // Map status to citizen-facing Korean label.
      let statusLabel: string
      let statusColor: string
      if (rawStatus === 'verified' || rawStatus === true) {
        statusLabel = '인증 완료'
        statusColor = 'green'
      } else if (rawStatus === 'pending') {
        statusLabel = '인증 처리 중'
        statusColor = 'yellow'
      } else if (rawStatus === 'failed' || rawStatus === false) {
        statusLabel = '인증 실패'
        statusColor = 'red'
      } else {
        statusLabel = String(rawStatus ?? '결과 수신됨')
        statusColor = 'white'
      }

      const authorityText = rawAuthority
        ? `출처: ${String(rawAuthority)}`
        : undefined

      // KOSMOS hotfix #2519 — wrap in <MessageResponse> for the CC ⎿ prefix.
      return React.createElement(
        MessageResponse,
        null,
        React.createElement(
          Box,
          { flexDirection: 'column' },
          React.createElement(
            Text,
            null,
            React.createElement(Text, { bold: true }, '검증 결과: '),
            React.createElement(Text, { color: statusColor as never }, statusLabel),
          ),
          authorityText
            ? React.createElement(
                Text,
                { dimColor: true },
                authorityText,
              )
            : null,
        ),
      )
    }

    // output.ok === false: render rejection reason in Korean.
    const errorMsg = output.error?.message ?? '검증 요청이 거부되었습니다.'
    return React.createElement(
      MessageResponse,
      { height: 1 },
      React.createElement(
        Text,
        { color: 'red' as never },
        `인증 거부: ${errorMsg}`,
      ),
    )
  },

  /**
   * Dispatch verify call via real IPC bridge (T010 — stub replaced).
   *
   * I-D8 / FR-009: args forwarded verbatim — NO tool_id→family_hint translation
   * at TUI side. The backend's _VerifyInputForLLM pre-validator owns translation.
   */
  async call(input, context) {
    return dispatchPrimitive<Output>({
      primitive: 'verify',
      args: input as Record<string, unknown>,  // forwarded verbatim (I-D8)
      context,
      registry: getOrCreatePendingCallRegistry(),
      bridge: getOrCreateKosmosBridge(),
    })
  },
} satisfies ToolDef<InputSchema, Output>)
