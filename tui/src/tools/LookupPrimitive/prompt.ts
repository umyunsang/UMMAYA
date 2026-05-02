// SPDX-License-Identifier: Apache-2.0
// KOSMOS-original — Epic #1634 P3 · LookupPrimitive prompt strings.
// Spec 2521 (2026-05-01) — fetch-only surface; BM25 adapter discovery is a
// backend-internal mechanism (auto-injected into the system prompt's
// <available_adapters> dynamic suffix), not an LLM-callable mode. Older
// "search/fetch two-mode" copy was the source of phantom tool-UI noise the
// user surfaced via Layer 5 frame capture (specs/2521 frames/raw.cast).
// Contract: specs/1634-tool-system-wiring/contracts/primitive-envelope.md § 2

export const LOOKUP_TOOL_NAME = 'lookup'

/** Citizen-facing Korean description shown to the LLM (≤ 240 chars). */
export const DESCRIPTION =
  '한국 공공서비스 어댑터를 호출합니다. 시스템 프롬프트의 <available_adapters> 블록에 백엔드가 사용자 발화에 맞는 후보 어댑터를 자동으로 inject합니다 — 그 목록의 tool_id를 골라 lookup({tool_id, params})로 호출하세요.'

/** Extended prompt included in the system-prompt tool-use section. */
export const LOOKUP_TOOL_PROMPT = `Invoke Korean public-service adapters registered in the KOSMOS tool registry.

Single mode (Spec 2521 fetch-only):

  Input:  { tool_id: string, params: object }
  Output: { tool_id: string, result: object }

Adapter discovery
─────────────────
Adapter discovery is a BACKEND-INTERNAL function — NOT a callable mode.
For every citizen turn the backend runs BM25 against the registry and
injects the top-K candidates into the system prompt's
<available_adapters> dynamic suffix. The LLM picks a tool_id from that
block and calls lookup directly.

Rules:
- Pick tool_id only from <available_adapters>. Never guess an id.
- Do NOT call lookup with mode='search' / query — those payloads are
  rejected with LookupErrorReason.invalid_params (Spec 2521).
- Do NOT call the same tool_id twice in a single turn — answer with the
  result you already have, or pick a different tool_id from the list.
- params shape mirrors the adapter's Pydantic input_schema (see the
  <available_adapters> hint for required keys).`
