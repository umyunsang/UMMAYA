// SPDX-License-Identifier: Apache-2.0
// UMMAYA-original — LocatePrimitive prompt strings.

export const LOCATE_TOOL_NAME = 'locate'

/** Citizen-facing English description shown to the LLM. */
export const DESCRIPTION =
  'Discover Korean location adapters. Prefer concrete location adapter functions loaded by ToolSearch or backend retrieval; locate is a legacy wrapper only.'

/** Extended prompt included in the system-prompt tool-use section. */
export const LOCATE_TOOL_PROMPT = `Resolve Korean location phrases with concrete location adapters.

Preferred path:
- Call concrete adapter functions directly after their schemas are loaded.
- Examples: kakao_keyword_search({ query: "부산 사하구 다대1동" }) or kakao_coord_to_region({ lat: 35.115446, lon: 128.967669 })
- Adapter schemas are progressively disclosed by ToolSearch or by backend top-K retrieval for the current citizen request.

Legacy root wrapper:
- If a concrete adapter function is not loaded and only the root primitive is available, locate accepts { tool_id, params } for old transcripts and compatibility paths.
- tool_id must be a concrete locate adapter id from <available_adapters>, never "locate", "find", "check", or "send".
- Invalid: locate({ tool_id: "locate", params: {...} })
- Compatibility-only: locate({ tool_id: "kakao_address_search", params: { query: "부산 사하구 다대1동" } })

Rules:
- Use kakao_keyword_search for named places, campuses, stations, landmarks, hospitals, and POIs.
- Coordinate-producing locate results may include KMA nx/ny; pass those exact values to KMA weather adapters that require nx and ny.
- Use kakao_address_search or juso_adm_cd_lookup for structured road/jibun addresses and district text.
- Use kakao_coord_to_region after a coordinate result when a downstream adapter needs q0/q1 or region names.
- If the result is kind="error", do not invent coordinates or administrative codes.`
