---
tool_id: nfa_emergency_info_service
primitive: lookup
tier: live
permission_tier: 1
---

# nfa_emergency_info_service

## Overview

Queries the NFA (소방청, National Fire Agency) emergency activity statistics service for historical, anonymized EMS records by region, fire station, and report year-month. Covers six sub-operations: dispatch activity, patient transport, patient condition, first-aid treatment, vehicle dispatch, and vehicle fleet information.

| Field | Value |
|---|---|
| Classification | Live · Permission tier 1 |
| Source | National Fire Agency (NFA / 소방청) / data.go.kr |
| Primitive | `lookup` |
| Module | `src/kosmos/tools/nfa119/emergency_info_service.py` |
| Wire research | `specs/2522-tool-surface-v4/research-nfa-wire.md` |

## Envelope

**Input model**: `NfaEmergencyInfoServiceInput`

| Field | Type | Required | Wire param | Description |
|---|---|---|---|---|
| `operation` | `NfaEmgOperation` (default `"getEmgencyActivityInfo"`) | no | `/{operation}` suffix | Sub-endpoint selector — appended to base URL. |
| `sido_hq_ogid_nm` | `str \| None` (max 22 chars) | no | `sidoHqOgidNm` | Regional fire HQ name (시도본부). Omit to query all regions. |
| `rsac_gut_fstt_ogid_nm` | `str` (max 7 chars) | yes | `rsacGutFsttOgidNm` | Fire station name (출동소방서). Do not guess. |
| `stmt_ym` | `str` (pattern `^\d{6}$`) | yes | `gutYm` or `stmtYm` (see table) | Report year-month YYYYMM. |
| `page_no` | `int` (≥1, default 1) | no | `pageNo` | Page number (1-indexed). |
| `num_of_rows` | `int` (1–100, default 10) | no | `numOfRows` | Records per page. Max 100. |
| `result_type` | `Literal["json"]` (fixed) | no | `resultType` | Fixed to `"json"`. |

**`NfaEmgOperation` — 6 sub-endpoints**:

| `operation` value | Wire sub-endpoint suffix | Korean name | ym wire param |
|---|---|---|---|
| `activity` | `/getEmgencyActivityInfo` | 구급활동정보 (default) | `gutYm` |
| `transfer` | `/getEmgPatientTransferInfo` | 구급환자이송정보 | `stmtYm` |
| `condition` | `/getEmgPatientConditionInfo` | 구급환자상태정보 | `stmtYm` |
| `firstaid` | `/getEmgPatientFirstaidInfo` | 구급환자응급처치정보 | `stmtYm` |
| `vehicle_dispatch` | `/getEmgVehicleDispatchInfo` | 구급차량출동정보 | `stmtYm` |
| `vehicle_info` | `/getEmgVehicleInfo` | 구급차량정보 | *(omitted — vehicle registry snapshot)* |

> **Wire param critical note**: `getEmgencyActivityInfo` uses `gutYm` (출동년월), while all other operations use `stmtYm` (신고년월). `getEmgVehicleInfo` is a static vehicle registry and does not accept a year-month parameter at all.

**Output model**: `NfaEmergencyInfoServiceOutput`

| Field | Type | Description |
|---|---|---|
| `operation` | `str` | The queried operation path. |
| `result_code` | `str` | API `resultCode` (`"00"` = NORMAL SERVICE). |
| `result_msg` | `str` | API `resultMsg`. |
| `page_no` | `int` | Requested page number. |
| `num_of_rows` | `int` | Rows per page. |
| `total_count` | `int` | Total matching records. |
| `items` | `list[NfaItem]` | Records. Empty list when no records match. |

`NfaItem` is a union of six operation-specific Pydantic models (all use `extra="allow"` to tolerate undocumented wire fields):
- `NfaActivityItem` — `gutYm`, dispatch distance, patient symptoms, crew qualifications
- `NfaTransferItem` — `stmtYm`, accident type, patient age/gender, location
- `NfaConditionItem` — `stmtYm`, vitals (BP/pulse/SpO2/temp), patient symptoms
- `NfaFirstaidItem` — `stmtYm`, treatment codes
- `NfaVehicleDispatchItem` — `stmtYm`, vehicle type/number/status, crew count
- `NfaVehicleInfoItem` — `stde` (기준일자), vehicle specs

