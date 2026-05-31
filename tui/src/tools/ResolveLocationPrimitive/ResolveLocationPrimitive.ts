// SPDX-License-Identifier: Apache-2.0
// UMMAYA-original — ResolveLocationPrimitive.
//
// LLM-visible tool name: "locate"
// Primitive wrapper over Spec 031 ummaya.tools.locate.

import React from 'react'
import { z } from 'zod/v4'
import { Text } from '../../ink.js'
import { MessageResponse } from '../../components/MessageResponse.js'
import { buildTool, type ToolDef, type ToolUseContext } from '../../Tool.js'
import { lazySchema } from '../../utils/lazySchema.js'
import {
  LOCATE_TOOL_NAME,
  DESCRIPTION,
  LOCATE_TOOL_PROMPT,
} from './prompt.js'
import { dispatchPrimitive } from '../_shared/dispatchPrimitive.js'
import { validateKmaAviationToolChoice } from '../_shared/kmaAviationGuard.js'
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
import { repairLocateQueryParamsFromConversation } from '../_shared/locationInputRepair.js'

const inputSchema = lazySchema(() =>
  z.preprocess(
    value => normalizeRootPrimitiveAdapterEnvelope(LOCATE_TOOL_NAME, value),
    z.strictObject({
      tool_id: z
        .string()
        .min(1)
        .describe(
          'Concrete locate adapter identifier from <available_adapters>. ' +
            'This is not the function name. Never use "locate", "find", "check", or "send".',
        ),
      params: z
        .record(z.string(), z.unknown())
        .describe('Adapter-defined Pydantic-validated parameter body.'),
    }),
  ),
)
type InputSchema = ReturnType<typeof inputSchema>

const outputSchema = lazySchema(() =>
  z.discriminatedUnion('ok', [
    z.object({
      ok: z.literal(true),
      result: z.unknown().describe('ResolveLocationOutput result.'),
      outbound_traces: z.array(z.unknown()).optional(),
    }),
    z.object({
      ok: z.literal(false),
      error: z.object({
        kind: z.string().describe('Error classification.'),
        message: z.string().describe('Human-readable error description.'),
      }),
      result: z.unknown().optional(),
      outbound_traces: z.array(z.unknown()).optional(),
    }),
  ]),
)
type OutputSchema = ReturnType<typeof outputSchema>

export type Output = z.infer<OutputSchema>

function stringField(obj: Record<string, unknown>, key: string): string | null {
  const value = obj[key]
  return typeof value === 'string' && value.length > 0 ? value : null
}

