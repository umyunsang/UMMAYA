// SPDX-License-Identifier: Apache-2.0
// KOSMOS-original — Epic #1634 P3 · SubscribePrimitive prompt strings.
// Epic γ #2294 · T018: Korean description tightened to ≤ 240 chars.
// Contract: specs/1634-tool-system-wiring/contracts/primitive-envelope.md § 5

export const SUBSCRIBE_TOOL_NAME = 'subscribe'

/** One-line citizen-facing Korean description shown to the LLM (≤ 240 chars). */
export const DESCRIPTION =
  '등록된 스트리밍 어댑터를 구독하고 세션 기반 핸들을 받습니다. 재난 알림·실시간 대기질 등 push 스트림을 tool_id로 지정하세요. 반환된 handle_id로 구독을 참조하며, 실제 스트림은 대화창 ⎿ 접두어로 전달됩니다.'

/** Extended prompt included in the system-prompt tool-use section. */
export const SUBSCRIBE_TOOL_PROMPT = `Subscribe to a streaming KOSMOS adapter and receive a session-lifetime handle.

Input: { tool_id: string, params: object, lifetime_seconds?: number }
  - tool_id: the streaming adapter identifier (obtain via lookup mode=search first)
  - params: adapter-defined Pydantic-validated subscription parameter body
  - lifetime_seconds: bounded handle lifetime in seconds — default 300 if omitted; maximum 31,536,000 (365 days)

Output: { handle_id: string, lifetime: string, kind: string }
  - handle_id: opaque subscription handle recorded in the audit ledger (Spec 024)
  - lifetime: actual granted lifetime (may differ from hint)
  - kind: adapter stream kind, e.g. "cbs_disaster_alert", "rss_feed"
  NOTE: The stream itself is delivered out-of-band via TUI ⎿ multi-turn citation prefix.
        The LLM receives only the handle — not the stream data directly.

Rules:
- subscribe is session-scoped and side-effecting — not concurrency safe.
- Use handle_id to reference the subscription in follow-up lookup or subscribe calls.
- Layer 2 orange ⓶ permission gauntlet executes before adapter dispatch.
- prefer 300 seconds unless the user explicitly requests a longer bounded lifetime.`
