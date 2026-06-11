// SPDX-License-Identifier: Apache-2.0

import type { ToolUseContext } from '../../Tool.js'

const DOCUMENT_READ_ONLY_OPERATIONS = new Set(['inspect', 'extract', 'validate'])

type PrimitiveName = 'find' | 'locate' | 'check' | 'send' | 'document'

export interface PrimitiveArgumentsOpts {
  readonly primitive: PrimitiveName
  readonly args: Record<string, unknown>
  readonly context: ToolUseContext
}

export function argumentsForPrimitive(
  opts: PrimitiveArgumentsOpts,
): Record<string, unknown> {
  if (opts.primitive !== 'document') return opts.args
  if (isReadOnlyDocumentOperation(opts.args)) return opts.args
  const userQuery = latestUserTextFromContext(opts.context)
  if (!userQuery) return opts.args
  return {
    ...opts.args,
    __ummaya_user_query: userQuery,
  }
}

function isReadOnlyDocumentOperation(args: Record<string, unknown>): boolean {
  const operation = typeof args.operation === 'string'
    ? args.operation.toLowerCase()
    : 'fill'
  return DOCUMENT_READ_ONLY_OPERATIONS.has(operation)
}

function latestUserTextFromContext(context: ToolUseContext): string | undefined {
  const messages = context.messages ?? []
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = recordFrom(messages[index])
    if (message === undefined || message.type !== 'user') continue
    const sdkMessage = recordFrom(message.message)
    if (sdkMessage === undefined || sdkMessage.role !== 'user') continue
    const content = sdkMessage.content
    if (typeof content === 'string' && content.trim() !== '') {
      return content
    }
    const text = textFromContentBlocks(content)
    if (text !== undefined) return text
  }
  return undefined
}

function textFromContentBlocks(content: unknown): string | undefined {
  if (!Array.isArray(content)) return undefined
  const text = content
    .map(block => {
      const item = recordFrom(block)
      if (item?.type !== 'text') return ''
      return typeof item.text === 'string' ? item.text : ''
    })
    .filter(Boolean)
    .join('\n')
    .trim()
  return text === '' ? undefined : text
}

function recordFrom(value: unknown): Record<string, unknown> | undefined {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? Object.fromEntries(Object.entries(value))
    : undefined
}
