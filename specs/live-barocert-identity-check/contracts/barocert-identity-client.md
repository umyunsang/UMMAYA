# Contract: BaroCert Identity Client

## Purpose

Defines the internal UMMAYA client boundary for BaroCert simple identity checks.
The contract is provider-aware, fixture-testable, and redaction-first.

## Provider Operations

### `request_identity(request: BarocertIdentityRequest) -> BarocertIdentityReceipt`

Starts a provider identity request.

Rules:
- Requires encrypted receiver fields and encrypted token placeholders.
- Does not accept raw phone, name, birthday, CI, or DI.
- For Toss live execution, calls the official `requestUserIdentity` SDK method.
- Returns only receipt metadata.

### `get_identity_status(provider: BarocertProvider, client_code: str, receipt_id: str) -> BarocertIdentityStatus`

Reads provider status for an existing receipt.

Rules:
- Requires non-empty `receipt_id`.
- For Toss live execution, calls the official `getUserIdentityStatus` SDK method.
- Maps provider state codes into normalized states.
- Non-complete states do not produce auth contexts.

### `verify_identity(provider: BarocertProvider, client_code: str, receipt_id: str) -> BarocertIdentityVerification`

Verifies a completed provider receipt.

Rules:
- Requires non-empty `receipt_id`.
- For Toss live execution, calls the official `verifyUserIdentity` SDK method.
- Provider result values such as `signedData`, `ci`, and `di` are reduced to
  evidence-present booleans.
- Repeated verify and provider exception paths produce sanitized fail-closed
  errors.

## Adapter Operation

### `invoke(session_context: dict[str, object]) -> GanpyeonInjeungContext | VerifyMismatchError`

Dispatches from the check primitive.

Required session context:
- `_tool_id` or `tool_id`: must be `live_verify_ganpyeon_injeung` for live path.
- `provider`: defaults to `toss` for v1 live path.
- `receiptID` or `receipt_id`: required for status/verify path.
- `clientCode` or `client_code`: optional override; otherwise read from
  `UMMAYA_BAROCERT_CLIENT_CODE`.

Safe output:
- `GanpyeonInjeungContext(provider="toss", published_tier="ganpyeon_injeung_toss_aal2")`
- `external_session_ref="barocert:toss:<receipt_id>"`

Unsafe fields forbidden in output:
- `ci`
- `di`
- `signedData`
- `receiverHP`
- `receiverName`
- `receiverBirthday`
- `receiverYear`
- `receiverDay`
- `receiverGender`
- `receiverForeign`
- `receiverAgeGroup`
- `receiverEmail`
- `receiverTelcoType`
