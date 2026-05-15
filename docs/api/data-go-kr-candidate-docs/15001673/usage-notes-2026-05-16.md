# 15001673 건강보험심사평가원_약국정보서비스

## Collection Status
- Source: <https://www.data.go.kr/data/15001673/openapi.do>
- Provider: 건강보험심사평가원
- Department: 빅데이터실
- Category: 보건 - 건강보험
- Service type: REST
- Response format: XML
- Application status: approved on data.go.kr.
- Usage-list evidence: `[승인] 건강보험심사평가원_약국정보서비스`, 신청일 `2026-05-16`, 만료예정일 `2028-05-16`.
- Development quota: 10,000 calls/day.
- Review policy: development account auto-approved, operation account review-approved.
- Update cycle: real time.
- License: KOGL type 1/source attribution. The portal warns that third-party rights may be included and must be confirmed by the user.

## Saved Artifacts
- `data-go-kr-detail.html`: data.go.kr detail page snapshot.
- `intake-record.json`: local intake metadata.
- `OpenAPI활용가이드_건강보험심사평가원(약국정보서비스).docx`: downloaded official guide.
- `OpenAPI활용가이드_건강보험심사평가원(약국정보서비스).docx.txt`: extracted text used for this summary.

## Endpoint Summary
- Base URL in the official guide: `http://apis.data.go.kr/B551182/pharmacyInfoService/`
- Preferred HTTPS shape for implementation if the gateway accepts it: `https://apis.data.go.kr/B551182/pharmacyInfoService/`
- Authentication parameter name in the guide: `ServiceKey`
- The operation name is officially misspelled as `getParmacyBasisList`; preserve that exact spelling.

### getParmacyBasisList
- Method: `GET`
- Path: `/getParmacyBasisList`
- Korean operation name: `약국기본목록`
- Purpose: returns pharmacy basic information managed by HIRA, including pharmacy name, address, phone number, coordinates, establishment date, local government codes, and encrypted institution identifier.

Required request parameter:
- `ServiceKey`: data.go.kr service key.

Optional request parameters:
- `pageNo`: page number. Official sample: `1`.
- `numOfRows`: rows per page. Official sample: `10`.
- `sidoCd`: metropolitan/province code. Official sample: `110000`.
- `sgguCd`: city/county/district code. Official sample: `110019`.
- `emdongNm`: 읍면동 name. Official sample: `신내동`.
- `yadmNm`: pharmacy-name keyword. The official guide labels it as 병원명, but this service uses it as the pharmacy-name filter. Korean values must be UTF-8 encoded.
- `xPos`: longitude. Official sample: `127.0965441345503`.
- `yPos`: latitude. Official sample: `37.60765568913871`.
- `radius`: search radius in meters. Official sample: `3000`.

Response fields:
- Header: `resultCode`, `resultMsg`.
- Pagination: `numOfRows`, `pageNo`, `totalCount`.
- Item fields: `ykiho`, `yadmNm`, `clCd`, `clCdNm`, `sidoCd`, `sidoCdNm`, `sgguCd`, `sgguCdNm`, `emdongNm`, `postNo`, `addr`, `telno`, `estbDd`, `xPos`/`XPos`, `yPos`/`YPos`, `distance`.

## Adapter Notes
- Suggested primitive: `lookup`.
- Suggested tool name: `hira_pharmacy_info_lookup`.
- This is a read-only public-data adapter for pharmacy lookup by area code, pharmacy-name keyword, neighborhood, or nearby coordinate search.
- `ykiho` is an encrypted one-to-one matched identifier. The portal explicitly says no decryption method or original institution identifier is provided.
- Region code inputs such as `sidoCd` and `sgguCd` should be validated or documented against HIRA's code lookup pages on `opendata.hira.or.kr`.
- For coordinate search, send `xPos`, `yPos`, and `radius` together. Treat `radius` as meters.
- The tool should not provide medical advice; it should only return official pharmacy lookup data with source attribution.

## Curl Shape
```bash
curl --get 'https://apis.data.go.kr/B551182/pharmacyInfoService/getParmacyBasisList' \
  --data-urlencode "ServiceKey=${DATA_GO_KR_SERVICE_KEY}" \
  --data-urlencode 'pageNo=1' \
  --data-urlencode 'numOfRows=10' \
  --data-urlencode 'sidoCd=110000' \
  --data-urlencode 'sgguCd=110019' \
  --data-urlencode 'emdongNm=신내동' \
  --data-urlencode 'yadmNm=온누리건강' \
  --data-urlencode 'xPos=127.0965441345503' \
  --data-urlencode 'yPos=37.60765568913871' \
  --data-urlencode 'radius=3000'
```

## Implementation Cautions
- Keep the official operation spelling `getParmacyBasisList`.
- Do not persist or print the service key in fixtures or documentation.
- Normalize coordinate field names because the official response examples use uppercase `XPos`/`YPos` while the field table also lists lowercase `xPos`/`yPos`.
- Preserve source attribution and KOGL type 1 notice in adapter metadata.
