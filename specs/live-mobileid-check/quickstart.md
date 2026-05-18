# Quickstart: Live MobileID Check Adapter

## Default Fixture Verification

Run the focused fixture tests without live calls:

```bash
uv run pytest tests/unit/tools/test_mobileid_client.py tests/unit/tools/test_verify_mobile_id_live_adapter.py tests/integration/test_live_mobileid_registration.py -m "not live"
```

Run the wider non-live backend suite:

```bash
uv run pytest -m "not live"
```

## Live Verification

Live tests are opt-in and skipped unless all required env vars exist:

```bash
export UMMAYA_MOBILEID_BASE_URL="https://operator-daemon.example.test"
export UMMAYA_MOBILEID_CLIENT_ID="REDACTED"
export UMMAYA_MOBILEID_TEST_TRXCODE="TRX-SANITIZED"
uv run pytest tests/live/test_live_mobileid.py -m live
```

Do not run this command in CI unless a dedicated, approved, non-production live-test environment is configured and explicitly allowed.

## Manual Adapter Smoke

The adapter is selected by tool id:

```json
{
  "tool_id": "live_verify_mobile_id",
  "params": {
    "trxcode": "TRX-SANITIZED",
    "id_type": "mdl"
  }
}
```

Expected success output is a `MobileIdContext` with an opaque `external_session_ref`. It must not include raw VP, CI, DI, resident identifier, phone number, name, or birthdate-like fields.

## Sanitized Curl Evidence Template

Record only redacted evidence:

```text
timestamp: 2026-05-18T00:00:00Z
base_url: REDACTED_OPERATOR_DAEMON
endpoint: /mip/trxsts
trxcode: TRX-SANITIZED
http_status: 200
decoded_result_summary: verified=true, status_code=COMPLETED
redaction_review: no raw vp, ci, di, resident identifier, phone, name, or birthdate fields
```

Do not store bearer tokens, API keys, full request bodies, full response bodies, raw `data`, or decrypted identity attributes.
