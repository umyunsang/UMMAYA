# Contract: `live_verify_mobile_id`

## Tool Metadata

| Field | Value |
|-------|-------|
| Tool id | `live_verify_mobile_id` |
| Primitive | `check` |
| Family | `mobile_id` |
| Source mode | `live` |
| Public output | Existing `MobileIdContext` |
| Mock compatibility | Does not modify `mock_verify_mobile_id` or `mock_verify_module_modid` |

## Input Schema

```json
{
  "type": "object",
  "required": ["trxcode"],
  "additionalProperties": false,
  "properties": {
    "trxcode": {
      "type": "string",
      "minLength": 1
    },
    "id_type": {
      "type": "string",
      "enum": ["mdl", "resident"],
      "default": "mdl",
      "description": "resident requires corroborating credential-type evidence in the verified upstream response"
    },
    "vp": {
      "type": ["object", "null"],
      "additionalProperties": false,
      "properties": {
        "presentType": {"type": "string"},
        "encryptType": {"type": "string"},
        "keyType": {"type": "string"},
        "authType": {"type": "string"},
        "did": {"type": "string"},
        "nonce": {"type": ["string", "null"]},
        "zkpNonce": {"type": ["string", "null"]},
        "type": {"type": "string", "const": "verify"},
        "data": {"type": "string"}
      }
    },
    "timeout_seconds": {
      "type": ["number", "null"],
      "exclusiveMinimum": 0
    }
  }
}
```

## Official Daemon Requests

### `/mip/vp`

Outer request:

```json
{
  "data": "<base64 encoded inner JSON>"
}
```

Inner request:

```json
{
  "type": "mip",
  "version": "1.0.0",
  "cmd": 400,
  "request": "presentation",
  "trxcode": "TRX-SANITIZED",
  "vp": {
    "presentType": "vp",
    "encryptType": "SANITIZED",
    "keyType": "SANITIZED",
    "authType": "SANITIZED",
    "did": "did:example:sanitized",
    "nonce": "SANITIZED",
    "type": "verify",
    "data": "REDACTED"
  }
}
```

### `/mip/trxsts`

Outer request:

```json
{
  "data": "<base64 encoded inner JSON>"
}
```

Inner request:

```json
{
  "trxcode": "TRX-SANITIZED"
}
```

## Output Schema

Success returns the existing `MobileIdContext` shape:

```json
{
  "status": "verified",
  "family": "mobile_id",
  "published_tier": "mobile_id_mdl_aal2",
  "nist_aal_hint": "AAL2",
  "verified_at": "2026-05-18T00:00:00Z",
  "external_session_ref": "mobileid:TRX-SANITIZED",
  "id_type": "mdl"
}
```

## Failure Contract

The adapter fails closed for:

- missing or blank `trxcode`
- malformed outer envelope
- malformed base64 or non-object inner JSON
- upstream HTTP status outside 2xx
- upstream explicit failure result
- expired, canceled, missing, or unsupported transaction status
- requested resident `id_type` without corroborating upstream credential-type evidence
- configured base URL without required credentials

Failure messages are sanitized and must not contain raw VP data, resident identifiers, CI, DI, phone numbers, names, or birthdate-like values.

## Environment Contract

Default tests do not require these variables. The live test requires all of them and skips before network access when any is absent:

- `UMMAYA_MOBILEID_BASE_URL`
- `UMMAYA_MOBILEID_CLIENT_ID`
- `UMMAYA_MOBILEID_TEST_TRXCODE`

## Live Readiness Evidence

Before claiming live readiness, capture a sanitized direct curl or equivalent operator-daemon request/response record. Store only redacted metadata and status evidence; never commit raw VP data, CI, DI, resident identifiers, phone numbers, names, or birthdate-like fields.
