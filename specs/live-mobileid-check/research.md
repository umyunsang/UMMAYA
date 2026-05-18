# Research: Live MobileID Check Adapter

## Decision 1: Use a dedicated live adapter under `src/ummaya/tools/live/`

**Decision**: Add `src/ummaya/tools/live/mobileid_client.py` and `src/ummaya/tools/live/verify_mobile_id.py`.

**Rationale**: Existing MobileID files under `src/ummaya/tools/mock/` are fixture-backed scaffolding. The live adapter needs env-gated HTTP, envelope decode/encode, redaction, and live-test boundaries that should not be mixed into mock modules.

**Alternatives considered**:

- Extend `mock_verify_mobile_id.py`: rejected because it risks changing mock semantics and makes source mode ambiguous.
- Put the client under a generic identity package: rejected because BaroCert and KB have separate contracts and credentials in separate worktrees.

## Decision 2: Keep v1 output compatible with `MobileIdContext`

**Decision**: Return `MobileIdContext` with `family="mobile_id"`, `published_tier`, `nist_aal_hint`, `verified_at`, `external_session_ref`, and `id_type`.

**Rationale**: The current verify primitive already has a typed MobileID context and downstream check consumers understand the `AuthContext` union. No new context member is required for v1 because raw VP and decrypted identity attributes are explicitly out of scope.

**Alternatives considered**:

- Return `ModidContext`: rejected because the official public pages do not define a downstream delegation-token exchange.
- Add a new context union member: rejected for v1 because it would widen shared schema surface without new safe fields.

## Decision 3: Dispatch live and mock MobileID by selected tool id, not only family

**Decision**: Extend verify adapter registration with an optional `tool_id`, and pass the selected check tool id into `session_context` from the stdio path.

**Rationale**: `mock_verify_mobile_id` and `live_verify_mobile_id` both belong to `family="mobile_id"`. A family-only adapter registry cannot keep both callable without one overwriting the other. Tool-id-specific dispatch preserves existing mock behavior and allows explicit live selection.

**Alternatives considered**:

- Register the live adapter under a fake family: rejected because it would make the returned `MobileIdContext.family` mismatch the selected family.
- Make `live_verify_mobile_id` a discovery-only alias for `mobile_id`: rejected because default mock dispatch could accidentally satisfy a live selection.

## Decision 4: Use fixture-first TDD and opt-in live tests

**Decision**: Unit and integration tests use synthetic/sanitized fixture data only. The live test is marked `@pytest.mark.live` and skips unless `UMMAYA_MOBILEID_BASE_URL`, `UMMAYA_MOBILEID_CLIENT_ID`, and `UMMAYA_MOBILEID_TEST_TRXCODE` are present.

**Rationale**: Identity endpoints require approvals, private service credentials, and real transaction contexts. CI must not call them.

**Alternatives considered**:

- Record cassettes from real MobileID transactions: rejected because identity payloads are too sensitive for replay artifacts.
- Make live tests fail when env is absent: rejected because the default suite must be credential-free and callable by CI.

## Decision 5: Treat all unexpected upstream states as fail-closed

**Decision**: Missing `trxcode`, malformed envelope data, non-JSON inner payload, non-2xx responses, explicit upstream failure, and expired/non-complete transaction states raise sanitized adapter errors instead of returning a context.

**Rationale**: Identity confidence cannot be inferred from partial or ambiguous upstream responses. Fail-closed behavior matches UMMAYA's PIPA and permission-pipeline posture in `docs/vision.md`.

**Alternatives considered**:

- Return a partially verified context with `status="pending"`: rejected because `AuthContext` currently means verified success.
- Fall back to `mock_verify_mobile_id`: rejected because live selection must never fabricate a verified live result.

## Official Contract Notes

- Start endpoints are documented for ceremony initiation: `/qrmpm/start`, `/qrcpm/start`, `/app2app/start`, and `/push/start`.
- v1 verification/status scope uses `/mip/vp` and `/mip/trxsts`.
- Request and response bodies use an outer JSON object with base64-encoded inner JSON under `data`.
- `/mip/vp` inner request includes `type`, `version`, `cmd=400`, `request=presentation`, `trxcode`, and a `vp` object with presentation metadata and encrypted VP data.
- Default request content type is `application/json; charset=utf-8`.
