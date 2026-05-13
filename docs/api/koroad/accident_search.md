---
tool_id: koroad_accident_search
primitive: find
tier: live
permission_tier: 1
---

# koroad_accident_search

## Overview

Queries the authoritative KOROAD accident-prone hotspot dataset for a Korean municipality by province/city code (2-digit `siDo`), district code (3-digit `guGun`), and dataset year category, returning ranked hazard zones with coordinates and casualty statistics.

**v4 change**: `siDo` field description corrected to "2-digit 광역시도" and `guGun` to "3-digit 시군구". Prior docs showing 4-digit codes (e.g. `"1100"`, `"1168"`) were wire-param misunderstandings — the API only accepts the 2+3-digit split scheme confirmed by live evidence (`/tmp/ummaya-evidence/koroad-mohw-evidence.md`). `KOROAD_SIDO_SHORT_REFERENCE` (17 시도 inline table) is now embedded directly in the `si_do` field description.

| Field | Value |
|---|---|
| Classification | Live · Permission tier 1 |
| Source | KOROAD (도로교통공단) — B552061/frequentzoneLg |
| Primitive | `find` |
| Module | `src/ummaya/tools/koroad/koroad_accident_search.py` |

## Envelope

**Input model**: `KoroadAccidentSearchInput` defined at `src/ummaya/tools/koroad/koroad_accident_search.py`.

| Field | Type | Required | Description |
|---|---|---|---|
| `search_year_cd` | `SearchYearCd` | yes | Dataset year/category code (`searchYearCd` wire parameter). Enum value maps to a specific annual release ID (e.g. `"2025119"` for 2024 general data). |
| `si_do` | `SidoCode` | yes | **2-digit** 광역시도 code (`siDo` wire parameter). Must be obtained from a prior `resolve_location` call — never filled from model memory. Short reference: `서울=11 부산=12 대구=22 인천=23 광주=24 대전=25 울산=26 세종=27 경기=13 강원=14 충북=15 충남=16 전북=17 전남=18 경북=19 경남=20 제주=21`. Valid values defined in `SidoCode` enum. |
| `gu_gun` | `GugunCode` | yes | **3-digit** 시군구 code (`guGun` wire parameter). Must be paired with the corresponding `si_do` value and obtained via `resolve_location`. Do NOT use 4-digit 행정구역코드 (e.g. `"1168"`) — only the 3-digit form (e.g. `"680"`) is accepted. Valid values defined in `GugunCode` enum. |
| `num_of_rows` | `int` | no | Rows per page (1–100). Default `10`. |
| `page_no` | `int` | no | 1-indexed page number. Default `1`. |

**Output model**: `KoroadAccidentSearchOutput` defined at `src/ummaya/tools/koroad/koroad_accident_search.py`.

| Field | Type | Required | Description |
|---|---|---|---|
| `total_count` | `int` | yes | Total hotspot records matching the query. |
| `page_no` | `int` | yes | Current page number returned. |
| `num_of_rows` | `int` | yes | Rows per page as requested. |
| `hotspots` | `list[AccidentHotspot]` | yes | Ranked accident hotspot zones. Empty list when no records exist. Each element contains `spot_cd`, `spot_nm`, `sido_sgg_nm`, `bjd_cd`, `occrrnc_cnt`, `caslt_cnt`, `dth_dnv_cnt`, `se_dnv_cnt`, `sl_dnv_cnt`, `wnd_dnv_cnt`, `la_crd`, `lo_crd`, `geom_json` (nullable), `afos_id`, `afos_fid`. |

## Search hints

- 한국어: `교통사고 위험지역 조회`, `사고다발구역`, `지자체별 위험지점`, `도로 위험구역`
- English: `accident hotspot`, `dangerous zone`, `traffic safety municipality`, `road hazard zone`

## Endpoint

- **data.go.kr endpoint**: `B552061/frequentzoneLg/getRestFrequentzoneLg`
- **Source URL**: https://www.data.go.kr/data/15063424/openapi.do
- **Authentication**: API key via `UMMAYA_DATA_GO_KR_API_KEY` (per Constitution IV)

## Permission tier rationale

