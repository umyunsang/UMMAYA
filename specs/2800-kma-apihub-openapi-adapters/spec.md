# Feature Specification: KMA APIHub OpenAPI Adapters

**Feature Branch**: `[2800-kma-apihub-openapi-adapters]`
**Created**: 2026-05-24
**Status**: Draft
**Originating Epic**: #3000
**Input**: User description: "Wrap every OpenAPI currently served by apihub.kma.go.kr into UMMAYA project adapters after directly verifying the currently open Chrome APIHub site with Computer Use."

## Source Grounding

- `docs/vision.md` — UMMAYA thesis and reference-material rule; KMA APIHub is the agency-owned credential boundary for KMA APIs.
- `docs/requirements/ummaya-migration-tree.md` — L1-B tool system and L1-C primitive surface requirements.
- `.references/claude-code-sourcemap/restored-src/` — Claude Code tool definition, registry, and execution-loop source of truth.
- `docs/api/kma/apihub-openapi-inventory.md` — local KMA APIHub structured OpenAPI inventory.
- KMA APIHub official pages verified on 2026-05-24 through the user's logged-in Chrome tab and public category pages.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Complete KMA Catalog Coverage (Priority: P1)

As a UMMAYA maintainer, I need the KMA APIHub structured OpenAPI catalog represented completely, so that every KMA read-only public weather data module can be discovered and tracked from one source of truth.

**Why this priority**: Without complete catalog coverage, adapter work proceeds by memory or one-off fixes and cannot satisfy the user's request for "all OpenAPI" wrapping.

**Independent Test**: Compare UMMAYA's KMA APIHub catalog against the official APIHub category pages and confirm that every structured OpenAPI operation has exactly one UMMAYA candidate entry with its category, service, operation, usage state, and citation.

**Acceptance Scenarios**:

1. **Given** the official APIHub category pages, **When** the KMA catalog is validated, **Then** all 85 structured `typ02/openApi` operations are accounted for.
2. **Given** an APIHub operation in the official catalog, **When** a maintainer searches the UMMAYA catalog, **Then** the corresponding candidate entry identifies its official category and usage-approval state.

---

### User Story 2 - Safe Citizen Weather Lookup Expansion (Priority: P2)

As a citizen using UMMAYA, I need KMA data tools to behave consistently across approved KMA APIHub modules, so that weather, observation, aviation, marine, typhoon, earthquake, radar, satellite, and model requests either return agency data or fail closed with a clear official-source reason.

**Why this priority**: The project already uses KMA weather tools in real conversations; expanding coverage must not regress the existing weather flow or fabricate data when authorization is missing.

**Independent Test**: For an approved KMA APIHub operation, execute a normal lookup and verify that the response is agency-derived. For an unapproved operation, verify that the user receives an authorization-pending or configuration failure without fallback fabrication.

**Acceptance Scenarios**:

1. **Given** a KMA APIHub operation with active utilization approval, **When** the user asks a matching weather question, **Then** UMMAYA can call the relevant read-only adapter and return a cited agency result.
2. **Given** a KMA APIHub operation without utilization approval, **When** the user asks a matching question, **Then** UMMAYA reports that the agency call is not currently authorized and does not substitute uncited data.

---

### User Story 3 - Approval-Aware Adapter Operations (Priority: P3)

As a maintainer operating API credentials, I need KMA APIHub key issuance and per-API utilization approval tracked separately, so that a key being present does not imply that every APIHub operation is live-callable.

**Why this priority**: The user has confirmed only a subset of APIHub applications are approved. Treating a single key as universal access would create misleading live-adapter claims.

**Independent Test**: Review the approval matrix and confirm that approved, authorization-pending, and out-of-scope operations are distinguishable without exposing the API key or user account details.

**Acceptance Scenarios**:

1. **Given** the APIHub My Page approval list, **When** the KMA catalog is audited, **Then** approved operations are marked separately from operations that exist in the catalog but still need utilization approval.
2. **Given** a missing or empty KMA APIHub credential, **When** any KMA APIHub adapter is invoked, **Then** the adapter fails closed with the required `UMMAYA_` environment variable name and no secret leakage.

### Edge Cases

