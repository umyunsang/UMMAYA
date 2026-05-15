# 15158980 대구광역시_수질정보 조회 서비스_GW

## Collection Status
- Source: <https://www.data.go.kr/data/15158980/openapi.do>
- Provider: 대구광역시
- Department: 상수도사업본부
- Category: 환경 - 상하수도·수질
- Service type: REST
- Response format: JSON
- Application status: approved.
- Usage-list evidence: `[승인] 대구광역시_수질정보 조회 서비스_GW`, 신청일 `2026-05-16`, 만료예정일 `2028-05-16`.
- Development quota: 10,000 calls/day.
- Review policy: development account auto-approved, operation account auto-approved.
- Update cycle: real time.
- License: the detail page shows `공공저작물 : 출처표시 (제 1유형)` and links the license policy; the application form displays `이용허락범위 제한 없음`.

## Saved Artifacts
- `data-go-kr-detail.html`: data.go.kr detail page snapshot.
- `data-go-kr-inline-swagger.json`: inline Swagger/OpenAPI metadata extracted from the data.go.kr detail page.
- `data-go-kr-catalog.json`: JSON-LD dataset/catalog metadata from the detail page.
- `intake-record.json`: local intake metadata.

## Endpoint Summary
- Service URL: `https://apis.data.go.kr/6270000/openData`
- Supported schemes in portal Swagger: `https`, `http`

Operation:
- `GET /WtrQuality`: 수질통계정보 조회.

Required request parameters:
- `serviceKey`: data.go.kr service key.
- `searchDate`: target year. The portal description says the response covers monthly values from January through December for the requested year.

Response fields include:
- `rsMsg.statusCode`: result status code.
- `rsMsg.message`: result message.
- `header`: item grouping/category header.
- `list.name`: water-treatment plant name.
- `list.codenm`: category/classification.
- `list.type`: water-quality item.
- `list.m1` through `list.m12`: monthly values for January through December for the plant and item.

## Domain Notes
The portal description states that the service covers Daegu Metropolitan City Waterworks Headquarters drinking-water quality statistics. The listed water-quality items include:
- turbidity
- pH
- residual chlorine

The portal description names major Daegu treatment plants including:
- 매곡
- 문산
- 공산
- 고산
- 가창

## Adapter Notes
- Suggested primitive: `lookup`.
- Suggested tool name: `daegu_water_quality_statistics_lookup`.
- This is a read-only drinking-water quality statistics lookup adapter.
- The adapter should expose `searchDate` as a required year field and normalize monthly columns into `{month, value}` records instead of leaving only `m1` through `m12`.
- Preserve `name`, `codenm`, and `type` because the same year can include multiple treatment plants and quality measurements.
- Output should include the source year and source URL so the agent can cite the municipal waterworks source.

## Curl Shape
```bash
curl --get 'https://apis.data.go.kr/6270000/openData/WtrQuality' \
  --data-urlencode "serviceKey=${DATA_GO_KR_SERVICE_KEY}" \
  --data-urlencode 'searchDate=2025'
```

## Implementation Cautions
- Do not persist or print the service key.
- Preserve exact official parameter casing: `serviceKey` and `searchDate`.
- The Swagger declares JSON output only; do not assume XML unless live endpoint evidence proves it.
- Treat monthly water-quality values as official statistics for the requested year, not as point-in-time sensor readings.
- If adapter output is filtered by treatment plant or quality item, implement filtering after retrieving the year unless the official endpoint later documents additional request parameters.
