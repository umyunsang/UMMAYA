# 15076244 외교부_국가∙지역별 특별여행주의보

## Collection Status
- Source: <https://www.data.go.kr/data/15076244/openapi.do>
- Provider: 외교부
- Department: 기획조정실 정보화담당관
- Category: 통일·외교 - 외교
- Service type: REST
- Response format: JSON+XML
- Application status: approved.
- Usage-list evidence: `[승인] 외교부_국가∙지역별 특별여행주의보`, 신청일 `2026-05-16`, 만료예정일 `2028-05-16`.
- Development quota: 10,000 calls/day for the selected operation.
- Review policy: development account auto-approved, operation account auto-approved.
- Update cycle: the portal detail page says real-time; the official technical document says daily at `00:00`.
- License: the detail page and application form show `이용허락범위 제한 없음`.

## Saved Artifacts
- `data-go-kr-detail.html`: data.go.kr detail page snapshot.
- `data-go-kr-inline-swagger.json`: inline Swagger/OpenAPI metadata extracted from the detail page.
- `intake-record.json`: local intake metadata.
- `외교부_기술문서_특별여행주의보_v1.docx`: official technical document downloaded from data.go.kr.
- `외교부_기술문서_특별여행주의보_v1.docx.txt`: text extraction of the official technical document.

## Endpoint Summary
- Service URL: `https://apis.data.go.kr/1262000/SptravelWarningServiceV2`
- Official document service URL: `http://apis.data.go.kr/1262000/SpTravelWarningServiceV2`
- Supported schemes in portal Swagger: `https`, `http`
- Operation: `GET /getSptravelWarningListV2`
- Portal operation id: `getSptravelWarningListV2`

The official document example uses mixed casing, `getSpTravelWarningListV2`, while the portal Swagger path is `getSptravelWarningListV2`. Use the portal Swagger path as the primary adapter path and preserve the document example as a compatibility note.

Required request parameters:
- `ServiceKey`: data.go.kr service key. This API uses the capitalized `ServiceKey` spelling.
- `numOfRows`: result count per page. The portal Swagger marks this required.
- `pageNo`: page number. The portal Swagger marks this required.

Optional request parameters:
- `returnType`: response type. Use `JSON` for adapter fixture collection.
- `cond[country_nm::EQ]`: Korean country name equality filter, for example `가나`.
- `cond[country_iso_alp2::EQ]`: ISO alpha-2 country code equality filter, for example `GH`.

The official technical document marks only `ServiceKey` as required and marks `numOfRows`, `pageNo`, the two filters, and `returnType` as optional. For stable adapter calls, include `numOfRows` and `pageNo` because the portal Swagger marks both as required.

Common response envelope fields:
- `response.header.resultCode`: response result code.
- `response.header.resultMsg`: response result message.
- `response.body.dataType`: response data type.
- `response.body.numOfRows`: rows per page.
- `response.body.pageNo`: current page number.
- `response.body.totalCount`: total result count.
- `response.body.items.item[]`: special travel warning records.

Record fields:
- `country_eng_nm`: English country name.
- `country_nm`: Korean country name.
- `country_iso_alp2`: ISO alpha-2 country code.
- `continent_cd`: continent code.
- `continent_eng_nm`: English continent name.
- `continent_nm`: Korean continent name.
- `dang_map_download_url`: risk map download URL.
- `flag_download_url`: flag download URL.
- `map_download_url`: map download URL.
- `evacuate_rcmnd_remark`: evacuation recommendation remarks.
- `evacuate_region_ty`: evacuation recommendation region type.
- `forbidden_rcmnd_remark`: immediate evacuation / travel-forbidden remarks.
- `forbidden_region_ty`: immediate evacuation / travel-forbidden region type.
- `written_dt`: written date.

## Domain Notes
This service exposes the Ministry of Foreign Affairs list of countries and regions subject to special travel warnings. It supports lookups by Korean country name or ISO alpha-2 country code and returns country, continent, map, flag, danger-map, evacuation recommendation, travel-forbidden, and written-date metadata.

The official document includes an ISO country-code reference table for request-parameter validation. Use that table as local controlled metadata for country-name/code normalization, but do not treat it as a substitute for the live API response.

The response example in the official document returns `items.item` as an array. The portal Swagger schema describes `items.item` as an object. The adapter should normalize both singleton-object and array response shapes.

## Adapter Notes
- Suggested primitive: `lookup`.
- Suggested tool name: `mofa_special_travel_warning_lookup`.
- This is a read-only travel-advisory infrastructure lookup adapter.
- Preserve the official `ServiceKey` parameter casing.
- Preserve official bracketed filter names, including `cond[country_nm::EQ]` and `cond[country_iso_alp2::EQ]`.
- Normalize raw country and warning fields into stable snake_case output, while preserving the raw item in source metadata.
- Expose filters for Korean country name and ISO alpha-2 country code.
- Treat the output as official advisory metadata, not as an emergency-decision engine.

## Curl Shape
```bash
curl --get 'https://apis.data.go.kr/1262000/SptravelWarningServiceV2/getSptravelWarningListV2' \
  --data-urlencode "ServiceKey=${DATA_GO_KR_SERVICE_KEY}" \
  --data-urlencode 'returnType=JSON' \
  --data-urlencode 'numOfRows=10' \
  --data-urlencode 'pageNo=1' \
  --data-urlencode 'cond[country_iso_alp2::EQ]=GH'
```

```bash
curl --get 'https://apis.data.go.kr/1262000/SptravelWarningServiceV2/getSptravelWarningListV2' \
  --data-urlencode "ServiceKey=${DATA_GO_KR_SERVICE_KEY}" \
  --data-urlencode 'returnType=JSON' \
  --data-urlencode 'numOfRows=10' \
  --data-urlencode 'pageNo=1' \
  --data-urlencode 'cond[country_nm::EQ]=가나'
```

## Implementation Cautions
- Do not persist or print the service key.
- Do not call this live endpoint from CI tests.
- URL-encode the bracketed `cond[...]` parameter names and their values through an HTTP client query-parameter API.
- Keep the gateway host/path casing aligned with the portal Swagger unless a later direct curl probe proves the official document's mixed-case example is also accepted.
- The official document states no message-level encryption and no transport-level encryption in its security matrix, while the portal Swagger supports `https`; prefer HTTPS for runtime calls.
- Do not infer a country-level safety recommendation beyond the fields returned by the Ministry of Foreign Affairs.
