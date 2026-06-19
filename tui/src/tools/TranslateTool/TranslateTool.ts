// SPDX-License-Identifier: Apache-2.0
// UMMAYA-original — Epic #1634 P4 · TranslateTool.
//
// Delegates Korean↔English↔Japanese translation to the FriendliAI K-EXAONE
// model through the existing stdio IPC bridge (LLMClient.complete()).
// Zero new runtime dependencies — uses only the existing Bun stdlib and the
// ipc/ modules already present in tui/package.json.
//
// I/O contract: contracts/primitive-envelope.md § 6
//   Input  — { text: string, source_lang: "ko"|"en"|"ja", target_lang: "ko"|"en"|"ja" }
//   Output — { text: string }

import { z } from 'zod/v4'
import { buildTool, type ToolDef } from '../../Tool.js'
import { lazySchema } from '../../utils/lazySchema.js'
import { LLMClient } from '../../ipc/llmClient.js'
import {
  getOrCreateUmmayaBridge,
  getUmmayaBridgeSessionId,
} from '../../ipc/bridgeSingleton.js'
import {
  TRANSLATE_TOOL_NAME,
  DESCRIPTION,
  TRANSLATE_TOOL_PROMPT,
  buildTranslatePrompt,
} from './prompt.js'
import { renderToolUseMessage, renderToolResultMessage } from './UI.js'

// ---------------------------------------------------------------------------
// Schema
// ---------------------------------------------------------------------------

const LANG_ENUM = z.enum(['ko', 'en', 'ja'])

const inputSchema = lazySchema(() =>
  z.strictObject({
    text: z
      .string()
      .min(1)
      .describe('The text to translate'),
    source_lang: LANG_ENUM.describe(
      'Source language code: "ko" (Korean), "en" (English), "ja" (Japanese)',
    ),
    target_lang: LANG_ENUM.describe(
      'Target language code: "ko" (Korean), "en" (English), "ja" (Japanese)',
    ),
  }),
)
type InputSchema = ReturnType<typeof inputSchema>

const outputSchema = lazySchema(() =>
  z.object({
    text: z.string().describe('Translated text'),
  }),
)
type OutputSchema = ReturnType<typeof outputSchema>

export type Output = z.infer<OutputSchema>

// ---------------------------------------------------------------------------
// The UMMAYA model identifier (matches services/api/ummaya.ts)
// ---------------------------------------------------------------------------

const UMMAYA_MODEL = 'LGAI-EXAONE/K-EXAONE-236B-A23B'

// ---------------------------------------------------------------------------
// Tool definition
// ---------------------------------------------------------------------------

export const TranslateTool = buildTool({
  name: TRANSLATE_TOOL_NAME,

  /** Keyword phrase for ToolSearch deferred-tool discovery. */
  searchHint: 'translate text between Korean, English, and Japanese',

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
    // Translation is purely read-only and side-effect-free.
    return true
  },

  isReadOnly() {
    return true
  },

  async description() {
    return DESCRIPTION
  },

  async prompt() {
    return TRANSLATE_TOOL_PROMPT
  },

  mapToolResultToToolResultBlockParam(output, toolUseID) {
    return {
      tool_use_id: toolUseID,
      type: 'tool_result',
      content: output.text,
    }
  },

  renderToolUseMessage,
  renderToolResultMessage,

  /**
   * Delegate translation to K-EXAONE via the existing stdio IPC bridge.
   *
   * Uses LLMClient.complete() — the non-streaming convenience wrapper —
   * so we get the full response as a single UmmayaMessageFinal, then
   * extract the text content block.  No new dependencies required.
   */
  async call({ text, source_lang, target_lang }, _context) {
    const bridge = getOrCreateUmmayaBridge()
    const sessionId = getUmmayaBridgeSessionId()

    const client = new LLMClient({
      bridge,
      model: UMMAYA_MODEL,
      sessionId,
    })

    const prompt = buildTranslatePrompt(text, source_lang, target_lang)

    const result = await client.complete({
      model: UMMAYA_MODEL,
      messages: [{ role: 'user', content: prompt }],
      max_tokens: 4_096,
      // Lower temperature for deterministic translation output.
      temperature: 0.1,
    })

    // Extract the first text block from the response content.
    let translated = ''
    for (const block of result.content) {
      if (block.type === 'text') {
        translated = block.text.trim()
        break
      }
    }

    return { data: { text: translated } }
  },
} satisfies ToolDef<InputSchema, Output>)
