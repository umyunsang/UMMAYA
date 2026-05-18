# Feature Specification: Live KB Identity Check Adapter

**Feature Branch**: `feat/live-kbcert-identity-check`
**Created**: 2026-05-18
**Status**: Draft
**Originating Epic**: #2888
**Input**: User description: "KB국민인증서 본인확인 요청/결과조회 API를 감싼 live check adapter를 추가한다. The adapter returns only `certTxId`/`reqTxId` based external session references and never stores encrypted identity attributes."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Start KB Identity Check (Priority: P1)

A citizen-facing flow can explicitly select KB국민인증서 identity verification and receive a KB transaction reference that can be handed to the KB standard window or app journey without exposing personal identity fields to UMMAYA.

**Why this priority**: The request step is the minimum useful integration point. It creates the external KB transaction and returns the opaque reference needed for later result polling.

**Independent Test**: Can be fully tested by replaying sanitized KB request fixtures and by asserting the adapter returns only `reqTxId`, `certTxId`, and optional `callUrl` metadata.

**Acceptance Scenarios**:

1. **Given** KB credentials are configured and a caller provides a synthetic `reqTxId`, **When** the live KB check adapter starts the identity request, **Then** it returns a verified check context with an opaque `external_session_ref` containing only transaction identifiers.
2. **Given** KB credentials are absent, **When** the default test suite runs, **Then** no KB network request is attempted and fixture tests still validate the adapter contract.

---

### User Story 2 - Poll KB Identity Result Safely (Priority: P2)

After the user completes KB국민인증서 in the KB app or standard window, UMMAYA can poll the KB result endpoint and convert successful completion into a check context while dropping CI, DI, name, birthday, gender, nationality, and encrypted identity values.

**Why this priority**: A check adapter is only useful if completion can be recognized, but UMMAYA must not become a repository for identity attributes.

**Independent Test**: Can be fully tested with sanitized request/result JSON fixtures, including fixtures that contain sentinel identity fields and prove they are redacted from outputs and logs.

**Acceptance Scenarios**:

1. **Given** a successful sanitized KB result fixture with `result-code=ok`, **When** the adapter parses the response, **Then** the returned context records only provider, verification timestamp, and opaque external transaction reference.
2. **Given** a failed status, missing `certTxId`, or mismatched `reqTxId`, **When** the adapter parses the response, **Then** it returns a fail-closed check error and does not expose any identity payload fields.

---

### User Story 3 - Discover KB Check as an Explicit Tool (Priority: P3)

The tool registry exposes KB국민인증서 as a `check`-only live adapter that can be selected explicitly by tool id without altering BaroCert, MobileID, or existing mock verification behavior.

**Why this priority**: Discovery must make the live adapter available while preserving the existing mock identity chain and avoiding cross-worktree merge conflicts.

**Independent Test**: Can be verified by registry tests that import the live adapter, confirm `live_verify_kb_identity` is discoverable under `check`, and confirm existing mock tool ids keep their current mappings.

**Acceptance Scenarios**:

1. **Given** the registry is built, **When** tools are searched for KB국민인증서 identity verification, **Then** `live_verify_kb_identity` appears as a non-core `check` candidate.
2. **Given** existing BaroCert, MobileID, and mock verify tests run, **When** this feature is present, **Then** their observed behavior remains unchanged.

### Edge Cases

