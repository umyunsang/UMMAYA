# 15085288 기상청_생활기상지수 조회서비스(3.0)

## Collection Status
- Source: <https://www.data.go.kr/data/15085288/openapi.do>
- Provider: 기상청
- Department: 국가기후데이터센터
- Category: 과학기술 - 과학기술연구
- Service type: REST
- Response format: JSON+XML
- Application status: approved.
- Usage-list evidence: `[승인] 기상청_생활기상지수 조회서비스(3.0)`, 신청일 `2026-05-16`, 만료예정일 `2028-05-16`.
- Development quota: 10,000 calls/day per selected operation.
- Review policy: development account auto-approved, operation account auto-approved.
- Update cycle: real time.
- License: the detail page and application form show `이용허락범위 제한 없음`.

## Saved Artifacts
- `data-go-kr-detail.html`: data.go.kr detail page snapshot.
- `data-go-kr-inline-swagger.json`: inline Swagger/OpenAPI metadata extracted from the data.go.kr detail page.
- `data-go-kr-catalog.json`: JSON-LD dataset/catalog metadata from the detail page.
- `intake-record.json`: local intake metadata.

## Endpoint Summary
- Service URL: `https://apis.data.go.kr/1360000/LivingWthrIdxServiceV5`
- Supported schemes in portal Swagger: `https`, `http`

Operations:
- `GET /getUVIdxV5`: 자외선지수조회. Looks up forecast values from the announcement time through up to 75 hours later in 3-hour intervals.
- `GET /getAirDiffusionIdxV5`: 대기정체지수조회. Looks up forecast values from the announcement time through up to 78 hours later in 3-hour intervals.

Required request parameters:
- `ServiceKey`: data.go.kr service key. The official casing uses uppercase `S` and `K`.
- `areaNo`: weather-area/location code. The portal parameter description notes that Seoul is the reference and that blank can request all locations.
- `time`: announcement time. The portal example describes `2021-07-06 18:00` style 발표 time; confirm exact compact format during live probing before adapter release.

Optional request parameters:
- `pageNo`: page number.
- `numOfRows`: result count per page. The portal default is 10.
- `dataType`: response type, `XML` or `JSON`. The portal default is XML.

Common response fields include:
- `header.resultCode`: response message code.
- `header.resultMsg`: response message.
- `body.dataType`: response data type.
- `body.totalCount`: total result count.
- `body.pageNo`: current page number.
- `body.numOfRows`: rows per page.
- `body.items.item.code`: index code.
- `body.items.item.areaNo`: area/location code.
- `body.items.item.date`: announcement time.
- `body.items.item.h0`, `h3`, `h6`, ...: forecast values at 3-hour offsets.

Operation-specific horizon:
- UV index response fields run from `h0` through `h75`.
- Air-diffusion index response fields run from `h3` through `h78`.

## Domain Notes
The portal description says this service exposes KMA living-weather indices including ultraviolet index and air-stagnation index. It is suitable for public weather-safety lookup, outdoor activity planning, health/safety notices, research, and policy-support contexts.

The application form shows the public-data location-information warning. The adapter should accept official KMA area codes as explicit query parameters and should not store user location unless a later UMMAYA flow has the proper legal and permission review.

## Adapter Notes
- Suggested primitive: `lookup`.
- Suggested tool name: `kma_living_weather_index_lookup`.
- This is a read-only weather-safety index lookup adapter.
- Preserve official parameter casing: `ServiceKey`, `pageNo`, `numOfRows`, `dataType`, `areaNo`, `time`.
- Normalize the `h*` forecast columns into an array such as `{offset_hours, value}` while preserving the raw field names in debug/source metadata.
- Expose `index_type` as a controlled adapter enum mapping to `getUVIdxV5` or `getAirDiffusionIdxV5`.
- Require callers to provide `areaNo` and `time` until live probes confirm whether blank `areaNo` is accepted for all locations with the current gateway.

## Curl Shape
```bash
curl --get 'https://apis.data.go.kr/1360000/LivingWthrIdxServiceV5/getUVIdxV5' \
  --data-urlencode "ServiceKey=${DATA_GO_KR_SERVICE_KEY}" \
  --data-urlencode 'pageNo=1' \
  --data-urlencode 'numOfRows=10' \
  --data-urlencode 'dataType=JSON' \
  --data-urlencode 'areaNo=1100000000' \
  --data-urlencode 'time=2021070618'
```

```bash
curl --get 'https://apis.data.go.kr/1360000/LivingWthrIdxServiceV5/getAirDiffusionIdxV5' \
  --data-urlencode "ServiceKey=${DATA_GO_KR_SERVICE_KEY}" \
  --data-urlencode 'pageNo=1' \
  --data-urlencode 'numOfRows=10' \
  --data-urlencode 'dataType=JSON' \
  --data-urlencode 'areaNo=1100000000' \
  --data-urlencode 'time=2021070618'
```

## Implementation Cautions
- Do not persist or print the service key.
- Do not call this live endpoint from CI tests.
- Do not hardcode the example `areaNo` or `time`; they are request-shape placeholders until live fixture probing.
- Treat index values as official weather forecast data. The adapter should not invent health guidance; higher-level response generation must cite KMA and any separate official interpretation table if guidance is needed.
- Keep `dataType=JSON` in adapter fixture collection so parser behavior is stable.
