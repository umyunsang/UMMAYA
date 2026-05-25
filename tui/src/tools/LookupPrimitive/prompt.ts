// SPDX-License-Identifier: Apache-2.0
// UMMAYA-original — Epic #1634 P3 · FindPrimitive prompt strings.
// 2026 migration note: root primitives are lightweight category descriptors
// and legacy transcript compatibility wrappers. Concrete adapter functions are
// loaded through CC ToolSearch/deferred schema expansion or backend top-K
// retrieval, then called directly with adapter schema arguments.
// Contract: specs/1634-tool-system-wiring/contracts/primitive-envelope.md § 2

export const FIND_TOOL_NAME = 'find'

/** Citizen-facing English description shown to the LLM (<= 240 chars). */
export const DESCRIPTION =
  'Discover Korean public-service lookup adapters. Prefer concrete adapter functions loaded by ToolSearch or backend retrieval; find is a legacy wrapper only.'

/** Extended prompt included in the system-prompt tool-use section. */
export const FIND_TOOL_PROMPT = `Discover Korean public-service lookup adapters registered in the UMMAYA tool registry.

Preferred path:
- Call concrete adapter functions directly after their schemas are loaded.
- Example: kma_current_observation({ base_date: "YYYYMMDD", base_time: "HH00", nx: 97, ny: 74 })
- Adapter schemas are progressively disclosed by ToolSearch or by backend top-K retrieval for the current citizen request.
- Only top candidates should be loaded; do not expect every adapter schema in the prompt.

Legacy root wrapper:
- If a concrete adapter function is not loaded and only the root primitive is available, find accepts { tool_id, params } for old transcripts and compatibility paths.
- tool_id must be a concrete adapter id from <available_adapters>, never "find", "locate", "check", or "send".
- Invalid: find({ tool_id: "find", params: {...} })
- Compatibility-only: find({ tool_id: "kma_current_observation", params: { base_date: "YYYYMMDD", base_time: "HH00", nx: 97, ny: 74 } })

Rules:
- Do not call find with mode='search' or query; discovery is handled outside the primitive call.
- Do not call the same adapter twice in a single turn unless a validation error requires corrected arguments.
- Use the concrete adapter schema fields exactly; never invent required keys.`
