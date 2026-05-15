# 15155042 행정안전부_CCTV정보 조회서비스

## Collection Status
- Source: <https://www.data.go.kr/data/15155042/openapi.do>
- Provider: 행정안전부
- Department: 지역디지털협력과
- Category: 공공질서및안전 - 안전관리
- Service type: REST
- Response format: JSON+XML
- Application status: approved.
- Usage-list evidence: `[승인] 행정안전부_CCTV정보 조회서비스`, 신청일 `2026-05-16`, 만료예정일 `2028-05-16`.
- Development quota: 10,000 calls/day for each selected operation.
- Review policy: development account auto-approved, operation account auto-approved.
- Update cycle: daily.
- License: the detail page and application form show `이용허락범위 제한 없음`.

## Saved Artifacts
- `data-go-kr-detail.html`: data.go.kr detail page snapshot.
- `data-go-kr-inline-swagger.json`: inline Swagger/OpenAPI metadata extracted from the detail page.
- `intake-record.json`: local intake metadata.
- `개방자치단체코드_영업상태코드.xlsx`: official supplementary local-government/open-status code workbook.
- `개방자치단체코드_영업상태코드.xlsx.txt`: text extraction of the supplementary code workbook. The workbook hash matches the already collected same-named workbook for `15155062`.

## Endpoint Summary
- Service URL: `https://apis.data.go.kr/1741000/cctv_info`
- Supported schemes in portal Swagger: `https`, `http`

Operations:
- `GET /info`: CCTV정보 데이터 조회. The portal description says the data is updated daily and is current as of two days before the request.
- `GET /history`: CCTV정보 데이터 이력조회. Looks up historical CCTV records for a requested base date. The portal states that `cond[BASE_DATE::EQ]` can be entered from `20260101` through the day before the lookup date.

Required request parameters for `/info`:
- `serviceKey`: data.go.kr service key.
- `pageNo`: page number.
- `numOfRows`: result count per page. The portal Swagger describes a maximum of 100.

Optional request parameters for `/info`:
- `returnType`: response type. Use `JSON` for adapter fixture collection.
- `cond[DAT_UPDT_PNT::GTE]`: data update timestamp lower bound, `YYYYMMDDHHMMSS`.
- `cond[DAT_UPDT_PNT::LT]`: data update timestamp upper bound, `YYYYMMDDHHMMSS`.
- `cond[LCTN_ROAD_NM_ADDR::LIKE]`: road-name address substring filter.
- `cond[INSTL_YM::GTE]`: installation year-month lower bound.
- `cond[OPN_ATMY_GRP_CD::EQ]`: open local-government code equality filter.
- `cond[DAT_CRTR_YMD::GTE]`: data reference date lower bound, `YYYYMMDD`.
- `cond[DAT_CRTR_YMD::LT]`: data reference date upper bound, `YYYYMMDD`.

Required request parameters for `/history`:
- `serviceKey`: data.go.kr service key.
- `pageNo`: page number.
- `numOfRows`: result count per page. The portal Swagger describes a maximum of 100.
- `cond[BASE_DATE::EQ]`: base date, `YYYYMMDD`.
- `cond[OPN_ATMY_GRP_CD::EQ]`: open local-government code equality filter.

Optional request parameters for `/history`:
- `returnType`: response type.
- `cond[DAT_CRTR_YMD::GTE]`: data creation/reference date lower bound, `YYYYMMDD`.
- `cond[DAT_CRTR_YMD::LT]`: data creation/reference date upper bound, `YYYYMMDD`.
- `cond[LAST_MDFCN_PNT::GTE]`: last modification timestamp lower bound, `YYYYMMDDHHMMSS`.
- `cond[LAST_MDFCN_PNT::LT]`: last modification timestamp upper bound, `YYYYMMDDHHMMSS`.
- `cond[LCTN_ROAD_NM_ADDR::LIKE]`: road-name address substring filter.
- `cond[INSTL_YM::GTE]`: installation year-month lower bound.

Common response envelope fields:
- `response.header.resultCode`: response result code.
- `response.header.resultMsg`: response result message.
- `response.body.dataType`: response data type.
- `response.body.numOfRows`: rows per page.
- `response.body.pageNo`: current page number.
- `response.body.totalCount`: total result count.
- `response.body.items.item[]`: CCTV records.

