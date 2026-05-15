# 15142227 해양수산부 국립해양조사원_ROMS 수치예측모델 조회

## Collection Status
- Source: <https://www.data.go.kr/data/15142227/openapi.do>
- Provider: 해양수산부 국립해양조사원
- Department: 해양예보과
- Category: 농축수산 - 해양수산·어촌
- Service type: REST
- Response format: JSON+XML
- Application status: approved.
- Usage-list evidence: `[승인] 해양수산부 국립해양조사원_ROMS 수치예측모델 조회`, 신청일 `2026-05-16`, 만료예정일 `2028-05-16`.
- Development quota: 10,000 calls/day for the selected operation.
- Review policy: development account auto-approved, operation account review-approved.
- Update cycle: real time.
- License: the detail page shows `공공저작물 : 출처표시 (제 1유형)` and the application form displays `이용허락범위 제한 없음`.

## Saved Artifacts
- `data-go-kr-detail.html`: data.go.kr detail page snapshot.
- `data-go-kr-inline-swagger.json`: inline Swagger/OpenAPI metadata extracted from the detail page.
- `intake-record.json`: local intake metadata.
- `오픈API 활용가이드_ROMS 수치예측모델.hwp`: official downloaded utilization guide.
- `오픈API 활용가이드_ROMS 수치예측모델.hwp.txt`: text extraction of the official utilization guide.

## Endpoint Summary
- Service URL: `https://apis.data.go.kr/1192136/roms`
- Supported schemes in portal Swagger: `https`, `http`

Operation:
- `GET /GetRomsApiService`: ROMS 수치예측모델. Looks up the nearest prediction point for a requested coordinate bounding box and returns predicted water temperature for 72 hours plus current direction and speed for 148 hours.

Required request parameters:
- `serviceKey`: data.go.kr service key.
- `type`: response type, `json` or `xml`.
- `ymin`: minimum latitude.
- `ymax`: maximum latitude.
- `xmin`: minimum longitude.
- `xmax`: maximum longitude.

Optional request parameters:
- `pageNo`: page number, default `1`.
- `numOfRows`: result count per page, default `10`, maximum `300`.
- `include`: comma-separated output field names to include, for example `lat,lot`.
- `exclude`: comma-separated output field names to exclude, for example `lat,lot`.

Common response envelope fields:
- `header.resultCode`: response result code.
- `header.resultMsg`: response result message.
- `body.type`: response type.
- `body.items.item[]`: prediction records.
- `body.totalCount`: total result count.
- `body.pageNo`: current page number.
- `body.numOfRows`: rows per page.

Record fields include:
- `crdir`: current direction.
- `crsp`: current speed.
- `wtem`: water temperature.
- `predcDt`: prediction datetime.
- `lat`: latitude.
- `lot`: longitude. Preserve the official `lot` spelling for raw source fields.

## Domain Notes
The portal description says this dataset provides ROMS-based ocean-environment prediction values from the Korea Hydrographic and Oceanographic Agency. It is meant for coordinate-area search using minimum and maximum latitude/longitude values, and its main contents are prediction datetime, prediction point latitude and longitude, surface current direction and speed, and water temperature.

The application form repeats the location-information warning. The adapter should treat user-supplied coordinate boxes as sensitive request context and avoid persisting them outside explicit UMMAYA session logs or sanitized fixtures.

## Adapter Notes
- Suggested primitive: `lookup`.
- Suggested tool name: `khoa_roms_marine_prediction_lookup`.
- This is a read-only marine forecast lookup adapter.
- Normalize the required coordinate box into explicit `min_latitude`, `max_latitude`, `min_longitude`, and `max_longitude` input fields, but send the official `ymin`, `ymax`, `xmin`, and `xmax` query keys.
- Preserve `predcDt` as the source prediction timestamp and parse it only in a derived normalized field if the official format is stable after live fixture collection.
- Keep `numOfRows` capped at `300` unless a later live probe proves a different gateway limit.
- Return raw units as published by the source; do not infer knots, meters per second, Celsius, or compass conventions without official guide evidence.

## Curl Shape
```bash
curl --get 'https://apis.data.go.kr/1192136/roms/GetRomsApiService' \
  --data-urlencode "serviceKey=${DATA_GO_KR_SERVICE_KEY}" \
  --data-urlencode 'type=json' \
  --data-urlencode 'ymin=39.59335' \
  --data-urlencode 'ymax=40.19335' \
  --data-urlencode 'xmin=127' \
  --data-urlencode 'xmax=128' \
  --data-urlencode 'pageNo=1' \
  --data-urlencode 'numOfRows=10'
```

```bash
curl --get 'https://apis.data.go.kr/1192136/roms/GetRomsApiService' \
  --data-urlencode "serviceKey=${DATA_GO_KR_SERVICE_KEY}" \
  --data-urlencode 'type=json' \
  --data-urlencode 'ymin=39.59335' \
  --data-urlencode 'ymax=40.19335' \
  --data-urlencode 'xmin=127' \
  --data-urlencode 'xmax=128' \
  --data-urlencode 'include=lat,lot,predcDt,wtem' \
  --data-urlencode 'pageNo=1' \
  --data-urlencode 'numOfRows=50'
```

## Implementation Cautions
- Do not persist or print the service key.
- Do not call this live endpoint from CI tests.
- Preserve exact official parameter casing and field spelling, especially `predcDt` and `lot`.
- Validate coordinate ranges before dispatching the request.
- Treat this service as a forecast/prediction source, not an observed current-condition source.
