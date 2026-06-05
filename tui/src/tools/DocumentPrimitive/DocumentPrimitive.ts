// SPDX-License-Identifier: Apache-2.0
// UMMAYA-original — DocumentPrimitive.

import React from 'react'
import { z } from 'zod/v4'
import { Text } from '../../ink.js'
import { buildTool, type ToolDef, type ToolUseContext } from '../../Tool.js'
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
type Input = z.infer<InputSchema>

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

const WRITE_INTENT_RE =
  /(작성|수정|편집|채우|입력|변경|저장|보정|서식|글꼴|글자색|배경색|정렬|굵게|write|edit|fill|apply|save|style|format|bold)/iu

function hasWriteIntent(input: Input): boolean {
  return hasWriteIntentFromText(input, undefined)
}

function hasWriteIntentFromText(input: Input, userText: string | undefined): boolean {
  if (typeof input.destination_path === 'string') return true
  if (Array.isArray(input.patches) && input.patches.length > 0) return true
  if (Array.isArray(input.styles) && input.styles.length > 0) return true
  return WRITE_INTENT_RE.test(input.instruction ?? '') ||
    (userText !== undefined && WRITE_INTENT_RE.test(userText))
}

function operationOf(input: Input, userText?: string): string {
  const displayOperation =
    typeof (input as Record<string, unknown>).__ummaya_display_operation === 'string'
      ? String((input as Record<string, unknown>).__ummaya_display_operation)
      : undefined
  if (
    displayOperation === 'fill' ||
    displayOperation === 'style' ||
    displayOperation === 'save'
  ) {
    return displayOperation
  }
  const operation = typeof input.operation === 'string' ? input.operation : 'fill'
  if (
    (operation === 'inspect' || operation === 'extract') &&
    hasWriteIntentFromText(input, userText)
  ) {
    return 'fill'
  }
  return operation
}

function latestUserTextFromContext(context: ToolUseContext): string | undefined {
  const messages = (context as Record<string, unknown>).messages
  if (!Array.isArray(messages)) return undefined
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index] as Record<string, unknown> | undefined
    if (!message || message.type !== 'user') continue
    const sdkMessage = message.message as Record<string, unknown> | undefined
    const content = sdkMessage?.content ?? message.content
    if (typeof content === 'string' && content.trim() !== '') {
      return content
    }
    if (!Array.isArray(content)) continue
    const text = content
      .map(block => {
        if (!block || typeof block !== 'object') return ''
        const item = block as Record<string, unknown>
        return item.type === 'text' && typeof item.text === 'string'
          ? item.text
          : ''
      })
      .filter(Boolean)
      .join('\n')
      .trim()
    if (text !== '') return text
  }
  return undefined
}

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
    const args = {
      ...(input as Record<string, unknown>),
      operation: operationOf(input as Input, latestUserTextFromContext(context)),
    }
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

function modelVisibleDocumentOutput(output: unknown): unknown {
  return rewriteModelVisibleDocumentValue(output)
}

function rewriteModelVisibleDocumentValue(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => rewriteModelVisibleDocumentValue(item))
  }
  const record = asRecord(value)
  if (record === null) {
    return value
  }

  const rewritten: Record<string, unknown> = {}
  for (const [key, nested] of Object.entries(record)) {
    rewritten[key] = rewriteModelVisibleDocumentValue(nested)
  }

  const displayLabel = nonEmptyString(rewritten.display_label)
  if (displayLabel !== undefined && typeof rewritten.target_path === 'string') {
    rewritten.target_path = displayLabel
  }
  return rewritten
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null
}

function nonEmptyString(value: unknown): string | undefined {
  if (typeof value !== 'string') {
    return undefined
  }
  const trimmed = value.trim()
  return trimmed === '' ? undefined : trimmed
}
