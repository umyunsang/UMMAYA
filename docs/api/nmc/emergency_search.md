---
tool_id: nmc_emergency_search
primitive: lookup
tier: live
permission_tier: 1
spec_version: v4
last_updated: 2026-05-05
---

# nmc_emergency_search

## Overview

Queries the National Medical Center (국립중앙의료원) public emergency medical institution location endpoint for the nearest ERs around a given WGS-84 coordinate. Returns a ranked list of emergency medical institutions with safety-enriched field names. This endpoint does not expose real-time bed counts; a future sibling adapter must wrap `getEmrrmRltmUsefulSckbdInfoInqire` if KOSMOS needs bed-count data.

| Field | Value |
|---|---|
| Classification | Live · Permission tier 1 (read-only public lookup) |
| Source | National Medical Center (NMC) / data.go.kr B552657 |
| Primitive | `lookup` |
| Module | `src/kosmos/tools/nmc/emergency_search.py` |
| Spec version | v4 (Spec 2522 — URL encoding safety + 5-section description) |

### v4 Changes (Spec 2522 T022)

1. **URL encoding safety**: The adapter enforces `httpx params={}` dict for all query parameters. Raw Korean string interpolation into URLs is prohibited — non-ASCII characters in query strings cause HTTP 400 from the NMC/data.go.kr upstream (evidence: `/tmp/kosmos-evidence/medical-evidence.md § Test 1`). The `params={}` dict approach delegates percent-encoding to httpx automatically, preventing this class of regression.

2. **5-section description**: `llm_description` is now built via `build_description_v4()` (`src/kosmos/tools/_description_template.py`) with five sections: purpose · input_quirk · short_reference · domain_quirk · self_contained_decl. Token budget: 324/500 tokens (≤100 per section, ≤500 combined).

3. **input_quirk section now mentions Korean URL encoding quirk** — if STAGE1/STAGE2 administrative division names (한국어 문자열) are ever used as query params in future endpoint migration, string interpolation must not be used.

## Envelope

**Input model**: `NmcEmergencySearchInput` defined at `src/kosmos/tools/nmc/emergency_search.py:41–77`.

| Field | Type | Required | Description |
|---|---|---|---|
| `lat` | `float` (-90 to 90) | yes | Latitude of the search origin in decimal degrees (WGS-84). Obtain from `resolve_location(want='coords')`. Example: `37.5665` for central Seoul. |
| `lon` | `float` (-180 to 180) | yes | Longitude of the search origin in decimal degrees (WGS-84). Obtain from `resolve_location(want='coords')`. Example: `126.9780` for central Seoul. |
| `limit` | `int` (1–100) | yes | Maximum number of nearest emergency rooms to return. All three fields are required with no defaults — the LLM must supply explicit values. |

**Output model (public read-only data)**: `LookupCollection` dict returned by `handle()`.

| Field | Type | Required | Description |
|---|---|---|---|
| `kind` | `str` ("collection") | yes | Envelope type discriminator. |
| `items` | `list[dict]` | yes | ER records — see "Item-level field semantics" below for the enriched per-record schema. |
| `total_count` | `int` | yes | Total matching ER records from NMC. |
| `meta` | `dict` | yes | Freshness metadata. `{"freshness_status": "fresh"}` when data is within threshold (or `"not_applicable"` when the location-static endpoint variant is used and `hvidate` is uniformly absent). |

### Item-level field semantics (Spec 2637 Epic F)

The upstream `getEgytLcinfoInqire` endpoint returns abbreviated fields whose names invite the LLM to render them as ER hours. The adapter rewrites every item via `_enrich_item` BEFORE the LLM ever sees the response.

**Removed (safety-critical)** — these raw upstream fields are stripped:

