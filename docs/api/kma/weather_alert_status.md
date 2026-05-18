---
tool_id: kma_weather_alert_status
primitive: find
tier: live
permission_tier: 1
---

# kma_weather_alert_status

## Overview

Retrieves the current list of active weather warnings and watches issued by the Korea Meteorological Administration (기상청) for all regions nationwide.

| Field | Value |
|---|---|
| Classification | Live · Permission tier 1 |
| Source | Korea Meteorological Administration (KMA) / data.go.kr |
| Primitive | `find` |
| Module | `src/ummaya/tools/kma/kma_weather_alert_status.py` |

## Envelope

**Input model**: `KmaWeatherAlertStatusInput` defined in `src/ummaya/tools/kma/kma_weather_alert_status.py`.

| Field | Type | Required | Description |
|---|---|---|---|
| `stn_id` | `str \| None` | no | Optional KMA station/region ID filter. If omitted, the adapter performs nationwide active-warning lookup. |
| `tmFc` | `str \| None` | no | Optional announcement-time filter in YYYYMMDDHHMI format. If omitted, the adapter returns the currently available announcement list. |
| `num_of_rows` | `int` (≥1, default 2000) | no | Number of rows per page (`numOfRows` wire parameter). 2000 returns all active alerts in a single page. |
| `page_no` | `int` (≥1, default 1) | no | Page number, 1-indexed (`pageNo` wire parameter). |
| `data_type` | `Literal["JSON", "XML"]` (default "JSON") | no | Response format (`dataType` wire parameter). Always leave as "JSON". |

**Output model**: `KmaWeatherAlertStatusOutput` defined in `src/ummaya/tools/kma/kma_weather_alert_status.py`.

| Field | Type | Required | Description |
|---|---|---|---|
| `total_count` | `int` | yes | Count of active (non-cancelled) warnings in the response. |
| `warnings` | `list[WeatherWarning]` | yes | Active warnings only; cancelled items (`cancel=1`) are filtered before this field is populated. |

Each `WeatherWarning` item carries:

| Field | Type | Required | Description |
|---|---|---|---|
| `stn_id` | `str` | yes | Station/region ID. |
| `title` | `str \| None` | no | Compact announcement title from `getWthrWrnList` when KMA returns title-centered rows. |
| `tm_fc` | `str` | yes | Announcement time in YYYYMMDDHHMI format (coerced from int if needed). |
| `tm_ef` | `str \| None` | no | Effective time in YYYYMMDDHHMI format (absent in compact responses). |
| `tm_seq` | `int` | yes | Sequence number within the announcement (default 0). |
| `area_code` | `str \| None` | no | Warning zone code (e.g., `S1151300`). |
| `area_name` | `str \| None` | no | Korean warning zone name (e.g., `서울`). |
| `warn_var` | `int \| None` | no | Warning type: 1=강풍, 2=호우, 3=한파, 4=건조, 5=해일, 6=태풍, 7=대설, 8=황사, 11=폭염. |
| `warn_stress` | `int \| None` | no | Severity: 0=주의보 (watch), 1=경보 (warning). |
| `cancel` | `int` | yes | Cancellation flag; 0=active, 1=cancelled. Always 0 in output (cancelled items are removed). |
| `command` | `int \| None` | no | Command code from KMA. |
| `warn_fc` | `int \| None` | no | Warning forecast flag. |

## Search hints

- 한국어: `기상특보`, `기상경보`, `태풍`, `호우`, `대설`, `한파`, `폭염`, `강풍`, `기상주의보`
- English: `weather warning`, `weather alert`, `typhoon`, `heavy rain`, `snow warning`, `cold wave`, `heat wave`, `wind warning`

## Endpoint

- **data.go.kr endpoint**: `1360000/WthrWrnInfoService/getWthrWrnList`
- **Source URL**: https://apis.data.go.kr/1360000/WthrWrnInfoService/getWthrWrnList
- **Authentication**: API key via `UMMAYA_DATA_GO_KR_API_KEY` (per Constitution IV)

## Permission tier rationale

This adapter is classified as Permission tier 1 because it returns entirely non-personal, publicly broadcast meteorological information (`pipa_class="non_personal"`, `is_personal_data=False`). No citizen identity is involved in the request or response. The data represents national-scope weather warnings already published by KMA for public safety purposes, making it low-risk for automated retrieval. Spec 033 defines tier 1 as the baseline for read-only, non-personal government data.

## Worked example

### Input envelope

```json
{
  "mode": "fetch",
  "tool_id": "kma_weather_alert_status",
  "params": {}
}
```

### Output envelope (success)

```json
{
  "tool_id": "kma_weather_alert_status",
  "result": {
    "total_count": 2,
    "warnings": [
      {
        "stn_id": "108",
        "title": "[특보] 제05-63호 : 2026.05.18.15:00 / 건조주의보 발표 (*)",
        "tm_fc": "202605181500",
        "tm_ef": null,
        "tm_seq": 63,
        "area_code": null,
        "area_name": null,
        "warn_var": null,
        "warn_stress": null,
        "cancel": 0,
        "command": null,
        "warn_fc": null
      },
      {
        "stn_id": "109",
        "title": "[특보] 제05-10호 : 2026.05.18.15:00 / 건조주의보 발표 (*)",
        "tm_fc": "202605181500",
        "tm_ef": null,
        "tm_seq": 10,
        "area_code": null,
        "area_name": null,
        "warn_var": null,
        "warn_stress": null,
        "cancel": 0,
        "command": null,
        "warn_fc": null
      }
    ]
  }
}
```

### Conversation snippet

```text
Citizen: 지금 전국에 기상특보 발효 중인 거 있어요?
UMMAYA: 현재 2건의 기상특보 발표가 조회됩니다. 2026년 5월 18일 15:00 기준 기상청 본청과 부산지방기상청 발표 건조주의보가 포함되어 있습니다.
```

## Constraints

- **Rate limit**: `rate_limit_per_minute=10`; data.go.kr daily quota applies per API key.
- **Freshness window**: `cache_ttl_seconds=300` (5 minutes). KMA typically updates active alerts within minutes of issuance or cancellation.
- **Fixture coverage gaps**: The wire response may return a single dict instead of a list when exactly one warning is active — the adapter normalizes this automatically. Compact responses (`stnId`, `title`, `tmFc`, `tmSeq`) are observed live; all non-required `WeatherWarning` fields may be `None`.
- **Error envelope examples**:
  - Tier-1 fail (no active alerts): `resultCode="03"` is treated as a normal empty result, not an error. Output will be `{"total_count": 0, "warnings": []}`.
  - Network timeout: `httpx.TimeoutException` propagates as `ToolExecutionError` after 30 s.
  - XML response guard: If the upstream ignores `_type=json` and returns XML, a `ToolExecutionError` is raised with a content-type hint.
