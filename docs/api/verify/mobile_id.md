---
tool_id: mock_verify_mobile_id
primitive: check
tier: mock
permission_tier: 2
---

# mock_verify_mobile_id

## Overview

Verifies a citizen's 모바일 신분증 (Mobile ID) session — either a mobile driver's license (`mdl`) or a mobile resident registration card (`resident`) — and returns a typed `MobileIdContext` envelope.

| Field | Value |
|---|---|
| Classification | Mock · Permission tier 2 |
| Source | 행정안전부 모바일 신분증 SDK reference documentation (OOS shape-mirror) |
| Primitive | `check` |
| Module | `src/ummaya/tools/mock/verify_mobile_id.py` |

## Envelope

**Input model**: `VerifyInput` defined at `src/ummaya/primitives/verify.py:44–51`.

| Field | Type | Required | Description |
|---|---|---|---|
| `family_hint` | `Literal["mobile_id"]` | yes | Must be `"mobile_id"`; dispatcher rejects any other value (FR-010). |
| `session_context` | `dict[str, object]` | no | Opaque external evidence. Pass `{"_fixture_override": {"id_type": "resident"}}` in tests to exercise the resident-card variant. |

**Output model**: `MobileIdContext` defined at `src/ummaya/primitives/verify.py:186–199`.

| Field | Type | Required | Description |
|---|---|---|---|
| `family` | `Literal["mobile_id"]` | yes | Discriminator field; always `"mobile_id"`. |
| `published_tier` | `str` | yes | One of `mobile_id_mdl_aal2`, `mobile_id_resident_aal2`. |
| `nist_aal_hint` | `str` | yes | NIST AAL shorthand; always `"AAL2"` for mobile IDs. |
| `verified_at` | `datetime` | yes | UTC timestamp when the external mobile-ID session was established. |
| `external_session_ref` | `str \| None` | no | Opaque reference returned by the identity provider. |
| `id_type` | `Literal["mdl", "resident"]` | yes | `"mdl"` = 모바일운전면허; `"resident"` = 모바일주민등록증. |

## Search hints

- 한국어: `모바일신분증`, `모바일운전면허`, `모바일주민등록증`, `행정안전부`
- English: `mobile id`, `mobile driver license`, `mdl`, `mobile resident card`

## Endpoint

- **Mode**: Fixture-replay only
- **Public spec source**: 행정안전부 모바일 신분증 (https://www.mobileid.go.kr/); SDK reference documentation shape-mirrored under OOS mode.
- **Fixture path**: Fixture data is hard-coded as constants inside the adapter module itself per the unit-test convention. Default fixture is `MobileIdContext(id_type="mdl", published_tier="mobile_id_mdl_aal2", nist_aal_hint="AAL2", verified_at=2026-04-19T09:00:00Z, external_session_ref="mock-mobile-id-ref-001")`.

## Permission tier rationale

This adapter carries `auth_level="AAL2"` and `is_irreversible=False`. Per `src/ummaya/tools/permissions.py` `compute_permission_tier()` (Spec 033 FR-011), AAL2 maps to **permission tier 2** (orange ⓶ in UI-C). Mobile ID contains a unique personal identifier (`pipa_class="personal_unique_id"`), which is a higher-sensitivity PIPA class than `personal_standard`. The permission gauntlet must surface an explicit consent prompt and record an audit receipt before the first invocation. The citizen's `id_type` preference (driver's license vs. resident card) influences which physical credential is presented but does not change the tier; both variants are AAL2.

## Worked example

### Input envelope

```json
{
  "mode": "fetch",
  "tool_id": "mock_verify_mobile_id",
  "params": {
    "family_hint": "mobile_id",
    "session_context": {}
  }
}
```

### Output envelope (success)

```json
{
  "tool_id": "mock_verify_mobile_id",
  "result": {
    "family": "mobile_id",
    "published_tier": "mobile_id_mdl_aal2",
    "nist_aal_hint": "AAL2",
    "verified_at": "2026-04-19T09:00:00+00:00",
    "external_session_ref": "mock-mobile-id-ref-001",
    "id_type": "mdl"
  }
}
```

### Conversation snippet

```text
시민: 모바일운전면허로 본인인증 해줘.
UMMAYA: 모바일 신분증 (모바일운전면허, AAL2) 인증이 확인되었습니다. 인증 시각: 2026-04-19 09:00 UTC, 세션 참조: mock-mobile-id-ref-001.
```

## Constraints

- **Rate limit**: N/A (fixture). `rate_limit_per_minute=10` is a soft advisory carried in the registration metadata; it applies to live deployments, not to this fixture-replay adapter.
- **Freshness window**: N/A. Fixture `verified_at` is a static recorded timestamp.
- **Network egress**: 0. No external HTTP connections are made under any circumstances.
- **Fixture coverage gaps**: The `resident` id_type (모바일주민등록증, `mobile_id_resident_aal2`) is not included in the default fixture. Pass `{"_fixture_override": {"id_type": "resident", "published_tier": "mobile_id_resident_aal2"}}` in `session_context` to exercise that path in tests.
- **Error envelope examples**:
  - Tier-2/3 unauthenticated (consent not granted):
    ```json
    {"error": {"code": "PERMISSION_DENIED", "tier": 2, "message": "Consent required for is_personal_data adapter. Run /consent to grant permission."}}
    ```
  - Fixture not found / adapter missing:
    ```json
    {"family": "mismatch_error", "reason": "family_mismatch", "expected_family": "mobile_id", "observed_family": "<no_adapter>", "message": "No verify adapter registered for family 'mobile_id'."}
    ```
  - Malformed input (wrong family_hint):
    ```json
    {"error": {"code": "VALIDATION_ERROR", "message": "family_hint: Input should be 'mobile_id'"}}
    ```
