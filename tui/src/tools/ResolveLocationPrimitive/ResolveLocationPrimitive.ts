// SPDX-License-Identifier: Apache-2.0
// KOSMOS — ResolveLocationPrimitive.
//
// LLM-visible tool name: "resolve_location".
// CC Tool-surface migration for the citizen-facing geocoding primitive.

import React from 'react'
import { z } from 'zod/v4'
import { Box, Text } from '../../ink.js'
import { MessageResponse } from '../../components/MessageResponse.js'
import { buildTool, type ToolDef } from '../../Tool.js'
import { lazySchema } from '../../utils/lazySchema.js'
import {
  RESOLVE_LOCATION_TOOL_NAME,
  DESCRIPTION,
  RESOLVE_LOCATION_TOOL_PROMPT,
} from './prompt.js'
import { dispatchPrimitive } from '../_shared/dispatchPrimitive.js'
import {
  renderVerboseInputJson,
  renderVerboseOutputJson,
} from '../_shared/verboseRender.js'
import { getOrCreateKosmosBridge } from '../../ipc/bridgeSingleton.js'
import { getOrCreatePendingCallRegistry } from '../../ipc/pendingCallSingleton.js'

const WANT_VALUES = [
  'coords',
  'adm_cd',
  'coords_and_admcd',
  'road_address',
  'jibun_address',
  'poi',
  'all',
] as const

const inputSchema = lazySchema(() =>
  z.strictObject({
    query: z
      .string()
      .min(1)
      .max(200)
      .describe('Physical place query extracted from the citizen message.'),
    want: z
      .enum(WANT_VALUES)
      .optional()
      .describe('Identifier shape needed by the follow-up adapter.'),
    near: z
      .tuple([z.number(), z.number()])
      .optional()
      .describe('Optional [lat, lon] tiebreaker for ambiguous place names.'),
  }),
)
type InputSchema = ReturnType<typeof inputSchema>

const outputSchema = lazySchema(() =>
  z.discriminatedUnion('ok', [
    z.object({
      ok: z.literal(true),
      result: z.unknown(),
      outbound_traces: z.array(z.unknown()).optional(),
    }),
    z.object({
      ok: z.literal(false),
      error: z.object({
        kind: z.string(),
        message: z.string(),
      }),
      result: z.unknown().optional(),
      outbound_traces: z.array(z.unknown()).optional(),
    }),
  ]),
)
type OutputSchema = ReturnType<typeof outputSchema>

export type Output = z.infer<OutputSchema>

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object'
    ? (value as Record<string, unknown>)
    : null
}

function formatNumber(value: unknown): string | null {
  return typeof value === 'number' && Number.isFinite(value)
    ? value.toFixed(6).replace(/0+$/, '').replace(/\.$/, '')
    : null
}

function renderBundleRows(result: Record<string, unknown>): React.ReactNode[] {
  const rows: React.ReactNode[] = []
  const coords = asRecord(result.coords)
  const admCd = asRecord(result.adm_cd)
  const address = asRecord(result.address)
  const poi = asRecord(result.poi)

  if (coords) {
    const lat = formatNumber(coords.lat)
    const lon = formatNumber(coords.lon)
    rows.push(
      React.createElement(
        Text,
        { key: 'coords', dimColor: true },
        `좌표: ${lat ?? '?'} / ${lon ?? '?'}${coords.source ? ` (${String(coords.source)})` : ''}`,
      ),
    )
  }
  if (admCd) {
    const code = typeof admCd.code === 'string' ? admCd.code : ''
    const name = typeof admCd.name === 'string' ? admCd.name : ''
    rows.push(
      React.createElement(
        Text,
        { key: 'adm_cd', dimColor: true },
        `행정코드: ${code}${name ? ` — ${name}` : ''}`,
      ),
    )
  }
  if (address) {
    const road =
      typeof address.road_address === 'string' ? address.road_address : null
    const jibun =
      typeof address.jibun_address === 'string' ? address.jibun_address : null
    rows.push(
      React.createElement(
        Text,
        { key: 'address', dimColor: true },
        `주소: ${road ?? jibun ?? '(주소 없음)'}`,
      ),
    )
  }
  if (poi) {
    const name = typeof poi.name === 'string' ? poi.name : '(POI)'
    const category = typeof poi.category === 'string' ? poi.category : null
    rows.push(
      React.createElement(
        Text,
        { key: 'poi', dimColor: true },
        `장소: ${name}${category ? ` — ${category}` : ''}`,
      ),
    )
  }
  return rows
}

