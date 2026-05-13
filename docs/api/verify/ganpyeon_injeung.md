---
tool_id: mock_verify_ganpyeon_injeung
primitive: check
tier: mock
permission_tier: 2
---

# mock_verify_ganpyeon_injeung

## Overview

Verifies a citizen's 간편인증 (Simple/App-cert) session from a provider such as Kakao, Naver, Toss, PASS, Samsung Pay, or Payco and returns a typed `GanpyeonInjeungContext` envelope identifying the provider.

| Field | Value |
|---|---|
| Classification | Mock · Permission tier 2 |
| Source | Barocert SDK documentation (https://developers.barocert.com/, OOS shape-mirror) |
| Primitive | `check` |
| Module | `src/ummaya/tools/mock/verify_ganpyeon_injeung.py` |

## Envelope

**Input model**: `VerifyInput` defined at `src/ummaya/primitives/verify.py:44–51`.

| Field | Type | Required | Description |
|---|---|---|---|
| `family_hint` | `Literal["ganpyeon_injeung"]` | yes | Must be `"ganpyeon_injeung"`; dispatcher rejects any other value (FR-010). |
| `session_context` | `dict[str, object]` | no | Opaque external evidence. Pass `{"_fixture_override": {"provider": "naver", "published_tier": "ganpyeon_injeung_naver_aal2"}}` in tests to exercise other provider variants. |

**Output model**: `GanpyeonInjeungContext` defined at `src/ummaya/primitives/verify.py:154–167`.

| Field | Type | Required | Description |
|---|---|---|---|
| `family` | `Literal["ganpyeon_injeung"]` | yes | Discriminator field; always `"ganpyeon_injeung"`. |
| `published_tier` | `str` | yes | One of `ganpyeon_injeung_pass_aal2`, `ganpyeon_injeung_kakao_aal2`, `ganpyeon_injeung_naver_aal2`, `ganpyeon_injeung_toss_aal2`, `ganpyeon_injeung_bank_aal2`, `ganpyeon_injeung_samsung_aal2`, `ganpyeon_injeung_payco_aal2`. |
| `nist_aal_hint` | `str` | yes | Always `"AAL2"` for all 간편인증 providers. |
| `verified_at` | `datetime` | yes | UTC timestamp when the external app-cert session was established. |
| `external_session_ref` | `str \| None` | no | Opaque reference returned by the provider. |
| `provider` | `Literal["pass", "kakao", "naver", "toss", "bank", "samsung", "payco"]` | yes | The app-cert provider that authenticated the citizen. |

## Search hints

- 한국어: `간편인증`, `카카오인증`, `네이버인증`, `토스인증`, `PASS`, `삼성패스`
- English: `simple auth`, `kakao cert`, `naver cert`, `toss cert`, `PASS`, `ganpyeon injeung`

## Endpoint

- **Mode**: Fixture-replay only
- **Public spec source**: Barocert SDK documentation (https://developers.barocert.com/); shape-mirrored from the Barocert identity verification API covering Kakao, Naver, PASS, and bank-issued app certificates.
- **Fixture path**: Fixture data is hard-coded as constants inside the adapter module itself per the unit-test convention. Default fixture is `GanpyeonInjeungContext(provider="kakao", published_tier="ganpyeon_injeung_kakao_aal2", nist_aal_hint="AAL2", verified_at=2026-04-19T09:00:00Z, external_session_ref="mock-ganpyeon-ref-001")`.

## Permission tier rationale

This adapter carries `auth_level="AAL2"` and `is_irreversible=False`. Per `src/ummaya/tools/permissions.py` `compute_permission_tier()` (Spec 033 FR-011), AAL2 maps to **permission tier 2** (orange ⓶ in UI-C). Although 간편인증 providers are private-sector apps rather than government PKI, the authentication context is still bound to a personal identifier (`pipa_class="personal_standard"`, `is_personal_data=True`), and the underlying OAuth handshake satisfies NIST AAL2. The permission gauntlet must surface the orange ⓶ consent modal and record a consent receipt before execution. Session-auto (`A`) grant is permitted for repeated same-session calls.

## Worked example

### Input envelope

```json
{
  "mode": "fetch",
  "tool_id": "mock_verify_ganpyeon_injeung",
  "params": {
    "family_hint": "ganpyeon_injeung",
    "session_context": {}
  }
}
```

### Output envelope (success)

```json
{
  "tool_id": "mock_verify_ganpyeon_injeung",
  "result": {
    "family": "ganpyeon_injeung",
    "published_tier": "ganpyeon_injeung_kakao_aal2",
    "nist_aal_hint": "AAL2",
    "verified_at": "2026-04-19T09:00:00+00:00",
    "external_session_ref": "mock-ganpyeon-ref-001",
    "provider": "kakao"
  }
}
```

### Conversation snippet

```text
시민: 카카오 간편인증으로 본인인증 해줘.
UMMAYA: 카카오 간편인증 (AAL2) 인증이 확인되었습니다. 인증 시각: 2026-04-19 09:00 UTC, 세션 참조: mock-ganpyeon-ref-001.
```

## Constraints

- **Rate limit**: N/A (fixture). `rate_limit_per_minute=10` is a soft advisory for live deployments.
- **Freshness window**: N/A. Fixture `verified_at` is a static recorded timestamp.
- **Network egress**: 0. No external HTTP connections are made under any circumstances.
- **Fixture coverage gaps**: Six provider variants (pass, naver, toss, bank, samsung, payco) are not included in the default fixture. Use `_fixture_override` in `session_context` to exercise each provider's `published_tier` string. All seven providers resolve to the same permission tier 2, so tier-level behavior is uniform.
- **Error envelope examples**:
  - Tier-2/3 unauthenticated (consent not granted):
    ```json
    {"error": {"code": "PERMISSION_DENIED", "tier": 2, "message": "Consent required for is_personal_data adapter. Run /consent to grant permission."}}
    ```
  - Fixture not found / adapter missing:
    ```json
    {"family": "mismatch_error", "reason": "family_mismatch", "expected_family": "ganpyeon_injeung", "observed_family": "<no_adapter>", "message": "No verify adapter registered for family 'ganpyeon_injeung'."}
    ```
  - Malformed input (invalid provider in override):
    ```json
    {"error": {"code": "VALIDATION_ERROR", "message": "provider: Input should be 'pass', 'kakao', 'naver', 'toss', 'bank', 'samsung' or 'payco'"}}
    ```
