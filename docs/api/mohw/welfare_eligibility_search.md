---
tool_id: mohw_welfare_eligibility_search
primitive: lookup
tier: live
permission_tier: 1
---

# mohw_welfare_eligibility_search

## Overview

Searches the SSIS (한국사회보장정보원) central-ministry welfare service catalog at bokjiro.go.kr for services matching life stage, household type, interest theme, age, or keyword. Returns a ranked list with service ID, name, ministry, summary, online-apply flag, and bokjiro.go.kr detail link.

As of Spec 2522 US4, the adapter has a **real handle() implementation** (XML parser + camelCase wire param mapping). The citizen_facing_gate is `read-only` — no authentication required to browse the public welfare catalog.

| Field | Value |
|---|---|
| Classification | Live · Permission tier 1 (read-only public catalog) |
| Source | Ministry of Health and Welfare (MOHW) via Korea Social Security Information Service (SSIS) / data.go.kr |
| Primitive | `lookup` |
| Module | `src/kosmos/tools/mohw/welfare_eligibility_search.py` |

## Envelope

**Input model**: `MohwWelfareEligibilitySearchInput` defined at `src/kosmos/tools/mohw/welfare_eligibility_search.py`.

| Field | Type | Required | Description |
|---|---|---|---|
| `search_wrd` | `str \| None` (max 100 chars) | no | Free-text keyword in Korean. Example: `출산`. Omit to filter by codes only. |
| `life_array` | `LifeArrayCode \| None` | no | Life-stage filter. See life-stage codes table below. |
| `trgter_indvdl_array` | `TrgterIndvdlCode \| None` | no | Target individual/household-type filter. Example: `020` for 다자녀, `040` for 장애인, `050` for 저소득. |
| `intrs_thema_array` | `IntrsThemaCode \| None` | no | Interest-theme filter. Authoritative 임신·출산 code: `080`. `010` = 신체건강. |
| `age` | `int \| None` (0–150) | no | Citizen age in years. Do NOT request without citizen consent. |
| `onap_psblt_yn` | `Literal["Y", "N"] \| None` | no | Filter to online-applicable services only when `"Y"`. Omit for both. |
| `order_by` | `OrderBy` (default `popular`) | no | Sort order: `popular` (조회 수) or `date` (등록순). |
| `page_no` | `int` (1–1000, default 1) | no | Page number. SSIS caps at 1000. |
| `num_of_rows` | `int` (1–500, default 10) | no | Records per page. Maximum 500 per SSIS contract. |

> **Auto-injected wire params (T026)**: `callTp=L` and `srchKeyCode=003` are always added by the adapter and must not be supplied in the LLM input. They are internal implementation details of `_build_params()`.

**Life-stage codes (`life_array`)**:

| Code | Label |
|---|---|
| `001` | 영유아 (infants and toddlers, 0–6세) |
| `002` | 아동 (children, 7–12세) |
| `003` | 청소년 (youth, 13–18세) |
| `004` | 청년 (young adults, 19–34세) |
| `005` | 중장년 (middle-aged, 35–64세) |
| `006` | 노년 (elderly, 65세+) |
| `007` | 임신·출산 (pregnancy and childbirth) |

**Output model**: `MohwWelfareEligibilitySearchOutput` defined in the same module.

| Field | Type | Required | Description |
|---|---|---|---|
| `result_code` | `str` | yes | Result code (`"0"` = SUCCESS in SSIS v2.0). |
| `result_message` | `str` | yes | Human-readable result message. |
| `page_no` | `int` | yes | Requested page number. |
| `num_of_rows` | `int` | yes | Rows per page. |
| `total_count` | `int` | yes | Total matching welfare services. |
| `items` | `list[SsisWelfareServiceItem]` | yes | Welfare service records. Empty list when no services match. |

Each `SsisWelfareServiceItem` carries:

| Field | Type | Required | Description |
|---|---|---|---|
| `servId` | `str` | yes | Service ID (e.g., `WLF00000056`). |
| `servNm` | `str` | yes | Service name (서비스명). |
| `jurMnofNm` | `str` | yes | Ministry name (소관부처명). |
| `jurOrgNm` | `str \| None` | no | Bureau name (소관조직명). |
| `inqNum` | `str \| None` | no | View count (raw string). |
| `servDgst` | `str \| None` | no | Service summary (서비스 요약). |
| `servDtlLink` | `str \| None` | no | Detail link (bokjiro.go.kr URL). |
| `svcfrstRegTs` | `str \| None` | no | Service registration date. |
| `lifeArray` | `str \| None` | no | Life stage label (human-readable, e.g., `"임신 · 출산"`). |
| `intrsThemaArray` | `str \| None` | no | Interest theme tags (comma-separated). |
| `trgterIndvdlArray` | `str \| None` | no | Target household type tags. |
| `sprtCycNm` | `str \| None` | no | Support cycle (e.g., `1회성`). |
| `srvPvsnNm` | `str \| None` | no | Provision type (e.g., `전자바우처`). |
| `rprsCtadr` | `str \| None` | no | Contact information. |
| `onapPsbltYn` | `Literal["Y", "N"] \| None` | no | Online application available. |