## Search hints

- 한국어: `119 구급`, `출동`, `소방청`, `구급정보`, `구급활동`, `구급차`, `통계`, `현황`, `소방서`, `긴급구조`
- English: `119 NFA emergency`, `ambulance dispatch`, `EMS activity statistics`, `fire station`, `Korea emergency services`

## Endpoint

- **Base URL**: `https://apis.data.go.kr/1661000/EmergencyInformationService`
- **Sub-endpoint**: `/{operation}` — mandatory suffix (e.g. `/getEmgencyActivityInfo`)
- **Authentication**: API key via `KOSMOS_DATA_GO_KR_API_KEY` (공공데이터포털 통합키)

## Wire quirks

1. **Operation suffix required**: Sending requests to the base URL without `/{operation}` returns `resultCode: 10` — this was the cause of all failures in the evidence testing phase (`medical-evidence.md`).
2. **ym param divergence**: `activity` → `gutYm`; all others → `stmtYm`; `vehicle_info` → none.
3. **resultType=json**: The wire param name has a capital `T` (`resultType`), value is lowercase `json`.
4. **Response JSON shape**: pagination fields (`pageNo`, `numOfRows`, `totalCount`) are inside `response.body`, not at the `response` level.
5. **Single-item response**: When `totalCount=1`, some API variants return `body.items.item` as a single dict instead of a list — the adapter normalizes this automatically.

## Permission tier rationale

Permission tier 1 despite `auth_type="api_key"` — underlying data is historical and anonymized. Records contain aggregate dispatch statistics by region, station, and month; no individual citizen health or identity data is exposed. The `api_key` enforces service access-control (preventing unauthenticated bulk scraping), not citizen privacy protection. Unauthenticated calls return `LookupError(reason="auth_required")` from the executor layer before `handle()` is reached.

## Worked examples

### Example 1: 구급활동정보 (dispatch activity — default operation)

```json
{
  "mode": "fetch",
  "tool_id": "nfa_emergency_info_service",
  "params": {
    "operation": "getEmgencyActivityInfo",
    "rsac_gut_fstt_ogid_nm": "천안동남소방서",
    "stmt_ym": "202112",
    "page_no": 1,
    "num_of_rows": 5
  }
}
```

Wire URL: `GET https://apis.data.go.kr/1661000/EmergencyInformationService/getEmgencyActivityInfo?serviceKey=...&rsacGutFsttOgidNm=천안동남소방서&gutYm=202112&pageNo=1&numOfRows=5&resultType=json`

Response (success):
```json
{
  "operation": "getEmgencyActivityInfo",
  "result_code": "00",
  "result_msg": "NORMAL SERVICE",
  "page_no": 1,
  "num_of_rows": 5,
  "total_count": 112,
  "items": [
    {
      "sidoHqOgidNm": "충청남도소방본부",
      "rsacGutFsttOgidNm": "천안동남소방서",
      "gutYm": "202112",
      "gutHh": "21",
      "sptMvmnDtc": "12",
      "ptntAge": "60~69세",
      "ptntSdtSeCdNm": "여",
      "ruptSptmCdNm": "기침",
      "emtpQlcClCd1Nm": "응급구조사(1급)"
    }
  ]
}
```

### Example 2: 구급환자상태정보 (patient condition)

```json
{
  "mode": "fetch",
  "tool_id": "nfa_emergency_info_service",
  "params": {
    "operation": "getEmgPatientConditionInfo",
    "sido_hq_ogid_nm": "경기도소방재난본부",
    "rsac_gut_fstt_ogid_nm": "파주소방서",
    "stmt_ym": "202107",
    "num_of_rows": 3
  }
}
```