function renderSingleResult(result: Record<string, unknown>): React.ReactNode[] {
  const kind = typeof result.kind === 'string' ? result.kind : 'result'
  if (kind === 'coords') {
    const lat = formatNumber(result.lat)
    const lon = formatNumber(result.lon)
    return [
      React.createElement(
        Text,
        { key: 'coords', dimColor: true },
        `좌표: ${lat ?? '?'} / ${lon ?? '?'}${result.source ? ` (${String(result.source)})` : ''}`,
      ),
    ]
  }
  if (kind === 'adm_cd') {
    return [
      React.createElement(
        Text,
        { key: 'adm_cd', dimColor: true },
        `행정코드: ${String(result.code ?? '')}${result.name ? ` — ${String(result.name)}` : ''}`,
      ),
    ]
  }
  if (kind === 'address') {
    const road =
      typeof result.road_address === 'string' ? result.road_address : null
    const jibun =
      typeof result.jibun_address === 'string' ? result.jibun_address : null
    return [
      React.createElement(
        Text,
        { key: 'address', dimColor: true },
        `주소: ${road ?? jibun ?? '(주소 없음)'}`,
      ),
    ]
  }
  if (kind === 'poi') {
    const lat = formatNumber(result.lat)
    const lon = formatNumber(result.lon)
    return [
      React.createElement(
        Text,
        { key: 'poi', dimColor: true },
        `장소: ${String(result.name ?? '(POI)')}${result.category ? ` — ${String(result.category)}` : ''}`,
      ),
      React.createElement(
        Text,
        { key: 'poi-coords', dimColor: true },
        `좌표: ${lat ?? '?'} / ${lon ?? '?'}`,
      ),
    ]
  }
  if ('lat' in result && 'lon' in result) {
    const lat = formatNumber(result.lat)
    const lon = formatNumber(result.lon)
    return [
      React.createElement(
        Text,
        { key: 'flat-coords', dimColor: true },
        `좌표: ${lat ?? '?'} / ${lon ?? '?'}`,
      ),
      result.b_code
        ? React.createElement(
            Text,
            { key: 'flat-b-code', dimColor: true },
            `행정코드: ${String(result.b_code)}`,
          )
        : null,
      result.address_name
        ? React.createElement(
            Text,
            { key: 'flat-address', dimColor: true },
            `주소: ${String(result.address_name)}`,
          )
        : null,
    ].filter(Boolean) as React.ReactNode[]
  }

  return [
    React.createElement(
      Text,
      { key: 'raw', dimColor: true },
      JSON.stringify(result),
    ),
  ]
}

export const ResolveLocationPrimitive = buildTool({
  name: RESOLVE_LOCATION_TOOL_NAME,

  searchHint: '위치 주소 좌표 행정동 resolve geocode location adm_cd POI',

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
    return true
  },

  isReadOnly() {
    return true
  },

  userFacingName() {
    return 'locate'
  },

  async description() {
    return DESCRIPTION
  },

  async prompt() {
    return RESOLVE_LOCATION_TOOL_PROMPT
  },

  mapToolResultToToolResultBlockParam(output, toolUseID) {
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
      type: 'tool_result' as const,
      content: JSON.stringify(llmContent),
    }
  },

  renderToolUseMessage(
    input: { query?: string; want?: string; near?: unknown },
    options: { verbose: boolean },
  ) {
    if (options.verbose) {
      return renderVerboseInputJson(input)
    }
    const want = input.want ? ` → ${input.want}` : ''
    return `${input.query ?? ''}${want}`
  },

  isMcp: false,

  async validateInput(input) {
    if (!input.query.trim()) {
      return {
        result: false as const,
        message: 'resolve_location query must not be empty.',
        errorCode: 1001,
      }
    }
    return { result: true as const }
  },

  renderToolResultMessage(
    output: Output,
    _progress: unknown,
    options: { verbose: boolean; isTranscriptMode?: boolean } = { verbose: false },
  ) {
    if (options.verbose || options.isTranscriptMode) {
      return renderVerboseOutputJson(output)
    }

    if (!output.ok) {
      return React.createElement(
        MessageResponse,
        { height: 1 },
        React.createElement(
          Text,
          { color: 'red' },
          `위치 해석 실패: ${output.error.message}`,
        ),
      )
    }

    const result = asRecord(output.result)
    if (!result) {
      return React.createElement(
        MessageResponse,
        { height: 1 },
        React.createElement(Text, { dimColor: true }, '위치 해석 결과 없음'),
      )
    }

    if (result.kind === 'error') {
      return React.createElement(
        MessageResponse,
        { height: 1 },
        React.createElement(
          Text,
          { color: 'red' },
          `위치 해석 실패: ${String(result.message ?? result.reason ?? 'unknown')}`,
        ),
      )
    }

    const rows =
      result.kind === 'bundle'
        ? renderBundleRows(result)
        : renderSingleResult(result)

    return React.createElement(
      MessageResponse,
      null,
      React.createElement(
        Box,
        { flexDirection: 'column' },
        React.createElement(Text, { bold: true }, '위치 해석 결과'),
        ...rows,
      ),
    )
  },

  async checkPermissions(input) {
    return { behavior: 'allow' as const, updatedInput: input }
  },

  async call(input, context) {
    return dispatchPrimitive<Output>({
      primitive: 'resolve_location',
      args: input as Record<string, unknown>,
      context,
      registry: getOrCreatePendingCallRegistry(),
      bridge: getOrCreateKosmosBridge(),
    })
  },
} satisfies ToolDef<InputSchema, Output>)
