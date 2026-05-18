# Feature Specification: Live MobileID Check Adapter

**Feature Branch**: `feat/live-mobileid-check`  
**Created**: 2026-05-18  
**Status**: Draft  
**Originating Epic**: #2886  
**Input**: User description: "Implement one worktree from the identity Live Check 1/2/3 plan; choose the MobileID verification daemon worktree first."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Verify MobileID Presentation Without Persisting Raw Identity Data (Priority: P1)

A citizen or operator has already completed a MobileID ceremony that produced a verification-daemon transaction reference, and UMMAYA can confirm the transaction through a live `check` adapter without storing the raw VP, resident identifier, phone number, CI, DI, or unredacted identity attributes.

**Why this priority**: The feature exists to turn official MobileID VP verification into a typed UMMAYA authentication context. If the result leaks raw identity data, the adapter violates the core PIPA boundary.

**Independent Test**: Can be tested with sanitized `/mip/vp` and `/mip/trxsts` fixtures that prove the adapter returns only `MobileIdContext`-compatible fields and an opaque external session reference.

**Acceptance Scenarios**:

1. **Given** a sanitized successful VP verification response from the verification daemon, **When** UMMAYA runs the live MobileID check adapter, **Then** it returns a verified MobileID context with `published_tier`, `nist_aal_hint`, `verified_at`, `id_type`, and `external_session_ref`.
2. **Given** the upstream response includes VP data or post-processing identity fields, **When** UMMAYA builds the adapter output, **Then** raw VP data, CI, DI, resident identifiers, phone numbers, and birthdate-like identity attributes are excluded.
3. **Given** no MobileID credentials or transaction reference are configured, **When** default tests run, **Then** no live MobileID endpoint is called.

---

### User Story 2 - Expose MobileID As An Explicit `check` Adapter (Priority: P1)

A maintainer or LLM-mediated flow can discover and select the new live MobileID adapter explicitly by tool id, while existing mock MobileID and mock `modid` delegation behavior remains unchanged.

**Why this priority**: UMMAYA's active surface keeps identity verification under `check`; this feature must not alter `find`, `locate`, `send`, or the mock delegation chain.

**Independent Test**: Can be tested by building the registry and confirming the live tool id is discoverable under the `check` primitive, while existing mock verify adapter outputs remain byte-shape compatible.

**Acceptance Scenarios**:

1. **Given** the adapter registry is built, **When** the live MobileID adapter is inspected, **Then** it is registered as `check` only and is not exposed under `find`, `locate`, or `send`.
2. **Given** existing tests call `mock_verify_mobile_id` or `mock_verify_module_modid`, **When** this feature is enabled, **Then** those mock adapters behave exactly as before.
3. **Given** a Government24 submit chain consumes a mock delegation context, **When** this live check adapter succeeds, **Then** no new live `send:*` delegation token is minted by this feature.

---

### User Story 3 - Fail Closed On Invalid, Expired, Or Malformed MobileID Evidence (Priority: P2)

When the transaction code is missing, the MobileID envelope is malformed, the upstream rejects the request, or the transaction is expired, UMMAYA returns a structured check failure rather than falling back to a mock, retrying unsafe identity data, or fabricating a verified session.

**Why this priority**: Identity checks are security-sensitive. A partial or ambiguous response must never be interpreted as a valid MobileID session.

**Independent Test**: Can be tested with fixture-only negative cases for missing `trxcode`, malformed base64 envelopes, upstream non-2xx responses, failed VP verification, and expired transaction status.

**Acceptance Scenarios**:

1. **Given** the request lacks a transaction code, **When** the adapter validates input, **Then** it fails before making an HTTP call.
2. **Given** the verification daemon returns malformed or non-JSON base64 data, **When** the client decodes the envelope, **Then** it returns a fail-closed check error with a sanitized message.
3. **Given** `/mip/trxsts` reports an expired or non-complete transaction, **When** UMMAYA evaluates the result, **Then** the adapter does not return a verified context.

---

### User Story 4 - Record Live Readiness Evidence Separately From CI (Priority: P2)

A maintainer can prove the live adapter is ready using sanitized direct-call evidence and opt-in live tests, while normal CI and default local test runs remain fixture-only.

**Why this priority**: Official identity endpoints may require service approval, private credentials, and real transactions. CI must never exercise them.

**Independent Test**: Can be tested by running the default suite without MobileID credentials and confirming live tests are deselected or skipped, then running explicit `-m live` tests only in a credentialed local environment.

**Acceptance Scenarios**:

