# 15000900 - 중앙선거관리위원회_투·개표 정보

## Application Status

- Portal: data.go.kr
- Application status: 승인
- Application date: 2026-05-16
- Expiration date: 2028-05-16
- Account: 개발
- Evidence page: data.go.kr 마이페이지 > 활용신청 현황
- Evidence row: `[승인] 중앙선거관리위원회_투·개표 정보`

## Local Source Artifacts

- `OpenAPI활용가이드(투개표정보)_v4.3.zip`
- `OpenAPI활용가이드(투개표정보)_v4.3-unzipped/zip-member-001.hwp`
- `OpenAPI활용가이드(투개표정보)_v4.3-unzipped/zip-member-001.hwp.txt`
- `OpenAPI활용가이드(투개표정보)_v4.3-unzipped/zip-member-002.hwpx`
- `data-go-kr-detail.html`

## UMMAYA Adapter Candidate

- Proposed module id: `nec_vote_count_status_service`
- Candidate primitive: `lookup`
- Korean search hints: 투개표, 투표결과, 개표결과, 대통령선거, 국회의원선거, 지방선거, 재보궐선거, 중앙선거관리위원회
- English search hints: Korean election vote results, ballot count, turnout, National Election Commission, election result lookup
- Domain fit: official post-election voting and counting result lookup.

## Endpoint

- Service root: `http://apis.data.go.kr/9760000/VoteXmntckInfoInqireService2`
- Data format: XML by provider guide default; portal labels the API as JSON+XML.
- Authentication parameter: `serviceKey`
- Development daily traffic: `10000`
- Data update note: not real-time on election day; data is normally transferred and validated within about two months after the election ends.
- Code dependency: `sgId`, `sgTypecode`, `sdName`, `wiwName`, and `sggName` should be derived from the provider's code-info service where possible.

## Operation 1: GET /getVoteSttusInfoInqire

Vote result lookup.

Request URL:

```text
http://apis.data.go.kr/9760000/VoteXmntckInfoInqireService2/getVoteSttusInfoInqire
```

Required parameters from the provider guide:

- `serviceKey`: data.go.kr service key
- `pageNo`: page number, max `100000`
- `numOfRows`: rows per page, max `100`
- `sgId`: election ID, example `20220309`
- `sgTypecode`: election type code

Optional parameters:

- `resultType`: default `xml`
- `sdName`: 시도명, example `서울특별시`
- `wiwName`: 구시군명, example `종로구`

Election type guidance from the provider guide:

- Presidential election: `1`
- National Assembly proportional representation lookup: `7`
- Local election governor/mayor lookup: `3`
- By-election: use values returned by the code-info API.

Response envelope:

- `header.resultCode`
- `header.resultMsg`
- `body.items.item[]`
- `body.numOfRows`
- `body.pageNo`
- `body.totalCount`

Representative `item` fields:

- `num`: result order
- `sgId`: election ID
- `sgTypecode`: election type code
- `sdName`: 시도명
- `wiwName`: 구시군명
- `totSunsu`: total eligible voters
- `psSunsu`: election-day eligible voters
- `psEtcSunsu`: residence, early, shipboard, overseas eligible voters
- `totTusu`: total voters
- `psTusu`: election-day voters
- `psEtcTusu`: residence, early, shipboard, overseas voters
- `turnout` or `Turnout`: turnout
- `vrOrder`: sort order

## Operation 2: GET /getXmntckSttusInfoInqire

Vote counting result lookup.

Request URL:

```text
http://apis.data.go.kr/9760000/VoteXmntckInfoInqireService2/getXmntckSttusInfoInqire
```

Required parameters from the provider guide:

- `serviceKey`: data.go.kr service key
- `pageNo`: page number, max `100000`
- `numOfRows`: rows per page, max `100`
- `sgId`: election ID, example `20220309`
- `sgTypecode`: election type code

Optional parameters:

- `resultType`: default `xml`
- `sggName`: 선거구명, example `대한민국`
- `sdName`: 시도명, example `서울특별시`
- `wiwName`: 구시군명, example `종로구`

Response envelope:

- `header.resultCode`
- `header.resultMsg`
- `body.items.item[]`
- `body.numOfRows`
- `body.pageNo`
- `body.totalCount`

Representative `item` fields:

- `num`: result order
- `sgId`: election ID
- `sgTypecode`: election type code
- `sggName`: 선거구명
- `sdName`: 시도명
- `wiwName`: 구시군명
- `sunsu`: eligible voters
- `tusu`: votes cast
- `yutusu`: valid votes
- `mutusu`: invalid votes
- `gigwonsu`: abstentions
- `jd01` through `jd50`: party names
- `hbj01` through `hbj50`: candidate names
- `dugsu01` through `dugsu50`: vote counts
- `crOrder`: sort order

## Error Notes

Public data portal errors are XML-only in the provider guide.

Provider error examples:

- `ERROR-03`: no matching data
- `ERROR-301`: invalid or missing file type parameter
- `ERROR-310`: service not found
- `ERROR-333`: invalid request-position type
- `ERROR-340`: missing required parameter
- `ERROR-500`: server error
- `ERROR-601`: SQL statement error

## Adapter Notes

- Store the portal service key only through the runtime secret channel; do not commit keys.
- Keep vote-status and counting-status as separate operation-specific request models.
- Use the provider guide as the primary source where the portal detail page and guide differ on whether `pageNo` and `numOfRows` are required.
- Preserve the provider's non-real-time warning in user-facing output so users do not mistake post-election data for election-day live counting.
- The first live probe should use `numOfRows=1`, a known historical `sgId`, and explicit `resultType=xml` before testing JSON behavior.
