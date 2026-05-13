---
tool_id: hira_hospital_search
primitive: find
tier: live
permission_tier: 1
spec_version: v4
---

# hira_hospital_search

## Overview

Searches HIRA's (건강보험심사평가원) hospital registry for medical facilities within a
specified WGS84 coordinate radius. Returns ranked results including name, address,
phone number, institution type, and distance.

**v4 changes (Spec 2522 US2)**:
- HTTP request param corrected from `type=json` → `_type=json` (underscore prefix).
  `type=json` and `dataType=JSON` are silently ignored by the HIRA API — both return XML.
- `llm_description` rewritten to Spec 2522 5-section format via `build_description_v4()`.
  Section 2 (input_quirk) now explicitly documents the agency naming convention:
  `xPos = longitude (lon)` / `yPos = latitude (lat)`.

| Field | Value |
|---|---|
| Classification | Live · Permission tier 1 |
| Source | Health Insurance Review and Assessment Service (HIRA) / data.go.kr |
| Primitive | `find` |
| Module | `src/ummaya/tools/hira/hospital_search.py` |
| Evidence | `/tmp/ummaya-evidence/medical-evidence.md § 1. HIRA` |

## Envelope

**Input model**: `HiraHospitalSearchInput` — `src/ummaya/tools/hira/hospital_search.py:40–88`.

| Field | Type | Required | Description |
|---|---|---|---|
| `xPos` | `float` (124.0–132.0) | yes | Longitude (lon) in WGS84 decimal degrees. Korean range: 124–132. Agency param name "xPos" = longitude by HIRA naming convention. Obtain from `resolve_location(want='coords')` — never guess. |
| `yPos` | `float` (33.0–39.0) | yes | Latitude (lat) in WGS84 decimal degrees. Korean range: 33–39. Agency param name "yPos" = latitude by HIRA naming convention. Obtain from `resolve_location(want='coords')` — never guess. |
| `radius` | `int` (1–10000, default 2000) | no | Search radius in meters. Maximum 10,000 m. Increase only if initial results are empty. |
| `pageNo` | `int` (≥1, default 1) | no | Page number for pagination (1-based). |
| `numOfRows` | `int` (1–100, default 20) | no | Number of rows per page. |

**Output model**: `LookupCollection` dict — `src/ummaya/tools/hira/hospital_search.py:95–213`.

| Field | Type | Required | Description |
|---|---|---|---|
| `kind` | `str` ("collection") | yes | Envelope type discriminator. |
| `items` | `list[dict]` | yes | Hospital records. Empty list when `resultCode="03"` (no data). |
| `total_count` | `int` | yes | Total matching records upstream (may exceed `numOfRows`). |

Each `items` entry:

| Field | Type | Notes |
|---|---|---|
| `ykiho` | `str` | HIRA unique institution identifier for follow-up detail queries. |
| `yadmNm` | `str` | Hospital/clinic name. |
| `addr` | `str` | Street address. |
| `telno` | `str` | Phone number. |
| `clCd` | `str` | Institution type code. |
| `clCdNm` | `str` | Institution type name (e.g., `의원`, `병원`, `종합병원`, `상급종합`). |
| `xPos` | `float \| None` | Institution longitude (from response field `XPos`, capital X). |
| `yPos` | `float \| None` | Institution latitude (from response field `YPos`, capital Y). |
| `distance` | `float \| None` | Distance from search origin in meters. Response is a high-precision decimal string — adapter does not parse; callers must convert via `float()`. |
| `sidoCdNm` | `str` | City/province name. |
| `sgguCdNm` | `str` | District name. |

## Search hints

- 한국어: `병원 검색`, `진료과목`, `의료기관 정보`, `근처 병원`, `내과`, `외과`, `소아과`, `치과`, `한의원`
- English: `hospital search`, `medical specialty`, `clinic nearby`, `healthcare provider`, `HIRA`, `Korea hospital`, `nearby medical facility`

## Endpoint

