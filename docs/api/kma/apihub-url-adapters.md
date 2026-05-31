# KMA APIHub URL Adapters

This note covers official KMA APIHub endpoints that are not
`typ02/openApi`. They are registered separately from the structured APIHub
adapter because their responses are text, image, or binary products rather than
the standard `response.header/body/items.item` envelope.

## Scope

- Source host: `https://apihub.kma.go.kr`
- API families: `typ01/url`, `typ01/cgi-bin`, and `typ07`
- Registered operations: 5
- Credential env var: `UMMAYA_KMA_API_HUB_AUTH_KEY`
- Auth query parameter: `authKey`
- Runtime mode: live call with fail-closed approval errors

Direct `curl` probes showed approved, callable responses for the decoded-METAR,
AMOS, high-resolution grid, AWS objective-analysis, and analyzed weather-chart
image URL products. The analyzed weather-chart image product was re-probed on
2026-05-27 after APIHub utilization approval and returned `200 OK` with
`image/png`. All URL wrappers fail closed on upstream errors and must not
fabricate weather values.

## Registered URL Operations

| Tool id | Official product | Endpoint | Selection rule |
|---|---|---|---|
| `kma_apihub_url_air_metar_decoded` | Aviation weather decoded METAR/SPECI text | `/api/typ01/url/air_metar_dec.php` | Primary approved decoded-METAR route while structured `AmmIwxxmService/getMetar` returns `APPLICATION_ERROR`. |
| `kma_apihub_url_air_amos_minute` | Aviation weather AMOS minute data | `/api/typ01/url/amos.php` | Supported-airport runway-area current conditions. Official station list includes Gimpo `110`; it does not list Gimhae. |
| `kma_apihub_url_high_resolution_grid_point` | Convergence weather 500m high-resolution analyzed grid point | `/api/typ01/url/sfc_nc_var.php` | Analyzed point weather values for WGS-84 coordinates, especially when a citizen asks for `분석자료`, `고해상도 격자자료`, or objective-analysis values. |
| `kma_apihub_url_aws_objective_analysis_grid` | Ground observation AWS objective-analysis grid | `/api/typ01/cgi-bin/aws/nph-aws_min_obj` | AWS objective-analysis grid products, not single-airport METAR or ordinary address forecasts. |
| `kma_apihub_url_analysis_weather_chart_image` | Numerical model analyzed weather-chart image | `/api/typ07/afsiwa/iwa/api/iwaImgUrlApi/retRecreateImgUrl.kfrm` | Analyzed synoptic weather-chart image or metadata requests. |

## Flight-Weather Routing

For a citizen query like "김해공항에서 김포공항으로 가는 비행편 날씨와
항공기상":

1. Resolve airport names to aviation identifiers when possible.
2. Prefer `kma_apihub_url_air_metar_decoded` for the approved KMA decoded-METAR
   channel while the structured IWXXM `AmmIwxxmService/getMetar` endpoint
   returns `APPLICATION_ERROR`. Use `RKPK` for Gimhae and `RKSS` for Gimpo when
   an aviation operation accepts ICAO.
3. Use `kma_apihub_url_air_amos_minute` only when the airport is in the
   official AMOS station list. Gimpo is listed as `110`; Gimhae is not listed on
   the APIHub AMOS page.
4. Use high-resolution analyzed grid data only as supporting area/weather
   analysis. It is useful because KMA has already applied objective analysis,
   but it is not a substitute for official aviation METAR/AMOS wording.
5. If APIHub returns 403 or another upstream error, report that official KMA
   APIHub lookup failed and name the channel; do not fall back to invented
   weather interpretation.

## Official Source Mapping

- Aviation category and METAR/SPECI:
  `https://apihub.kma.go.kr/apiList.do?seqApi=14`
- AMOS minute data:
  `https://apihub.kma.go.kr/apiList.do?apiMov=기상청+AMOS+매분자료+조회&seqApi=14&seqApiSub=259`
- 500m high-resolution grid analyzed data:
  `https://apihub.kma.go.kr/apiList.do?apiMov=1.+고해상도+격자자료+조회(해상도:+500m)&seqApi=971&seqApiSub=936`
- AWS objective analysis:
  `https://apihub.kma.go.kr/apiList.do?apiMov=AWS%20객관분석&seqApi=2&seqApiSub=248`
- Analyzed weather-chart image:
  `https://apihub.kma.go.kr/apiList.do?apiMov=1.+(그래픽)+분석일기도+조회&seqApi=9&seqApiSub=285`
