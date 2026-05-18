# Feature Specification: Live BaroCert Identity Check

**Feature Branch**: `feat/live-barocert-identity-check`
**Created**: 2026-05-18
**Status**: Ready for implementation
**Originating Epic**: #2887
**Input**: Worktree 2 from "신원검증 Live Check 1·2·3 병렬 구현 설계도"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Toss-backed identity check returns a redacted auth context (Priority: P1)

A citizen or operator explicitly selects `live_verify_ganpyeon_injeung` for a
BaroCert Toss 본인확인 ceremony. UMMAYA starts or resumes the provider session,
verifies the provider receipt, and returns a `GanpyeonInjeungContext`-compatible
auth result containing only provider name, external session reference,
verification time, published tier, and AAL hint.

**Why this priority**: This is the MVP value: moving the existing
`mock_verify_ganpyeon_injeung` shape to an explicit live check adapter without
changing mock behavior or leaking identity payloads.

**Independent Test**: Unit tests can replay sanitized Toss request/status/verify
fixtures and assert the resulting context has `provider="toss"`,
`external_session_ref`, `verified_at`, `published_tier`, and `nist_aal_hint`,
with no CI, DI, phone, birthday, name, or signedData in the output.

**Acceptance Scenarios**:

1. **Given** a completed Toss `receiptID`, **When** UMMAYA invokes
   `live_verify_ganpyeon_injeung`, **Then** the result is a verified
   `ganpyeon_injeung` context with `provider="toss"` and only a sanitized
   external session reference.
2. **Given** a Toss response containing CI, DI, encrypted identity attributes,
   or signedData, **When** the adapter parses the response, **Then** those fields
   are used only to decide that expected identity evidence exists and are not
   returned, logged, snapshotted, or persisted.

---

### User Story 2 - Provider client supports fixture-backed Kakao and Naver variants (Priority: P2)

An engineer can exercise the same BaroCert client interface for `toss`, `kakao`,
and `naver` using sanitized fixtures. Toss is the only v1 live priority, but the
client interface must make Kakao and Naver extension work additive rather than a
new architecture.

**Why this priority**: Kakao and Naver share request/status/verify semantics
with different method names and response fields. Capturing that interface now
prevents a Toss-only implementation from hard-coding the wrong boundary.

**Independent Test**: Fixture tests instantiate the provider enum for all three
providers and assert provider-specific method names, request-body validation,
status parsing, and sensitive-field redaction.

**Acceptance Scenarios**:

1. **Given** a provider value of `kakao` or `naver`, **When** fixture replay runs,
   **Then** the client validates required request fields and parses receipt/status
   shapes without any live network call.
2. **Given** a provider mismatch between request and verify metadata, **When** the
   result is parsed, **Then** the adapter fails closed with a structured check
   error instead of coercing it into a successful context.

---

### User Story 3 - Live validation is opt-in and safe by default (Priority: P3)

CI and default local tests must never call BaroCert or transmit identity data.
Live validation runs only when a human explicitly selects live tests and provides
BaroCert credentials and test receipt inputs.

**Why this priority**: Identity providers are high-risk external systems. A
default test run must prove fixture behavior and redaction without touching a
government or identity service.

**Independent Test**: `uv run pytest -m "not live"` completes without BaroCert
network calls. `tests/live/...barocert...` is marked `@pytest.mark.live` and
skips unless all required `UMMAYA_BAROCERT_*` variables are present.

**Acceptance Scenarios**:

1. **Given** no BaroCert environment variables, **When** the default test suite
   runs, **Then** live BaroCert tests are skipped or excluded and no network call
   is attempted.
2. **Given** all live credentials and a sanitized Toss test receipt, **When** a
   human runs the live test marker, **Then** the test validates provider status
   and redaction without printing or storing raw identity values.

### Edge Cases

- Missing `receiptID` must fail closed before provider invocation.
- Expired, rejected, failed, or pending receipts must return a non-verified check
  error and must not produce an auth context.
- Repeated verify calls after provider one-shot or two-shot limits must surface a
  provider error as fail-closed, not as a retry loop.
- Missing encrypted input placeholders for live request start must fail validation.
- Upstream non-2xx responses, SDK exceptions, malformed response objects, provider
  mismatch, and missing required result fields must all produce sanitized errors.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST add a new explicit live check tool id
  `live_verify_ganpyeon_injeung`.
- **FR-002**: System MUST keep existing `mock_verify_ganpyeon_injeung` behavior,
  registration, output shape, and tests unchanged unless docs reference the new
  live alternative.
- **FR-003**: System MUST model a BaroCert provider enum with `toss`, `kakao`,
  and `naver`.
- **FR-004**: System MUST prioritize Toss 본인확인 using
  `requestUserIdentity(clientCode, UserIdentity)`,
  `getUserIdentityStatus(clientCode, receiptID)`, and
  `verifyUserIdentity(clientCode, receiptID)`.
