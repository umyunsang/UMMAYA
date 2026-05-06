// SPDX-License-Identifier: Apache-2.0
// Epic γ #2294 · T003 · primitive citation helper.
//
// KOSMOS does not invent permission language. Every primitive call routed to
// an adapter MUST surface the agency's published policy URL + authority
// verbatim. This helper centralises the extraction so the 4 primitives stay
// uniform and the boot guard (T004) can verify presence in one place.

/**
 * Numeric error codes returned in `ValidationResult.errorCode` from each
 * primitive's `validateInput`. Matches the `Tool<>` contract at
 * `tui/src/Tool.ts:489` (which expects a numeric `errorCode`).
 */
export const PrimitiveErrorCode = {
  AdapterNotFound: 1001,
  CitationMissing: 1002,
  RestrictedMode: 1003,
  InvalidParams: 1004,
} as const

export type PrimitiveErrorCode =
  (typeof PrimitiveErrorCode)[keyof typeof PrimitiveErrorCode]

/**
 * Adapter citation pulled from the backend `AdapterRealDomainPolicy`
 * (Spec 2295 commit `c6747dd`). Both fields are non-empty by the boot-guard
 * invariant — primitives MUST treat empty as a hard failure.
 */
export type AdapterCitation = {
  real_classification_url: string
  policy_authority: string
}

/**
 * Shape the primitives expect on the resolved adapter object. Only the
 * citation block is read — the rest of the adapter metadata is opaque to the
 * primitive layer.
 */
export type AdapterWithPolicy = {
  name: string
  real_domain_policy?: {
    real_classification_url?: string
    policy_authority?: string
  }
}

/**
 * Extract the verbatim citation strings from an adapter's
 * `AdapterRealDomainPolicy` metadata.
 *
 * Returns `null` when either citation field is empty — the caller MUST fail
 * closed and surface `PrimitiveErrorCode.CitationMissing`. KOSMOS never
 * fabricates a citation.
 */
export function extractCitation(
  adapter: AdapterWithPolicy,
): AdapterCitation | null {
  const url = adapter.real_domain_policy?.real_classification_url
  const authority = adapter.real_domain_policy?.policy_authority
  if (!url || !authority) {
    return null
  }
  return {
    real_classification_url: url,
    policy_authority: authority,
  }
}
