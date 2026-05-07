// SPDX-License-Identifier: Apache-2.0
// KOSMOS-original — Epic #2077 K-EXAONE tool wiring · T005.
//
// Mirrors _cc_reference/api.ts:toolToAPISchema (line 119-266)
// Converts the TUI's Zod-defined tool catalog into ToolDefinition[] for
// ChatRequestFrame.tools. Uses zod/v4 built-in z.toJSONSchema() (Draft 2020-12).

import { z } from 'zod/v4'
import type { Tool } from '../Tool.js'
import type { ToolDefinition } from '../ipc/codec.js'
import { getAllBaseTools } from '../tools.js'

// ---------------------------------------------------------------------------
// Published-to-LLM name set — FR-003 single-source rule (TUI side).
//
// Includes ONLY the active reserved primitives (Migration Tree § L1-C.C1).
// subscribe is deferred until KOSMOS has a real app/push-notification runtime.
// MVP-7 auxiliary tools (Migration Tree § L1-C.C6) are tracked client-side
// for permissions / sandbox infrastructure but NOT yet exposed to the LLM:
// their TUI-side execution path (``runTools`` → ``tool_result`` frame back
// to backend) is wired but the backend's IPC bridge does not yet round-trip
// non-primitive ``tool_call`` futures end-to-end. Surfacing them here would
// invite K-EXAONE to call them and trip the backend whitelist gate. Wiring
// is deferred to a follow-up epic — see spec § Deferred to Future Work.
//
// Excludes CC-developer tools that are inappropriate for citizen UX:
//   Read, Write, Edit, Bash, Glob, Grep, NotebookEdit  (Migration Tree § L1-C.C6)
// ---------------------------------------------------------------------------
const PUBLISHED_NAMES: ReadonlySet<string> = new Set([
  // Active root primitives — Epic #2077 FR-003 single-source-of-truth.
  'lookup',
  'resolve_location',
  'submit',
  'verify',
])

/**
 * Returns true if the tool should be included in the LLM's tool inventory.
 * Only tools whose `name` appears in the published set are forwarded.
 */
function isPublishedToLLM(tool: Tool): boolean {
  return PUBLISHED_NAMES.has(tool.name)
}

// ---------------------------------------------------------------------------
// Serialization helpers
// ---------------------------------------------------------------------------

/**
 * Converts a single {@link Tool} to an OpenAI-compatible {@link ToolDefinition}.
 *
 * - `function.name`        = tool.name
 * - `function.description` = description() + "\n\n" + prompt().slice(0, 200)
 *                            (either part omitted when absent/empty)
 * - `function.parameters`  = z.toJSONSchema(tool.inputSchema) — Draft 2020-12
 */
export async function toolToFunctionSchema(tool: Tool): Promise<ToolDefinition> {
  // KOSMOS primitives implement description() and prompt() as zero-arg constants.
  // Auxiliary tools (e.g. WebFetchTool) implement description(input, opts) and
  // require a real input value to produce a meaningful string.  We call with no
  // args and catch any destructuring error, falling back to an empty string.
  // This is safe: description() is used here only for the LLM's tool catalog
  // entry, where a static capability phrase is sufficient.
  const descFn = tool.description as unknown as (() => Promise<string>) | undefined
  const promptFn = tool.prompt as unknown as (() => Promise<string>) | undefined

  let descriptionText = ''
  try {
    descriptionText = descFn ? await descFn() : ''
  } catch {
    // Non-primitive tools whose description() requires an input arg are
    // silently skipped; the function.name alone identifies the tool to the LLM.
    descriptionText = ''
  }

  let promptText = ''
  try {
    promptText = promptFn ? (await promptFn()).slice(0, 200) : ''
  } catch {
    promptText = ''
  }

  const description = [descriptionText, promptText].filter(Boolean).join('\n\n')

  const parameters = z.toJSONSchema(tool.inputSchema) as Record<string, unknown>

  return {
    type: 'function' as const,
    function: {
      name: tool.name,
      description,
      parameters,
    },
  }
}

/**
 * Walks {@link getAllBaseTools} and returns the publishable tool inventory,
 * sorted alphabetically by `function.name`.
 *
 * Called once per `chat_request` turn in `tui/src/query/deps.ts`.
 * Budget: ≤ 50 ms (4 published primitive schemas; Zod conversion is fast and tool descriptions
 * are constant-string returns — no I/O).
 */
export async function getToolDefinitionsForFrame(): Promise<ToolDefinition[]> {
  const allTools = getAllBaseTools()
  const visible = allTools.filter(isPublishedToLLM)
  const defs = await Promise.all(visible.map(toolToFunctionSchema))
  return defs.sort((a, b) => a.function.name.localeCompare(b.function.name))
}
