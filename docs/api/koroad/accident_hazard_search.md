---
tool_id: koroad_accident_hazard_search
primitive: find
tier: live
permission_tier: 1
---

# koroad_accident_hazard_search

## Overview

Queries the KOROAD accident hazard spot dataset for a Korean municipality by 10-digit administrative code (`adm_cd`) and calendar year, returning a ranked collection of hazard locations with occurrence counts and casualty counts. GeoJSON geometry fields (`geom_json`, ~500 chars per item) are stripped from output to reduce LLM context window usage.

**v4 change**: `_strip_geom_json()` helper added — all output items no longer include the raw `geom_json` Polygon string. `llm_description` updated with 5-section format including ORDERING RULE and wire format notes. Both tools confirmed to use the same KOROAD `getRestFrequentzoneLg` endpoint; the differentiation is in input scheme (adm_cd vs 2+3-digit siDo/guGun).

| Field | Value |
|---|---|
| Classification | Live · Permission tier 1 |
| Source | KOROAD (도로교통공단) — B552061/frequentzoneLg |
| Primitive | `find` |
| Module | `src/ummaya/tools/koroad/accident_hazard_search.py` |

## Envelope

**Input model**: `AccidentHazardSearchInput` defined at `src/ummaya/tools/koroad/accident_hazard_search.py`.

| Field | Type | Required | Description |
|---|---|---|---|
| `adm_cd` | `str` | yes | 10-digit 행정동 administrative code. Must match pattern `^[0-9]{10}$`. Obtain via `resolve_location(want='adm_cd')`. Example: `'1168000000'` for 서울특별시 강남구. |
| `year` | `int` | yes | Calendar year for the accident dataset (2019–2100). The adapter maps the year to the correct KOROAD `searchYearCd` internally, including 2023+ code changes for 강원/전북. Example: `2024`. |
| `num_of_rows` | `int` (1–100, default 10) | no | Rows per page. Maps to official `numOfRows`. Verified by direct curl on 2026-05-06. |
| `page_no` | `int` (≥1, default 1) | no | 1-indexed page number. Maps to official `pageNo`. Verified by direct curl on 2026-05-06. |

**Output**: LookupCollection-shaped dict returned by `handle()`.

| Field | Type | Required | Description |
|---|---|---|---|
| `kind` | `str` | yes | Always `"collection"`. |
| `items` | `list[dict]` | yes | Ranked hazard spots. Each item contains `spot_nm`, `tot_dth_cnt`, `spot_cd`, `sido_sgg_nm`, `occrrnc_cnt`, `caslt_cnt`, `la_crd`, `lo_crd`. **`geom_json` is stripped** from all items by `_strip_geom_json()`. |
| `total_count` | `int` | yes | Total matching hazard records from the upstream API. |

## Search hints

- 한국어: `교통사고 위험지점`, `사고다발구역`, `행정동코드`, `연도별 위험지역`, `도로 위험구역 조회`
- English: `accident hazard spot`, `dangerous zone`, `adm_cd year`, `traffic safety Korea`, `road hazard by administrative code`

## Endpoint

- **data.go.kr endpoint**: `B552061/frequentzoneLg/getRestFrequentzoneLg`
- **Source URL**: https://www.data.go.kr/data/15063424/openapi.do
- **Authentication**: API key via `UMMAYA_DATA_GO_KR_API_KEY` (per Constitution IV)

## Permission tier rationale

This adapter is classified as Permission tier 1 (green) per Spec 033 (`specs/033-permission-v2-spectrum/spec.md`). The underlying endpoint is identical to `koroad_accident_search` — aggregated public road safety statistics with no individual personal data. `pipa_class` is `non_personal`, `auth_level` is `AAL1`, and `is_irreversible=False`. The distinguishing characteristic of this adapter is its simplified input interface (10-digit `adm_cd` + integer `year`), which makes it easier to call directly after a `resolve_location` step. No consent prompt is required; the adapter may execute automatically within a citizen lookup session.

## Worked example

### Input envelope

```json
{
  "mode": "fetch",
  "tool_id": "koroad_accident_hazard_search",
  "params": {
    "adm_cd": "1168000000",
    "year": 2024,
    "num_of_rows": 20,
    "page_no": 1
  }
}
```

The adapter internally maps `adm_cd="1168000000"` → `siDo=11` (2-digit, 서울), `guGun=680` (3-digit, 강남구) and `year=2024` → `searchYearCd="2025119"` before calling the KOROAD API. It passes `num_of_rows` / `page_no` as the official `numOfRows` / `pageNo` wire parameters.

### Output envelope (success)

```json
{
  "tool_id": "koroad_accident_hazard_search",
  "result": {
    "kind": "collection",
    "total_count": 3,
    "items": [
      {
        "spot_nm": "서울 강남구 역삼동(리춘시장 강남역점 부근)",
        "tot_dth_cnt": 0,
        "spot_cd": "11680001",
        "sido_sgg_nm": "서울 강남구1",
        "occrrnc_cnt": 63,
        "caslt_cnt": 68,
        "la_crd": 37.4979,
        "lo_crd": 127.0276
      }
    ]
  }
}
```

Note: `geom_json` is not present in output items — it is stripped by `_strip_geom_json()` before the dict is assembled.

### Conversation snippet

```text
Citizen: 강남구에서 작년에 교통사고가 많이 난 위험한 곳을 알려주세요.
UMMAYA: 2024년 강남구(adm_cd 1168000000) 교통사고 위험지점 조회 결과, 총 3개 지점이 확인되었습니다.
        가장 사고가 잦은 곳은 '역삼동 리춘시장 강남역점 부근'으로 연간 63건의 사고(총 68명 사상)가 발생했습니다.
        위치는 위도 37.4979, 경도 127.0276 근방입니다.
```

## Constraints

- **geom_json strip (v4)**: The `geom_json` field (GeoJSON Polygon string, ~500 chars per item) is removed from all output items by `_strip_geom_json()`. This reduces context window pressure without losing actionable information — the LLM cannot meaningfully render or reason over raw Polygon WKT.
- **siDo/guGun mapping**: The internal `_PREFIX5_TO_SIDO` / `_PREFIX5_TO_GUGUN` codebook maps 5-digit `adm_cd` prefixes to 2-digit `siDo` + 3-digit `guGun` wire params. Unknown prefixes fall back to a 2-digit sido heuristic. The mapping handles 2023+ code changes for 강원 (42→51) and 전북 (45→52).
- **부천시 split quirk**: 부천시 pre-2023 uses sub-gu codes 191/193/195; 2023+ uses unified 192. The adapter resolves this automatically based on `year`.
- **Rate limit**: data.go.kr daily quota: 1,000 requests per API key. In-adapter rate limit: 10 requests/minute (`rate_limit_per_minute=10`).
- **Freshness window**: Annual dataset; 2024 data uses `searchYearCd=2025119`. New datasets publish each spring. `cache_ttl_seconds=3600`.
- **Error envelope examples**:
  - Tier-1 fail: `{"error": {"code": "TOOL_EXECUTION_ERROR", "tool_id": "koroad_accident_hazard_search", "message": "KOROAD API error: code='99' msg='SERVICE_ERROR'"}}`
  - Tier-2 / Tier-3 (auth) fail: `{"error": {"code": "CONFIGURATION_ERROR", "message": "Missing required environment variable: UMMAYA_DATA_GO_KR_API_KEY"}}`
  - Network timeout: `{"error": {"code": "TOOL_EXECUTION_ERROR", "tool_id": "koroad_accident_hazard_search", "message": "Network error reaching KOROAD API: timed out after 30s"}}`
