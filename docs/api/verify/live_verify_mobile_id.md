# live_verify_mobile_id

`live_verify_mobile_id` is an explicit live `check` adapter for an existing MobileID verification-daemon transaction. It returns the existing `MobileIdContext` shape and does not mint downstream `send:*` delegation.

## Official Sources

- MobileID verification daemon API guide: `https://dev.mobileid.go.kr/mip/dfs/useguide/mdGuide.do?guide=demonapiguide`
- MobileID API use procedure: `https://dev.mobileid.go.kr/mip/dfs/apiuse/apiusestep.do`

## Scope

This adapter covers verification/status only:

- `POST /mip/vp`
- `POST /mip/trxsts`

The official start endpoints are upstream ceremony entry points, but v1 does not initiate every ceremony mode:

- `POST /qrmpm/start`
- `POST /qrcpm/start`
- `POST /app2app/start`
- `POST /push/start`

Other daemon endpoints listed by the public guide remain outside this v1 adapter surface: `/mip/profile`, `/mip/image`, `/mip/error`, and `/mip/revp`.

## Request Envelope

MobileID daemon requests and responses use an outer JSON object:

```json
{
  "data": "<base64-encoded inner JSON>"
}
```

Requests use:

```text
Content-Type: application/json; charset=utf-8
```

For `/mip/vp`, the inner JSON includes:

```json
{
  "type": "mip",
  "version": "1.0.0",
  "cmd": 400,
  "request": "presentation",
  "trxcode": "TRX-SANITIZED",
  "vp": {
    "presentType": "VP",
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

## Input

```json
{
  "tool_id": "live_verify_mobile_id",
  "params": {
    "trxcode": "TRX-SANITIZED",
    "id_type": "mdl"
  }
}
```

`id_type` is `mdl` or `resident`. `vp` is optional when the operator daemon has already processed VP evidence and UMMAYA only needs status verification. `resident` is fail-closed unless the verified upstream response includes corroborating credential-type metadata such as a sanitized `credentialType`, `idType`, or VC `type` value that identifies a resident MobileID.

## Output

Success returns a `MobileIdContext`:

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

The adapter never returns raw VP data, CI, DI, resident identifiers, phone numbers, names, or birthdate-like identity attributes.

## Environment

Default tests do not require credentials. The opt-in live test requires:

```bash
export UMMAYA_MOBILEID_BASE_URL="https://operator-daemon.example.test"
export UMMAYA_MOBILEID_CLIENT_ID="REDACTED"
export UMMAYA_MOBILEID_TEST_TRXCODE="TRX-SANITIZED"
uv run pytest tests/live/test_live_mobileid.py -m live
```

If any variable is missing, the live test skips before network access.

## Failure Behavior

The adapter fails closed for:

- missing or blank `trxcode`
- malformed base64 envelope data
- decoded inner payload that is not a JSON object
- upstream HTTP status outside 2xx
- upstream `result=false`
- expired, canceled, pending, or unsupported transaction status
- requested `id_type="resident"` without corroborating upstream credential-type evidence

It does not fall back to `mock_verify_mobile_id` when `live_verify_mobile_id` is explicitly selected.

## Sanitized Curl Evidence

Before claiming live readiness, capture operator evidence separately from CI:

```text
timestamp: 2026-05-18T00:00:00Z
base_url: REDACTED_OPERATOR_DAEMON
endpoint: /mip/trxsts
trxcode: TRX-SANITIZED
http_status: 200
decoded_result_summary: verified=true, status_code=COMPLETED
redaction_review: no raw vp, ci, di, resident identifier, phone, name, or birthdate fields
```

Do not commit bearer tokens, API keys, full request bodies, full response bodies, raw `data`, decrypted identity attributes, CI, DI, resident identifiers, phone numbers, names, or birthdate-like fields.