- Missing KB headers or credential environment variables must fail before a network request.
- Missing `certTxId`, missing `reqTxId`, failed KB status, non-object JSON, upstream non-2xx, timeout, and `reqTxId` mismatch must produce fail-closed check errors.
- CI, DI, name, birthday, phone number, gender, nationality, and encrypted identity result values must not appear in returned contexts, logs, fixture snapshots, or documentation examples.
- Default `uv run pytest` and CI runs must not call KB live endpoints.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a live KB국민인증서 identity check adapter with tool id `live_verify_kb_identity`.
- **FR-002**: The adapter MUST bind only to the `check` primitive and MUST NOT alter existing `find`, `locate`, or `send` adapters.
- **FR-003**: The adapter MUST support the KB identity request flow using `companyCd`, caller-generated `reqTxId`, and `requestType`, with KB `apiKey` and `hsKey` headers supplied from `UMMAYA_` environment variables.
- **FR-004**: The adapter MUST support the KB identity result lookup flow using `companyCd`, `reqTxId`, `certTxId`, and `requestType`.
- **FR-005**: The adapter MUST return an `AuthContext`-compatible result that includes `provider="kb"`, `verified_at`, `published_tier`, `nist_aal_hint`, and an opaque `external_session_ref` derived from `reqTxId` and `certTxId`.
- **FR-006**: The adapter MUST NOT return or persist CI, DI, user name, birthday, phone number, gender, nationality, or encrypted identity result fields.
- **FR-007**: The adapter MUST validate KB response status using `dataHeader.resultCode`, `dataHeader.successCode`, and `dataBody.result-code` before reporting success.
- **FR-008**: The adapter MUST fail closed for missing identifiers, failed KB status, mismatched transaction identifiers, malformed payloads, upstream non-2xx responses, and network timeouts.
- **FR-009**: Tests that call real KB endpoints MUST be marked `@pytest.mark.live`, skipped without required `UMMAYA_KBCERT_*` credentials, and excluded from default CI behavior.
- **FR-010**: Fixture and unit tests MUST use synthetic or sanitized payloads only.
- **FR-011**: The adapter documentation MUST cite the official KB pages for the identity flow, common API domain/content-type information, and test procedure, and MUST state that sanitized curl evidence is required before live-readiness claims.
- **FR-012**: BaroCert, MobileID, and existing mock verification adapters MUST remain behaviorally unchanged.

### Key Entities *(include if feature involves data)*

- **KbIdentityRequest**: Caller-side request fields required to open a KB identity transaction: `companyCd`, `reqTxId`, `requestType`.
- **KbIdentityRequestReceipt**: Sanitized KB request response metadata: `reqTxId`, `certTxId`, optional `callUrl`, and normalized status.
- **KbIdentityResultReceipt**: Sanitized KB result lookup metadata: `reqTxId`, `certTxId`, normalized status, and a boolean indicator that KB returned expected identity evidence.
- **KbIdentityContext**: AuthContext-compatible output for UMMAYA that keeps only provider and opaque transaction reference metadata.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `uv run pytest tests/...kb... -m "not live"` passes without KB credentials and without attempting a KB network request.
- **SC-002**: Registry tests confirm `live_verify_kb_identity` is discoverable as `primitive="check"` and no existing mock verify tool id mapping changes.
- **SC-003**: Redaction tests prove sentinel CI, DI, user name, birthday, gender, and nationality fields from KB result fixtures are absent from adapter outputs.
- **SC-004**: Negative tests cover missing `certTxId`, failed KB status, mismatched `reqTxId`, missing credential headers, upstream non-2xx, and timeout behavior.
- **SC-005**: Live tests are skipped by default and execute only when all required `UMMAYA_KBCERT_*` variables are present.

## Assumptions

- The initial KB adapter returns an identity-check context only; it does not issue a downstream delegation token.
- `GanpyeonInjeungContext` compatibility is acceptable if adding a new context variant would create cross-worktree conflicts; otherwise a narrow `KbIdentityContext` may be added additively.
- `requestType="NONE"` is the default request type because KB documents it for the standard input window flow.
- `reqTxId` generation may be caller-supplied or generated by the adapter, but tests use deterministic synthetic values.
- Sanitized curl evidence is a documentation prerequisite for claiming live readiness, but credentialed live evidence is not required for default CI acceptance.

## Scope Boundaries & Deferred Items *(mandatory)*

### Out of Scope (Permanent)

- KB standard window browser automation, app deep-link automation, and user-device interaction automation are excluded from this adapter; KB owns that ceremony.
- Decryption, storage, display, or comparison of KB returned identity attributes is excluded; UMMAYA only records opaque transaction references and verification state.
- BaroCert, MobileID, Government24 submit, and mock adapter behavior changes are excluded from this branch.

### Deferred to Future Work

No items deferred. All requirements for this Epic are addressed in this feature scope.
