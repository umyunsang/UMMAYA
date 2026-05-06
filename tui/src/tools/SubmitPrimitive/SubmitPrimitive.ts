// SPDX-License-Identifier: Apache-2.0
// KOSMOS-original — Epic #1634 P3 · SubmitPrimitive.
//
// LLM-visible tool name: "submit"
// Primitive wrapper over Spec 031 kosmos.primitives.submit.
// Permission-gated side-effecting citizen action (application, report, etc.)
//
// Epic γ #2294 · T010/T011/T012: real validateInput + renderToolResultMessage.
//
// I/O contract: specs/1634-tool-system-wiring/contracts/primitive-envelope.md § 3

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
import { SUBMIT_TOOL_NAME, DESCRIPTION, SUBMIT_TOOL_PROMPT } from './prompt.js'
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
      .describe('Registered adapter identifier (obtain via lookup mode=search)'),
    params: z
      .record(z.string(), z.unknown())
      .describe('Adapter-defined Pydantic-validated parameter body'),
  }),
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

type JsonObject = Record<string, unknown>

function asJsonObject(value: unknown): JsonObject | null {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? (value as JsonObject)
    : null
}

function stringValue(record: JsonObject | null | undefined, key: string): string | null {
  if (!record) return null
  const value = record[key]
  return typeof value === 'string' && value.trim() ? value : null
}

function submitActionLabel(actionType: string | null): string | null {
  if (actionType === 'file_return') return '신고 제출'
  if (actionType === 'create_payment_deadline_reminder') return '납부기한 알림 생성'
  if (actionType === 'mock_payment_after_confirmation') return '모의 납부 완료'
  return actionType
}

function paymentStepLabel(paymentState: string | null): string | null {
  if (paymentState === 'separate_submit_required_before_payment') {
    return '별도 납부 확인 필요'
  }
  if (paymentState === 'deadline_reminder_created') {
    return '납부기한 알림 생성됨'
  }
  if (paymentState === 'mock_payment_executed_after_confirmation') {
    return '모의 납부 완료'
  }
  return paymentState
}

function submitStatusLabel(status: string | null): string | null {
  if (status === 'accepted') return '접수됨'
  if (status === 'pending') return '처리 중'
  if (status === 'rejected') return '반려됨'
  if (status === 'succeeded') return '성공'
  if (status === 'failed') return '실패'
  return status
}

// ---------------------------------------------------------------------------
// Tool definition
// ---------------------------------------------------------------------------