- **FR-005**: System MUST require encrypted placeholders for live identity request
  start inputs: receiver phone, receiver name, receiver birthday, and token.
- **FR-006**: System MUST require `receiptID` before status or verify lookup.
- **FR-007**: System MUST return a `GanpyeonInjeungContext`-compatible result
  with `provider`, `external_session_ref`, `verified_at`, `published_tier`, and
  `nist_aal_hint` when the provider result is complete.
- **FR-008**: System MUST NOT return, log, persist, snapshot, or expose raw CI,
  DI, phone number, birthday, name, signedData, or encrypted identity result
  payloads.
- **FR-009**: System MUST record only sanitized receipt metadata such as provider,
  receipt reference, status code, evidence-present booleans, and timestamps.
- **FR-010**: System MUST register the new live adapter under primitive `check`
  only; it MUST NOT modify `find`, `locate`, or `send` behavior.
- **FR-011**: System MUST map `live_verify_ganpyeon_injeung` to the canonical
  `ganpyeon_injeung` family without changing mock tool-id mapping.
- **FR-012**: System MUST make default tests fixture-only and ensure CI does not
  call BaroCert.
- **FR-013**: System MUST mark live BaroCert tests with `@pytest.mark.live` and
  skip them unless required credentials are present.
- **FR-014**: System MUST document required environment variables:
  `UMMAYA_BAROCERT_LINK_ID`, `UMMAYA_BAROCERT_SECRET_KEY`,
  `UMMAYA_BAROCERT_CLIENT_CODE`, and provider/test receipt variables used by
  live tests.

### Key Entities *(include if feature involves data)*

- **BarocertProvider**: Provider selector with `toss`, `kakao`, and `naver`.
- **BarocertIdentityRequest**: Sanitized request-start input carrying provider,
  client code, encrypted receiver fields, token, expiry, app-to-app options, and
  optional return URL.
- **BarocertIdentityReceipt**: Provider receipt metadata containing provider,
  receipt reference, optional app scheme, and no raw identity attributes.
- **BarocertIdentityStatus**: Provider status metadata normalized to pending,
  complete, expired, rejected, or failed.
- **BarocertIdentityVerification**: Sanitized verification summary recording
  whether identity evidence and signed data were present, without storing those
  values.
- **GanpyeonInjeungContext**: Existing UMMAYA auth context consumed by the
  check/submit chain.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `uv run pytest tests/...barocert... -m "not live"` passes without
  network access.
- **SC-002**: Registry tests prove `live_verify_ganpyeon_injeung` is discoverable
  under primitive `check`.
- **SC-003**: Fixture tests prove CI, DI, phone, birthday, name, signedData, and
  encrypted identity payload fields are redacted from returned models and logs.
- **SC-004**: Negative tests cover missing `receiptID`, expired receipt, repeated
  verify, provider mismatch, missing encrypted placeholders, and upstream error.
- **SC-005**: With credentials and explicit `-m live`, a sanitized Toss live check
  records direct evidence before docs claim live readiness.

## Assumptions

- BaroCert live execution uses the official Python SDK surface when present; the
  adapter fails closed with a configuration error if credentials or SDK runtime
  are missing during a live invocation.
- Toss is the only live-priority provider for v1. Kakao and Naver share the
  client interface but are covered by sanitized fixture replay in this Epic.
- UMMAYA does not decrypt or compare CI/DI inside the harness. It records that
  provider identity evidence was returned and leaves raw identity comparison to
  the upstream relying-party boundary.
- The explicit live tool id and existing mock tool id both resolve to
  `family_hint="ganpyeon_injeung"`; explicit `tool_id` selection determines
  whether the family adapter uses live or mock behavior.

## Scope Boundaries & Deferred Items *(mandatory)*

### Out of Scope (Permanent)

- Government24 submit live integration — no public submission API is available
  for this workstream, and this Epic is check-only.
- Raw resident identifiers, phone numbers, CI/DI, signedData, and full provider
  result storage — prohibited by the feature's privacy boundary.
- Replacing the existing mock adapter — the mock remains a fixture-backed
  reference surface.

### Deferred to Future Work

| Item | Reason for Deferral | Target Epic/Phase | Tracking Issue |
|------|---------------------|-------------------|----------------|
| Full Kakao live identity execution | v1 priority is Toss; Kakao shares interface but needs its own credential and live evidence pass. | BaroCert provider expansion | #2945 |
| Full Naver live identity execution | v1 priority is Toss; Naver has provider-specific statuses and return URL constraints needing separate live evidence. | BaroCert provider expansion | #2946 |
| Provider-side decrypted identity comparison workflow | UMMAYA v1 only records evidence presence and sanitized receipt metadata; comparison policy belongs at relying-party boundary. | Identity evidence policy | #2947 |
