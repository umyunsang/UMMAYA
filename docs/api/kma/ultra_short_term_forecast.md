---
tool_id: kma_ultra_short_term_forecast
primitive: find
tier: live
permission_tier: 1
---

# kma_ultra_short_term_forecast

## Overview

Fetches the KMA ultra-short-term forecast (초단기예보) for a grid point, covering the next 6 hours at hourly resolution. The live API accepts `HHMM` request times and may canonicalize the response rows to the actually published `baseTime`. Returns the same pivot-row item format as the short-term forecast.

| Field | Value |
|---|---|
| Classification | Live · Permission tier 1 |
| Source | KMA (기상청) — VilageFcstInfoService_2.0/getUltraSrtFcst |
| Primitive | `find` |
| Module | `src/ummaya/tools/kma/kma_ultra_short_term_forecast.py` |

## Envelope

**Input model**: `KmaUltraShortTermForecastInput` defined at `src/ummaya/tools/kma/kma_ultra_short_term_forecast.py:44-95`.

| Field | Type | Required | Description |
|---|---|---|---|
| `base_date` | `str` | yes | Forecast base date in `YYYYMMDD` format. |
| `base_time` | `str` | yes | Forecast base time in valid `HHMM` format (e.g. `0630`, `1130`, `1500`, `1529`). Live evidence on 2026-05-18 showed KMA accepts non-`HH30` values and canonicalizes returned rows to the published `baseTime`. |
| `nx` | `int` | yes | KMA Lambert grid X coordinate (1–149). |
| `ny` | `int` | yes | KMA Lambert grid Y coordinate (1–253). |
| `num_of_rows` | `int` | no | Rows per page. Default `60` (6 hours × ~10 categories). |
| `page_no` | `int` | no | 1-indexed page number. Default `1`. |
| `data_type` | `Literal["JSON", "XML"]` | no | Response format. Default `"JSON"`. XML is rejected at call time. |

**Output model**: `KmaUltraShortTermForecastOutput` (alias for `KmaShortTermForecastOutput`) defined at `src/ummaya/tools/kma/kma_ultra_short_term_forecast.py:98`.

| Field | Type | Required | Description |
|---|---|---|---|
| `total_count` | `int` | yes | Total forecast items available for this query. |
| `items` | `list[ForecastItem]` | yes | Up to 60 forecast pivot rows. Each `ForecastItem` carries `base_date`, `base_time`, `fcst_date`, `fcst_time`, `nx`, `ny`, `category`, `fcst_value`. Categories are a subset of the short-term forecast: `T1H` (temperature), `RN1` (precipitation), `SKY` (sky), `UUU`, `VVV`, `VEC` (wind), `WSD` (wind speed), `PTY` (precipitation type), `REH` (humidity), `LGT` (lightning). |

## Search hints

- 한국어: `초단기예보`, `6시간 예보`, `기온`, `강수`, `하늘상태`, `습도`, `풍속`, `번개`
- English: `ultra-short-term forecast`, `6-hour weather`, `temperature precipitation`, `sky condition`, `wind speed`, `lightning`

## Endpoint

- **data.go.kr endpoint**: `1360000/VilageFcstInfoService_2.0/getUltraSrtFcst`
- **Source URL**: https://www.data.go.kr/data/15084084/openapi.do
- **Authentication**: API key via `UMMAYA_DATA_GO_KR_API_KEY` (per Constitution IV)

## Permission tier rationale

This adapter is classified as Permission tier 1 (green) per Spec 033 (`specs/033-permission-v2-spectrum/spec.md`). Ultra-short-term forecast data is public meteorological information with no personal data (`pipa_class=non_personal`, `auth_level=AAL1`). The call is read-only and concurrency-safe. `cache_ttl_seconds=600` (10 minutes) matches the half-hourly publication cadence; a shorter TTL than the short-term forecast is intentional because the ultra-short-term data is updated more frequently. No consent prompt is required.

## Worked example

### Input envelope

```json
{
  "mode": "fetch",
  "tool_id": "kma_ultra_short_term_forecast",
  "params": {
    "base_date": "20260426",
    "base_time": "1330",
    "nx": 61,
    "ny": 125,
    "num_of_rows": 60,
    "page_no": 1
  }
}
```

### Output envelope (success)

```json
{
  "tool_id": "kma_ultra_short_term_forecast",
  "result": {
    "total_count": 60,
    "items": [
      {
        "base_date": "20260426",
        "base_time": "1330",
        "fcst_date": "20260426",
        "fcst_time": "1400",
        "nx": 61,
        "ny": 125,
        "category": "T1H",
        "fcst_value": "19"
      },
      {
        "base_date": "20260426",
        "base_time": "1330",
        "fcst_date": "20260426",
        "fcst_time": "1400",
        "nx": 61,
        "ny": 125,
        "category": "SKY",
        "fcst_value": "1"
      }
    ]
  }
}
```

### Conversation snippet

```text
Citizen: 지금부터 6시간 동안 서울 날씨가 어떻게 될까요?
UMMAYA: 2026년 4월 26일 13시 30분 기준 서울(격자 61, 125) 초단기예보(향후 6시간)입니다. 오후 2시 기온은 19°C이며 하늘상태는 맑음(SKY=1)입니다. 강수는 예측되지 않습니다. 전체 60개 예보 항목을 조회했습니다.
```

## Constraints

- **Rate limit**: data.go.kr daily quota: 1,000 requests per API key. In-adapter rate limit: 10 requests/minute (`rate_limit_per_minute=10`).
- **Freshness window**: `cache_ttl_seconds=600`. KMA may return rows whose `base_time` differs from the requested `base_time`; the response row's `base_time` is authoritative. Requesting a time before data is available may still return a `NO_DATA` error.
- **Fixture coverage gaps**: `LGT` (lightning) category is only included when there is a lightning risk; fixtures may not cover this path. The output model is shared with `kma_short_term_forecast` — TMN/TMX and WAV categories do not appear in ultra-short-term data and are never present in `items`.
- **Error envelope examples**:
  - Tier-1 fail: `{"error": {"code": "TOOL_EXECUTION_ERROR", "tool_id": "kma_ultra_short_term_forecast", "message": "KMA API error: resultCode='03' resultMsg='NO_DATA'"}}`
  - Tier-2 / Tier-3 (auth) fail: `{"error": {"code": "CONFIGURATION_ERROR", "message": "Missing required environment variable: UMMAYA_DATA_GO_KR_API_KEY"}}`
  - Network timeout: `{"error": {"code": "TOOL_EXECUTION_ERROR", "tool_id": "kma_ultra_short_term_forecast", "message": "Network error reaching KMA ultra-short-term forecast API: connection refused"}}`
