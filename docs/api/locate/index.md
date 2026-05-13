---
tool_id: locate
primitive: locate
tier: live
permission_tier: 1
---

# locate

## Overview

`locate` converts Korean place references into provider-specific location data by calling one of five live locate adapters. The root tool is an envelope:

```json
{
  "tool_id": "kakao_keyword_search",
  "params": {
    "query": "동아대학교 승학캠퍼스"
  }
}
```

The model must choose a provider adapter from the dynamic `<available_adapters>` block and fill that adapter's schema directly. Coordinates, administrative codes, and region names must come from a locate adapter response, never from model memory.

| Adapter | Provider endpoint | Use when |
|---|---|---|
| `kakao_address_search` | Kakao Local `search/address` | Road/jibun address or district text |
| `kakao_keyword_search` | Kakao Local `search/keyword` | Campus, station, landmark, hospital, or POI name |
| `kakao_coord_to_region` | Kakao Local `coord2regioncode` | A prior coordinate result must be converted to `q0`/`q1` names or a 10-digit code |
| `juso_adm_cd_lookup` | JUSO address-link `addrLinkApi.do` | A Korean address must produce a 10-digit `adm_cd` |
| `sgis_adm_cd_lookup` | SGIS `rgeocodewgs84` | A prior coordinate result must produce a 10-digit `adm_cd` through SGIS |

## Envelope

**Input model**: provider-specific. The root `locate` schema accepts `tool_id` and `params`, then validates `params` against the selected adapter.

**Output model**: location result union from `src/ummaya/tools/models.py`, including coordinates, address, POI, administrative code, region, bundle, or structured error.

## Search hints

- Korean: `주소`, `위치`, `좌표`, `행정동코드`, `도로명주소`, `지번주소`, `장소검색`
- English: `geocode`, `location`, `coordinates`, `administrative code`, `address`, `place search`, `reverse geocode`

## Endpoint

- Kakao Local API: `https://dapi.kakao.com/v2/local/search/address.json`, `https://dapi.kakao.com/v2/local/search/keyword.json`, `https://dapi.kakao.com/v2/local/geo/coord2regioncode.json`
- JUSO address-link API: `https://business.juso.go.kr/addrlink/addrLinkApi.do`
- SGIS reverse geocoding API: `https://sgisapi.mods.go.kr/OpenAPI3/addr/rgeocodewgs84.json`

Authentication is operator-managed through packaged runtime configuration: `UMMAYA_KAKAO_API_KEY`, `UMMAYA_JUSO_CONFM_KEY`, `UMMAYA_SGIS_KEY`, and `UMMAYA_SGIS_SECRET`.

## Permission tier rationale

Locate adapters are permission tier 1 because they resolve non-personal place references and return public location data. Coordinates and administrative region codes are read-only public data. No citizen identity assertion is required.

## Worked example

```text
Citizen: 동아대학교 승학캠퍼스 근처 응급실 찾아줘.
UMMAYA: calls locate(tool_id="kakao_keyword_search", params={"query": "동아대학교 승학캠퍼스"})
UMMAYA: calls locate(tool_id="kakao_coord_to_region", params={"lat": 35.115446, "lon": 128.967669})
UMMAYA: uses those live results as inputs to downstream `find` adapters.
```

## Constraints

- Do not invent coordinates, KMA grid values, region names, or administrative codes.
- Use `kakao_keyword_search` for named places and POIs.
- Use `kakao_address_search` or `juso_adm_cd_lookup` for structured addresses or district text.
- Use `kakao_coord_to_region` or `sgis_adm_cd_lookup` only after a coordinate-producing adapter has returned lat/lon.
