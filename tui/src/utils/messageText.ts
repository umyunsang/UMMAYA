// SPDX-License-Identifier: Apache-2.0
// Spec debug-infra-rebuild (2026-05-02): tiny module so the most-imported
// helpers (isEmptyMessageText, stripPromptXMLTags) can be loaded without
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
