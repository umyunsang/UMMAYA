# Data Model: Live MobileID Check Adapter

## Entity: LiveMobileIdCheckInput

Represents the public input accepted by `live_verify_mobile_id`.

| Field | Type | Rules |
|-------|------|-------|
| `trxcode` | `str` | Required, trimmed, non-empty transaction reference. |
| `id_type` | `"mdl" \| "resident"` | Defaults to `mdl`; `resident` is honored only when verified upstream metadata corroborates the resident credential type. |
| `vp` | `LiveMobileIdVpInput \| null` | Optional encrypted VP presentation metadata for `/mip/vp`. If omitted, v1 can still perform transaction-status verification when the operator daemon has already processed VP evidence. |
| `timeout_seconds` | `float \| null` | Optional bounded HTTP timeout override for tests/operators; must remain positive and small. |

## Entity: LiveMobileIdVpInput

Represents the sanitized structure sent inside the `/mip/vp` inner request. The encrypted `data` value is accepted only for transport and must never be returned or persisted.

| Field | Type | Rules |
|-------|------|-------|
| `presentType` | `str` | Required. |
| `encryptType` | `str` | Required. |
| `keyType` | `str` | Required. |
| `authType` | `str` | Required. |
| `did` | `str` | Required. |
| `nonce` | `str \| null` | Required unless `zkpNonce` is present. |
| `zkpNonce` | `str \| null` | Required unless `nonce` is present. |
| `type` | `str` | Must be `verify`. |
| `data` | `str` | Required encrypted VP payload. Redacted from output/logs. |

## Entity: MipEnvelope

The MobileID verification daemon wire envelope.

| Field | Type | Rules |
|-------|------|-------|
| `data` | `str` | Base64-encoded UTF-8 JSON object. |

Encoding rules:

1. Serialize the inner JSON object with deterministic separators.
2. Encode UTF-8 bytes with standard base64.
3. Send `{"data": "<encoded>"}` with `Content-Type: application/json; charset=utf-8`.

Decoding rules:

1. Outer body must be a JSON object with a string `data` field.
2. `data` must be valid base64.
3. Decoded bytes must be valid UTF-8 JSON.
4. Decoded JSON must be an object.

## Entity: MobileIdVpStatus

The normalized status derived from `/mip/vp` and `/mip/trxsts`.

| Field | Type | Rules |
|-------|------|-------|
| `trxcode` | `str` | Echoed transaction code, if supplied by upstream. |
| `verified` | `bool` | True only when status and VP result indicate successful verification. |
| `status_code` | `str \| null` | Sanitized upstream transaction/status code. |
| `message` | `str \| null` | Sanitized diagnostic string; no identity data. |
| `credential_type_evidence` | `mdl`, `resident`, or `null` | Optional daemon/operator metadata such as `credentialType` or `idType`. Required before returning `mobile_id_resident_aal2`. |

## Entity: MobileIdContext

The output uses the existing `src/ummaya/primitives/verify.py` model.

| Field | Value |
|-------|-------|
| `family` | `mobile_id` |
| `published_tier` | `mobile_id_mdl_aal2` or `mobile_id_resident_aal2` |
| `nist_aal_hint` | `AAL2` |
| `verified_at` | Current UTC timestamp |
| `external_session_ref` | Opaque reference derived from `trxcode`, never raw VP data |
| `id_type` | `mdl` or `resident` |

## Redaction Set

The client and docs treat these keys as identity-bearing even in nested fixtures:

- `vp`
- `data`
- `ci`
- `di`
- `rrn`
- `residentRegistrationNumber`
- `jumin`
- `phone`
- `phoneNumber`
- `receiverHP`
- `birth`
- `birthDate`
- `birthdate`
- `name`

Values under these keys must not appear in adapter output, committed fixtures, logs, or snapshots.