1. **Given** default `uv run pytest` or `uv run pytest -m "not live"` runs, **When** this feature is present, **Then** no request is sent to `dev.mobileid.go.kr` or an operator MobileID daemon.
2. **Given** `UMMAYA_MOBILEID_BASE_URL`, `UMMAYA_MOBILEID_CLIENT_ID`, and `UMMAYA_MOBILEID_TEST_TRXCODE` are configured, **When** the live test is explicitly selected, **Then** it validates a sanitized transaction without exposing raw identity payloads.
3. **Given** a maintainer claims live readiness, **When** they open the feature docs, **Then** sanitized curl evidence and credential names are documented separately from fixture tests.

### Edge Cases

- The request contains an empty, whitespace-only, or syntactically invalid transaction code.
- The envelope body is not an object, lacks `data`, or contains non-base64 text.
- The decoded inner body is not JSON or lacks required MobileID fields.
- `/mip/vp` returns `result=false` or an HTTP status outside 2xx.
- `/mip/trxsts` returns a transaction that is not VP verification complete.
- The upstream includes identity-bearing fields in post-processing data that must be redacted.
- The operator daemon base URL is configured but one or more credential variables are missing.
- A live test is selected in CI by mistake.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST add one explicitly selectable live MobileID check adapter with tool id `live_verify_mobile_id`.
- **FR-002**: System MUST register `live_verify_mobile_id` under the active `check` primitive only.
- **FR-003**: System MUST keep existing `mock_verify_mobile_id` behavior unchanged.
- **FR-004**: System MUST keep existing `mock_verify_module_modid` delegation-token behavior unchanged; live MobileID v1 does not mint downstream `send:*` delegation tokens.
- **FR-005**: System MUST wrap the official MobileID verification daemon message envelope where request and response bodies carry `data` as base64-encoded inner JSON.
- **FR-006**: System MUST support the official MobileID verification endpoints needed for v1 status and verification checks: `/mip/vp` and `/mip/trxsts`.
- **FR-007**: System MUST document the official start endpoints `/qrmpm/start`, `/qrcpm/start`, `/app2app/start`, and `/push/start` as upstream ceremony entry points, even if v1 does not initiate all ceremony modes.
- **FR-008**: System MUST use `Content-Type: application/json; charset=utf-8` for MobileID verification daemon requests.
- **FR-009**: System MUST require a transaction code before calling `/mip/vp` or `/mip/trxsts`.
- **FR-010**: System MUST validate that the `/mip/vp` request shape includes `type`, `version`, `cmd=400`, `request=presentation`, `trxcode`, and a `vp` object with the documented presentation metadata.
- **FR-011**: System MUST return a typed MobileID context compatible with existing UMMAYA verify consumers: `family="mobile_id"`, `published_tier`, `nist_aal_hint`, `verified_at`, `external_session_ref`, and `id_type`.
- **FR-011a**: System MUST fail closed before issuing `mobile_id_resident_aal2` unless the verified upstream response includes corroborating credential-type evidence for a resident MobileID. Caller-supplied `id_type="resident"` alone is insufficient.
- **FR-012**: System MUST NOT return or persist raw VP payloads, CI, DI, resident identifiers, phone numbers, birthdate-like identity attributes, or full decrypted identity result data.
- **FR-013**: System MUST return fail-closed structured errors for missing `trxcode`, malformed base64, malformed inner JSON, upstream non-2xx, upstream `result=false`, expired transaction, and unsupported transaction status.
- **FR-014**: System MUST keep all default tests fixture-backed and free of live MobileID, government, identity, payment, or citizen-infrastructure calls.
- **FR-015**: System MUST mark live MobileID tests with `@pytest.mark.live` and require explicit `UMMAYA_MOBILEID_*` credentials before calling a real daemon.
- **FR-016**: System MUST redact credential headers, transaction metadata beyond the opaque external reference, and identity-bearing fields from logs, snapshots, docs, and test fixtures.
- **FR-017**: System MUST add documentation under `docs/api/verify/` covering official source URLs, env credential names, request/response envelope, failure behavior, live-test gating, and non-persistence rules.
- **FR-018**: System MUST cite the MobileID development support center verification daemon API definition and use-procedure pages as primary public references.

### Official Source Contract

| Area | Required Contract |
|------|-------------------|
| API list | Official verification daemon lists `/qrmpm/start`, `/qrcpm/start`, `/app2app/start`, `/push/start`, `/mip/profile`, `/mip/image`, `/mip/vp`, `/mip/error`, `/mip/trxsts`, and `/mip/revp`. |
| Envelope | Official daemon messages are JSON and are transmitted as base64-encoded data. |
| VP verification | `/mip/vp` is a POST endpoint for VP verification and requires `Content-Type: application/json; charset=utf-8`. |
| VP request fields | `/mip/vp` inner request includes `type=mip`, `version=1.0.0`, `cmd=400`, `request=presentation`, `trxcode`, and `vp` metadata such as `presentType`, `encryptType`, `keyType`, `authType`, `did`, `nonce` or `zkpNonce`, `type=verify`, and encrypted `data`. |
| Transaction status | `/mip/trxsts` returns transaction state including verification result and status code fields. |
| Use procedure | The MobileID development support center describes service application, approval review, terms and privacy confirmation, and additional review for unique identifier collection. |

