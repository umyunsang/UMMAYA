---
tool_id: kma_forecast_fetch
primitive: find
tier: live
permission_tier: 1
---

# kma_forecast_fetch

## Overview

Fetches a KMA short-term weather forecast (단기예보, ~3 days) for a location specified as WGS-84 coordinates, projecting them internally to the KMA Lambert Conformal Conic grid. Returns a `LookupTimeseries` with one point per forecast hour carrying temperature, precipitation probability, precipitation amount, and sky condition.

| Field | Value |
|---|---|
| Classification | Live · Permission tier 1 |
| Source | KMA (기상청) — VilageFcstInfoService_2.0/getVilageFcst |
| Primitive | `find` |
| Module | `src/ummaya/tools/kma/forecast_fetch.py` |

## Envelope

**Input model**: `KmaForecastFetchInput` defined at `src/ummaya/tools/kma/forecast_fetch.py:52-93`.

| Field | Type | Required | Description |
|---|---|---|---|
| `lat` | `float` | yes | WGS-84 latitude in decimal degrees (−90 to 90). For Korean locations typically 33–38. Obtain via `resolve_location(want='coords')`. |
| `lon` | `float` | yes | WGS-84 longitude in decimal degrees (−180 to 180). For Korean locations typically 126–130. Obtain via `resolve_location(want='coords')`. |
| `base_date` | `str` | yes | Forecast base date in `YYYYMMDD` format (e.g. `"20260416"`). |
| `base_time` | `str` | yes | Forecast base time in `HHMM` format. Must be one of: `0200`, `0500`, `0800`, `1100`, `1400`, `1700`, `2000`, `2300` (KST). |

**Output model**: `LookupTimeseries` (from `ummaya.tools.models`) returned by `_fetch()` at `src/ummaya/tools/kma/forecast_fetch.py:170-321`.

| Field | Type | Required | Description |
|---|---|---|---|
| `kind` | `str` | yes | Always `"timeseries"`. |
| `points` | `list[dict]` | yes | One dict per forecast hour, sorted by `timestamp_iso`. Each point contains `timestamp_iso` (ISO-8601 KST naive, e.g. `"2026-04-26T14:00:00"`), `temperature_c` (`float \| None`), `pop_pct` (`int \| None`), `precipitation_mm` (`str \| None`, e.g. `"강수없음"` or `"1.0mm"`), `sky_code` (`str \| None`; `"1"`=clear, `"3"`=cloudy, `"4"`=overcast), `interval` (always `"hour"`). |
| `interval` | `str` | yes | Always `"hour"`. |
| `meta` | `LookupMeta` | yes | Contains `source="kma_forecast_fetch"`, `fetched_at` (UTC datetime), `request_id` (UUID), `elapsed_ms`. |

On domain or upstream errors the adapter returns a `LookupError` dict with `kind="error"`, `reason` (enum: `invalid_params`, `out_of_domain`, `upstream_unavailable`, `timeout`), `message`, and optional `retryable`.

## Search hints

- 한국어: `단기예보`, `날씨`, `기온`, `강수확률`, `하늘상태`, `좌표 입력 날씨`, `위도경도 날씨`
- English: `short-term weather forecast`, `temperature precipitation`, `forecast by coordinates`, `lat lon weather`, `KMA grid forecast`

## Endpoint

- **data.go.kr endpoint**: `1360000/VilageFcstInfoService_2.0/getVilageFcst`
- **Source URL**: https://www.data.go.kr/data/15084084/openapi.do
- **Authentication**: API key via `UMMAYA_DATA_GO_KR_API_KEY` (per Constitution IV)

## Permission tier rationale

This adapter is classified as Permission tier 1 (green) per Spec 033 (`specs/033-permission-v2-spectrum/spec.md`). It wraps the same KMA `getVilageFcst` endpoint as `kma_short_term_forecast` but accepts WGS-84 coordinates instead of a pre-computed grid point, making it easier to compose with `resolve_location`. `pipa_class=non_personal`, `auth_level=AAL1`, and `is_irreversible=False`. Coordinates passed by the user are used only to compute the KMA grid cell — they are not stored, logged, or treated as personal data. `cache_ttl_seconds=0` is set (no caching) because forecast data at fine spatial and temporal resolution changes with every publication cycle and stale cache would degrade forecast accuracy.

## Worked example

### Input envelope

```json
{
  "mode": "fetch",
  "tool_id": "kma_forecast_fetch",
  "params": {
    "lat": 37.5665,
    "lon": 126.9780,
    "base_date": "20260426",
    "base_time": "1100"
  }
}
```

### Output envelope (success)

```json
{
  "tool_id": "kma_forecast_fetch",
  "result": {
    "kind": "timeseries",
    "interval": "hour",
    "points": [
      {
        "timestamp_iso": "2026-04-26T12:00:00",
        "temperature_c": 19.0,
        "pop_pct": 10,
        "precipitation_mm": "강수없음",
        "sky_code": "1",
        "interval": "hour"
      },
      {
        "timestamp_iso": "2026-04-26T13:00:00",
        "temperature_c": 20.0,
        "pop_pct": 20,
        "precipitation_mm": "강수없음",
        "sky_code": "3",
        "interval": "hour"
      }
    ],
    "meta": {
      "source": "kma_forecast_fetch",
      "fetched_at": "2026-04-26T02:14:37Z",
      "request_id": "a1b2c3d4-0000-0000-0000-000000000001",
      "elapsed_ms": 412
    }
  }
}
```

### Conversation snippet

```text
Citizen: 서울 시청 근처 내일 날씨를 알려주세요. 비가 올 확률도요.
UMMAYA: 서울 시청(위도 37.5665, 경도 126.9780) 2026년 4월 26일 오전 11시 발표 단기예보입니다. 오후 12시 기온 19°C, 강수확률 10%, 하늘 맑음(SKY=1)으로 예보되어 있습니다. 오후 1시에는 기온 20°C, 강수확률 20%, 구름 많음(SKY=3)으로 변할 것으로 예상됩니다. 비가 올 가능성은 낮습니다.
```

## Constraints

- **Rate limit**: data.go.kr daily quota: 1,000 requests per API key. In-adapter rate limit: 10 requests/minute (`rate_limit_per_minute=10`).
- **Freshness window**: KMA publishes 8 times/day. `cache_ttl_seconds=0` (no cache). Coordinates outside the KMA Lambert domain (approximately 33–38°N, 126–130°E) return a `LookupError` with `reason="out_of_domain"`.
- **Fixture coverage gaps**: `precipitation_mm` values are raw KMA strings (`"강수없음"`, `"1.0mm"`, `"30.0~50.0mm"`) and require caller-side parsing. TMN/TMX items appear once per day; they will be present in `points` but not at every hour. `sky_code` may be `None` for hours beyond the 3-day window.
- **Error envelope examples**:
  - Tier-1 fail: `{"kind": "error", "reason": "upstream_unavailable", "message": "KMA API error: resultCode='03' resultMsg='NO_DATA'", "retryable": false}`
  - Domain error: `{"kind": "error", "reason": "out_of_domain", "message": "Coordinates (lat=35.0, lon=120.0) are outside the KMA Lambert domain."}`
  - Tier-2 / Tier-3 (auth) fail: `{"error": {"code": "CONFIGURATION_ERROR", "message": "Missing required environment variable: UMMAYA_DATA_GO_KR_API_KEY"}}`
  - Network timeout: `{"kind": "error", "reason": "timeout", "message": "Network error reaching KMA forecast API: timed out", "retryable": true}`