Wire URL: `.../getEmgPatientConditionInfo?...&sidoHqOgidNm=경기도소방재난본부&rsacGutFsttOgidNm=파주소방서&stmtYm=202107&...`

Response item:
```json
{
  "sidoHqOgidNm": "경기도소방재난본부",
  "rsacGutFsttOgidNm": "파주소방서",
  "stmtYm": "202107",
  "stmtHh": "06",
  "ptntAge": "60~69세",
  "lwsBpsr": "73",
  "topBpsr": "122",
  "ptntHbco": "80",
  "ptntBfco": "16",
  "ptntOsv": "99",
  "ptntBht": "36",
  "ruptSptmCdNm": "어지러움"
}
```

### Example 3: 구급차량정보 (vehicle fleet — no ym param)

```json
{
  "mode": "fetch",
  "tool_id": "nfa_emergency_info_service",
  "params": {
    "operation": "getEmgVehicleInfo",
    "sido_hq_ogid_nm": "대구소방안전본부",
    "rsac_gut_fstt_ogid_nm": "동부소방서",
    "stmt_ym": "202201"
  }
}
```

Wire URL: `.../getEmgVehicleInfo?...&sidoHqOgidNm=대구소방안전본부&rsacGutFsttOgidNm=동부소방서&...` (no stmtYm or gutYm)

### Example 4: 구급환자이송정보 (patient transfer)

```json
{
  "mode": "fetch",
  "tool_id": "nfa_emergency_info_service",
  "params": {
    "operation": "getEmgPatientTransferInfo",
    "rsac_gut_fstt_ogid_nm": "공주소방서",
    "stmt_ym": "202101"
  }
}
```

Wire URL: `.../getEmgPatientTransferInfo?...&rsacGutFsttOgidNm=공주소방서&stmtYm=202101&...`

### Example 5: 구급환자응급처치정보 (first-aid treatment)

```json
{
  "mode": "fetch",
  "tool_id": "nfa_emergency_info_service",
  "params": {
    "operation": "getEmgPatientFirstaidInfo",
    "rsac_gut_fstt_ogid_nm": "천안동남소방서",
    "stmt_ym": "202105"
  }
}
```

### Example 6: 구급차량출동정보 (vehicle dispatch)

```json
{
  "mode": "fetch",
  "tool_id": "nfa_emergency_info_service",
  "params": {
    "operation": "getEmgVehicleDispatchInfo",
    "sido_hq_ogid_nm": "서울소방재난본부",
    "rsac_gut_fstt_ogid_nm": "은평소방서",
    "stmt_ym": "202101"
  }
}
```

### Conversation snippet

```text
Citizen: 2021년 12월에 천안동남소방서 구급 출동이 얼마나 있었는지 알고 싶어요.
KOSMOS: 2021년 12월 천안동남소방서 구급활동 정보를 조회했습니다. 해당 기간 총 112건의 출동 기록이 있으며, 예시로 1건을 살펴보면 60~69세 여성 환자가 기침 증세로 현장과 12m 거리에서 1급 응급구조사가 대응했습니다. 더 자세한 내용이나 다른 기간의 통계도 조회해 드릴 수 있습니다.
```

## Constraints

- **Rate limit**: `rate_limit_per_minute=10`; data.go.kr daily quota applies per API key.
- **Freshness**: `cache_ttl_seconds=86400` (24 hours). Historical monthly statistics — upstream updates quarterly.
- **rsac_gut_fstt_ogid_nm max 7 chars**: Field size strictly enforced. Station names like `천안동남소방서` (7 chars) are valid; longer names will be rejected by the input validator.
- **Error envelope**:
  - Missing API key: `ConfigurationError` before HTTP call.
  - `resultCode="10"`: `ToolExecutionError` — check station name spelling, stmt_ym format, and serviceKey validity.
  - XML content-type response: `ToolExecutionError` — service returned XML despite `resultType=json` (likely serviceKey gateway error).
  - HTTP 5xx: `ToolExecutionError`.
  - Unauthenticated executor call (Layer 3 gate): `LookupError(reason="auth_required")` before `handle()` is reached.