| Raw field | Why stripped |
|---|---|
| `startTime` | Means *outpatient (외래) consultation start time* (typically Monday's `dutyTime1s` from `getEgytBassInfoInqire`), NOT the emergency-room operating window. Live evidence (Jongno-gu, 2026-05-04): all five returned hospitals (incl. SNUH권역응급의료센터 + NMC지역응급의료센터 — both 24/7 ER) have startTime ∈ {0800, 0830, 0900}. Surfacing as "운영시간 08:30" produced the snap-010 mis-info. |
| `endTime` | Same reason — the institution's outpatient close time (e.g. 1700, 1800), NOT ER close time. ER never closes. |

**Added (LLM-visible enriched fields)**:

| Field | Type | Description |
|---|---|---|
| `er_24h_operating` | `bool` (always `True`) | Every record from this endpoint is a registered 응급의료기관 per 응급의료에 관한 법률 §31 = 365-day 24-hour ER operation. |
| `er_operating_hours_note` | `str` | Korean explanatory note instructing the LLM that `outpatient_*_time` ≠ ER hours. |
| `outpatient_open_time` | `str | None` | Outpatient (외래) clinic open time, `HH:MM` format. Derived from raw `startTime`. Example: `"08:30"`. |
| `outpatient_close_time` | `str | None` | Outpatient (외래) clinic close time, `HH:MM` format. Derived from raw `endTime`. Example: `"17:00"`. |
| `outpatient_hours_display` | `str | None` | Human-readable display string with the literal `(외래진료)` label. Example: `"08:30~17:00 (외래진료)"`. |
| `hospital_main_phone` | `str` | Aliased from `dutyTel1`. The hospital's **main switchboard**, NOT the ER hotline (`dutyTel3` is omitted by this endpoint variant). |
| `er_phone_note` | `str` | Korean note clarifying that `dutyTel1` is not the ER direct number; recommends 119 or the sibling `getEgytBassInfoInqire` for ER hotline lookups. |
| `hospital_type` | `str` | Aliased from `dutyDivName`. The institution's **hospital classification** (종합병원 / 병원 / 의원). |
| `hospital_type_note` | `str` | Korean note clarifying that `dutyDivName` is hospital type, NOT ER tier (`dutyEmclsName` from `getEgytListInfoInqire` carries the 권역/지역/시설 tier). |
| `_raw_outpatient_start_hhmm` | `str | int` | The raw upstream `startTime` value, preserved for explicit-access consumers. Underscore prefix signals "internal — do not surface". |
| `_raw_outpatient_end_hhmm` | `str | int` | The raw upstream `endTime` value, preserved similarly. |

**Passed through unchanged** (safe to surface):

| Field | Type | Description |
|---|---|---|
| `dutyName` | `str` | Institution name. |
| `dutyAddr` | `str` | Street address. |
| `distance` | `float` | Distance from search origin in kilometres. |
| `hpid` | `str` | NMC institution ID (e.g. `"A1100017"`). |
| `latitude` / `longitude` | `float` | WGS-84 coordinates of the institution. |
| `dutyDiv` | `str` | Hospital classification code (`"A"` = 종합병원). |
| `dutyTel1` / `dutyDivName` | `str` | Original upstream values — preserved for backward compatibility but new consumers should use the aliased `hospital_main_phone` / `hospital_type` fields. |
| `cnt`, `rnum`, `dutyFax` | various | Upstream metadata; not LLM-relevant. |

**Output model (stale data — fail-closed)**:

| Field | Type | Required | Description |
|---|---|---|---|
| `kind` | `str` ("error") | yes | Envelope type discriminator. |
| `reason` | `str` ("stale_data") | yes | `LookupErrorReason.stale_data`. |
| `message` | `str` | yes | Human-readable staleness description including data age and threshold in minutes. |
| `retryable` | `bool` (False) | yes | Stale data is not retryable — data must be refreshed upstream. |

## Search hints

- 한국어: `응급실`, `응급의료센터`, `국립중앙의료원`, `가까운 응급실`, `응급의료기관 위치`, `응급실 찾기`
- English: `emergency room`, `nearest emergency room`, `NMC`, `emergency medical institution`, `Korea emergency location`

## Endpoint

- **Source URL**: `https://apis.data.go.kr/B552657/ErmctInfoInqireService/getEgytLcinfoInqire`
- **Authentication**: service API key via `KOSMOS_DATA_GO_KR_API_KEY` (no citizen identity)
- **Query params** (httpx `params={}` dict — automatic percent-encoding):
  - `serviceKey`: API key string
  - `pageNo`: pagination page number (default 1)
  - `numOfRows`: result limit (from `inp.limit`)
  - `WGS84_LAT`: latitude as float
  - `WGS84_LON`: longitude as float
  - `_type`: `json`

### URL encoding safety (v4)

Korean string query params (e.g. `STAGE1=서울특별시`) MUST NOT be string-interpolated into URLs directly. Non-ASCII characters in raw URL query strings cause HTTP 400 from the NMC/data.go.kr upstream (documented in evidence file, `medical-evidence.md § NMC Test 1`). This adapter uses `httpx params={}` dict which delegates URL encoding to httpx automatically. Future callers adding Korean-string params must follow this same pattern.

## Freshness sub-tool

The freshness validation is implemented in `src/kosmos/tools/nmc/freshness.py`. It is an internal quality-control module invoked automatically by `handle()` before any response is returned.

**`check_freshness(hvidate_str, threshold_minutes=None)`**:
- Accepts the NMC `hvidate` field value (format: `YYYY-MM-DD HH:MM:SS` KST).
- Reads `settings.nmc_freshness_minutes` when `threshold_minutes` is `None`.
- Returns a frozen `FreshnessResult` dataclass with four fields: `is_fresh`, `data_age_minutes`, `threshold_minutes`, `hvidate_raw`.
- **Fail-closed design**: missing, empty, unparseable, or future-dated `hvidate` values all return `is_fresh=False` unconditionally.

**`_evaluate_freshness(items)`** (`emergency_search.py`): computes the worst-case freshness across all returned ER items. If any single item is missing `hvidate` or is stale, the entire batch is rejected.

The freshness threshold is configurable via `KOSMOS_NMC_FRESHNESS_MINUTES` (default 30 minutes). The threshold is visible in every stale-data error message so the LLM can relay the exact age and threshold to the citizen.

## Permission tier rationale

This adapter is classified as Permission tier 1 because the current `getEgytLcinfoInqire` call returns public emergency medical institution location metadata. KOSMOS sends the coordinates derived from the citizen's place query plus a service API key; it does not send citizen identity, resident registration data, health records, or a user-specific entitlement token. The tool policy is therefore `citizen_facing_gate="read-only"` and the lookup permission modal must not open for "nearby ER" questions. Future NMC adapters that combine citizen identity, clinical context, submissions, or real-time bed-routing decisions must be implemented as separate tools with their own stricter policy gate and citation.

## Worked example

### Input envelope

```json
{
  "mode": "fetch",
  "tool_id": "nmc_emergency_search",
  "params": {
    "lat": 37.5665,
    "lon": 126.9780,
    "limit": 3
  }
}
```

### Output envelope (success — enriched item shape from the location endpoint)

```json
{
  "tool_id": "nmc_emergency_search",
  "result": {
    "kind": "collection",
    "items": [
      {
        "dutyName": "서울대학교병원",
        "dutyAddr": "서울특별시 종로구 대학로 101 (연건동)",
        "distance": 1.88,
        "hpid": "A1100017",
        "latitude": 37.57966608924356,
        "longitude": 126.99896308412191,
        "er_24h_operating": true,
        "er_operating_hours_note": "응급실은 365일 24시간 운영 (응급의료에 관한 법률 §31). outpatient_open_time/outpatient_close_time 은 외래진료(=일반 외래) 시간이며 응급실 운영시간이 아님.",
        "outpatient_open_time": "08:00",
        "outpatient_close_time": "18:00",
        "outpatient_hours_display": "08:00~18:00 (외래진료)",
        "hospital_main_phone": "02-1588-5700",
        "er_phone_note": "dutyTel1 = 병원 대표번호. 응급실 직통(dutyTel3) 은 본 endpoint 에서 미제공 — 의료기관 기본정보(getEgytBassInfoInqire) 또는 119 안내 권장.",
        "hospital_type": "종합병원",
        "hospital_type_note": "dutyDivName 은 의료기관 종별(종합병원/병원/의원), 응급의료센터 등급 아님. 본 endpoint 의 모든 결과는 응급의료기관 등록 시설 (24시간 응급실 운영)."
      }
    ],
    "total_count": 76,
    "meta": {
      "freshness_status": "not_applicable"
    }
  }
}
```

> Note: `startTime` / `endTime` are **never** present in the LLM-visible items — they are stripped by `_enrich_item` and replaced by the explicitly-labelled outpatient fields above. This is the safety-critical behaviour that prevents an "응급실 운영시간 08:30~17:00" mis-rendering during an emergency. See `tests/tools/nmc/test_field_semantics_enrichment.py` for the regression suite.

### Output envelope (stale data — fail-closed)

```json
{
  "tool_id": "nmc_emergency_search",
  "result": {
    "kind": "error",
    "reason": "stale_data",
    "message": "NMC data is stale: 35 min old (threshold: 30 min)",
    "retryable": false
  }
}
```

### Conversation snippet (correct rendering — Spec 2637 Epic F)

```text
Citizen: 지금 종로구에서 가까운 응급실 알려줘.
KOSMOS: 종로구 인근 응급실 (모두 24시간 운영):
  1. 강북삼성병원 — 1.12km · 02-2001-2001 (대표번호)
  2. 서울적십자병원 — 1.27km · 02-2002-8000 (대표번호)
  3. 서울대학교병원 (권역응급의료센터) — 1.88km · 02-1588-5700 (대표번호)
응급 상황은 119에 직접 전화하시는 것이 가장 빠릅니다. (위 병원들의 외래진료 시간은 08:00~18:00 정도이지만 응급실은 365일 24시간 열려 있습니다.)
```

> **Anti-pattern** (the snap-010 mis-rendering this Epic fixes — DO NOT emit):
> ~~"강북삼성병원 - 운영시간: 08:30~17:00"~~ — this conflates the institution's outpatient (외래) clinic hours with the ER, putting a citizen at risk during a real emergency.

## Constraints

- **Rate limit**: `rate_limit_per_minute=10`; NMC API quota applies per service key.
- **Freshness window**: `cache_ttl_seconds=0` — no client-side caching. Freshness threshold is controlled by `KOSMOS_NMC_FRESHNESS_MINUTES` (default 30 minutes). Stale responses are rejected rather than degraded.
- **URL encoding** (v4): All query parameters are passed via `httpx params={}` dict — never string-interpolated into URLs. This prevents HTTP 400 from non-ASCII characters in query strings (documented in `medical-evidence.md § NMC Test 1`).
- **Fixture coverage gaps**: CI tests do not call the live endpoint (AGENTS.md hard rule: never call live `data.go.kr` APIs from CI). Fixture shapes cover the coordinate location endpoint and the sibling real-time freshness fields used by regression tests.
- **Error envelope summary**:
  - Stale data (freshness SLO): `{"kind": "error", "reason": "stale_data", "message": "NMC data is stale: N min old (threshold: M min)", "retryable": false}`.
  - Missing API key: `{"kind": "error", "reason": "upstream_unavailable", "message": "KOSMOS_DATA_GO_KR_API_KEY is not configured", "retryable": false}`.
  - Non-JSON upstream response: `{"kind": "error", "reason": "upstream_unavailable", "message": "NMC API returned non-JSON content-type: ...", "retryable": true}`.
  - NMC API error code: `{"kind": "error", "reason": "upstream_unavailable", "message": "NMC API error: resultCode=...", "retryable": true}`.
