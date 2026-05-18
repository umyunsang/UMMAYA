---
tool_id: live_verify_kb_identity
primitive: check
tier: live
permission_tier: 2
---

# live_verify_kb_identity

## Overview

Wraps KB국민인증서 identity verification as an opt-in live `check` adapter. The
adapter starts a KB certificate identity transaction or polls a transaction
result, then returns only a `KbIdentityContext` with an opaque
`external_session_ref`.

| Field | Value |
|---|---|
| Classification | Live · Permission tier 2 |
| Source | KB국민인증서 identity API docs |
| Primitive | `check` |
| Family | `kb_identity` |
| Module | `src/ummaya/tools/live/verify_kb_identity.py` |

Official KB source pages:

- Identity flow: <https://cert.kbstar.com/quics?page=C112279>
- Common OpenAPI guidance: <https://cert.kbstar.com/quics?page=C112276>
- Test procedure guidance: <https://cert.kbstar.com/quics?page=C112283>

## Runtime Configuration

The adapter is inert unless all required credentials are configured:

| Env var | Required | Description |
|---|---:|---|
| `UMMAYA_KBCERT_BASE_URL` | yes | KB OpenAPI base URL. Staging is `https://stg-openapi.kbstar.com:8443/`; production is `https://openapi.kbstar.com:8443/`. |
| `UMMAYA_KBCERT_API_KEY` | yes | KB `apiKey` request header value. |
| `UMMAYA_KBCERT_HS_KEY` | yes | KB `hsKey` request header value. |
| `UMMAYA_KBCERT_COMPANY_CD` | yes | KB `dataBody.companyCd`. |
| `UMMAYA_KBCERT_REQUEST_TYPE` | no | KB `dataBody.requestType`; defaults to `NONE` until a partner profile defines a stricter value. |

Default CI must not set these values and must not run live-marked tests.

## KB Contract

Base URLs:

- Staging: `https://stg-openapi.kbstar.com:8443/`
- Production: `https://openapi.kbstar.com:8443/`

Endpoints:

| Flow | Method | Path |
|---|---|---|
| Start request | `POST` | `/kbsign/api/sign_request2` |
| Result lookup | `POST` | `/kbsign/api/sign_result` |

Headers:

```http
apiKey: <UMMAYA_KBCERT_API_KEY>
hsKey: <UMMAYA_KBCERT_HS_KEY>
Content-Type: application/json; charset=UTF-8
```

Request body shape:

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

Result lookup adds `certTxId`:

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

## Input Envelope

Call only through the `check` primitive:

```json
{
  "tool_id": "live_verify_kb_identity",
  "params": {
    "mode": "request",
    "reqTxId": "synthetic-req-tx-id"
  }
}
```

Supported params:

| Field | Type | Required | Description |
|---|---|---:|---|
| `mode` | `"auto" \| "request" \| "result"` | no | `auto` starts a request unless `certTxId` is present. |
| `reqTxId` | `str` | result: yes | External request transaction id. Generated when omitted in request mode. |
| `certTxId` | `str` | result: yes | KB certificate transaction id returned by request mode. |
| `requestType` | `str` | no | Overrides `UMMAYA_KBCERT_REQUEST_TYPE` for a single call. |

## Output Envelope

`KbIdentityContext` contains only sanitized metadata:

```json
{
  "family": "kb_identity",
  "provider": "kb",
  "published_tier": "kb_identity_aal2",
  "nist_aal_hint": "AAL2",
  "verified_at": "2026-05-18T00:00:00+00:00",
  "external_session_ref": "kbcert:reqTxId=synthetic-req-tx-id;certTxId=synthetic-cert-tx-id"
}
```

The adapter never returns or logs raw identity fields such as name, birthdate,
phone number, CI, DI, gender, nationality, or encrypted identity payloads.

## Evidence Requirement

Before claiming live readiness for a partner environment, record sanitized curl
evidence outside CI:

1. `sign_request2` request/response against the configured KB test endpoint.
2. `sign_result` request/response for the same `reqTxId` and `certTxId`.
3. Redaction check showing no raw CI, DI, name, birthdate, phone, gender,
   nationality, API key, or `hsKey` appears in the saved evidence.

Evidence files must contain only sanitized transaction metadata. Do not commit
partner credentials or identity-bearing payloads.

## Tests

Default tests use synthetic fixtures only:

```bash
uv run pytest tests/unit/tools/live/test_kb_identity_client.py tests/unit/tools/live/test_verify_kb_identity.py -m "not live"
uv run pytest tests/live/test_live_kb_identity.py -m "not live"
```

Credentialed smoke tests are opt-in:

```bash
UMMAYA_KBCERT_BASE_URL=https://stg-openapi.kbstar.com:8443/ \
UMMAYA_KBCERT_API_KEY=... \
UMMAYA_KBCERT_HS_KEY=... \
UMMAYA_KBCERT_COMPANY_CD=... \
uv run pytest tests/live/test_live_kb_identity.py -m live
```
