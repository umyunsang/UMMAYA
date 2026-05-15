# 15073554 행정안전부_안전정보 통합공개 조회 서비스

## Collection Status
- Source: <https://www.data.go.kr/data/15073554/openapi.do>
- Provider: 행정안전부
- Department: 재난안전점검과
- Category: 공공질서및안전 - 안전관리
- Service type: REST
- Response format: JSON+XML
- Application status: already approved in the account. Pressing `활용신청` returned the portal alert `이미 신청 된 데이터입니다.`
- Usage-list evidence: `[승인] 행정안전부_안전정보 통합공개 조회 서비스`, 신청일 `2026-05-16`, 만료예정일 `2028-05-16`.
- Development quota: 5,000 calls/day.
- Review policy: development account auto-approved, operation account auto-approved.
- Update cycle: real time.
- License: no public-data usage restriction shown on data.go.kr.
- Count policy for this collection loop: this should not be counted as a fresh new application because the portal reported it was already applied.

## Saved Artifacts
- `data-go-kr-detail.html`: data.go.kr detail page snapshot.
- `data-go-kr-catalog.json`: local catalog metadata.
- `data-go-kr-inline-swagger.json`: inline Swagger 2.0 specification extracted from the portal page.
- `intake-record.json`: local intake metadata.

## Endpoint Summary
- Base URL: `https://apis.data.go.kr/1741000/FcltsSafetyInfoService2025`
- Alternate scheme declared by Swagger: `http`
- Authentication parameter: `serviceKey`
- Response selector: `resultType`, required on every operation. Official values are `xml` or `json`.

The API is a two-step lookup surface:
1. Search facility base records with `/getFcltsInfoSearch_4`.
2. Use the returned `fcltyCd`/facility key as `fclts_cd` for domain-specific safety-detail endpoints.

### Facility Search
`GET /getFcltsInfoSearch_4`

Required parameters:
- `serviceKey`: data.go.kr service key.
- `resultType`: response type, `xml` or `json`.
- `fclts_nm`: facility name.

Optional parameters:
- `pageNo`: page number.
- `numOfRows`: rows per page.
- `gp_cd`: facility type.
- `ldong_addr_mgpl_dg_cd`: province/metropolitan legal-dong address code.
- `ldong_addr_mgpl_sggu_cd`: city/county/district legal-dong address code.
- `ldong_addr_mgpl_sggu_emd_cd`: eup/myeon/dong legal-dong address code.

Facility-search response fields include:
- `fcltyNm`: facility name.
- `lnmadr`: facility address.
- `latitude`, `longitude`: location.
- `fcltyCd`: facility key.
- `seCd`: facility category.

### Safety Detail Endpoints
These operations share the same required request parameters:
- `serviceKey`: data.go.kr service key.
- `resultType`: `xml` or `json`.
- `fclts_cd`: facility key returned from `/getFcltsInfoSearch_4`.

