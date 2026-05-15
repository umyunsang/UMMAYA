# 15155062 행정안전부_무료와이파이정보 조회서비스

## Collection Status
- Source: <https://www.data.go.kr/data/15155062/openapi.do>
- Provider: 행정안전부
- Department: 지역디지털협력과
- Category: 과학기술 - 과학기술연구
- Service type: REST
- Response format: JSON+XML
- Application status: approved.
- Usage-list evidence: `[승인] 행정안전부_무료와이파이정보 조회서비스`, 신청일 `2026-05-16`, 만료예정일 `2028-05-16`.
- Development quota: 10,000 calls/day for the selected operation.
- Review policy: development account auto-approved, operation account auto-approved.
- Update cycle: daily.
- License: the detail page and application form show `이용허락범위 제한 없음`.

## Saved Artifacts
- `data-go-kr-detail.html`: data.go.kr detail page snapshot.
- `data-go-kr-inline-swagger.json`: inline Swagger/OpenAPI metadata extracted from the detail page.
- `intake-record.json`: local intake metadata.
- `개방자치단체코드_영업상태코드.xlsx`: official supplementary local-government/open-status code workbook.
- `개방자치단체코드_영업상태코드.xlsx.txt`: text extraction of the supplementary code workbook.

## Endpoint Summary
- Service URL: `https://apis.data.go.kr/1741000/free_wifi_info`
- Supported schemes in portal Swagger: `https`, `http`

Operation:
- `GET /info`: 무료와이파이정보 데이터 조회. Looks up nationwide public/free Wi-Fi installation and management records. The operation description notes that the data is updated daily and is current as of two days before the request.

Required request parameters:
- `serviceKey`: data.go.kr service key.
- `pageNo`: page number.
- `numOfRows`: result count per page. The portal Swagger describes a maximum of 100.

Optional request parameters:
- `returnType`: response type. Use `JSON` for adapter fixture collection.
- `cond[DAT_UPDT_PNT::GTE]`: data update timestamp lower bound, `YYYYMMDDHHMMSS`.
- `cond[DAT_UPDT_PNT::LT]`: data update timestamp upper bound, `YYYYMMDDHHMMSS`.
- `cond[LCTN_ROAD_NM_ADDR::LIKE]`: road-name address substring filter.
- `cond[INSTL_YM::GTE]`: installation year-month lower bound.
- `cond[OPN_ATMY_GRP_CD::EQ]`: open local-government code equality filter.
- `cond[DAT_CRTR_YMD::GTE]`: data reference date lower bound, `YYYYMMDD`.
- `cond[DAT_CRTR_YMD::LT]`: data reference date upper bound, `YYYYMMDD`.

Common response envelope fields:
- `response.header.resultCode`: response result code.
- `response.header.resultMsg`: response result message.
- `response.body.dataType`: response data type.
- `response.body.numOfRows`: rows per page.
- `response.body.pageNo`: current page number.
- `response.body.totalCount`: total result count.
- `response.body.items.item[]`: free Wi-Fi records.

Record fields include:
- `INSTL_FCLT_SE_NM`: installation facility category name.
- `OPN_ATMY_GRP_CD`: open local-government code.
- `MNG_NO`: management number.
- `INSTL_PLC_NM`: installation place name.
- `INSTL_PLC_DTL`: installation place detail.
- `INSTL_CTPV_NM`: installation province/city name.
- `INSTL_SGG_NM`: installation city/county/district name.
- `SRVC_PROV_NM`: service provider name.
- `WIFI_SSID`: Wi-Fi SSID.
- `INSTL_YM`: installation year-month.
- `LCTN_ROAD_NM_ADDR`: road-name address.
- `LCTN_LOTNO_ADDR`: lot-number address.
- `MNG_INST_NM`: managing institution name.
- `MNG_INST_TELNO`: managing institution telephone number.
- `WGS84_LAT`: WGS84 latitude.
- `WGS84_LOT`: WGS84 longitude. Keep the official `LOT` spelling when preserving raw source fields.
- `DAT_CRTR_YMD`: data reference date, `YYYYMMDD`.
- `LAST_MDFCN_PNT`: last modification timestamp, `YYYYMMDDHHMMSS`.
- `DAT_UPDT_PNT`: data update timestamp, `YYYYMMDDHHMMSS`.
- `DAT_UPDT_SE`: data update category.

## Domain Notes
The portal description says the service provides nationwide free Wi-Fi information managed by local governments, including service provider, installation place, SSID, managing institution contact, road/lot address, and WGS84 coordinates.

The application form shows the public-data location-information warning. The adapter should treat user-provided location text or coordinates as sensitive context and should not persist it unless a later UMMAYA flow adds explicit legal and permission handling.

The supplementary workbook provides local-government code values. Examples from the extracted workbook include `6110000_ALL` for Seoul, `6260000_ALL` for Busan, and `6270000_ALL` for Daegu.

## Adapter Notes
- Suggested primitive: `locate`.
- Suggested tool name: `public_free_wifi_location_lookup`.
- This is a read-only location/infrastructure lookup adapter.
- Preserve official request parameter names, including the bracketed `cond[...]` filter keys.
- Normalize the official uppercase item fields into snake_case fields for UMMAYA output, while preserving the raw item in source metadata.
- Expose filters for local-government code, road-name-address substring, update timestamp range, data reference date range, and installation year-month lower bound.
- Keep `numOfRows` capped at 100 unless a later live probe proves the gateway accepts a larger value.
- Use the supplementary local-government code workbook as controlled lookup metadata, not as a replacement for the official API response.

## Curl Shape
```bash
curl --get 'https://apis.data.go.kr/1741000/free_wifi_info/info' \
  --data-urlencode "serviceKey=${DATA_GO_KR_SERVICE_KEY}" \
  --data-urlencode 'pageNo=1' \
  --data-urlencode 'numOfRows=100' \
  --data-urlencode 'returnType=JSON' \
  --data-urlencode 'cond[OPN_ATMY_GRP_CD::EQ]=6110000_ALL'
```

```bash
curl --get 'https://apis.data.go.kr/1741000/free_wifi_info/info' \
  --data-urlencode "serviceKey=${DATA_GO_KR_SERVICE_KEY}" \
  --data-urlencode 'pageNo=1' \
  --data-urlencode 'numOfRows=50' \
  --data-urlencode 'returnType=JSON' \
  --data-urlencode 'cond[LCTN_ROAD_NM_ADDR::LIKE]=종로'
```

## Implementation Cautions
- Do not persist or print the service key.
- Do not call this live endpoint from CI tests.
- URL-encode the bracketed `cond[...]` parameter names and their values through an HTTP client query-parameter API.
- Treat `WGS84_LAT` and `WGS84_LOT` as official coordinates for public Wi-Fi facility locations, not as user location.
- Do not infer current Wi-Fi availability, network security, or user eligibility from this dataset. The service exposes public facility records only.
