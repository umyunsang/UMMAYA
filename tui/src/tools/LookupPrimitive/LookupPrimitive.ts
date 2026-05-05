// SPDX-License-Identifier: Apache-2.0
// KOSMOS-original — Epic #1634 P3 · LookupPrimitive.
//
// LLM-visible tool name: "lookup"
// Primitive wrapper over Spec 022 kosmos.tools.lookup — two modes:
//   search: BM25+dense hybrid retrieval over registered adapters
//   fetch:  direct adapter invocation by tool_id
//
// Epic γ #2294 · T006/T007: real validateInput + renderToolResultMessage.
//
// I/O contract: specs/1634-tool-system-wiring/contracts/primitive-envelope.md § 2

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
import {
  isManifestSynced,
  resolveAdapter,
} from '../../services/api/adapterManifest.js'
import { LOOKUP_TOOL_NAME, DESCRIPTION, LOOKUP_TOOL_PROMPT } from './prompt.js'
import { dispatchPrimitive } from '../_shared/dispatchPrimitive.js'
import {
  renderVerboseInputJson,
  renderVerboseOutputJson,
} from '../_shared/verboseRender.js'
import { truncateJson } from '../_shared/jsonTruncate.js'
import { getOrCreateKosmosBridge } from '../../ipc/bridgeSingleton.js'
import { getOrCreatePendingCallRegistry } from '../../ipc/pendingCallSingleton.js'

// ---------------------------------------------------------------------------
// KOSMOS citation extension — attaches resolved citation to the context so the
// permission UI can surface the verbatim agency policy URL. Does NOT modify
// Tool.ts or ToolPermissionContext (byte-identical CC port).
// ---------------------------------------------------------------------------
type ContextWithCitation = ToolUseContext & {
  kosmosCitations?: AdapterCitation[]
}

// ---------------------------------------------------------------------------
// Input schema — Spec 2521 (2026-05-01) fetch-only.
//
// BM25 adapter discovery is a backend-internal mechanism (auto-injected
// into the system prompt's <available_adapters> dynamic suffix). The LLM
// MUST NOT see ``search`` as a callable mode — it picks a tool_id from
// the suffix and calls lookup with ``{tool_id, params}`` only.
// ---------------------------------------------------------------------------

const inputSchema = lazySchema(() =>
  z.object({
    tool_id: z
      .string()
      .min(1)
      .describe(
        'Registered adapter identifier, picked from <available_adapters>. ' +
          'e.g. "kma_forecast_fetch", "hira_hospital_search".',
      ),
    params: z
      .record(z.string(), z.unknown())
      .describe('Adapter-defined Pydantic-validated parameter body'),
  }),
)
type InputSchema = ReturnType<typeof inputSchema>

// ---------------------------------------------------------------------------
// Output schema — discriminated union on "ok"
// ---------------------------------------------------------------------------

