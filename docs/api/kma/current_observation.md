---
tool_id: kma_current_observation
primitive: find
tier: live
permission_tier: 1
---

# kma_current_observation

## Overview

Fetches the KMA ultra-short-term current observation (초단기실황) for a grid point, returning the most recently measured temperature, precipitation, humidity, wind speed, wind direction, and precipitation type as a flat observation record.

| Field | Value |
|---|---|
| Classification | Live · Permission tier 1 |
| Source | KMA (기상청) — VilageFcstInfoService_2.0/getUltraSrtNcst |
| Primitive | `find` |
| Module | `src/ummaya/tools/kma/kma_current_observation.py` |

## Envelope

**Input model**: `KmaCurrentObservationInput` defined at `src/ummaya/tools/kma/kma_current_observation.py:38-77`.

| Field | Type | Required | Description |
|---|---|---|---|
| `base_date` | `str` | yes | Observation base date in `YYYYMMDD` format. Validated by regex `\d{8}`. |
| `base_time` | `str` | yes | Observation base time in `HHMM` format. The validator normalizes any minute value to `HH00` (rounded down to the hour) to avoid "data not ready" errors. |
| `nx` | `int` | yes | KMA Lambert grid X coordinate (1–149). Obtain via `resolve_location` or `latlon_to_lcc`. |
| `ny` | `int` | yes | KMA Lambert grid Y coordinate (1–253). Obtain via `resolve_location` or `latlon_to_lcc`. |
| `num_of_rows` | `int` | no | Rows per page. Default `10`. |
| `page_no` | `int` | no | 1-indexed page number. Default `1`. |
| `data_type` | `Literal["JSON", "XML"]` | no | Response format. Default `"JSON"`. XML is rejected at call time. |

**Output model**: `KmaCurrentObservationOutput` defined at `src/ummaya/tools/kma/kma_current_observation.py:80-135`.

| Field | Type | Required | Description |
|---|---|---|---|
| `base_date` | `str` | yes | Observation date `YYYYMMDD`. |
| `base_time` | `str` | yes | Observation time `HHMM`. |
| `nx` | `int` | yes | Grid X coordinate. |
| `ny` | `int` | yes | Grid Y coordinate. |
| `t1h` | `float \| None` | no | Temperature in degrees Celsius. |
| `rn1` | `float` | yes | 1-hour accumulated precipitation in mm. Sentinel `"-"` normalized to `0.0`. |
| `uuu` | `float \| None` | no | East-west wind component in m/s (positive = eastward). |
| `vvv` | `float \| None` | no | North-south wind component in m/s (positive = northward). |
| `wsd` | `float \| None` | no | Wind speed in m/s. |
| `reh` | `float \| None` | no | Relative humidity in percent. |
| `pty` | `int` | yes | Precipitation type: 0=none, 1=rain, 2=rain+snow, 3=snow, 5=drizzle, 6=drizzle+snow, 7=snow flurry. |
| `vec` | `float \| None` | no | Wind direction in degrees (0–360, meteorological convention). |

## Search hints

- 한국어: `현재 날씨`, `기온`, `강수량`, `습도`, `풍속`, `초단기실황`, `관측`
- English: `current weather`, `temperature`, `precipitation`, `humidity`, `wind observation`, `real-time weather`

## Endpoint

- **data.go.kr endpoint**: `1360000/VilageFcstInfoService_2.0/getUltraSrtNcst`
- **Source URL**: https://www.data.go.kr/data/15084084/openapi.do
- **Authentication**: API key via `UMMAYA_DATA_GO_KR_API_KEY` (per Constitution IV)

## Permission tier rationale

This adapter is classified as Permission tier 1 (green) per Spec 033 (`specs/033-permission-v2-spectrum/spec.md`). KMA current observation data is public meteorological data with no personal information (`pipa_class=non_personal`, `auth_level=AAL1`). The call is read-only and idempotent (`is_irreversible=False`, `is_concurrency_safe=True`). Citizens expect weather lookups to execute without an explicit consent prompt; automatic execution within a session is appropriate. The short `cache_ttl_seconds=600` ensures data freshness while reducing API quota pressure.

## Worked example

### Input envelope

```json
{
  "mode": "fetch",
  "tool_id": "kma_current_observation",
  "params": {
    "base_date": "20260426",
    "base_time": "1400",
    "nx": 61,
    "ny": 125
  }
}
```

### Output envelope (success)

```json
{
  "tool_id": "kma_current_observation",
  "result": {
    "base_date": "20260426",
    "base_time": "1400",
    "nx": 61,
    "ny": 125,
    "t1h": 18.5,
    "rn1": 0.0,
    "uuu": -1.2,
    "vvv": 0.8,
    "wsd": 2.3,
    "reh": 55.0,
    "pty": 0,
    "vec": 245.0
  }
}
```

### Conversation snippet

```text
Citizen: 지금 서울 날씨가 어떤가요? 기온이랑 비 오는지 알고 싶어요.
UMMAYA: 2026년 4월 26일 오후 2시 기준 서울(격자 61, 125) 현재 날씨입니다. 기온은 18.5°C이며 현재 강수는 없습니다(강수유형: 없음). 풍속은 2.3 m/s, 습도는 55%입니다.
```

## Constraints

- **Rate limit**: data.go.kr daily quota: 1,000 requests per API key. In-adapter rate limit: 10 requests/minute (`rate_limit_per_minute=10`).
- **Freshness window**: KMA publishes observation data every hour (HH:00 KST). `cache_ttl_seconds=600` (10 minutes). Requesting a `base_time` more than ~1 hour in the past may return stale data.
- **Fixture coverage gaps**: The `rn1` sentinel normalization (`"-"` → `0.0`) is not represented by all recorded fixtures. Partial rows (fewer than the expected 8 categories) are silently handled by `_pivot_rows_to_output` leaving missing fields as `None`.
- **Error envelope examples**:
  - Tier-1 fail: `{"error": {"code": "TOOL_EXECUTION_ERROR", "tool_id": "kma_current_observation", "message": "KMA API error: resultCode='03' resultMsg='NO_DATA'"}}`
  - Tier-2 / Tier-3 (auth) fail: `{"error": {"code": "CONFIGURATION_ERROR", "message": "Missing required environment variable: UMMAYA_DATA_GO_KR_API_KEY"}}`
  - Network timeout: `{"error": {"code": "TOOL_EXECUTION_ERROR", "tool_id": "kma_current_observation", "message": "Network error reaching KMA API: timed out after 30s"}}`
