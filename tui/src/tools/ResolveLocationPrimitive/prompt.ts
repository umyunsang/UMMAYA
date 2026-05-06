// SPDX-License-Identifier: Apache-2.0
// KOSMOS — ResolveLocationPrimitive prompt strings.
// Mirrors the CC Tool prompt convention while exposing the KOSMOS citizen
// location primitive as a first-class Tool object.

export const RESOLVE_LOCATION_TOOL_NAME = 'resolve_location'

export const DESCRIPTION =
  '시민 발화의 물리적 위치, 주소, 행정동, 관공서, 역, 병원, POI를 좌표와 행정코드로 변환합니다. 온라인 행정 서비스명에는 호출하지 말고 실제 장소가 필요한 후속 lookup 전에 사용하세요.'

export const RESOLVE_LOCATION_TOOL_PROMPT = `Resolve a Korean physical place reference into location identifiers.

Input:
  { query: string, want?: "coords" | "adm_cd" | "coords_and_admcd" | "road_address" | "jibun_address" | "poi" | "all", near?: [number, number] }

Use this tool only for physical places: addresses, districts, stations, offices, hospitals, landmarks, and walk-in centers.
Do not use it for online-only service names such as Hometax, Government24, certificates, or mobile ID unless the citizen asks for a physical office/location.

For location-dependent public data, call resolve_location first, then pass only returned coordinates or administrative codes into the matching lookup adapter.`
