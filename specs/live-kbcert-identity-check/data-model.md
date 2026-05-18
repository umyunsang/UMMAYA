# Data Model: Live KB Identity Check Adapter

## KbIdentityCheckInput

Caller-facing `check` params accepted by `live_verify_kb_identity`.

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `reqTxId` | string | no for request mode, yes for result mode | Non-empty synthetic/caller transaction id; generated when omitted in request mode |
| `certTxId` | string | no for request mode, yes for result mode | Non-empty KB transaction id returned by request API |
| `requestType` | string | no | Defaults to `NONE`; non-empty |
| `mode` | string | no | `request`, `result`, or `auto`; defaults to `auto` |

`companyCd`, `apiKey`, `hsKey`, and `base_url` come from environment configuration, not LLM params.

## KbIdentityRequestBody

KB request API body.

```json
{
  "dataHeader": {},
  "dataBody": {
    "companyCd": "TEST0000",
    "reqTxId": "synthetic-req-tx-id",
    "requestType": "NONE"
  }
}
```

Validation:

- `companyCd`, `reqTxId`, and `requestType` must be non-empty strings.
- Headers must include `apiKey` and `hsKey`.

## KbIdentityResultBody

KB result lookup API body.

```json
{
  "dataHeader": {},
  "dataBody": {
    "companyCd": "TEST0000",
    "reqTxId": "synthetic-req-tx-id",
    "certTxId": "synthetic-cert-tx-id",
    "requestType": "NONE"
  }
}
```

Validation:

- `certTxId` is required for result lookup.
- `reqTxId` returned by KB must match the requested `reqTxId` when both are present.

## KbIdentityReceipt

Sanitized receipt metadata.

| Field | Type | Notes |
|-------|------|-------|
| `req_tx_id` | string | Opaque institution transaction id |
| `cert_tx_id` | string | Opaque KB transaction id |
| `call_url` | string or null | Present after request API when KB returns it |
| `result_code` | string | Normalized from KB `result-code` |
| `client_message` | string or null | Sanitized user-facing KB status text |
| `system_message` | string or null | Sanitized KB system status text |
| `identity_evidence_present` | boolean | True when KB result body contained expected identity evidence keys; individual values are dropped |

## KbIdentityContext

AuthContext variant returned by the check primitive.

| Field | Type | Notes |
|-------|------|-------|
| `family` | literal `kb_identity` | Verify dispatcher discriminator |
| `provider` | literal `kb` | Provider marker |
| `published_tier` | literal `kb_identity_aal2` | UMMAYA registry tier label |
| `nist_aal_hint` | literal `AAL2` | Advisory hint |
| `verified_at` | datetime | UTC completion timestamp |
| `external_session_ref` | string | Opaque `kbcert:` reference containing only `reqTxId` and `certTxId` |
| `status` | literal `verified` | Inherited AuthContext success discriminator |

Forbidden fields:

- `CI`
- `DI`
- `userNm`
- `birthday`
- `receiverHP`
- `receiverName`
- `receiverBirthday`
- `gender`
- `krnFrgnDstcd`
- raw KB result payload

## State Transitions

```text
missing credentials -> sanitized VerifyMismatchError
request mode -> request API -> KbIdentityContext with external_session_ref
result mode -> result API -> status validation -> KbIdentityContext
result mode -> failed/malformed response -> sanitized VerifyMismatchError
```
