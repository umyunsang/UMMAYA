// SPDX-License-Identifier: Apache-2.0
// Spec debug-infra-rebuild (2026-05-02): tiny module so the most-imported
// helpers can be loaded without
// dragging in the 5,000+-line `messages.ts` parse cost. The Bun loader on
// Linux CI repeatedly emitted
//   SyntaxError: Export named 'isEmptyMessageText' not found in module
//   '/.../tui/src/utils/messages.ts'
// when `tests/ipc/thinking-delta-render.test.tsx` (transitively via
// AssistantThinkingMessage) tried to load messages.ts. The same Bun
// version (1.3.x) on macOS accepts the file. Splitting the helpers off
// gives thinking-delta-render — and any other small consumer — a safe
// load path that doesn't depend on the rest of messages.ts evaluating
// cleanly under every Bun build.
//
// `messages.ts` re-exports these names so existing call sites keep working.

import { NO_CONTENT_MESSAGE } from '../constants/messages.js'

const STRIPPED_TAGS_RE =
  /<(commit_analysis|context|function_analysis|pr_analysis)>.*?<\/\1>\n?/gs

export function stripPromptXMLTags(content: string): string {
  return content.replace(STRIPPED_TAGS_RE, '').trim()
}

export function isEmptyMessageText(text: string): boolean {
  return (
    stripPromptXMLTags(text).trim() === '' || text.trim() === NO_CONTENT_MESSAGE
  )
}

export const SYNTHETIC_MODEL = '<synthetic>'

const INTERRUPT_MESSAGE = '[Request interrupted by user]'
const INTERRUPT_MESSAGE_FOR_TOOL_USE =
  '[Request interrupted by user for tool use]'
const CANCEL_MESSAGE =
  "The user doesn't want to take this action right now. STOP what you are doing and wait for the user to tell you how to proceed."
const REJECT_MESSAGE =
  "The user doesn't want to proceed with this tool use. The tool use was rejected (eg. if it was a file edit, the new_string was NOT written to the file). STOP what you are doing and wait for the user to tell you how to proceed."
const NO_RESPONSE_REQUESTED = 'No response requested.'

export const SYNTHETIC_MESSAGES = new Set([
  INTERRUPT_MESSAGE,
  INTERRUPT_MESSAGE_FOR_TOOL_USE,
  CANCEL_MESSAGE,
  REJECT_MESSAGE,
  NO_RESPONSE_REQUESTED,
])

/**
 * Extract text from an array of content blocks, joining text blocks with the
 * given separator. Works with ContentBlock, ContentBlockParam, BetaContentBlock,
 * and their readonly/DeepImmutable variants via structural typing.
 */
export function extractTextContent(
  blocks: readonly { readonly type: string }[],
  separator = '',
): string {
  return blocks
    .filter((b): b is { type: 'text'; text: string } => b.type === 'text')
    .map(b => b.text)
    .join(separator)
}