## Search hints

- 한국어: `복지서비스`, `출산`, `보조금`, `복지혜택`, `신청`, `사회보장정보원`, `보건복지부`, `임산부 지원`, `육아`, `장애인 복지`
- English: `welfare benefit`, `eligibility search`, `childbirth subsidy`, `MOHW`, `SSIS`, `social security Korea`, `welfare service catalog`, `government benefit`

## Endpoint

- **data.go.kr endpoint**: `B554287/NationalWelfareInformationsV001/NationalWelfarelistV001`
- **Source URL**: `https://apis.data.go.kr/B554287/NationalWelfareInformationsV001/NationalWelfarelistV001`
- **Authentication**: API key via `KOSMOS_DATA_GO_KR_API_KEY` (per Constitution IV)
- **Response format**: UTF-8 XML only (no JSON option)

## Implementation notes (Spec 2522 US4)

- `handle()` issues an async HTTP GET via `traced_async_client` and parses the UTF-8 XML response using `xml.etree.ElementTree` (stdlib only — zero new deps).
- `_build_params()` converts pydantic snake_case fields to camelCase wire params (`life_array→lifeArray`, `num_of_rows→numOfRows`, etc.) and always injects `callTp=L` + `srchKeyCode=003` (T026).
- `_parse_xml_response()` walks `<response>/<servList>/<servList>` (SSIS reuses the tag name for items), extracting the 15 documented fields per item. Items missing `servId` or `servNm` are silently dropped as malformed.
- The adapter previously raised `Layer3GateViolation` as an interface-only stub. US4 replaces this with the real implementation and changes `citizen_facing_gate` from `"login"` to `"read-only"`.

## Worked example

### Input envelope

```json
{
  "mode": "fetch",
  "tool_id": "mohw_welfare_eligibility_search",
  "params": {
    "life_array": "007",
    "intrs_thema_array": "080",
    "onap_psblt_yn": "Y",
    "order_by": "popular",
    "num_of_rows": 5
  }
}
```

### Output envelope (success, from live evidence lifeArray=007)

```json
{
  "result_code": "0",
  "result_message": "정상 처리되었습니다.",
  "page_no": 1,
  "num_of_rows": 5,
  "total_count": 21,
  "items": [
    {
      "servId": "WLF00000056",
      "servNm": "의료급여(요양비)",
      "jurMnofNm": "보건복지부",
      "jurOrgNm": "기초의료보장과",
      "lifeArray": "임신 · 출산",
      "intrsThemaArray": "신체건강,임신·출산",
      "trgterIndvdlArray": "저소득",
      "onapPsbltYn": "Y",
      "servDtlLink": "https://www.bokjiro.go.kr/ssis-tbu/twataa/wlfareInfo/moveTWAT52011M.do?wlfareInfoId=WLF00000056"
    }
  ]
}
```

### Conversation snippet

```text
Citizen: 임산부 복지 혜택이 뭐가 있나요?
KOSMOS: 임신·출산 관련 복지 서비스를 조회했습니다. 총 21개 서비스 중 온라인 신청 가능한 서비스를 안내드립니다.
  1. 의료급여(요양비) — 저소득 임산부 대상, 보건복지부 기초의료보장과
     상세: bokjiro.go.kr/.../WLF00000056
더 많은 서비스 목록을 보시겠습니까?
```

## Constraints

- **Rate limit**: `rate_limit_per_minute=10`; data.go.kr daily quota applies per API key.
- **Freshness**: `cache_ttl_seconds=0` — no client-side caching. SSIS catalog is managed by the Korea Social Security Information Service and may update at any time.
- **Wire format**: XML only. The `_type=json` parameter used by some data.go.kr APIs is NOT supported by this endpoint; the adapter always sends XML.
- **SSIS resultCode convention**: `"0"` (single digit) = SUCCESS. This differs from most data.go.kr APIs that use `"00"`. The adapter treats both `"0"` and `"00"` as success.
- **Error codes**: Non-`"0"` resultCode raises `ToolExecutionError` with the SSIS error message. Common cause: invalid API key or missing required params.
- **age field**: Must not be requested from a citizen without explicit consent (PII under PIPA).
