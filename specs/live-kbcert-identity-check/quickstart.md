# Quickstart: Live KB Identity Check Adapter

## Default Fixture Tests

Run the non-live KB test slice:

```bash
uv run pytest tests/unit/tools/live/test_kb_identity_client.py tests/unit/tools/live/test_verify_kb_identity.py -m "not live"
```

Run the broader non-live check/registry slice:

```bash
uv run pytest tests/unit/primitives/verify tests/unit/test_verify_canonical_map_parser.py tests/integration/test_discovery_bridge_path_b.py -m "not live"
```

## Live Smoke

Live smoke requires KB partner credentials and allowlisted network access.

```bash
export UMMAYA_KBCERT_BASE_URL="https://stg-openapi.kbstar.com:8443/"
export UMMAYA_KBCERT_API_KEY="<issued apiKey>"
export UMMAYA_KBCERT_HS_KEY="<generated hsKey>"
export UMMAYA_KBCERT_COMPANY_CD="<companyCd>"
uv run pytest tests/live/test_live_kb_identity.py -m live -v
```

## Sanitized Curl Evidence Template

Before claiming live readiness, record sanitized direct-curl evidence outside CI:

```bash
curl --request POST "$UMMAYA_KBCERT_BASE_URL/kbsign/api/sign_request2" \
  --header "apiKey: <redacted>" \
  --header "hsKey: <redacted>" \
  --header "Content-Type: application/json; charset=UTF-8" \
  --data '{"dataHeader":{},"dataBody":{"companyCd":"<redacted>","reqTxId":"synthetic-req-tx-id","requestType":"NONE"}}'
```

Redact `apiKey`, `hsKey`, `companyCd`, CI, DI, name, birthday, phone number, gender, nationality, and any encrypted identity values from saved evidence.
