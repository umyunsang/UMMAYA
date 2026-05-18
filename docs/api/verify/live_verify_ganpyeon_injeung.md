# live_verify_ganpyeon_injeung

`live_verify_ganpyeon_injeung` is the explicit live BaroCert identity check
adapter for the existing `ganpyeon_injeung` family. It is registered under the
`check` primitive only and maps to the same canonical family as
`mock_verify_ganpyeon_injeung`; explicit `tool_id` selection decides whether the
mock adapter or the BaroCert-backed live adapter runs.

## Provider Scope

V1 live priority is Toss 본인확인. Kakao and Naver are represented through the
same provider metadata and sanitized fixture parsing so future live expansion is
additive.

Official BaroCert references:

- Toss 본인확인 API:
  <https://developers.barocert.com/reference/toss/asp/userIdentity/api>
- Kakao 본인인증 API:
  <https://developers.barocert.com/reference/kakao/asp/identity/api>
- Naver 본인인증 API:
  <https://developers.barocert.com/reference/naver/asp/identity/api>
- Python SDK setup:
  <https://developers.barocert.com/guide/toss/identity/python/getting-started/sdk-configuration>

The Toss contract uses:

- `requestUserIdentity(clientCode, UserIdentity)`
- `getUserIdentityStatus(clientCode, receiptID)`
- `verifyUserIdentity(clientCode, receiptID)`

Status values are normalized as `0=pending`, `1=complete`, and `2=expired`.
Expired, failed, malformed, or provider-mismatched payloads fail closed as
`VerifyMismatchError`.

## Runtime Inputs

Typical explicit check call:

```json
{
  "tool_id": "live_verify_ganpyeon_injeung",
  "params": {
    "provider": "toss",
    "receiptID": "TOSS_RECEIPT_FROM_PRIOR_REQUEST",
    "scope_list": ["check:ganpyeon.identity"],
    "purpose_ko": "본인확인",
    "purpose_en": "Identity verification"
  }
}
```

UMMAYA does not accept raw phone number, name, birthday, CI, DI, or resident
identifier values for this adapter. Request-start fields, when used by future
flows, must already be encrypted placeholders matching BaroCert SDK input
requirements:

- `receiverHP`
- `receiverName`
- `receiverBirthday`
- `token`
- `expireIn`
- `appUseYN`
- `deviceOSType` and `returnURL` for Toss app-to-app requests

## Environment

Live execution is disabled unless the caller explicitly selects
`live_verify_ganpyeon_injeung` and credentials are available:

- `UMMAYA_BAROCERT_LINK_ID`
- `UMMAYA_BAROCERT_SECRET_KEY`
- `UMMAYA_BAROCERT_CLIENT_CODE`
- `UMMAYA_BAROCERT_TEST_RECEIPT_ID` for the opt-in live pytest

Optional SDK transport settings:

- `UMMAYA_BAROCERT_IP_RESTRICT`
- `UMMAYA_BAROCERT_USE_STATIC_IP`

The Python SDK must be installed in the runtime environment for live execution.
Default tests use sanitized fixture replay only.

## Output Contract

Successful live verification returns a `GanpyeonInjeungContext`-compatible
result:

```json
{
  "family": "ganpyeon_injeung",
  "provider": "toss",
  "external_session_ref": "barocert:toss:<receiptID>",
  "published_tier": "ganpyeon_injeung_toss_aal2",
  "nist_aal_hint": "AAL2",
  "verified_at": "<provider verification time>"
}
```

The adapter only records sanitized receipt metadata and booleans such as
identity evidence present and signed data present. It never returns or persists
raw CI, DI, phone, birthday, name, `signedData`, or encrypted identity payload
values.

## Testing

Default non-live tests:

```bash
uv run pytest tests/unit/tools/live tests/integration/test_live_barocert_discovery.py -m "not live"
```

Opt-in live validation:

```bash
UMMAYA_BAROCERT_LINK_ID=... \
UMMAYA_BAROCERT_SECRET_KEY=... \
UMMAYA_BAROCERT_CLIENT_CODE=... \
UMMAYA_BAROCERT_TEST_RECEIPT_ID=... \
uv run pytest tests/live/test_live_barocert_identity.py -m live
```

Do not run live BaroCert tests in CI. Record sanitized direct evidence before
claiming live readiness for a new provider or credential set.
