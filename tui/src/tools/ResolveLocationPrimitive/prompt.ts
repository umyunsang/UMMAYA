// SPDX-License-Identifier: Apache-2.0
// UMMAYA-original — LocatePrimitive prompt strings.

export const LOCATE_TOOL_NAME = 'locate'

/** Citizen-facing English description shown to the LLM. */
export const DESCRIPTION =
  'Discover Korean location adapters. Prefer concrete location adapter functions loaded by ToolSearch or backend retrieval; locate is a legacy wrapper only.'

/** Extended prompt included in the system-prompt tool-use section. */
export const LOCATE_TOOL_PROMPT = `Resolve Korean location phrases with concrete location adapters.

Preferred path:
- Call concrete adapter functions directly after their schemas are loaded.
- Adapter schemas are progressively disclosed by ToolSearch or by backend top-K retrieval for the current citizen request.

Legacy root wrapper:
- If a concrete adapter function is not loaded and only the root primitive is available, locate accepts { tool_id, params } for old transcripts and compatibility paths.
- tool_id must be a concrete locate adapter id from <available_adapters>, never "locate", "find", "check", or "send".
- Invalid: locate({ tool_id: "locate", params: {...} })

Rules:
- Use the concrete location adapter schema fields exactly.
- Reuse exact coordinate, region, or administrative-code fields from successful location results when a downstream adapter requires them.
- If the result is kind="error", do not invent coordinates or administrative codes.`
