// SPDX-License-Identifier: Apache-2.0
// UMMAYA-original — Epic #1634 P3 · FindPrimitive.
//
// LLM-visible tool name: "find"
// Primitive wrapper over Spec 022 ummaya.tools.find — fetch-only; adapter
// discovery runs inside the backend and is injected into the system prompt.
//
// Epic γ #2294 · T006/T007: real validateInput + renderToolResultMessage.
//
// I/O contract: specs/1634-tool-system-wiring/contracts/primitive-envelope.md § 2

import React from 'react'
import { z } from 'zod/v4'
import { Text } from '../../ink.js'
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
import { FIND_TOOL_NAME, DESCRIPTION, FIND_TOOL_PROMPT } from './prompt.js'
import { dispatchPrimitive } from '../_shared/dispatchPrimitive.js'
import { validateKmaAviationToolChoice } from '../_shared/kmaAviationGuard.js'
import { validateKmaAnalysisToolChoice } from '../_shared/kmaAnalysisGuard.js'
import { validateNmcAedToolChoice } from '../_shared/nmcAedGuard.js'
import { validateProtectedCheckToolChoice } from '../_shared/protectedCheckGuard.js'
import { validateDirectPublicDataToolChoice } from '../_shared/directPublicDataGuard.js'
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
// UMMAYA citation extension — attaches resolved citation to the context so the
// permission UI can surface the verbatim agency policy URL. Does NOT modify
// Tool.ts or ToolPermissionContext (byte-identical CC port).
// ---------------------------------------------------------------------------
type ContextWithCitation = ToolUseContext & {
  ummayaCitations?: AdapterCitation[]
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === 'object'
    ? value as Record<string, unknown>
    : null
}

