// SPDX-License-Identifier: Apache-2.0
// KOSMOS-original — Wave-2 G5 (Spec realuse-audit-2026-05-05).
//
// F-alpha-08 — Ctrl-O / transcript-mode reveal of LLM ``thinking`` text was
// surfacing internal scaffolding (``available_adapters`` block name,
// ``tool_id`` field name, registry adapter ids) verbatim to the citizen.
// CC restored-src never had this problem because the Anthropic system
// prompt did not contain those internal tokens. KOSMOS' system prompt /
// suffix does. We sanitize at the citizen-facing display surface only;
// the raw ``thinking`` channel that the agentic loop sends back to the
// LLM in subsequent turns is **not** modified — agentic context is
// preserved.
//
// Allow / deny list rationale (see specs/realuse-audit-2026-05-05/research/g5-render.md):
//
//   redact:
//     - "available_adapters"  — internal block name (suffix injection)
//     - "tool_id"             — internal field name
//     - adapter ids matching one of the registered ministry namespaces
//       (hira_*, kma_*, koroad_*, nmc_*, nfa119_*, mohw_*, mock_verify_*,
//        mock_lookup_*, mock_submit_*, mock_subscribe_*)
//
//   preserve (NOT redacted):
//     - 5 primitive names (lookup / resolve_location / submit / verify /
//       subscribe) — these are also citizen-facing in the ``⏺ lookup(...)``
//       gutter glyph rows; redacting would create a cognitive mismatch.
//     - Korean prose — the citizen needs to see the model's reasoning.

const REDACT_TOKENS: readonly RegExp[] = [
  /\bavailable_adapters\b/g,
  /\btool_id\b/g,
] as const

// Adapter id namespaces. The list mirrors the ministry / mock prefixes
// used in src/kosmos/tools/<ministry>/ and the ``mock_<verb>_*`` family.
// `\b` word boundary prevents partial matches inside Korean text.
const ADAPTER_ID_RE: RegExp =
  /\b(?:hira|kma|koroad|nmc|nfa119|mohw|mock_(?:verify|lookup|submit|subscribe))_[a-z0-9_]+\b/g

const INTERNAL_PLACEHOLDER = '⟨내부⟩'
const ADAPTER_PLACEHOLDER = '⟨adapter⟩'

/**
 * Redact internal scaffolding tokens from an LLM ``thinking`` string before
 * it is rendered to the citizen via Ctrl-O / transcript mode.
 *
 * Idempotent: applying the function twice yields the same result. Operates
 * on a per-character / per-regex basis with no markdown awareness — the
 * downstream renderer (``Markdown`` component in AssistantThinkingMessage)
 * still handles formatting.
 *
 * @param thinking Raw LLM reasoning text (assistant message ``thinking`` field).
 * @returns Sanitized string safe for citizen-facing display.
 */
export function sanitizeThinking(thinking: string): string {
  if (!thinking) return thinking
  let out = thinking
  for (const re of REDACT_TOKENS) {
    out = out.replace(re, INTERNAL_PLACEHOLDER)
  }
  out = out.replace(ADAPTER_ID_RE, ADAPTER_PLACEHOLDER)
  return out
}
