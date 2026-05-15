# 15106731 - 한국저작권위원회_저작권등록정보서비스(신규)

## Application Status

- Portal: data.go.kr
- Application status: 승인
- Application date: 2026-05-16
- Account: 개발
- Form period statement: 승인일로부터 24개월 간 활용가능
- Evidence page: data.go.kr 마이페이지 > 활용신청 현황
- Evidence row: `[승인] 한국저작권위원회_저작권등록정보서비스(신규)`

## Local Source Artifacts

- `intake-record.json`
- `data-go-kr-catalog.json`
- `data-go-kr-swagger-url.json`
- `data-go-kr-inline-swagger.json`

## UMMAYA Adapter Candidate

- Proposed module id: `copyright_registration_info_service`
- Candidate primitive: `lookup`
- Korean search hints: 저작권등록정보, 저작권 등록번호, 저작자, 저작물 제호, 한국저작권위원회, 저작물검색
- English search hints: copyright registration, registered work, author lookup, copyright owner, Korea Copyright Commission
- Domain fit: copyright registration search and registered-work detail lookup.

## Endpoint

- Base URL: `https://api.odcloud.kr/api`
- Alternate scheme in Swagger: `http`
- Authentication:
  - Header: `Authorization`
  - Query parameter: `serviceKey`
- Default response: JSON
- XML response option: `returnType=XML`
- Pagination:
  - `page`: page index, default `1`
  - `perPage`: page size, default `10`

## Operations

### GET /CpyrRegInforService/v1/getCpyrRegInforUniList

Copyright registration integrated search list.

Required parameters:

- `serviceKey` or `Authorization`

Optional query parameters:

- `page`: integer page index
- `perPage`: integer page size
- `returnType`: use `XML` for XML; omit for JSON
- `cond[REG_ID::EQ]`: 저작권 등록번호 exact match
- `cond[CONT_TITLE::LIKE]`: 제호 partial match
- `cond[AUTHOR_NAME::LIKE]`: 저작자 partial match

Response envelope:

- `page`
- `perPage`
- `totalCount`
- `currentCount`
- `matchCount`
- `data[]`

Representative `data[]` fields:

- `REG_ID`: 저작권 등록번호
- `CONT_TITLE`: 제호
- `AUTHOR_NAME`: 저작자
- `REG_DATE`: 등록일자

### GET /CpyrRegInforService/v1/getCpyrRegInforUniDetail

Copyright registration integrated detail lookup.

Required parameters:

- `serviceKey` or `Authorization`

Optional query parameters:

- `page`: integer page index
- `perPage`: integer page size
- `returnType`: use `XML` for XML; omit for JSON
- `cond[REG_ID::EQ]`: 저작권 등록번호 exact match

Adapter validation note:

- The provider Swagger does not mark `cond[REG_ID::EQ]` as required, but this detail endpoint is only meaningful with a registration number filter. The adapter should treat missing `REG_ID` as a local validation error or downgrade the call to the list operation.

Response envelope:

- `page`
- `perPage`
- `totalCount`
- `currentCount`
- `matchCount`
- `data[]`

Representative `data[]` fields:

- `REG_ID`: 저작권 등록번호
- `REG_REASON`: 등록원인
- `CONT_TITLE`: 제호
- `REG_PART1_NAME`: 등록부문1
- `REG_PART2_NAME`: 등록부문2
- `CONT_CLASS_NAME`: 저작물 종류
- `AUTHOR_NAME`: 저작자
- `REG_DATE`: 등록일자
- `DISPOSAL_NAME`: 등록권리자

## Adapter Notes

- Store the portal service key only through the runtime secret channel; do not commit keys.
- Use ODCLOUD parameter encoding exactly for conditional filters, including square brackets and `::`.
- Start live validation with the list endpoint and a narrow `perPage=1` query.
- For user-facing results, preserve source attribution to 한국저작권위원회 and the data.go.kr page.
