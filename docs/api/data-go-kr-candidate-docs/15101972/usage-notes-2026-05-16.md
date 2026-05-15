# 15101972 한국관광공사_빅데이터_지역별 방문자수_GW

## Collection Status

- Source: <https://www.data.go.kr/data/15101972/openapi.do>
- Provider: 한국관광공사
- Category: 문화관광
- Service type: REST, JSON/XML
- Application status: approved in data.go.kr usage list on 2026-05-16
- Usage-list evidence: `[승인] 한국관광공사_빅데이터_지역별 방문자수_GW`, 신청일 `2026-05-16`, 만료예정일 `2028-05-16`
- Development quota: 1,000 calls per operation per day
- Activation note: TourAPI manual says development account keys may become usable after about 10-30 minutes because of data.go.kr and 한국관광공사 synchronization.

## Saved Artifacts

- `data-go-kr-detail.html`
- `data-go-kr-catalog.json`
- `data-go-kr-inline-swagger.json`
- `TourAPI_Guide_(관광빅데이터)v4.1.zip`
- `TourAPI_Guide_(관광빅데이터)v4.1-unzipped/zip-member-001.docx`
- `TourAPI_Guide_(관광빅데이터)v4.1-unzipped/zip-member-001.docx.txt`
- `TourAPI_Guide_(관광빅데이터)v4.1-unzipped/zip-member-002.docx`
- `TourAPI_Guide_(관광빅데이터)v4.1-unzipped/zip-member-002.docx.txt`

## Endpoint Summary

Base URL:

```text
https://apis.data.go.kr/B551011/DataLabService
```

The manual also lists `http://apis.data.go.kr/B551011/DataLabService`; prefer HTTPS for adapters unless live probing proves an endpoint-specific issue.

### metcoRegnVisitrDDList

Purpose: 광역 지자체 지역방문자수 집계 데이터 정보 조회.

```http
GET /metcoRegnVisitrDDList
```

Required query parameters:

- `serviceKey`: data.go.kr service key
- `MobileOS`: one of `IOS`, `AND`, `WIN`, `ETC`
- `MobileApp`: service/application name used for usage statistics
- `startYmd`: start date, `YYYYMMDD`
- `endYmd`: end date, `YYYYMMDD`

Optional query parameters:

- `pageNo`: page number, sample `1`
- `numOfRows`: rows per page, sample `10`
- `_type`: response format selector; use `_type=json` for JSON, omit for default XML

Important response fields:

- `baseYmd`: 기준연월일
- `areaCode`: 시도코드
- `areaNm`: 시도명
- `daywkDivCd`, `daywkDivNm`: weekday code/name
- `touDivCd`, `touDivNm`: visitor classification code/name
- `touNum`: visitor count

### locgoRegnVisitrDDList

Purpose: 기초 지자체 지역방문자수 집계 데이터 정보 조회.

```http
GET /locgoRegnVisitrDDList
```

Required and optional query parameters are the same as `metcoRegnVisitrDDList`.

Important response fields:

- `baseYmd`: 기준연월일
- `signguCode`: 시군구코드
- `signguNm`: 시군구명
- `daywkDivCd`, `daywkDivNm`: weekday code/name
- `touDivCd`, `touDivNm`: visitor classification code/name
- `touNum`: visitor count

## Codes And Semantics

- `daywkDivCd`: `1` Monday, `2` Tuesday, `3` Wednesday, `4` Thursday, `5` Friday, `6` Saturday, `7` Sunday.
- `touDivCd`: `1` local resident, `2` non-local domestic visitor, `3` foreign visitor.
- Provider result codes include `00 NORMAL_CODE`, `03 NODATA_ERROR`, `10 INVALID_REQUEST_PARAMETER_ERROR`, `11 NO_MANDATORY_REQUEST_PARAMETERS_ERROR`, `22 LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR`, `30 SERVICE_KEY_IS_NOT_REGISTERED_ERROR`, and `31 DEADLINE_HAS_EXPIRED_ERROR`.

## Adapter Fit

- Primitive: `lookup`
- Suggested tool name: `knto_regional_visitor_counts_lookup`
- Read-only public-data adapter.
- Good first operations:
  - metropolitan visitor-count lookup by date range
  - local-government visitor-count lookup by date range
- The official description warns that visitor counts are based on mobile-carrier data and should not be blindly treated as exact tourist counts. It also warns that metropolitan and local-government totals use different aggregation criteria and should not be arbitrarily summed.

## Curl Shape

Use after key propagation; do not commit the real key.

```bash
curl --get 'https://apis.data.go.kr/B551011/DataLabService/metcoRegnVisitrDDList' \
  --data-urlencode "serviceKey=${DATA_GO_KR_SERVICE_KEY}" \
  --data-urlencode 'MobileOS=ETC' \
  --data-urlencode 'MobileApp=UMMAYA' \
  --data-urlencode 'startYmd=20210513' \
  --data-urlencode 'endYmd=20210513' \
  --data-urlencode 'pageNo=1' \
  --data-urlencode 'numOfRows=10' \
  --data-urlencode '_type=json'
```
