// SPDX-License-Identifier: Apache-2.0
// KOSMOS-original — Epic #1634 P3 · VerifyPrimitive prompt strings.
// Epic γ #2294 · T015: Korean description tightened to ≤ 240 chars.
// Contract: specs/1634-tool-system-wiring/contracts/primitive-envelope.md § 4

export const VERIFY_TOOL_NAME = 'verify'

/** One-line citizen-facing Korean description shown to the LLM (≤ 240 chars). */
export const DESCRIPTION =
  '인증 어댑터에 scope-bound 위임을 요청합니다. 등록된 verify tool_id와 params.scope_list·purpose_ko·purpose_en을 함께 지정하세요. 결과는 후속 lookup/submit에 전달할 DelegationContext입니다.'

/** Extended prompt included in the system-prompt tool-use section. */
export const VERIFY_TOOL_PROMPT = `Delegate credential verification to a registered KOSMOS auth adapter.

Input: { tool_id: string, params: { scope_list: string[], purpose_ko: string, purpose_en: string } }
  - tool_id: the verify adapter identifier from <verify_families> or delegation_source_tool_id metadata.
  - params.scope_list: every downstream primitive scope this ceremony must cover.
    Example: ["lookup:hometax.simplified", "submit:hometax.tax-return"]
  - params.purpose_ko / params.purpose_en: bilingual purpose for the consent ledger.

Output (discriminated by auth_family):
  - auth_family: "gongdong_injeungseo" | "geumyung_injeungseo" | "ganpyeon_injeung" | "digital_onepass" | "mobile_id" | "mydata"
  - The LLM uses auth_family to determine the resulting auth level (AAL1/AAL2/AAL3)
    and to decide subsequent calls (e.g., "now I have AAL2, I can call this submit adapter")

Rules:
- verify NEVER mints credentials — it requests a scope-bound DelegationContext.
- Always pass non-empty params.scope_list, purpose_ko, and purpose_en. Never call verify with params={}.
- Pass the returned DelegationContext into every downstream lookup/submit that requires delegation.
- Do NOT store or log credential values in params.`
