// SPDX-License-Identifier: Apache-2.0
// UMMAYA-original — DocumentPrimitive.

import React from 'react'
import { z } from 'zod/v4'
import { Text } from '../../ink.js'
import { buildTool, type ToolDef } from '../../Tool.js'
import { lazySchema } from '../../utils/lazySchema.js'
import { getOrCreateUmmayaBridge } from '../../ipc/bridgeSingleton.js'
import { getOrCreatePendingCallRegistry } from '../../ipc/pendingCallSingleton.js'
import { dispatchPrimitive } from '../_shared/dispatchPrimitive.js'
import {
  applyDocumentVisualRenderGateToOutput,
  isDocumentVisualRenderFailedOutput,
  renderDocumentToolResultIfPresent,
} from '../_shared/documentToolResultRender.js'
import {
  renderVerboseInputJson,
  renderVerboseOutputJson,
} from '../_shared/verboseRender.js'
import {
  isPrimitiveResultPreviewTruncated,
  renderCompactPrimitiveResult,
} from '../_shared/compactPrimitiveResult.js'
import { resolveDocumentPrimitiveTimeoutMs } from '../_shared/documentPrimitiveTimeout.js'
import {
  DOCUMENT_TOOL_NAME,
  DESCRIPTION,
  DOCUMENT_TOOL_PROMPT,
} from './prompt.js'
import {
  latestUserTextFromContext,
  normalizeDocumentPrimitiveInputForDispatch as normalizeDispatchInput,
  operationOf,
} from './dispatchNormalization.js'
import { modelVisibleDocumentOutput } from './modelVisibleOutput.js'

export { normalizeDocumentPrimitiveInputForDispatch } from './dispatchNormalization.js'

const documentRefSchema = z
  .object({
    path: z.string().min(1).optional(),
    artifact_id: z.string().min(1).optional(),
    expected_format: z
      .enum(['hwpx', 'hwp', 'docx', 'pdf', 'xlsx', 'pptx'])
      .optional(),
  })
  .passthrough()

const inputSchema = lazySchema(() =>
  z
    .object({
      correlation_id: z.string().min(1),
      document: documentRefSchema,
      operation: z
        .enum(['inspect', 'extract', 'fill', 'style', 'validate', 'save'])
        .optional(),
      instruction: z.string().min(1),
      destination_path: z.string().min(1).optional(),
      destination_display_name: z.string().min(1).optional(),
      template_id: z.string().min(1).optional(),
      patches: z.array(z.unknown()).optional(),
      styles: z.array(z.unknown()).optional(),
    })
    .passthrough(),
)
type InputSchema = ReturnType<typeof inputSchema>
export type Input = z.infer<InputSchema>

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

function documentTarget(input: Input): string {
  const document = input.document as Record<string, unknown>
  const path = typeof document.path === 'string' ? document.path : undefined
  const artifactId =
    typeof document.artifact_id === 'string' ? document.artifact_id : undefined
  return path ?? artifactId ?? 'document'
}

function documentAction(input: Input): string {
  switch (operationOf(input)) {
    case 'inspect':
      return 'Inspect document'
    case 'extract':
      return 'Read document'
    case 'style':
      return 'Apply document formatting'
    case 'validate':
      return 'Validate public-form rules'
    case 'save':
      return 'Save document'
    case 'fill':
    default:
      return 'Write document'
  }
}

function buildDocumentErrorRows(output: Extract<Output, { ok: false }>): React.ReactNode[] {
  return [
    React.createElement(
      Text,
      { key: 'document-error', color: 'red' },
      `Document failed: ${output.error.message}`,
    ),
  ]
}

export const DocumentPrimitive = buildTool({
  name: DOCUMENT_TOOL_NAME,

  searchHint:
    'document hwpx hwp docx pdf xlsx pptx form fill render save diff public document',

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
    return false
  },

  isReadOnly(input?: Input) {
    const operation = input ? operationOf(input) : 'fill'
    return operation === 'inspect' || operation === 'extract' || operation === 'validate'
  },

  isDestructive() {
    return false
  },

  async description() {
    return DESCRIPTION
  },

  async prompt() {
    return DOCUMENT_TOOL_PROMPT
  },

  mapToolResultToToolResultBlockParam(output, toolUseID) {
    const gatedOutput = applyDocumentVisualRenderGateToOutput(output)
    return {
      tool_use_id: toolUseID,
      type: 'tool_result',
      content: JSON.stringify(modelVisibleDocumentOutput(gatedOutput)),
      ...(isDocumentVisualRenderFailedOutput(gatedOutput) ? { is_error: true } : {}),
    }
  },

  renderToolUseMessage(input: Input, options: { verbose: boolean }) {
    if (options.verbose) return renderVerboseInputJson(input)
    return `${documentAction(input)}: ${documentTarget(input)}`
  },

  isMcp: false,

  async validateInput(input: Input, _context: ToolUseContext) {
    if (typeof input !== 'object' || input === null) {
      return {
        result: false as const,
        message: 'document expects a JSON object argument.',
        errorCode: 1,
      }
    }
    const document = input.document as Record<string, unknown> | undefined
    if (!document || typeof document !== 'object') {
      return {
        result: false as const,
        message: 'document.document is required.',
        errorCode: 1,
      }
    }
    if (
      typeof document.path !== 'string' &&
      typeof document.artifact_id !== 'string'
    ) {
      return {
        result: false as const,
        message: 'document requires either document.path or document.artifact_id.',
        errorCode: 1,
      }
    }
    if (typeof input.instruction !== 'string' || input.instruction.trim() === '') {
      return {
        result: false as const,
        message: 'document.instruction is required.',
        errorCode: 1,
      }
    }
    return { result: true as const }
  },

  renderToolResultMessage(
    output: Output,
    _progress: unknown,
    options: { verbose: boolean; isTranscriptMode?: boolean } = { verbose: false },
  ) {
    const gatedOutput = applyDocumentVisualRenderGateToOutput(output) as Output
    const documentResult = renderDocumentToolResultIfPresent(gatedOutput, options)
    if (documentResult !== null) return documentResult
    if (options.verbose || options.isTranscriptMode) {
      return renderVerboseOutputJson(gatedOutput)
    }
    return renderCompactPrimitiveResult(
      gatedOutput.ok
        ? [React.createElement(Text, { key: 'document-ok' }, 'Document result received.')]
        : buildDocumentErrorRows(gatedOutput),
    )
  },

  isResultTruncated(output: Output): boolean {
    if (output.ok) return false
    return isPrimitiveResultPreviewTruncated(buildDocumentErrorRows(output))
  },

  async call(input, context) {
    const args = normalizeDispatchInput(
      input as Input,
      latestUserTextFromContext(context),
    )
    const result = await dispatchPrimitive<Output>({
      primitive: 'document',
      args,
      context,
      registry: getOrCreatePendingCallRegistry(),
      bridge: getOrCreateUmmayaBridge(),
      timeoutMs: resolveDocumentPrimitiveTimeoutMs(),
    })
    return {
      ...result,
      data: applyDocumentVisualRenderGateToOutput(result.data) as Output,
    }
  },
} satisfies ToolDef<InputSchema, Output>)