Endpoints:
- `GET /getRcrfctSafetyInfoSearch_4`: 휴양림 안전정보 조회.
- `GET /getHotelSafetyInfoSearch_4`: 호텔 안전정보 조회.
- `GET /getSsrftSafetyInfoSearch_4`: 아동센터·돌봄센터 안전정보 조회.
- `GET /getQuakefcltySafetyInfoSearch_4`: 지진안전시설물 인증정보 조회.
- `GET /getTrditMrktSafetyInfoSearch_4`: 전통시장 안전정보 조회.
- `GET /getHlhsnSafetyInfoSearch_4`: 유해화학물질취급시설 안전정보 조회.
- `GET /getEclntSafetyInfoSearch_4`: 사방시설 안전정보 조회.
- `GET /getHarborfcltySafetyInfoSearch_4`: 항만시설 안전정보 조회.
- `GET /getPsnshipSafetyInfoSearch_4`: 여객선 안전정보 조회.
- `GET /getWaterLeisureSafetyInfoSearch_4`: 수상레저시설 안전정보 조회.
- `GET /getRuralHomestaySafetyInfoSearch_4`: 농어촌민박시설 안전정보 조회.
- `GET /getLongTermCareSafetyInfoSearch_4`: 장기요양시설 안전정보 조회.
- `GET /getMultiUseFacilitySafetyInfoSearch_4`: 다중이용시설 안전정보 조회.
- `GET /getFoodfcltySafetyInfoSearch_4`: 식품판매시설 안전정보 조회.
- `GET /getConcerthallSafetyInfoSearch_4`: 공연장시설 안전정보 조회.
- `GET /getMechanicalSafetyInfoSearch_4`: 기계식주차장시설 안전정보 조회.
- `GET /getYouthTrainingSafetyInfoSearch_4`: 청소년수련시설 안전정보 조회.
- `GET /getSlopeLandSafetyInfoSearch_4`: 급경사지시설 안전정보 조회.
- `GET /getAgrprodSafetyInfoSearch_4`: 농업생산기반시설 안전정보 조회.
- `GET /getWasteSafetyInfoSearch_4`: 폐기물처리시설 안전정보 조회.
- `GET /getHospitalSafetyInfoSearch_4`: 병원시설 인증정보 조회.
- `GET /getAmuseSafetyInfoSearch_4`: 테마파크 안전정보 조회.
- `GET /getSmlPublicSafetyInfoSearch_4`: 소규모공공시설 안전정보 조회.
- `GET /getBuildSafetyInfoSearch_4`: 건축물 안전정보 조회.
- `GET /getAlsfcSafetyInfoSearch_4`: 체육시설 안전정보 조회.
- `GET /getFmsfcltySafetyInfoSearch_4`: FMS 시설점검 안전정보 조회.
- `GET /getNlprkSafetyInfoSearch_4`: 국립공원 안전정보 조회.
- `GET /getCiSafetyInfoSearch_4`: 어린이놀이시설 안전정보 조회.
- `GET /getScleqipSafetyInfoSearch_4`: 학교시설 안전정보 조회.
- `GET /getCrSafetyInfoSearch_4`: 어린이집 안전정보 조회.

Detail responses vary by endpoint, but most include safety-inspection fields such as:
- `category`: facility/safety category.
- `chck_start_ymd`, `chck_end_ymd`: inspection period.
- `chck_dtls_type`: inspection type.
- `chck_inst_nm`: inspection target name.
- `chck_rslt_safe_grad`: inspection result or safety grade.
- `chck_compt_ymd`: expected completion date.
- `chck_fllw_managt`: findings or follow-up management.
- `chck_rslt_cn`: action/result content.

## Adapter Notes
- Suggested primitive: `lookup`.
- Suggested tool name: `mois_facility_safety_info_lookup`.
- The adapter should model `/getFcltsInfoSearch_4` as the discovery operation and safety-detail endpoints as follow-up lookups keyed by `fclts_cd`.
- A caller should not ask users for `fclts_cd` first unless the key is already known; search by facility name/address/category should come first.
- Legal-dong address-code filters are optional but should be validated or documented as official administrative codes when added to the adapter.
- The service aggregates safety data from multiple ministries and institutions. Adapter output should preserve the facility category, source endpoint, inspection period, and result fields so downstream tools can explain provenance.

## Curl Shapes
Facility search:
```bash
curl --get 'https://apis.data.go.kr/1741000/FcltsSafetyInfoService2025/getFcltsInfoSearch_4' \
  --data-urlencode "serviceKey=${DATA_GO_KR_SERVICE_KEY}" \
  --data-urlencode 'resultType=json' \
  --data-urlencode 'pageNo=1' \
  --data-urlencode 'numOfRows=10' \
  --data-urlencode 'fclts_nm=시설물명'
```

Safety detail lookup:
```bash
curl --get 'https://apis.data.go.kr/1741000/FcltsSafetyInfoService2025/getHotelSafetyInfoSearch_4' \
  --data-urlencode "serviceKey=${DATA_GO_KR_SERVICE_KEY}" \
  --data-urlencode 'resultType=json' \
  --data-urlencode "fclts_cd=${FACILITY_KEY}"
```

## Implementation Cautions
- Do not persist or print the service key.
- Keep `resultType` required even when the endpoint also declares `produces` JSON/XML.
- Do not count this API as a fresh new application in this loop because data.go.kr reported it had already been applied for this account.
- Consider a typed enum for the 30 safety-detail endpoint names rather than accepting arbitrary path strings.