This adapter is classified as Permission tier 1 (green) per Spec 033 (`specs/033-permission-v2-spectrum/spec.md`). The endpoint returns aggregated, non-personal public safety data — accident zone statistics by administrative boundary with no individual-level personal information. `pipa_class` is `non_personal` and `auth_level` is `AAL1`. Because the data is read-only (`is_irreversible=False`) and does not expose personal data, no citizen consent prompt is required; the system may execute automatically once the user has initiated a lookup session.

## Worked example

### Input envelope

```json
{
  "mode": "fetch",
  "tool_id": "koroad_accident_search",
  "params": {
    "search_year_cd": "2025119",
    "si_do": 11,
    "gu_gun": 680,
    "num_of_rows": 5,
    "page_no": 1
  }
}
```

**Wire params sent to KOROAD**: `siDo=11` (2-digit), `guGun=680` (3-digit), `searchYearCd=2025119`, `type=json`.

### Output envelope (success)

```json
{
  "tool_id": "koroad_accident_search",
  "result": {
    "total_count": 3,
    "page_no": 1,
    "num_of_rows": 5,
    "hotspots": [
      {
        "spot_cd": "11680001",
        "spot_nm": "서울 강남구 역삼동(리춘시장 강남역점 부근)",
        "sido_sgg_nm": "서울 강남구1",
        "bjd_cd": "1168010100",
        "occrrnc_cnt": 63,
        "caslt_cnt": 68,
        "dth_dnv_cnt": 0,
        "se_dnv_cnt": 12,
        "sl_dnv_cnt": 52,
        "wnd_dnv_cnt": 4,
        "la_crd": 37.4979,
        "lo_crd": 127.0276,
        "geom_json": null,
        "afos_id": "2025119",
        "afos_fid": "6967684"
      }
    ]
  }
}
```

### Conversation snippet

```text
Citizen: 강남구에서 교통사고가 자주 발생하는 위험한 곳이 어디인지 알려주세요.
UMMAYA: 강남구(서울특별시)의 2024년 교통사고 사고다발구역 조회 결과입니다. 총 3개 위험지점이 확인되었으며,
        가장 사고 빈도가 높은 지점은 '역삼동 리춘시장 강남역점 부근'으로 2024년 한 해 63건의 사고가
        발생해 68명의 사상자가 나왔습니다. 좌표는 위도 37.4979, 경도 127.0276입니다.
```

## Constraints

- **Wire param format (v4)**: `siDo` is a **2-digit** integer (e.g. `11` for 서울). `guGun` is a **3-digit** integer (e.g. `680` for 강남구). 4-digit 행정구역코드 (e.g. `1100`, `1168`) are NOT accepted and will produce `NODATA_ERROR`. This is confirmed by live testing (`koroad-mohw-evidence.md § siDo/guGun Code Scheme`).
- **Rate limit**: data.go.kr daily quota: 1,000 requests per API key. In-adapter rate limit: 10 requests/minute (`rate_limit_per_minute=10`).
- **Freshness window**: Dataset is updated annually. The 2024 general dataset (`searchYearCd=2025119`) was published in 2025; new datasets typically release each spring. `cache_ttl_seconds=3600`.
- **Legacy sido codes**: `SidoCode.GANGWON_LEGACY` (42) and `SidoCode.JEONBUK_LEGACY` (45) are only valid for pre-2023 datasets. Use `SidoCode.GANGWON` (51) and `SidoCode.JEONBUK` (52) for 2023+ data. A `model_validator` enforces this constraint at input time.
- **Fixture coverage gaps**: Single-item response (exactly one hotspot) triggers a dict-not-list wire quirk normalized by `_normalize_items`. NODATA_ERROR (resultCode `"03"`) returns an empty `hotspots` list.
- **Error envelope examples**:
  - Tier-1 fail: `{"error": {"code": "TOOL_EXECUTION_ERROR", "tool_id": "koroad_accident_search", "message": "KOROAD API returned error: code='99' msg='SERVICE_ERROR'"}}`
  - Tier-2 / Tier-3 (auth) fail: `{"error": {"code": "CONFIGURATION_ERROR", "message": "Missing required environment variable: UMMAYA_DATA_GO_KR_API_KEY"}}`
  - Network timeout: `{"error": {"code": "TOOL_EXECUTION_ERROR", "tool_id": "koroad_accident_search", "message": "Network error: timed out after 30s"}}`
