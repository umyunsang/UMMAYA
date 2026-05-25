// SPDX-License-Identifier: Apache-2.0
// UMMAYA-original — Epic #1634 P3 · CheckPrimitive prompt strings.
// Epic γ #2294 · T015: English description kept within 240 chars.
// Contract: specs/1634-tool-system-wiring/contracts/primitive-envelope.md § 4

export const CHECK_TOOL_NAME = 'check'

/** One-line citizen-facing English description shown to the LLM (<= 240 chars). */
export const DESCRIPTION =
  'Discover credential-check adapters. Prefer concrete adapter functions loaded by retrieval; check never mints or stores credentials.'

/** Extended prompt included in the system-prompt tool-use section. */
export const CHECK_TOOL_PROMPT = `Delegate credential checking to a concrete UMMAYA auth adapter.

Preferred path:
- Call concrete adapter functions directly after their schemas are loaded.
- Adapter schemas are progressively disclosed by ToolSearch or backend top-K retrieval for the current citizen request.
- Use the adapter's exact schema fields for scope, purpose, and session-bound evidence.

Legacy root wrapper:
- If a concrete adapter function is not loaded and only the root primitive is available, check accepts { tool_id, params } for old transcripts and compatibility paths.
- tool_id must be a registered check adapter id, not "check", "find", "locate", or "send".

Output (discriminated by auth_family):
  - auth_family: "gongdong_injeungseo" | "geumyung_injeungseo" | "ganpyeon_injeung" | "digital_onepass" | "mobile_id" | "mydata"
  - The LLM uses auth_family to determine the resulting auth level (AAL1/AAL2/AAL3)
    and to decide subsequent calls (e.g., "now I have AAL2, I can call this send adapter")

Rules:
- check NEVER mints credentials — it only delegates verification.
- Use the auth_family in the output to plan subsequent send or find calls.
- Do NOT store or log credential values in params.
- Layer 1 green ⓵ permission applies; no user confirmation modal for read-only check.`
