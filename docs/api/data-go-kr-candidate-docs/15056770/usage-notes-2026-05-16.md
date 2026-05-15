# 15056770 한국도로교통공단_지자체별 대상 교통사고 통계

## Collection Status
- Source: <https://www.data.go.kr/data/15056770/openapi.do>
- Provider: 한국도로교통공단
- Department: 데이터융합처
- Category: 공공질서및안전 - 안전관리
- Service type: REST
- Response format: JSON+XML
- Application status: already approved in the account. Pressing `활용신청` returned the portal alert `이미 신청 된 데이터입니다.`
- Usage-list evidence: `[승인] 한국도로교통공단_지자체별 대상 교통사고 통계`, 신청일 `2026-04-13`, 만료예정일 `2028-04-13`.
- Development quota: 10,000 calls/day.
- Review policy: development account auto-approved, operation account auto-approved.
- Update cycle: real time.
- License: no public-data usage restriction shown on data.go.kr.
- Count policy for this collection loop: this should not be counted as a fresh new application because the portal reported it was already applied.

## Saved Artifacts
- `data-go-kr-detail.html`: data.go.kr detail page snapshot.
- `intake-record.json`: local intake metadata.
- `기술문서_한국도로교통공단_지자체별 대상 교통사고 통계정보.hwp`: downloaded official guide.
- `기술문서_한국도로교통공단_지자체별 대상 교통사고 통계정보.hwp.txt`: extracted text from the guide. The extraction does not preserve the guide tables, so the request/response table values below were checked against the data.go.kr detail page.

## Endpoint Summary
- Request URL: `http://apis.data.go.kr/B552061/lgStat/getRestLgStat`
- Service URL: `http://apis.data.go.kr/B552061/lgStat`
- Operation name: `지자체별 대상사고통계정보 Rest 조회`
- Operation purpose: looks up local-government traffic-accident statistics by year, province code, and city/county/district code.

Required request parameters:
- `ServiceKey`: data.go.kr service key. The portal table uses capital `S`.
- `searchYearCd`: year code. Official sample: `2019`.

Optional request parameters:
- `siDo`: province/metropolitan code. Official sample: `1100`.
- `guGun`: city/county/district code. Official sample: `1116`.
- `type`: response format, `xml` or `json`. Official sample: `xml`.
- `numOfRows`: rows per page. Official sample: `10`.
- `pageNo`: page number. Official sample: `1`.

Response fields include:
- `resultCode`: API result code.
- `resultMsg`: API result message.
- `std_year`: statistics year.
- `acc_cl_nm`: accident classification name.
- `sido_sgg_nm`: province/city/county/district name.
- `acc_cnt`: accident count.
- `acc_cnt_cmrt`: accident-count composition ratio.
- `dth_dnv_cnt`: death count.
- `dth_dnv_cnt_cmrt`: death-count composition ratio.
- `ftlt_rate`: fatality rate, deaths per 100 traffic accidents.
- `injpsn_cnt`: injured-person count.
- `injpsn_cnt_cmrt`: injured-person composition ratio.
- `tot_acc_cnt`: national total accidents for the accident category.
- `tot_dth_dnv_cnt`: national total deaths for the accident category.
- `tot_injpsn_cnt`: national total injured persons for the accident category.
- `pop_100k`: accidents per 100,000 people, only for total-accident category.
- `car_10k`: accidents per 10,000 vehicles, only for total-accident category.
- `cnt_027_01` through `cnt_027_07`, `cnt_027_99`: violation-type accident counts, only for total-accident category.
- `cnt_014_01` through `cnt_014_04`: accident-type counts, only for total-accident category.
- `totalCount`, `numOfRows`, `pageNo`: pagination fields.

## Domain Notes
The portal description lists 13 accident categories:
- 전체사고
- 어린이사고
- 고령자사고
- 보행자사고
- 자전거사고
- 야간사고
- 어린이보행자사고
- 스쿨존내어린이사고
- 고령운전자사고
- 고령보행자사고
- 개인형이동수단(PM)사고
- 뺑소니사고
- 무면허사고

The official guide also includes code tables for `searchYearCd`, `siDo`, and `guGun`. It notes that 경북 군위군 was incorporated into 대구 군위군 on `2023-07-01`; before July 2023 it is counted as 경북 군위군 accidents, and from July 2023 as 대구 군위군 accidents. For some traffic-condition-derived rates, 2023 경북 군위군 and 대구 군위군 values are combined and may appear identical.

## Adapter Notes
- Suggested primitive: `lookup`.
- Suggested tool name: `koroad_local_traffic_accident_stats_lookup`.
- This is a read-only statistical lookup adapter for local-government traffic-accident summaries.
- The adapter should expose `searchYearCd` as required and allow optional locality narrowing with `siDo` and `guGun`.
- The adapter should preserve official rate semantics: fatality rate is deaths per 100 accidents, while population/vehicle-normalized fields are provided only for the total-accident category.
- Code-table handling should be explicit. Do not silently accept arbitrary locality strings unless a resolver maps them to official `siDo`/`guGun` codes.

## Curl Shape
```bash
curl --get 'http://apis.data.go.kr/B552061/lgStat/getRestLgStat' \
  --data-urlencode "ServiceKey=${DATA_GO_KR_SERVICE_KEY}" \
  --data-urlencode 'searchYearCd=2019' \
  --data-urlencode 'siDo=1100' \
  --data-urlencode 'guGun=1116' \
  --data-urlencode 'type=json' \
  --data-urlencode 'numOfRows=10' \
  --data-urlencode 'pageNo=1'
```

## Implementation Cautions
- Do not persist or print the service key.
- Preserve the official `ServiceKey` parameter casing unless live probing proves lowercase also works.
- Treat this API as already-applied legacy access for this account, not a fresh application in the current 30-new-API loop.
- Keep the downloaded HWP even though text extraction did not preserve tables; the data.go.kr detail page provided the usable request/response parameter table.
