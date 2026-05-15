# 15159322 한국환경공단_지하역사 실내공기질 자동측정망 실시간 측정데이터 초미세먼지 정보

## Collection Status
- Source: <https://www.data.go.kr/data/15159322/openapi.do>
- Provider: 한국환경공단
- Department: 생활환경안전처 생활환경지원부
- Category: 환경 - 대기
- Service type: REST
- Response format: JSON+XML
- Application status: approved.
- Usage-list evidence: `[승인] 한국환경공단_지하역사 실내공기질 자동측정망 실시간 측정데이터 초미세먼지 정보`, 신청일 `2026-05-16`, 만료예정일 `2028-05-16`.
- Development quota: 1,000 calls/day.
- Review policy: development account auto-approved, operation account requires review.
- Update cycle: real time.
- License: the detail page shows `이용허락범위 제한 없음`; the application form license checkbox was accepted during usage application.

## Saved Artifacts
- `data-go-kr-detail.html`: data.go.kr detail page snapshot.
- `data-go-kr-inline-swagger.json`: inline Swagger/OpenAPI metadata extracted from the data.go.kr detail page.
- `intake-record.json`: local intake metadata.

## Endpoint Summary
- Service URL: `https://apis.data.go.kr/B552584/udgdScnAutoMntnwRltmUlfdInfoService`
- Supported schemes in portal Swagger: `https`, `http`

Operation:
- `GET /getUlfdInfo`: 지하역사 실내공기질 측정데이터 초미세먼지 정보.

Required request parameters:
- `serviceKey`: data.go.kr service key.
- `pageNo`: page number.
- `numOfRows`: result count per page.
- `returnType`: response type. Use `json` for JSON fixtures unless XML behavior is explicitly needed.

Optional request parameters:
- `slineNm`: subway line name.
- `msrmtDt`: measurement timestamp filter.
- `pstnNm`: station/location name.

Response fields include:
- `header.resultCode`: response code.
- `header.resultMsg`: response message.
- `body.totalCount`: total result count.
- `body.pageNo`: current page number.
- `body.numOfRows`: rows per page.
- `body.items.item[].msinSttsIndctSeNm`: measuring-device status label.
- `body.items.item[].msrmtDt`: measurement timestamp.
- `body.items.item[].slineNm`: subway line name.
- `body.items.item[].pstnNm`: station/location name.
- `body.items.item[].brnchNm`: branch/measurement point name.
- `body.items.item[].operInstNm`: operating institution name.
- `body.items.item[].artclNm`: measured item name.
- `body.items.item[].msrmtVlNumv`: measured numeric value.

## Domain Notes
The portal description states that the service opens real-time indoor PM2.5 information for subway stations nationwide. The detail page also states that the data is produced and finalized by each rail operating institution, and that the public data can lag by about one hour because of the verification/finalization process.

The application form shows the public-data location-information warning. For UMMAYA, treat this adapter as a read-only public environmental lookup and avoid storing user location unless a later product flow explicitly requires location-based personalization with the proper legal review.

## Adapter Notes
- Suggested primitive: `lookup`.
- Suggested tool name: `underground_station_pm25_realtime_lookup`.
- This is a read-only subway-station indoor-air-quality lookup adapter.
- Preserve official parameter casing: `serviceKey`, `pageNo`, `numOfRows`, `returnType`, `slineNm`, `msrmtDt`, `pstnNm`.
- Normalize station records into a stable shape with line, station/location, branch, operating institution, item name, measurement value, measurement timestamp, and device status.
- Include the one-hour verification-lag caveat in user-visible source notes when the agent answers "current" air-quality questions.
- Keep pagination explicit because the endpoint can return nationwide station data.

## Curl Shape
```bash
curl --get 'https://apis.data.go.kr/B552584/udgdScnAutoMntnwRltmUlfdInfoService/getUlfdInfo' \
  --data-urlencode "serviceKey=${DATA_GO_KR_SERVICE_KEY}" \
  --data-urlencode 'pageNo=1' \
  --data-urlencode 'numOfRows=10' \
  --data-urlencode 'returnType=json'
```

Optional filtered example:

```bash
curl --get 'https://apis.data.go.kr/B552584/udgdScnAutoMntnwRltmUlfdInfoService/getUlfdInfo' \
  --data-urlencode "serviceKey=${DATA_GO_KR_SERVICE_KEY}" \
  --data-urlencode 'pageNo=1' \
  --data-urlencode 'numOfRows=10' \
  --data-urlencode 'returnType=json' \
  --data-urlencode 'slineNm=1호선' \
  --data-urlencode 'pstnNm=서울역'
```

## Implementation Cautions
- Do not persist or print the service key.
- Do not call this live endpoint from CI tests.
- Treat `msrmtVlNumv` as a numeric public measurement value and preserve the original timestamp string until live samples confirm the exact timestamp format.
- Do not infer health advice or exposure guidance from the PM2.5 value inside the adapter; return official measurements and let higher-level policy/UX layers handle interpretation with citations.
- The endpoint supports JSON and XML according to the portal Swagger, but fixture collection should prefer JSON for adapter shape validation.
