# Data Model: Live BaroCert Identity Check

## BarocertProvider

Provider selector for the BaroCert client.

| Field | Type | Validation |
|-------|------|------------|
| `provider` | `Literal["toss", "kakao", "naver"]` | Required |

## BarocertIdentityRequest

Sanitized request-start input. Values are already encrypted or test placeholders;
raw phone, name, birthday, CI, or DI are not accepted.

| Field | Type | Validation |
|-------|------|------------|
| `provider` | `BarocertProvider` | Required |
| `client_code` | `str` | 12 characters for BaroCert client code |
| `receiver_hp_encrypted` | `str` | Non-empty encrypted placeholder |
| `receiver_name_encrypted` | `str` | Non-empty encrypted placeholder |
| `receiver_birthday_encrypted` | `str` | Non-empty encrypted placeholder |
| `token_encrypted` | `str` | Non-empty encrypted placeholder |
| `expire_in` | `int` | Positive; Toss maximum 1800 seconds |
| `app_use_yn` | `bool` | Defaults false |
| `device_os_type` | `Literal["ANDROID", "IOS"] \| None` | Required only for app-to-app provider variants that need it |
| `return_url` | `str \| None` | Required only for app-to-app provider variants that need it |

## BarocertIdentityReceipt

Provider receipt metadata that can be returned safely.

| Field | Type | Validation |
|-------|------|------------|
| `provider` | `BarocertProvider` | Required |
| `receipt_id` | `str` | Required, non-empty |
| `scheme` | `str \| None` | Optional app scheme |
| `market_url` | `str \| None` | Optional Naver app market URL |

## BarocertIdentityStatus

Normalized provider status.

| Field | Type | Validation |
|-------|------|------------|
| `provider` | `BarocertProvider` | Required |
| `receipt_id` | `str` | Required, non-empty |
| `state` | `Literal["pending", "complete", "expired", "rejected", "failed"]` | Required |
| `expire_dt` | `str \| None` | Provider timestamp if present |
| `complete_dt` | `str \| None` | Provider timestamp if present |

### Status Mapping

| Provider state code | Normalized state |
|---------------------|------------------|
| `0` | `pending` |
| `1` | `complete` |
| `2` | `expired` |
| `3` | `rejected` |
| `4` | `failed` |

Providers that do not define `3` or `4` still reject those values if seen in a
fixture or live response.

## BarocertIdentityVerification

Sanitized verification summary produced from provider result payloads.

| Field | Type | Validation |
|-------|------|------------|
| `provider` | `BarocertProvider` | Required |
| `receipt_id` | `str` | Required |
| `state` | `Literal["complete"]` | Only complete results can verify |
| `signed_data_present` | `bool` | Required |
| `identity_evidence_present` | `bool` | Required; true if CI/DI or provider identity fields are present |
| `verified_at` | `datetime` | UTC timestamp |

### Redaction Rule

Raw provider keys `ci`, `di`, `signedData`, `receiverHP`, `receiverName`,
`receiverBirthday`, `receiverYear`, `receiverDay`, `receiverGender`,
`receiverForeign`, `receiverAgeGroup`, `receiverEmail`, and `receiverTelcoType`
are consumed only for evidence presence and must not appear in model dumps,
logs, fixtures snapshots, or returned auth contexts.

## GanpyeonInjeungContext Output

The live adapter returns the existing `GanpyeonInjeungContext` shape:

| Field | Value |
|-------|-------|
| `family` | `ganpyeon_injeung` |
| `provider` | Provider literal, v1 live priority `toss` |
| `published_tier` | `ganpyeon_injeung_toss_aal2` for Toss |
| `nist_aal_hint` | `AAL2` |
| `verified_at` | Provider verification time as UTC timestamp |
| `external_session_ref` | Sanitized reference such as `barocert:toss:<receipt_id>` |