Current `/info` record fields include:
- `INSTL_PRPS_SE_NM`: installation purpose category name.
- `OPN_ATMY_GRP_CD`: open local-government code.
- `MNG_NO`: management number.
- `MNG_INST_NM`: managing institution name.
- `LCTN_ROAD_NM_ADDR`: road-name address.
- `LCTN_LOTNO_ADDR`: lot-number address.
- `CAM_CNTOM`: camera count.
- `CAM_PIXEL_CNT`: camera pixel count.
- `SHT_ANGLE_INFO`: shooting direction information.
- `KPNG_DAY_CNT`: storage/retention days.
- `INSTL_YM`: installation year-month.
- `MNG_INST_TELNO`: managing institution telephone number.
- `WGS84_LAT`: WGS84 latitude.
- `WGS84_LOT`: WGS84 longitude. Keep the official `LOT` spelling when preserving raw source fields.
- `DAT_CRTR_YMD`: data reference date, `YYYYMMDD`.
- `LAST_MDFCN_PNT`: last modification timestamp, `YYYYMMDDHHMMSS`.
- `DAT_UPDT_PNT`: data update timestamp, `YYYYMMDDHHMMSS`.
- `DAT_UPDT_SE`: data update category.

Historical `/history` records use mostly the same fields but expose `INSTL_PRPS_SE` instead of `INSTL_PRPS_SE_NM`, and do not include `DAT_UPDT_PNT` or `DAT_UPDT_SE` in the Swagger response field list.

## Domain Notes
The portal description says this service provides nationwide outdoor CCTV records installed for public purposes such as traffic information and crime prevention. It includes managing institution, location, installation purpose, camera count, pixel count, shooting direction, retention days, installation year-month, managing institution contact, road/lot address, and WGS84 coordinates.

The detail page names the legal-policy contact as 개인정보보호위원회 신기술개인정보과 / `02-2100-3064` and states that coordinates use the WGS84 latitude/longitude coordinate system.

The application form shows the public-data location-information warning. The adapter should treat user-provided location text or coordinates as sensitive context and should not persist it unless a later UMMAYA flow adds explicit legal and permission handling.

## Adapter Notes
- Suggested primitive: `locate`.
- Suggested tool name: `public_cctv_location_lookup`.
- This is a read-only public-safety infrastructure lookup adapter.
- Preserve official request parameter names, including the bracketed `cond[...]` filter keys.
- Normalize official uppercase item fields into snake_case fields for UMMAYA output, while preserving the raw item in source metadata.
- Expose filters for local-government code, road-name-address substring, installation year-month lower bound, data update timestamp range, and data reference date range.
- Use `/history` only when the caller explicitly asks for historical records and supplies both `base_date` and local-government code.
- Keep `numOfRows` capped at 100 unless a later live probe proves the gateway accepts a larger value.
- Use the supplementary local-government code workbook as controlled lookup metadata, not as a replacement for the official API response.

## Curl Shape
```bash
curl --get 'https://apis.data.go.kr/1741000/cctv_info/info' \
  --data-urlencode "serviceKey=${DATA_GO_KR_SERVICE_KEY}" \
  --data-urlencode 'pageNo=1' \
  --data-urlencode 'numOfRows=100' \
  --data-urlencode 'returnType=JSON' \
  --data-urlencode 'cond[OPN_ATMY_GRP_CD::EQ]=6110000_ALL'
```

```bash
curl --get 'https://apis.data.go.kr/1741000/cctv_info/info' \
  --data-urlencode "serviceKey=${DATA_GO_KR_SERVICE_KEY}" \
  --data-urlencode 'pageNo=1' \
  --data-urlencode 'numOfRows=50' \
  --data-urlencode 'returnType=JSON' \
  --data-urlencode 'cond[LCTN_ROAD_NM_ADDR::LIKE]=종로'
```

```bash
curl --get 'https://apis.data.go.kr/1741000/cctv_info/history' \
  --data-urlencode "serviceKey=${DATA_GO_KR_SERVICE_KEY}" \
  --data-urlencode 'pageNo=1' \
  --data-urlencode 'numOfRows=100' \
  --data-urlencode 'returnType=JSON' \
  --data-urlencode 'cond[BASE_DATE::EQ]=20260101' \
  --data-urlencode 'cond[OPN_ATMY_GRP_CD::EQ]=6110000_ALL'
```

## Implementation Cautions
- Do not persist or print the service key.
- Do not call this live endpoint from CI tests.
- URL-encode the bracketed `cond[...]` parameter names and their values through an HTTP client query-parameter API.
- Treat CCTV coordinates as public facility coordinates, not as user location.
- Do not infer real-time camera availability, camera stream access, surveillance coverage, or public-safety risk from this dataset. The service exposes installation records only.
- Do not expose this adapter as a camera-video retrieval tool; the documented API is metadata lookup only.
