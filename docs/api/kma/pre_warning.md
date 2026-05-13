---
tool_id: kma_pre_warning
primitive: find
tier: live
permission_tier: 1
---

# kma_pre_warning

## Overview

Retrieves the list of weather pre-warning (기상예비특보) announcements from the Korea Meteorological Administration (기상청), providing early notification of developing weather events before formal warnings are issued.

| Field | Value |
|---|---|
| Classification | Live · Permission tier 1 |
| Source | Korea Meteorological Administration (KMA) / data.go.kr |
| Primitive | `find` |
| Module | `src/ummaya/tools/kma/kma_pre_warning.py` |

## Envelope

**Input model**: `KmaPreWarningInput` defined at `src/ummaya/tools/kma/kma_pre_warning.py:39–59`.

| Field | Type | Required | Description |
|---|---|---|---|
| `num_of_rows` | `int` (≥1, default 100) | no | Number of rows per page (`numOfRows` wire parameter). |
| `page_no` | `int` (≥1, default 1) | no | Page number, 1-indexed (`pageNo` wire parameter). |
| `stn_id` | `str \| None` | no | Station/region ID filter. If omitted, results from all stations are returned. Example: `108` for Seoul, `159` for Busan. |
| `data_type` | `Literal["JSON", "XML"]` (default "JSON") | no | Response format (`dataType` wire parameter). Always leave as "JSON". |

**Output model**: `KmaPreWarningOutput` defined at `src/ummaya/tools/kma/kma_pre_warning.py:80–89`.

| Field | Type | Required | Description |
|---|---|---|---|
| `total_count` | `int` | yes | Total number of pre-warning items available on the upstream. |
| `items` | `list[PreWarningItem]` | yes | Pre-warning announcement items for the requested page. |

Each `PreWarningItem` (defined at lines 62–77) carries:

| Field | Type | Required | Description |
|---|---|---|---|
| `stn_id` | `str` | yes | Station/region ID that issued the pre-warning. |
| `title` | `str` | yes | Announcement title (e.g., `[예비] 제06-7호 : 2017.06.07.07:30`). |
| `tm_fc` | `str` | yes | Announcement time in YYYYMMDDHHMI format. |
| `tm_seq` | `int` | yes | Monthly sequence number of this announcement. |

## Search hints

- 한국어: `기상예비특보`, `예비특보`, `태풍예고`, `호우예고`, `대설예고`, `한파예고`, `폭염예고`, `강풍예고`
- English: `weather pre-warning`, `preliminary weather alert`, `typhoon advance notice`, `heavy-rain pre-warning`, `snow pre-warning`, `cold-wave pre-warning`, `heat pre-warning`, `wind pre-warning`

## Endpoint

- **data.go.kr endpoint**: `1360000/WthrWrnInfoService/getWthrPwnList`
- **Source URL**: https://apis.data.go.kr/1360000/WthrWrnInfoService/getWthrPwnList
- **Authentication**: API key via `UMMAYA_DATA_GO_KR_API_KEY` (per Constitution IV)

## Permission tier rationale

This adapter is classified as Permission tier 1 because it returns entirely non-personal, publicly broadcast meteorological pre-warning information (`pipa_class="non_personal"`, `is_personal_data=False`). Pre-warnings are KMA's advance public safety announcements — no citizen-specific data is requested or returned. The optional `stn_id` parameter filters by geographic region, not by citizen identity. Spec 033 defines tier 1 as the baseline for read-only, non-personal government data.

## Worked example

### Input envelope

```json
{
  "mode": "fetch",
  "tool_id": "kma_pre_warning",
  "params": {
    "num_of_rows": 10,
    "page_no": 1,
    "stn_id": "108"
  }
}
```

### Output envelope (success)

```json
{
  "tool_id": "kma_pre_warning",
  "result": {
    "total_count": 3,
    "items": [
      {
        "stn_id": "108",
        "title": "[예비] 제26-5호 : 2026.04.26.09:00",
        "tm_fc": "202604260900",
        "tm_seq": 5
      },
      {
        "stn_id": "108",
        "title": "[예비] 제26-4호 : 2026.04.24.14:00",
        "tm_fc": "202604241400",
        "tm_seq": 4
      }
    ]
  }
}
```

### Conversation snippet

```text
Citizen: 서울에 곧 기상경보가 발령될 예정인가요?
UMMAYA: 서울(108) 기상예비특보 목록에서 최근 공지를 확인했습니다. 가장 최근 예비특보는 '2026년 4월 26일 09:00' 기준 '[예비] 제26-5호'입니다. 예비특보는 정식 기상특보 발령 전 사전 안내이므로, 이후 기상경보로 격상될 수 있습니다. 기상청 발표를 지속적으로 확인하시기 바랍니다.
```

## Constraints

- **Rate limit**: `rate_limit_per_minute=10`; data.go.kr daily quota applies per API key.
- **Freshness window**: `cache_ttl_seconds=300` (5 minutes). Pre-warnings are issued ahead of developing events; polling frequency can be reduced during calm weather.
- **Fixture coverage gaps**: The wire response may return a single dict instead of a list when exactly one pre-warning exists — the adapter normalizes this automatically. When no pre-warnings are active, `resultCode="03"` is returned by KMA and the adapter yields `{"total_count": 0, "items": []}`.
- **Error envelope examples**:
  - Tier-1 fail (no pre-warnings active): `resultCode="03"` → `{"total_count": 0, "items": []}` (not an error).
  - API error: `resultCode` other than `"00"` or `"03"` → `ToolExecutionError` with code and message.
  - XML response guard: If the upstream ignores `_type=json` and returns XML, a `ToolExecutionError` is raised with a content-type hint.
  - Network timeout: `httpx.TimeoutException` propagates as `ToolExecutionError` after 30 s.