- KMA APIHub exposes non-structured sample URLs such as `typ01/url`, `typ03`, `typ05`, `typ06`, and `typ09`; these must not be treated as structured OpenAPI adapters in this feature.
- KMA APIHub may show an endpoint in the public catalog while rejecting live calls until a per-API utilization application is approved.
- APIHub responses may be XML by default, JSON when requested, or non-JSON error HTML for authorization failures.
- Some official pages expose duplicate service names across categories; the UMMAYA tool identity must remain stable and unambiguous.
- Existing KMA weather tools must continue to answer current-weather and forecast requests without changing the citizen-facing behavior that already works.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST account for every structured `typ02/openApi` operation exposed by the official KMA APIHub category pages verified for this feature.
- **FR-002**: The system MUST represent each structured operation as a distinct UMMAYA tool candidate with official category, service name, operation name, sample URL, request parameters, response fields when available, and source citation.
- **FR-003**: The system MUST preserve the current KMA forecast and observation behavior for the already-working citizen weather flow.
- **FR-004**: The system MUST use the KMA APIHub credential boundary for KMA APIHub operations and MUST NOT silently fall back to data.go.kr credentials for APIHub endpoints.
- **FR-005**: The system MUST distinguish API key presence from per-operation utilization approval.
- **FR-006**: The system MUST fail closed for missing credentials, authorization rejection, unsupported response shape, and upstream agency errors.
- **FR-007**: The system MUST avoid committing API keys, account details, or logged-in APIHub My Page personal information.
- **FR-008**: The system MUST not call live KMA, data.go.kr, or other citizen-infrastructure APIs from default CI tests.
- **FR-009**: The system MUST preserve UMMAYA's primitive surface by exposing KMA read-only operations through the existing read-only discovery and invocation path.
- **FR-010**: The system MUST record which KMA APIHub operations are live-approved now, live-capable but approval-pending, or outside this feature's structured OpenAPI scope.
- **FR-011**: The system MUST provide fixture-backed tests for representative success and error shapes without requiring live agency calls.
- **FR-012**: The system MUST keep user-visible and source text in English except Korean domain names and official Korean field labels.

### Key Entities *(include if feature involves data)*

- **APIHub Category**: A top-level KMA APIHub category such as ground observation, marine observation, radar, satellite, forecast/warning, aviation weather, or world weather.
- **APIHub Operation**: One structured `typ02/openApi/<service>/<operation>` entry exposed by KMA APIHub, including its official sample URL and parameter tables.
- **Adapter Contract**: The UMMAYA representation of an APIHub operation, including input fields, output fields, credential requirements, policy citation, primitive, and live/mock state.
- **Usage Approval State**: The current operational status of an APIHub operation for the user's APIHub account: approved, authorization pending, or outside structured scope.
- **Credential Boundary**: The `authKey`-based KMA APIHub credential surface, stored only through the configured `UMMAYA_` environment variable path.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the 85 verified structured KMA APIHub `typ02/openApi` operations are represented in the UMMAYA catalog or explicitly marked out of scope with a reason.
- **SC-002**: 100% of existing KMA forecast and current-observation regression tests continue to pass after the catalog expansion.
- **SC-003**: Every executable KMA APIHub adapter has at least one fixture-backed success or agency-error test and one credential/authorization failure test.
- **SC-004**: No default CI job performs a live call to KMA APIHub, data.go.kr, or other citizen-infrastructure APIs.
- **SC-005**: A maintainer can audit approved versus approval-pending KMA APIHub operations from a single repository artifact without exposing secrets.
- **SC-006**: Existing citizen weather prompts that already succeed continue to produce a single non-duplicated answer with tool output grounded in KMA APIHub data.

## Assumptions

- The current feature scope is the structured `typ02/openApi` catalog only, because it shares a common APIHub envelope and credential parameter.
- The official KMA APIHub catalog verified on 2026-05-24 is the baseline for this feature.
- The user's current APIHub account has only a subset of operations approved; unapproved operations can be cataloged and shaped but must not be claimed as live-working until approved.
- Current KMA current-weather and forecast adapters remain the compatibility baseline.
- Read-only weather data has no citizen submission side effect, but it still requires official-source citation and fail-closed behavior.

## Scope Boundaries & Deferred Items *(mandatory)*

### Out of Scope (Permanent)

- Changing KMA APIHub, KMA account approvals, or agency data contracts — UMMAYA is only a client-side caller.
- Storing or publishing the user's APIHub account details, API key, phone number, or email — secrets and personal data remain outside repository artifacts.

### Deferred to Future Work

| Item | Reason for Deferral | Target Epic/Phase | Tracking Issue |
|------|---------------------|-------------------|----------------|
| `typ01/url`, `typ03`, `typ05`, `typ06`, and `typ09` APIHub sample URL families | These endpoints do not share the structured `typ02/openApi` envelope and need separate contracts for text, image, binary, and special response shapes | KMA non-structured APIHub adapters | #3037 |
| `specialApiList.do` 산업특화 sample URLs | The verified page exposes only `typ01` samples, not structured `typ02/openApi` operations | KMA non-structured APIHub adapters | #3038 |
| Live validation for every unapproved APIHub operation | APIHub utilization approval is per operation and cannot be bypassed by a key alone | KMA APIHub approval expansion | #3039 |