// Spec 2521 (2026-05-02) — ``outbound_traces`` carries the captured
// outbound HTTP request/response array from
// ``kosmos.tools._outbound_trace``. Optional + ``z.unknown()`` items so
// each primitive doesn't have to mirror the full Pydantic schema. The
// verbose render path (``verboseRender.ts``) reads this field; without
// it Zod's strip default would drop the trace at safeParse time.
const outputSchema = lazySchema(() =>
  z.discriminatedUnion('ok', [
    z.object({
      ok: z.literal(true),
      result: z.unknown().describe('Adapter result or search results array'),
      outbound_traces: z.array(z.unknown()).optional(),
    }),
    z.object({
      ok: z.literal(false),
      error: z.object({
        kind: z.string().describe('Error classification, e.g. "tool_not_found"'),
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

export const LookupPrimitive = buildTool({
  name: LOOKUP_TOOL_NAME,

  /** Bilingual keyword hint for ToolSearch deferred-tool discovery. */
  searchHint: '조회 검색 lookup discover search adapter 공공 API 어댑터',

  maxResultSizeChars: 100_000,

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
    // lookup is read-only and side-effect-free.
    return true
  },

  isReadOnly() {
    return true
  },

  async description() {
    return DESCRIPTION
  },

  async prompt() {
    return LOOKUP_TOOL_PROMPT
  },

  mapToolResultToToolResultBlockParam(output, toolUseID) {
    // Spec 2521 (2026-05-02) — strip ``outbound_traces`` from the
    // LLM-facing content. The trace is UI-only (verbose render);
    // shipping raw HTTP bodies back into the next turn would bloat
    // K-EXAONE's context with KMA/data.go.kr response payloads.
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

  // KOSMOS hotfix #2518 follow-up — CC pattern (tools/BashTool/UI.tsx:renderToolUseMessage)
  // 따라 args preview 반환. null 반환은 AssistantToolUseMessage가 tool block을 통째로
  // 숨겨서 시민이 어떤 tool이 dispatch 됐는지 못 봄. CC byte-identical pattern.
  // Spec 2521 (2026-05-01) — fetch-only surface; legacy mode='search'
  // payloads from older sessions surface as the bare tool_id.
  // Spec 2521 (2026-05-01 evening) — verbose flag mirrors CC BashTool's
  // verbose==true full-payload pattern: Ctrl+O expand surfaces the full
  // request JSON the LLM sent to the adapter.
  renderToolUseMessage(
    input: { tool_id?: string; mode?: string; query?: string; params?: unknown },
    options: { verbose: boolean },
  ) {
    if (options.verbose) {
      return renderVerboseInputJson(input)
    }
    return input.tool_id ?? input.query ?? ''
  },

  // Epic γ #2294 · 9-member interface compliance.
  isMcp: false,

  /**
   * T006 — real validateInput per contracts/primitive-shape.md § validateInput.
   *
   * Steps (Spec 2521 fetch-only):
   *  1. resolve tool_id against the synced backend manifest.
   *  2. If not found: fail closed with Korean diagnostic.
   *  3. Read citation from adapter; attach to context for permission UI.
   *  4. Return { result: true }.
   */
  async validateInput(
    input: z.infer<InputSchema>,
    context: ToolUseContext,
  ): Promise<import('../../Tool.js').ValidationResult> {
    // Epic ε #2296 T011 — two-tier resolution (FR-017 / FR-018 / FR-019 / FR-020).
    // Spec 2521 (2026-05-01) — citation-missing branch added so the
    // 1002 contract (Spec 024 invariant: every adapter cites the agency
    // policy URL) is enforced at the primitive surface, not just at the
    // permission gauntlet.

    // Tier 1 — synced backend manifest (FR-017).
    if (isManifestSynced()) {
      const backendEntry = resolveAdapter(input.tool_id)
      if (backendEntry) {
        // Internal-mode adapters are exempt from the citation invariant.
        if (backendEntry.source_mode === 'internal') {
          ;(context as ContextWithCitation).kosmosCitations = []
          return { result: true }
        }
        if (!backendEntry.policy_authority_url) {
          return {
            result: false,
            message: `'${input.tool_id}' 어댑터 정책 인용이 누락되었습니다 (Spec 024 invariant 위반).`,
            errorCode: PrimitiveErrorCode.CitationMissing,
          }
        }
        const citation: AdapterCitation = {
          real_classification_url: backendEntry.policy_authority_url,
          policy_authority: backendEntry.name,
        }
        ;(context as ContextWithCitation).kosmosCitations = [citation]
        return { result: true }
      }
    }

    // Tier 2 — TS-side internal tools fallback (FR-018 / existing path).
    const internalAdapter = (context.options.tools as unknown as AdapterWithPolicy[]).find(
      (t) => t.name === input.tool_id,
    )
    if (internalAdapter) {
      const citation = extractCitation(internalAdapter)
      if (!citation) {
        return {
          result: false,
          message: `'${input.tool_id}' 어댑터 정책 인용이 누락되었습니다 (Spec 024 invariant 위반).`,
          errorCode: PrimitiveErrorCode.CitationMissing,
        }
      }
      ;(context as ContextWithCitation).kosmosCitations = [citation]
      return { result: true }
    }

    // Tier 0 — fail closed if manifest not yet synced AND no internal hit
    // (FR-019). When a citizen retry happens before backend boot completes
    // we keep the original manifest-not-synced diagnostic, otherwise the
    // tool_id is genuinely unknown.
    if (!isManifestSynced()) {
      return {
        result: false,
        message: 'Adapter manifest not yet synced from backend; retry once boot completes.',
        errorCode: PrimitiveErrorCode.AdapterNotFound,
      }
    }

    // Fail closed (FR-020).
    return {
      result: false,
      message: `AdapterNotFound: '${input.tool_id}' is not in the synced backend manifest or the internal tools list.`,
      errorCode: PrimitiveErrorCode.AdapterNotFound,
    }
  },

  /**
   * T007 — citizen-facing Korean rendering per contracts/primitive-shape.md
   * § renderToolResultMessage Lookup row.
   *
   * - mode='fetch', ok=true:  adapter name + result count + first-3 summary.
   * - mode='search', ok=true: ranked-hit list.
   * - ok=false:               Korean error message in citizen-friendly tone.
   */
  renderToolResultMessage(
    output: Output,
    _progress: unknown,
    options: { verbose: boolean; isTranscriptMode?: boolean } = { verbose: false },
  ): React.ReactNode {
    // Spec 2521 (2026-05-01 evening) — Ctrl+O expand / transcript mode
    // surfaces the full envelope JSON the backend returned. Mirrors
    // CC BashTool/UI.tsx:renderToolResultMessage(verbose).
    if (options.verbose || options.isTranscriptMode) {
      return renderVerboseOutputJson(output)
    }
    // KOSMOS hotfix #2519 (CC-original migration, 2026-04-30):
    //
    // After the dispatchPrimitive register-and-await rewrite, output.result
    // is the actual primitive output (the inner of the backend envelope:
    // src/kosmos/tools/lookup.py LookupSearchResult / LookupRecord /
    // LookupCollection / LookupTimeseries / LookupError) — discriminated by
    // its own `kind` field. The CC pattern wraps each branch in
    // <MessageResponse> so the "  ⎿  " gutter glyph prefixes every row
    // (tui/src/components/MessageResponse.tsx:22).
    if (!output.ok) {
      return React.createElement(
        MessageResponse,
        null,
        React.createElement(
          Text,
          { color: 'red' },
          `오류가 발생했습니다: ${output.error.message}`,
        ),
      )
    }

    const result = output.result as Record<string, unknown>

    // search mode (LookupSearchResult, models.py:820):
    //   { kind: "search", candidates: [AdapterCandidate], total_registry_size, effective_top_k, reason }
    if (result?.kind === 'search') {
      const hits = Array.isArray(result.candidates) ? result.candidates : []
      if (hits.length === 0) {
        return React.createElement(
          MessageResponse,
          { height: 1 },
          React.createElement(
            Text,
            { color: 'red' },
            '검색 결과가 없습니다 — 다른 도구(resolve_location 등)를 시도하거나 시민에게 직접 안내하세요.',
          ),
        )
      }
      const hitRows = hits.slice(0, 10).map((hit: unknown, i: number) => {
        const h = hit as Record<string, unknown>
        const toolId = typeof h.tool_id === 'string' ? h.tool_id : '(알 수 없음)'
        const score =
          typeof h.score === 'number' ? ` [${h.score.toFixed(2)}]` : ''
        const hint =
          typeof h.search_hint === 'string' ? ` — ${h.search_hint}` : ''
        return React.createElement(
          Text,
          { key: i },
          `${i + 1}. ${toolId}${score}${hint}`,
        )
      })
      return React.createElement(
        MessageResponse,
        null,
        React.createElement(
          Box,
          { flexDirection: 'column' },
          React.createElement(
            Text,
            { bold: true },
            `검색 결과 (${hits.length}건):`,
          ),
          ...hitRows,
        ),
      )
    }

    // fetch error (LookupError, models.py — kind="error"):
    //   { kind: "error", reason, message, retryable, ... }
    if (result?.kind === 'error') {
      return React.createElement(
        MessageResponse,
        null,
        React.createElement(
          Text,
          { color: 'red' },
          `검색 오류: ${typeof result.message === 'string' ? result.message : String(result.reason ?? 'unknown')}`,
        ),
      )
    }

    // fetch result (LookupRecord / LookupCollection / LookupTimeseries):
    //   record:    { kind: "record",     tool_id, fields }
    //   collection:{ kind: "collection", tool_id, items }
    //   timeseries:{ kind: "timeseries", tool_id, points }
    const toolId =
      typeof result?.tool_id === 'string'
        ? result.tool_id
        : typeof result?.kind === 'string'
          ? result.kind
          : '(어댑터 미상)'
    const adapterResult =
      (result?.fields as unknown) ??
      (result?.items as unknown) ??
      (result?.points as unknown) ??
      result
    let countText = ''
    let summaryRows: React.ReactNode[] = []

    if (Array.isArray(adapterResult)) {
      countText = `${adapterResult.length}건`
      summaryRows = adapterResult.slice(0, 3).map((item: unknown, i: number) => {
        // Wave-2 G5 (F-beta-05) — JSON-aware ellipsis. Bare slice(0,N) was
        // producing mid-key cuts like ``"sky_code":"1","interval`` with no
        // closing brace and no indicator. truncateJson appends U+2026 when
        // the input exceeds the budget so the citizen always sees a clear
        // truncation marker.
        const raw =
          typeof item === 'object' && item !== null
            ? JSON.stringify(item)
            : String(item)
        const summary = truncateJson(raw, 120)
        return React.createElement(
          Text,
          { key: i, dimColor: true },
          `  ${i + 1}. ${summary}`,
        )
      })
    } else if (adapterResult !== null && adapterResult !== undefined) {
      countText = '1건'
      // Wave-2 G5 (F-beta-05) — same JSON-aware ellipsis as the array branch.
      const raw =
        typeof adapterResult === 'object'
          ? JSON.stringify(adapterResult)
          : String(adapterResult)
      const summary = truncateJson(raw, 240)
      summaryRows = [React.createElement(Text, { key: 0, dimColor: true }, `  ${summary}`)]
    }

    // Audit-2 P0: check _mode === 'mock' from transparency stamp (Spec 024).
    const mockMeta = extractMockMeta(output)
    const isMock = mockMeta.isMock

    const lookupHeading = isMock ? mockLabel('검색 결과') : toolId
    const headingColor = isMock ? ('cyan' as const) : undefined

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
            { bold: true, color: headingColor, dimColor: isMock },
            lookupHeading,
          ),
          !isMock && countText ? ` — ${countText}` : '',
          isMock && countText ? ` (${toolId} — ${countText})` : '',
        ),
        isMock
          ? React.createElement(
              Text,
              { dimColor: true },
              '실제 행정 영향 없는 시연 결과입니다.',
            )
          : null,
        ...summaryRows,
        isMock && mockMeta.actualEndpointWhenLive
          ? React.createElement(
              Text,
              { dimColor: true },
              `실제 엔드포인트 (운영 시): ${mockMeta.actualEndpointWhenLive}`,
            )
          : null,
      ),
    )
  },

  /**
   * lookup is read-only — always allow, defer to the general permission system.
   * Explicit declaration avoids relying on the buildTool default and makes the
   * intent clear at the primitive surface (Spec 031 / Spec 024).
   */
  async checkPermissions(input) {
    return { behavior: 'allow' as const, updatedInput: input }
  },

  /**
   * Dispatch lookup call via real IPC bridge (T009 — stub replaced).
   * validateInput has already resolved the adapter and populated kosmosCitations on the context.
   */
  async call(input, context) {
    return dispatchPrimitive<Output>({
      primitive: 'lookup',
      args: input as Record<string, unknown>,
      context,
      registry: getOrCreatePendingCallRegistry(),
      bridge: getOrCreateKosmosBridge(),
    })
  },
} satisfies ToolDef<InputSchema, Output>)
