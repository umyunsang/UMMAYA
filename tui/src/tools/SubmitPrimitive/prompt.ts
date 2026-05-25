// SPDX-License-Identifier: Apache-2.0
// UMMAYA-original — SendPrimitive prompt strings.
// Contract: specs/1634-tool-system-wiring/contracts/primitive-envelope.md § 3

export const SEND_TOOL_NAME = 'send'

/** One-line English description (<= 240 chars). */
export const DESCRIPTION =
  'Discover side-effecting public-service send adapters. Prefer concrete adapter functions loaded by retrieval; send is a permission-gated legacy wrapper.'

/** Extended prompt included in the system-prompt tool-use section. */
export const SEND_TOOL_PROMPT = `Send a side-effecting citizen action through a concrete UMMAYA adapter.

Preferred path:
- Call concrete adapter functions directly after their schemas are loaded.
- Adapter schemas are progressively disclosed by ToolSearch or backend top-K retrieval for the current citizen request.
- Use the adapter's exact schema fields and cite the resulting receipt in the citizen-facing answer.

Legacy root wrapper:
- If a concrete adapter function is not loaded and only the root primitive is available, send accepts { tool_id, params } for old transcripts and compatibility paths.
- tool_id must be a registered send adapter id, not "send", "find", "locate", or "check".

Output: { transaction_id: string, status: string, adapter_receipt: object }
  - transaction_id: deterministically derived identifier for idempotency reasoning
  - status: "accepted" | "rejected" | "pending"
  - adapter_receipt: adapter-specific confirmation payload

Rules:
- send is IRREVERSIBLE — confirm intent clearly before calling.
- The permission gauntlet (Layer 2 orange ⓶) executes before adapter dispatch.
- Use transaction_id to reason about idempotency (same input → same ID).
- Do NOT send on behalf of the user without explicit confirmation.`