function numberValue(obj: Record<string, unknown>, key: string): number | null {
  const value = obj[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function stringValue(obj: Record<string, unknown>, key: string): string | null {
  const value = obj[key]
  return typeof value === 'string' && value.length > 0 ? value : null
}

function firstStringValue(obj: Record<string, unknown>, keys: string[]): string | null {
  for (const key of keys) {
    const value = obj[key]
    if (typeof value === 'string' && value.trim().length > 0) {
      return value.trim()
    }
    if (typeof value === 'number' && Number.isFinite(value)) {
      return String(value)
    }
  }
  return null
}

function firstNumberValue(obj: Record<string, unknown>, keys: string[]): number | null {
  for (const key of keys) {
    const value = obj[key]
    if (typeof value === 'number' && Number.isFinite(value)) {
      return value
    }
    if (typeof value === 'string' && value.trim().length > 0) {
      const parsed = Number(value)
      if (Number.isFinite(parsed)) return parsed
    }
  }
  return null
}

function formatDistanceMeters(value: number | null): string | null {
  if (value === null) return null
  if (value >= 1000) return `${(value / 1000).toFixed(value >= 10_000 ? 0 : 1)} km`
  return `${Math.round(value)} m`
}

function formatDistanceKilometers(value: number | null): string | null {
  if (value === null) return null
  if (value < 1) return `${Math.round(value * 1000)} m`
  return `${value.toFixed(value >= 10 ? 0 : 1)} km`
}

function normalizeDistanceUnit(value: unknown): 'm' | 'km' | null {
  if (typeof value !== 'string') return null
  const normalized = value.trim().toLowerCase()
  if (['m', 'meter', 'meters'].includes(normalized)) return 'm'
  if (['km', 'kilometer', 'kilometers'].includes(normalized)) return 'km'
  return null
}

function isNmcRecord(record: Record<string, unknown>): boolean {
  return (
    stringValue(record, '_nmc_operation') !== null ||
    stringValue(record, 'dutyName') !== null ||
    stringValue(record, 'dutyAddr') !== null ||
    stringValue(record, 'dutyTel3') !== null
  )
}

function formatRecordDistance(record: Record<string, unknown>): string | null {
  const kilometers = firstNumberValue(record, [
    'distance_km',
    'distanceKm',
    'distance_kilometers',
    'distanceKilometers',
  ])
  if (kilometers !== null) return formatDistanceKilometers(kilometers)

  const meters = firstNumberValue(record, [
    'distance_m',
    'distanceMeters',
    'distance_meter',
    'distanceMeter',
    'dist_m',
    'distMeters',
  ])
  if (meters !== null) return formatDistanceMeters(meters)

  const generic = firstNumberValue(record, ['distance', 'dist'])
  if (generic === null) return null

  const unit =
    normalizeDistanceUnit(record.distance_unit) ??
    normalizeDistanceUnit(record.distanceUnit)
  if (unit === 'km') return formatDistanceKilometers(generic)
  if (unit === 'm') return formatDistanceMeters(generic)

  return isNmcRecord(record)
    ? formatDistanceKilometers(generic)
    : formatDistanceMeters(generic)
}

function extractErrorMessage(message: string): string {
  try {
    const parsed = JSON.parse(message) as unknown
    const record = asRecord(parsed)
    const error = asRecord(record?.error)
    const nested = typeof error?.message === 'string' ? error.message : null
    if (nested) return nested
  } catch {
    // Keep original message when it is not JSON.
  }
  return message
}

function formatGenericCollectionItem(item: unknown, index: number): React.ReactNode[] {
  const record = asRecord(item)
  if (!record) {
    return [
      React.createElement(
        Text,
        { key: `generic-${index}-value`, dimColor: true },
        `  ${index + 1}. ${String(item).slice(0, 120)}`,
      ),
    ]
  }

  const name =
    firstStringValue(record, [
      'yadmNm',
      'dutyName',
      'spot_nm',
      'spotName',
      'facilName',
      'facil_nm',
      'name',
      'title',
      'serviceName',
      'wlfareInfoNm',
    ]) ?? `Result ${index + 1}`
  const kind = firstStringValue(record, [
    'clCdNm',
    'dutyEmclsName',
    'type',
    'category',
    'spot_type',
    'facilKind',
    'kind',
  ])
  const distance = formatRecordDistance(record)
  const address = firstStringValue(record, [
    'addr',
    'dutyAddr',
    'adres',
    'address',
    'roadAddr',
    'rnAdres',
    'location',
  ])
  const phone = firstStringValue(record, [
    'telno',
    'dutyTel1',
    'dutyTel3',
    'tel',
    'phone',
    'telephone',
  ])

  const suffix = [kind, distance].filter(Boolean).join(' · ')
  const rows: React.ReactNode[] = [
    React.createElement(
      Text,
      { key: `generic-${index}-head`, dimColor: true },
      `  ${index + 1}. ${name}${suffix ? ` · ${suffix}` : ''}`,
    ),
  ]
  if (address) {
    rows.push(
      React.createElement(
        Text,
        { key: `generic-${index}-addr`, dimColor: true },
        `     Address: ${address}`,
      ),
    )
  }
  if (phone) {
    rows.push(
      React.createElement(
        Text,
        { key: `generic-${index}-phone`, dimColor: true },
        `     Phone: ${phone}`,
      ),
    )
  }
  return rows
}

function precipitationTypeLabel(code: number | null): string | null {
  switch (code) {
    case 0:
      return 'none'
    case 1:
      return 'rain'
    case 2:
      return 'rain/snow'
    case 3:
      return 'snow'
    case 5:
      return 'raindrops'
    case 6:
      return 'raindrops/snow flurries'
    case 7:
      return 'snow flurries'
    default:
      return code === null ? null : `code ${code}`
  }
}

function skyLabel(code: string | null): string | null {
  switch (code) {
    case '1':
      return 'clear'
    case '3':
      return 'mostly cloudy'
    case '4':
      return 'cloudy'
    default:
      return code === null ? null : `SKY ${code}`
  }
}

function forecastCategoryLabel(category: string, value: string): string | null {
  switch (category) {
    case 'TMP':
      return `temperature ${value}°C`
    case 'POP':
      return `precipitation chance ${value}%`
    case 'PTY':
      return `precipitation type ${precipitationTypeLabel(Number(value)) ?? value}`
    case 'PCP':
      return `precipitation ${value}`
    case 'REH':
      return `humidity ${value}%`
    case 'WSD':
      return `wind speed ${value} m/s`
    case 'SKY':
      return `sky ${skyLabel(value) ?? value}`
    default:
      return null
  }
}

function formatKmaShortTermForecast(item: Record<string, unknown>): React.ReactNode[] | null {
  const source = stringValue(asRecord(item.meta) ?? {}, 'source')
  const data = asRecord(item.item) ?? item
  const rows = Array.isArray(data.items) ? data.items : null
  const hasForecastRows = rows?.some((raw) => {
    const row = asRecord(raw)
    return row && stringValue(row, 'category') !== null && stringValue(row, 'fcst_value') !== null
  }) ?? false
  if (source !== 'kma_short_term_forecast' && !hasForecastRows) {
    return null
  }
  if (!rows || rows.length === 0) {
    return null
  }

  const byTime = new Map<string, string[]>()
  for (const raw of rows) {
    const row = asRecord(raw)
    if (!row) continue
    const fcstDate = stringValue(row, 'fcst_date')
    const fcstTime = stringValue(row, 'fcst_time')
    const category = stringValue(row, 'category')
    const value = stringValue(row, 'fcst_value')
    if (!fcstDate || !fcstTime || !category || value === null) continue
    const label = forecastCategoryLabel(category, value)
    if (!label) continue
    const key = `${fcstDate} ${fcstTime}`
    const existing = byTime.get(key) ?? []
    existing.push(label)
    byTime.set(key, existing)
  }

  const totalCount = numberValue(data, 'total_count')
  const summary: string[] = []
  if (totalCount !== null) summary.push(`Forecast items: ${totalCount}`)
  for (const [time, labels] of Array.from(byTime.entries()).slice(0, 5)) {
    summary.push(`${time}: ${labels.slice(0, 5).join(', ')}`)
  }
  if (byTime.size > 5) summary.push(`${byTime.size - 5} more time slots`)
  return summary.map((row, i) => React.createElement(Text, { key: `kma-stf-${i}`, dimColor: i === 0 }, `  ${row}`))
}

function formatKmaCurrentObservation(item: Record<string, unknown>): React.ReactNode[] | null {
  const source = stringValue(asRecord(item.meta) ?? {}, 'source')
  const data = asRecord(item.item) ?? item
  if (source !== 'kma_current_observation' && !('t1h' in data && 'rn1' in data && 'reh' in data)) {
    return null
  }

  const rows: string[] = []
  const baseDate = stringValue(data, 'base_date')
  const baseTime = stringValue(data, 'base_time')
  if (baseDate && baseTime) rows.push(`Observed at: ${baseDate} ${baseTime}`)

  const t1h = numberValue(data, 't1h')
  if (t1h !== null) rows.push(`Temperature: ${t1h}°C`)

  const rn1 = numberValue(data, 'rn1')
  if (rn1 !== null) rows.push(`Rainfall last 1h: ${rn1} mm`)

  const pty = numberValue(data, 'pty')
  const ptyLabel = precipitationTypeLabel(pty)
  if (ptyLabel) rows.push(`Precipitation type: ${ptyLabel}`)

  const reh = numberValue(data, 'reh')
  if (reh !== null) rows.push(`Humidity: ${reh}%`)

  const wsd = numberValue(data, 'wsd')
  if (wsd !== null) rows.push(`Wind speed: ${wsd} m/s`)

  const vec = numberValue(data, 'vec')
  if (vec !== null) rows.push(`Wind direction: ${vec}°`)

  const nx = numberValue(data, 'nx')
  const ny = numberValue(data, 'ny')
  if (nx !== null && ny !== null) rows.push(`KMA grid: X ${nx}, Y ${ny}`)

  return rows.map((row, i) => React.createElement(Text, { key: `kma-${i}`, dimColor: i === 0 }, `  ${row}`))
}

function renderRowsForSearchResult(result: Record<string, unknown>): React.ReactNode {
  const hits = Array.isArray(result.candidates) ? result.candidates : []
  if (hits.length === 0) {
    return React.createElement(
      MessageResponse,
      { height: 1 },
      React.createElement(
        Text,
        { color: 'red' },
        'No search results. Try a different tool such as locate, or answer the citizen directly.',
      ),
    )
  }

  const hitRows = hits.slice(0, 10).map((hit: unknown, i: number) => {
    const h = hit as Record<string, unknown>
    const toolId = typeof h.tool_id === 'string' ? h.tool_id : '(unknown)'
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

  return renderCompactPrimitiveResult([
    React.createElement(Text, { key: 'search-heading', bold: true }, `Search results (${hits.length}):`),
    ...hitRows,
  ])
}

function buildFindResultRows(output: Output): React.ReactNode[] {
  const result = output.ok ? (output.result as Record<string, unknown>) : null
  if (!result) return []

  const toolId =
    typeof result?.tool_id === 'string'
      ? result.tool_id
      : typeof result?.kind === 'string'
        ? result.kind
        : '(unknown adapter)'
  const adapterResult =
    (result?.fields as unknown) ??
    (result?.items as unknown) ??
    (result?.points as unknown) ??
    result
  let countText = ''
  let summaryRows: React.ReactNode[] = []

  if (Array.isArray(adapterResult)) {
    const totalCount = firstNumberValue(result, ['total_count', 'totalCount', 'total'])
    countText =
      totalCount !== null && totalCount > adapterResult.length
        ? `${adapterResult.length} of ${totalCount} shown`
        : `${adapterResult.length} results`
    summaryRows = adapterResult
      .slice(0, 5)
      .flatMap((item: unknown, i: number) => formatGenericCollectionItem(item, i))
    if (totalCount !== null && totalCount > adapterResult.length) {
      summaryRows.push(
        React.createElement(
          Text,
          { key: 'generic-more', dimColor: true },
          `  ${Math.max(0, totalCount - adapterResult.length)} more`,
        ),
      )
    } else if (adapterResult.length > 5) {
      summaryRows.push(
        React.createElement(
          Text,
          { key: 'generic-more', dimColor: true },
          `  ${adapterResult.length - 5} more`,
        ),
      )
    }
  } else if (adapterResult !== null && adapterResult !== undefined) {
    countText = '1 result'
    const structuredRows = formatKmaCurrentObservation(result)
    if (structuredRows) {
      summaryRows = structuredRows
    } else {
      const forecastRows = formatKmaShortTermForecast(result)
      if (forecastRows) {
        summaryRows = forecastRows
      } else {
        const summary =
          typeof adapterResult === 'object'
            ? JSON.stringify(adapterResult).slice(0, 240)
            : String(adapterResult).slice(0, 240)
        summaryRows = [React.createElement(Text, { key: 0, dimColor: true }, `  ${summary}`)]
      }
    }
  }

  const mockMeta = extractMockMeta(output)
  const isMock = mockMeta.isMock
  const lookupHeading = isMock ? mockLabel('Search result') : toolId
  const headingColor = isMock ? ('cyan' as const) : undefined

  return [
    React.createElement(
      Text,
      { key: 'heading' },
      React.createElement(
        Text,
        { bold: true, color: headingColor, dimColor: isMock },
        lookupHeading,
      ),
      !isMock && countText ? ` — ${countText}` : '',
      isMock && countText ? ` (${toolId} — ${countText})` : '',
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
    ...summaryRows,
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

// ---------------------------------------------------------------------------
// Input schema — Spec 2521 (2026-05-01) fetch-only.
//
// BM25 adapter discovery is a backend-internal mechanism (auto-injected
// into the system prompt's <available_adapters> dynamic suffix). The LLM
// MUST NOT see ``search`` as a callable mode — it picks a tool_id from
// the suffix and calls find with ``{tool_id, params}`` only.
// ---------------------------------------------------------------------------

const inputSchema = lazySchema(() =>
  z.preprocess(
    value => normalizeRootPrimitiveAdapterEnvelope(FIND_TOOL_NAME, value),
    z.object({
      tool_id: z
        .string()
        .min(1)
        .describe(
          'Concrete adapter identifier picked from <available_adapters>. ' +
            'This is not the function name. Never use "find", "locate", "check", or "send". ' +
            'Examples: "kma_forecast_fetch", "hira_hospital_search".',
        ),
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

// Spec 2521 (2026-05-02) — ``outbound_traces`` carries the captured
// outbound HTTP request/response array from
// ``ummaya.tools._outbound_trace``. Optional + ``z.unknown()`` items so
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
  name: FIND_TOOL_NAME,

  /** English keyword hint for ToolSearch deferred-tool discovery. */
  searchHint: 'lookup search find discover public API adapter',

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
    // find is read-only and side-effect-free.
    return true
  },

  isReadOnly() {
    return true
  },

  async description() {
    return DESCRIPTION
  },

  async prompt() {
    return FIND_TOOL_PROMPT
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

  // UMMAYA hotfix #2518 follow-up — CC pattern (tools/BashTool/UI.tsx:renderToolUseMessage).
  // Return an args preview so the citizen can see which tool was dispatched.
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

    if (isRootPrimitiveToolId(input.tool_id)) {
      return {
        result: false,
        message: rootPrimitiveSelfTargetMessage(input.tool_id, 'find'),
        errorCode: PrimitiveErrorCode.AdapterNotFound,
      }
    }

    const protectedChoice = validateProtectedCheckToolChoice(input.tool_id, context)
    if (protectedChoice) return protectedChoice
    const directPublicDataChoice = validateDirectPublicDataToolChoice(
      input.tool_id,
      context,
      input.params,
    )
    if (directPublicDataChoice) return directPublicDataChoice
    const kmaAviationChoice = validateKmaAviationToolChoice(input.tool_id, context)
    if (kmaAviationChoice) return kmaAviationChoice
    const kmaAnalysisChoice = validateKmaAnalysisToolChoice(input.tool_id, context)
    if (kmaAnalysisChoice) return kmaAnalysisChoice
    const nmcAedChoice = validateNmcAedToolChoice(input.tool_id, context)
    if (nmcAedChoice) return nmcAedChoice

    // Tier 1 — synced backend manifest (FR-017).
    if (isManifestSynced()) {
      const backendEntry = resolveAdapter(input.tool_id)
      if (backendEntry) {
        // Internal-mode adapters are exempt from the citation invariant.
        if (backendEntry.source_mode === 'internal') {
          ;(context as ContextWithCitation).ummayaCitations = []
          return { result: true }
        }
        if (!backendEntry.policy_authority_url) {
          return {
            result: false,
            message: `Adapter '${input.tool_id}' is missing a policy citation (Spec 024 invariant violation).`,
            errorCode: PrimitiveErrorCode.CitationMissing,
          }
        }
        const citation: AdapterCitation = {
          real_classification_url: backendEntry.policy_authority_url,
          policy_authority: backendEntry.name,
        }
        ;(context as ContextWithCitation).ummayaCitations = [citation]
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
          message: `Adapter '${input.tool_id}' is missing a policy citation (Spec 024 invariant violation).`,
          errorCode: PrimitiveErrorCode.CitationMissing,
        }
      }
      ;(context as ContextWithCitation).ummayaCitations = [citation]
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
    // UMMAYA hotfix #2519 (CC-original migration, 2026-04-30):
    //
    // After the dispatchPrimitive register-and-await rewrite, output.result
    // is the actual primitive output (the inner of the backend envelope:
    // src/ummaya/tools/find.py LookupSearchResult / LookupRecord /
    // LookupCollection / LookupTimeseries / LookupError) — discriminated by
    // its own `kind` field. The CC pattern wraps each branch in
    // <MessageResponse> so the "  ⎿  " gutter glyph prefixes every row
    // (tui/src/components/MessageResponse.tsx:22).
    if (!output.ok) {
      const message = extractErrorMessage(output.error.message)
      return React.createElement(
        MessageResponse,
        null,
        React.createElement(
          Text,
          { color: 'red' },
          `Error: ${message}`,
        ),
      )
    }

    const result = output.result as Record<string, unknown>

    // search mode (LookupSearchResult, models.py:820):
    //   { kind: "search", candidates: [AdapterCandidate], total_registry_size, effective_top_k, reason }
    if (result?.kind === 'search') {
      return renderRowsForSearchResult(result)
    }

    // fetch error (LookupError, models.py — kind="error"):
    //   { kind: "error", reason, message, retryable, ... }
    if (result?.kind === 'error') {
      const message =
        typeof result.message === 'string'
          ? extractErrorMessage(result.message)
          : String(result.reason ?? 'unknown')
      return React.createElement(
        MessageResponse,
        null,
        React.createElement(
          Text,
          { color: 'red' },
          `Search error: ${message}`,
        ),
      )
    }

    // fetch result (LookupRecord / LookupCollection / LookupTimeseries):
    //   record:    { kind: "record",     tool_id, fields }
    //   collection:{ kind: "collection", tool_id, items }
    //   timeseries:{ kind: "timeseries", tool_id, points }
    return renderCompactPrimitiveResult(buildFindResultRows(output))
  },

  isResultTruncated(output: Output): boolean {
    if (!output.ok) return false
    const result = output.result as Record<string, unknown>
    if (result?.kind === 'search') {
      const hits = Array.isArray(result.candidates) ? result.candidates : []
      return hits.length + 1 > 3
    }
    return isPrimitiveResultPreviewTruncated(buildFindResultRows(output))
  },

  /**
   * find is read-only — always allow, defer to the general permission system.
   * Explicit declaration avoids relying on the buildTool default and makes the
   * intent clear at the primitive surface (Spec 031 / Spec 024).
   */
  async checkPermissions(input) {
    return { behavior: 'allow' as const, updatedInput: input }
  },

  /**
   * Dispatch find call via real IPC bridge (T009 — stub replaced).
   * validateInput has already resolved the adapter and populated ummayaCitations on the context.
   */
  async call(input, context) {
    return dispatchPrimitive<Output>({
      primitive: 'find',
      args: input as Record<string, unknown>,
      context,
      registry: getOrCreatePendingCallRegistry(),
      bridge: getOrCreateUmmayaBridge(),
    })
  },
} satisfies ToolDef<InputSchema, Output>)
