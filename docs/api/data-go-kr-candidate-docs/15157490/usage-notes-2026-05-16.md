# 15157490 부산시설공단_공영주차장 시설 현황 조회 서비스

## Collection Status
- Source: <https://www.data.go.kr/data/15157490/openapi.do>
- Provider: 부산시설공단
- Department: 디지털정보팀
- Category: 교통및물류 - 도로
- Service type: REST
- Response format: JSON+XML
- Application status: approved.
- Usage-list evidence: `[승인] 부산시설공단_공영주차장 시설 현황 조회 서비스`, 신청일 `2026-05-16`, 만료예정일 `2028-05-16`.
- Development quota: 1,000 calls/day per operation.
- Review policy: development account auto-approved, operation account auto-approved.
- License: no public-data usage restriction shown on data.go.kr.

## Saved Artifacts
- `data-go-kr-detail.html`: data.go.kr detail page snapshot.
- `data-go-kr-inline-swagger.json`: inline Swagger/OpenAPI metadata extracted from the data.go.kr detail page.
- `intake-record.json`: local intake metadata.

## Endpoint Summary
- Service URL: `https://apis.data.go.kr/B552587/ParkingInfoService_v2`
- Supported schemes: `https`, `http`

Operations:
- `GET /getParkingList_v2`: 주차장 목록 조회.
- `GET /getParkingInfoList_v2`: 실시간 주차현황 조회.

Common required request parameters:
- `serviceKey`: data.go.kr service key.
- `pageNo`: page number.
- `numOfRows`: rows per page.

Common optional request parameters:
- `resultType`: response format, `json` or `xml`; default is `xml`.

Additional request parameters:
- `pParkGCd`: optional parking-lot code for `getParkingInfoList_v2`.

`getParkingList_v2` response fields include:
- `header.resultCode`: API result code.
- `header.resultMsg`: API result message.
- `body.items.item.parknm`: parking-lot name.
- `body.items.item.parkgcd`: parking-lot classification/code.
- `body.totalCount`, `body.numOfRows`, `body.pageNo`: pagination fields.

`getParkingInfoList_v2` response fields include:
- `header.resultCode`: API result code.
- `header.resultMsg`: API result message.
- `body.items.item.parknm`: parking-lot name.
- `body.items.item.parkgcd`: parking-lot classification/code.
- `body.items.item.parkingcnt`: currently parked vehicle count at the latest update time.
- `body.items.item.curravacnt`: currently available parking spaces at the latest update time.
- `body.items.item.maxcnt`: maximum parking capacity.
- `body.items.item.lastupdatetime`: latest update timestamp.
- `body.totalCount`, `body.numOfRows`, `body.pageNo`: pagination fields.

## Adapter Notes
- Suggested primitive: `lookup`.
- Suggested tool name: `busan_public_parking_status_lookup`.
- This is a read-only public-parking lookup adapter for Busan public parking facilities and live occupancy.
- The adapter should expose two lookup modes: parking-lot catalog and live parking status.
- The live-status mode should optionally accept `pParkGCd`; if a user supplies a parking-lot name, resolve it through `getParkingList_v2` before calling `getParkingInfoList_v2`.
- Preserve `lastupdatetime` in the output so the agent can state data freshness.

## Curl Shape
```bash
curl --get 'https://apis.data.go.kr/B552587/ParkingInfoService_v2/getParkingList_v2' \
  --data-urlencode "serviceKey=${DATA_GO_KR_SERVICE_KEY}" \
  --data-urlencode 'pageNo=1' \
  --data-urlencode 'numOfRows=10' \
  --data-urlencode 'resultType=json'

curl --get 'https://apis.data.go.kr/B552587/ParkingInfoService_v2/getParkingInfoList_v2' \
  --data-urlencode "serviceKey=${DATA_GO_KR_SERVICE_KEY}" \
  --data-urlencode 'pageNo=1' \
  --data-urlencode 'numOfRows=10' \
  --data-urlencode 'pParkGCd=<parking_code>' \
  --data-urlencode 'resultType=json'
```

## Implementation Cautions
- Do not persist or print the service key.
- The portal metadata uses lowercase `serviceKey`; preserve that casing unless live curl evidence proves an alias is accepted.
- `pParkGCd` is optional on the live-status endpoint, but supplying it should narrow results to one parking lot.
- Treat occupancy counts as real-time operational data with freshness bound by `lastupdatetime`, not as guaranteed current physical availability.