- **data.go.kr service**: `B551182/hospInfoServicev2/getHospBasisList`
- **Full URL**: https://apis.data.go.kr/B551182/hospInfoServicev2/getHospBasisList
- **Authentication**: API key via `UMMAYA_DATA_GO_KR_API_KEY` (per Constitution IV)
- **JSON format param**: `_type=json` (underscore prefix — agency quirk; `type=json` returns XML)

## Permission tier rationale

Classified as Permission tier 1: returns publicly searchable institutional information
about registered medical facilities (`pipa_class="non_personal"`). The HIRA hospital
registry is published for public benefit under HIRA's open data policy. Input contains
only geographic coordinates and a radius — no citizen identity is transmitted.
Coordinates are lookup parameters, not citizen profile data. Spec 033 defines tier 1
as the baseline for read-only, non-personal government data.

Policy citation: https://www.hira.or.kr/bbs/informationNotice.do?pgmid=HIRAA030011000000

## Worked example

### Input envelope

```json
{
  "mode": "fetch",
  "tool_id": "hira_hospital_search",
  "params": {
    "xPos": 127.047,
    "yPos": 37.517,
    "radius": 2000,
    "pageNo": 1,
    "numOfRows": 5
  }
}
```

Note: `xPos=127.047` is **longitude** (강남구 경도), `yPos=37.517` is **latitude** (강남구 위도).
HIRA's parameter naming reversal (x=lon, y=lat) is the agency standard — not a UMMAYA convention.

### Output envelope (success)

```json
{
  "tool_id": "hira_hospital_search",
  "result": {
    "kind": "collection",
    "items": [
      {
        "ykiho": "JDQ4MTg4MSM1MSMkMSMkMCMkODkkMzgxMzUxIzExIyQxIyQzIyQ3OSQ0NjEwMDIjNjEjJDEjJDQjJDgz",
        "yadmNm": "강북삼성병원",
        "addr": "서울특별시 종로구 새문안로 29",
        "telno": "02-2001-2001",
        "clCd": "01",
        "clCdNm": "상급종합",
        "xPos": 126.9677,
        "yPos": 37.5684,
        "distance": 935.52,
        "sidoCdNm": "서울특별시",
        "sgguCdNm": "종로구"
      }
    ],
    "total_count": 48
  }
}
```

### Conversation snippet

```text
Citizen: 강남구에서 2km 이내 병원 찾아줘.
UMMAYA: 강남구 반경 2km 이내 병원 48곳을 찾았습니다. 가장 가까운 곳은 '강북삼성병원' (상급종합) 으로 약 936m 거리, 전화 02-2001-2001 입니다.
```

## Constraints

- **Rate limit**: `rate_limit_per_minute=10`; data.go.kr daily quota applies per API key.
- **Freshness**: `cache_ttl_seconds=0` — no client-side caching. HIRA registry updates at irregular intervals.
- **JSON format quirk (v4 fix)**: The `_type=json` param (underscore prefix) is mandatory for
  JSON responses. `type=json` and `dataType=JSON` are silently ignored — API returns XML. See
  evidence: `/tmp/ummaya-evidence/medical-evidence.md § HIRA Key Findings`.
- **Coordinate naming quirk**: Input `xPos`=longitude / `yPos`=latitude (agency naming convention).
  Response fields are uppercase: `XPos`/`YPos` (capital X and Y). The adapter normalises these
  to lowercase `xPos`/`yPos` in output items.
- **Distance field type**: Response `distance` is a high-precision decimal string
  (e.g. `"935.52085158947152138489499336459860718"`), not a float. Callers must convert via `float()`.
- **Single-item normalisation**: When exactly one hospital is found, HIRA returns a dict instead
  of a list. The adapter normalises this to `[dict]`.
- **Error envelopes**:
  - No results: `resultCode="03"` → `{"kind": "collection", "items": [], "total_count": 0}`.
  - API error: `resultCode` other than `"00"` / `"03"` → `ToolExecutionError`.
  - XML guard: If upstream returns XML (wrong format param), `ToolExecutionError` is raised.
  - Network timeout: `httpx.TimeoutException` propagates after 30 s.