function numberField(obj: Record<string, unknown>, key: string): number | null {
  const value = obj[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function summarizeLocationSlot(key: string, value: Record<string, unknown>): React.ReactNode[] {
  const rows: React.ReactNode[] = []
  if (key === 'coords') {
    const lat = numberField(value, 'lat')
    const lon = numberField(value, 'lon')
    const nx = numberField(value, 'nx')
    const ny = numberField(value, 'ny')
    if (lat !== null && lon !== null) {
      rows.push(React.createElement(Text, { key: 'coords-latlon' }, `Coordinates: ${lat.toFixed(6)}, ${lon.toFixed(6)}`))
    }
    if (nx !== null && ny !== null) {
      rows.push(React.createElement(Text, { key: 'coords-grid' }, `KMA grid: X ${nx}, Y ${ny}`))
    }
    return rows
  }

  if (key === 'adm_cd') {
    const code = stringField(value, 'code')
    const name = stringField(value, 'name')
    const level = stringField(value, 'level')
    if (code || name) {
      rows.push(
        React.createElement(
          Text,
          { key: 'adm-code' },
          `Administrative district: ${name ?? 'unnamed'}${code ? ` (${code})` : ''}${level ? ` · ${level}` : ''}`,
        ),
      )
    }
    return rows
  }

  if (key === 'region') {
    const name = stringField(value, 'address_name') ?? stringField(value, 'name')
    const code = stringField(value, 'code')
    if (name || code) {
      rows.push(React.createElement(Text, { key: 'region' }, `Region: ${name ?? 'unnamed'}${code ? ` (${code})` : ''}`))
    }
    return rows
  }

  if (key === 'address') {
    const road = stringField(value, 'road_address')
    const jibun = stringField(value, 'jibun_address')
    if (road) rows.push(React.createElement(Text, { key: 'road' }, `Road address: ${road}`))
    if (jibun) rows.push(React.createElement(Text, { key: 'jibun' }, `Jibun address: ${jibun}`))
    return rows
  }

  if (key === 'poi') {
    const name = stringField(value, 'name')
    const category = stringField(value, 'category')
    const lat = numberField(value, 'lat')
    const lon = numberField(value, 'lon')
    const nx = numberField(value, 'nx')
    const ny = numberField(value, 'ny')
    if (name) rows.push(React.createElement(Text, { key: 'poi' }, `Place: ${name}${category ? ` · ${category}` : ''}`))
    if (lat !== null && lon !== null) {
      rows.push(React.createElement(Text, { key: 'poi-latlon' }, `Coordinates: ${lat.toFixed(6)}, ${lon.toFixed(6)}`))
    }
    if (nx !== null && ny !== null) {
      rows.push(React.createElement(Text, { key: 'poi-grid' }, `KMA grid: X ${nx}, Y ${ny}`))
    }
  }
  return rows
}

function summarizeLocationResult(result: unknown): React.ReactNode[] {
  if (result === null || typeof result !== 'object') {
    return [React.createElement(Text, { key: 'raw', dimColor: true }, String(result))]
  }

  const obj = result as Record<string, unknown>
  const rows: React.ReactNode[] = []
  const kind = stringField(obj, 'kind')

  if (kind === 'bundle') {
    for (const key of ['coords', 'adm_cd', 'address', 'poi', 'region']) {
      const value = obj[key]
      if (value && typeof value === 'object') {
        rows.push(...summarizeLocationSlot(key, value as Record<string, unknown>))
      }
    }
    return rows.length > 0
      ? rows
      : [React.createElement(Text, { key: 'empty', dimColor: true }, 'No location result')]
  }

  const lat = numberField(obj, 'lat')
  const lon = numberField(obj, 'lon')
  if (lat !== null && lon !== null) {
    rows.push(React.createElement(Text, { key: 'coords' }, `Coordinates: ${lat}, ${lon}`))
  }
  const nx = numberField(obj, 'nx')
  const ny = numberField(obj, 'ny')
  if (nx !== null && ny !== null) {
    rows.push(React.createElement(Text, { key: 'grid' }, `KMA grid: X ${nx}, Y ${ny}`))
  }

  const code = stringField(obj, 'code') ?? stringField(obj, 'b_code') ?? stringField(obj, 'region_code')
  if (code) {
    rows.push(React.createElement(Text, { key: 'code' }, `Administrative/legal code: ${code}`))
  }

  const name =
    stringField(obj, 'address_name') ??
    stringField(obj, 'name') ??
    stringField(obj, 'road_address') ??
    stringField(obj, 'jibun_address')
  if (name) {
    rows.push(React.createElement(Text, { key: 'name' }, `Location name: ${name}`))
  }

  const source = stringField(obj, 'source')
  if (source) {
    rows.push(React.createElement(Text, { key: 'source', dimColor: true }, `source: ${source}`))
  }

  return rows.length > 0
    ? rows
    : [React.createElement(Text, { key: 'json', dimColor: true }, JSON.stringify(result).slice(0, 240))]
}

export const ResolveLocationPrimitive = buildTool({
  name: LOCATE_TOOL_NAME,

  searchHint: 'location address coordinates administrative district legal district locate geocode',

  maxResultSizeChars: 40_000,

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

  async description() {
    return DESCRIPTION
  },

  async prompt() {
    return LOCATE_TOOL_PROMPT
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
      type: 'tool_result',
      content: JSON.stringify(llmContent),
    }
  },

  renderToolUseMessage(input: { tool_id?: string; query?: string; want?: string }, options: { verbose: boolean }) {
    if (options.verbose) {
      return renderVerboseInputJson(input)
    }
    return input.tool_id ?? input.query ?? ''
  },

  isMcp: false,

  async validateInput(input: z.infer<InputSchema>, context: ToolUseContext) {
    if (isRootPrimitiveToolId(input.tool_id)) {
      return {
        result: false as const,
        message: rootPrimitiveSelfTargetMessage(input.tool_id, 'locate'),
        errorCode: 1,
      }
    }
    const kmaAviationChoice = validateKmaAviationToolChoice(input.tool_id, context)
    if (kmaAviationChoice) return kmaAviationChoice
    const directPublicDataChoice = validateDirectPublicDataToolChoice(
      input.tool_id,
      context,
      input.params,
    )
    if (directPublicDataChoice) return directPublicDataChoice
    return { result: true as const }
  },

  renderToolResultMessage(
    output: Output,
    _progress: unknown,
    options: { verbose: boolean; isTranscriptMode?: boolean } = { verbose: false },
  ): React.ReactNode {
    if (options.verbose || options.isTranscriptMode) {
      return renderVerboseOutputJson(output)
    }

    if (!output.ok) {
      return React.createElement(
        MessageResponse,
        null,
        React.createElement(Text, { color: 'red' }, `Location resolution error: ${output.error.message}`),
      )
    }

    return renderCompactPrimitiveResult([
      React.createElement(Text, { key: 'heading', bold: true }, 'Location result'),
      ...summarizeLocationResult(output.result),
    ])
  },

  isResultTruncated(output: Output): boolean {
    if (!output.ok) return false
    return isPrimitiveResultPreviewTruncated([
      React.createElement(Text, { key: 'heading', bold: true }, 'Location result'),
      ...summarizeLocationResult(output.result),
    ])
  },

  async checkPermissions(input) {
    return { behavior: 'allow' as const, updatedInput: input }
  },

  async call(input, context) {
    const repairedInput = repairLocateQueryParamsFromConversation(
      input as Record<string, unknown>,
      context.messages,
    )
    return dispatchPrimitive<Output>({
      primitive: 'locate',
      args: repairedInput,
      context,
      registry: getOrCreatePendingCallRegistry(),
      bridge: getOrCreateUmmayaBridge(),
    })
  },
} satisfies ToolDef<InputSchema, Output>)
