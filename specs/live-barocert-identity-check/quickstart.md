# Quickstart: Live BaroCert Identity Check

## Fixture-only validation

Run the default non-live BaroCert tests:

```bash
uv run pytest tests/unit/tools/live tests/integration/test_live_barocert_discovery.py -m "not live" -q
```

Expected:
- Provider selection tests pass for `toss`, `kakao`, and `naver`.
- Toss request/status/verify fixtures replay without network access.
- Redaction assertions prove CI, DI, phone, birthday, name, signedData, and
  encrypted identity payload fields are absent from output.

## Registry validation

```bash
uv run pytest tests/integration/test_tool_id_to_family_hint_translation.py tests/integration/test_live_barocert_discovery.py -q
```

Expected:
- `live_verify_ganpyeon_injeung` resolves to `family_hint="ganpyeon_injeung"`.
- Existing mock tool-id mappings still pass.
- Main registry contains the live adapter as primitive `check`.

## Live validation

Live validation is opt-in and must not run in CI.

Required environment:

```bash
export UMMAYA_BAROCERT_LINK_ID=...
export UMMAYA_BAROCERT_SECRET_KEY=...
export UMMAYA_BAROCERT_CLIENT_CODE=...
export UMMAYA_BAROCERT_TEST_RECEIPT_ID=...
```

Run:

```bash
uv run pytest tests/live/test_live_barocert_identity.py -m live -q
```

Expected:
- The test skips when any required environment variable is absent.
- With credentials, the adapter verifies only sanitized provider evidence.
- The output contains no raw CI, DI, phone, birthday, name, signedData, or full
  provider result payload.