Primary references:

- `https://dev.mobileid.go.kr/mip/dfs/useguide/mdGuide.do?guide=demonapiguide`
- `https://dev.mobileid.go.kr/mip/dfs/apiuse/apiusestep.do`

### Key Entities *(include if feature involves data)*

- **MobileID Transaction Reference**: The opaque transaction code or session reference used to query VP verification and transaction status.
- **MIP Envelope**: The outer JSON object containing a base64-encoded inner JSON document under `data`.
- **VP Verification Request**: The MobileID `/mip/vp` request payload containing the transaction code and VP metadata. Raw VP `data` is never persisted by UMMAYA.
- **VP Verification Result**: The upstream success, failure, or transaction status signal used to decide whether a `MobileIdContext` can be returned.
- **MobileID Auth Context**: The UMMAYA-safe typed result consumed by downstream mock or live flows without exposing raw identity data.
- **Sanitized Live Evidence**: Operator-captured curl/test proof that redacts credentials and identity-bearing fields before docs or fixtures are committed.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Default `uv run pytest -m "not live"` performs zero live MobileID calls.
- **SC-002**: `uv run pytest tests/...mobileid... -m "not live"` passes using only synthetic or sanitized fixtures.
- **SC-003**: The registry exposes `live_verify_mobile_id` under `check` and does not expose it under `find`, `locate`, or `send`.
- **SC-004**: 100% of MobileID unit fixtures contain no raw resident identifier, phone number, CI, DI, or full VP data.
- **SC-005**: Negative tests cover missing `trxcode`, malformed base64, upstream non-2xx, upstream `result=false`, and expired transaction behavior.
- **SC-006**: Live tests are skipped or fail before network access unless all required `UMMAYA_MOBILEID_*` env vars are present.
- **SC-007**: The adapter docs include official endpoints, credential names, request parameters, response shape, live-test command, and redaction rules.

## Assumptions

- The operator already has or can deploy an approved MobileID verification daemon; UMMAYA does not host or issue the MobileID credential.
- v1 receives an existing transaction reference rather than initiating every ceremony mode.
- `MobileIdContext` is sufficient for v1 unless planning proves that `ModidContext` is required for compatibility; any `verify.py` change must be additive and narrowly scoped.
- `id_type` can default to `mdl`; `resident` requires corroborating credential-type metadata from the verified upstream response before the adapter may return the resident published tier.
- `UMMAYA_MOBILEID_BASE_URL`, `UMMAYA_MOBILEID_CLIENT_ID`, and `UMMAYA_MOBILEID_TEST_TRXCODE` are the initial live-test env names; planning may add a secret or service-code variable if the official or operator daemon requires it.
- Sanitized direct curl evidence is required before claiming live readiness, but not before writing fixture-only unit tests.

## Scope Boundaries & Deferred Items *(mandatory)*

### Out of Scope (Permanent)

- Government24 submit live implementation; no public submit API is available in this feature's source set.
- BaroCert Toss/Kakao/Naver 간편인증 live check; that is a separate worktree and Epic.
- KB국민인증서 live check; that is a separate worktree and Epic.
- Storing raw VP, CI, DI, resident identifiers, phone numbers, or decrypted identity attributes in UMMAYA state, logs, fixtures, or docs.
- Replacing the active primitive surface or modifying `find`, `locate`, or `send` behavior.

### Deferred to Future Work

| Item | Reason for Deferral | Target Epic/Phase | Tracking Issue |
|------|---------------------|-------------------|----------------|
| Live MobileID-to-`send:*` delegation token exchange | The provided public MobileID pages define verification daemon messages but do not define an official delegation-token exchange contract for downstream UMMAYA `send` adapters. | Future MobileID delegation design | NEEDS TRACKING |
| Starting every MobileID ceremony mode from UMMAYA | v1 focuses on verification/status around an existing transaction reference; full QR/App2App/Push orchestration depends on operator daemon deployment details and user experience decisions. | MobileID ceremony orchestration follow-up | NEEDS TRACKING |
| Sanitized real curl evidence artifact | Must be captured in a credentialed operator environment after fixture-only implementation proves the contract. | Live readiness evidence task | NEEDS TRACKING |