export const SubmitPrimitive = buildTool({
  name: SUBMIT_TOOL_NAME,

  /** Bilingual keyword hint for ToolSearch deferred-tool discovery. */
  searchHint: '제출 신청 신고 submit apply report 공공 서비스 side-effect',

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
    // submit is side-effecting — not concurrency safe.
    return false
  },

  isReadOnly() {
    return false
  },

  isDestructive() {
    // submit can be irreversible (e.g., form submission, report filing).
    return true
  },

  userFacingName() {
    return 'send'
  },

  async description() {
    return DESCRIPTION
  },

  async prompt() {
    return SUBMIT_TOOL_PROMPT
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

    // Tier 1 — synced backend manifest (FR-017).
    if (isManifestSynced()) {
      const backendEntry = resolveAdapter(input.tool_id)
      if (backendEntry) {
        // Internal-mode adapters (lookup/submit/verify/subscribe primitives
        // themselves, resolve_location, etc.) are not citizen-facing
        // agency calls and are exempt from the citation invariant.
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
      (t): t is typeof t & AdapterWithPolicy => t.name === input.tool_id,
    ) as (AdapterWithPolicy & { name: string }) | undefined

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
    // the full envelope JSON. CC BashTool/UI.tsx:renderToolResultMessage
    // pattern.
    if (options.verbose || options.isTranscriptMode) {
      return renderVerboseOutputJson(output)
    }
    // NOTE: This file is `.ts` (not `.tsx`); Bun runtime cannot parse JSX in
    // `.ts`. Use `React.createElement` for parity with the other 3 primitives.
    //
    // KOSMOS hotfix #2519 — after dispatchPrimitive register-and-await
    // rewrite, output.result is the actual submit primitive output
    // (transaction_id / ministry / status / agency_handoff_url) unwrapped
    // from ToolResultEnvelope.result.
    if (output.ok) {
      const result = asJsonObject(output.result)
      const resultKind = stringValue(result, 'kind')
      const resultReason = stringValue(result, 'reason')
      const resultMessage = stringValue(result, 'message')
      if (resultKind === 'error' || resultReason === 'adapter_invocation_failed') {
        return React.createElement(
          MessageResponse,
          null,
          React.createElement(
            Box,
            { flexDirection: 'column' },
            React.createElement(
              Text,
              { color: 'red' },
              `✗ ${resultMessage ?? resultReason ?? '제출 처리 중 오류가 발생했습니다.'}`,
            ),
            resultReason
              ? React.createElement(Text, { dimColor: true }, `사유: ${resultReason}`)
              : null,
          ),
        )
      }
      const adapterReceipt = asJsonObject(result?.adapter_receipt)
      const preflightValidation = asJsonObject(adapterReceipt?.preflight_validation)
      const receiptId =
        stringValue(adapterReceipt, 'receipt_id') ??
        stringValue(adapterReceipt, 'receipt_number') ??
        stringValue(adapterReceipt, '접수번호') ??
        stringValue(result, 'receipt_id') ??
        stringValue(result, 'transaction_id')
      const transactionId = stringValue(result, 'transaction_id')
      const ministry = stringValue(result, 'ministry')
      const receiptStatus =
        stringValue(adapterReceipt, 'status') ?? stringValue(result, 'status')
      const statusLabel = submitStatusLabel(receiptStatus)
      const actionLabel = submitActionLabel(stringValue(adapterReceipt, 'action_type'))
      const paymentLabel = paymentStepLabel(stringValue(preflightValidation, 'payment'))
      const handoffUrl = stringValue(result, 'agency_handoff_url')
      const rejectionReason =
        stringValue(adapterReceipt, 'reason') ?? stringValue(adapterReceipt, 'error')
      const isRejected = receiptStatus === 'rejected' || receiptStatus === 'failed'
      const isPending = receiptStatus === 'pending'

      // KOSMOS hotfix #2519 — wrap in <MessageResponse> for the CC ⎿ prefix.
      // Audit-2 P0: check _mode === 'mock' from transparency stamp (Spec 024).
      const mockMeta = extractMockMeta(output)
      const isMock = mockMeta.isMock

      const resultLabel = isRejected
        ? isMock
          ? mockLabel('제출 반려')
          : `✗ ${ministry ? `[${ministry}] ` : ''}제출이 반려되었습니다.`
        : isPending
          ? isMock
            ? mockLabel('제출 처리 중')
            : `… ${ministry ? `[${ministry}] ` : ''}제출 처리 중입니다.`
          : isMock
            ? mockLabel('제출 접수')
            : `✓ ${ministry ? `[${ministry}] ` : ''}제출이 접수되었습니다.`
      const resultColor = isRejected
        ? ('red' as const)
        : isPending
          ? ('yellow' as const)
          : isMock
            ? ('cyan' as const)
            : ('green' as const)

      return React.createElement(
        MessageResponse,
        null,
        React.createElement(
          Box,
          { flexDirection: 'column' },
          React.createElement(
            Text,
            { color: resultColor, dimColor: isMock && !isRejected },
            isMock ? `${resultLabel}${ministry ? ` — [${ministry}]` : ''}` : resultLabel,
          ),
          isMock
            ? React.createElement(
                Text,
                { dimColor: true },
                '실제 행정 영향 없는 시연 결과입니다.',
              )
            : null,
          actionLabel
            ? React.createElement(Text, { dimColor: true }, `처리: ${actionLabel}`)
            : null,
          receiptId
            ? React.createElement(Text, { dimColor: true }, `접수 번호: ${receiptId}`)
            : null,
          receiptStatus
            ? React.createElement(Text, { dimColor: true }, `상태: ${statusLabel}`)
            : null,
          rejectionReason
            ? React.createElement(Text, { dimColor: true }, `반려 사유: ${rejectionReason}`)
            : null,
          paymentLabel
            ? React.createElement(Text, { dimColor: true }, `납부 단계: ${paymentLabel}`)
            : null,
          transactionId && transactionId !== receiptId
            ? React.createElement(Text, { dimColor: true }, `트랜잭션: ${transactionId}`)
            : null,
          handoffUrl
            ? React.createElement(Text, { dimColor: true }, `기관 확인: ${handoffUrl}`)
            : null,
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

    // Error branch
    const handoffUrl =
      typeof (output.error as Record<string, unknown>)?.agency_handoff_url ===
      'string'
        ? ((output.error as Record<string, unknown>).agency_handoff_url as string)
        : null

    return React.createElement(
      MessageResponse,
      null,
      React.createElement(
        Box,
        { flexDirection: 'column' },
        React.createElement(Text, { color: 'red' }, `✗ ${output.error.message}`),
        handoffUrl
          ? React.createElement(Text, { dimColor: true }, `기관 문의: ${handoffUrl}`)
          : null,
      ),
    )
  },

  /**
   * Backend owns the KOSMOS permission gauntlet for backend-dispatched
   * primitives. Submit is side-effecting and remains gated in Python
   * GATED_PRIMITIVES; the stdio dispatcher emits the canonical
   * PermissionRequestFrame before adapter invocation. A second client-side
   * prompt here deadlocks the frame consumer before that backend request can
   * be observed.
   */
  async checkPermissions(input) {
    return { behavior: 'allow' as const, updatedInput: input }
  },

  /**
   * Dispatch submit call via real IPC bridge (T011 — stub replaced).
   */
  async call(input, context) {
    return dispatchPrimitive<Output>({
      primitive: 'submit',
      args: input as Record<string, unknown>,
      context,
      registry: getOrCreatePendingCallRegistry(),
      bridge: getOrCreateKosmosBridge(),
    })
  },
} satisfies ToolDef<InputSchema, Output>)
