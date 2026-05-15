# 15058166 - 국토교통부_공동주택 입찰공고 정보제공 서비스

## Collection Status

- Source page: `https://www.data.go.kr/data/15058166/openapi.do`
- Captured contract: `data-go-kr-inline-swagger.json`
- Downloaded technical document: `코드정의서.xlsx` and extracted text `코드정의서.xlsx.txt`
- Application status: submitted through data.go.kr and visible in `활용신청 현황` as `[승인] 국토교통부_공동주택 입찰공고 정보제공 서비스`.
- Application evidence captured from data.go.kr account list: 신청일 `2026-05-16`, 만료예정일 `2028-05-16`, 계정 `개발`.
- Application type shown by data.go.kr: `개발계정 | 활용신청`
- Review mode shown by data.go.kr: `자동승인`
- Usage period shown by data.go.kr: `승인일로부터 24개월 간 활용가능`
- License shown by data.go.kr: `이용허락범위 제한 없음`
- Selected functions on form: all listed detail functions selected.

## Request Base

- Protocols: `https`, `http`
- Host/service root: `apis.data.go.kr/1613000/ApHusBidPblAncInfoOfferServiceV2`
- Auth parameter: `serviceKey`
- Common optional paging parameters: `pageNo`, `numOfRows`
- Response media shown by Swagger: `application/json`

Example shape:

```text
GET https://apis.data.go.kr/1613000/ApHusBidPblAncInfoOfferServiceV2/getHsmpCdSearchV2?serviceKey={DATA_GO_KR_SERVICE_KEY}&kaptCode={KAPT_CODE}&pageNo=1&numOfRows=10
```

## Operations

| Operation | Meaning | Required query parameters | Optional query parameters |
| --- | --- | --- | --- |
| `GET /getHsmpNmSearchV2` | 단지명 조회 | `serviceKey`, `bidKaptname`, `searchYear` | `pageNo`, `numOfRows` |
| `GET /getBidMethodSearchV2` | 입찰 방법 조회 | `serviceKey`, `codeWay`, `searchYear` | `pageNo`, `numOfRows` |
| `GET /getBidPblAncNmSearchV2` | 입찰 공고명 조회 | `serviceKey`, `bidTitle`, `searchYear` | `pageNo`, `numOfRows` |
| `GET /getBidClosDeSearchV2` | 입찰 마감일 조회 | `serviceKey`, `startDate`, `endDate` | `pageNo`, `numOfRows` |
| `GET /getBidKndSearchV2` | 입찰 종류 조회 | `serviceKey`, `codeAuth`, `searchYear` | `pageNo`, `numOfRows` |
| `GET /getBidSttusSearchV2` | 입찰 상태 조회 | `serviceKey`, `bidState`, `searchYear` | `pageNo`, `numOfRows` |
| `GET /getPblAncDeSearchV2` | 입찰 공고일 조회 | `serviceKey`, `startDate`, `endDate` | `pageNo`, `numOfRows` |
| `GET /getHsmpCdSearchV2` | 단지코드 조회 | `serviceKey`, `kaptCode` | `regDate`, `pageNo`, `numOfRows` |

## Parameter Notes

- `bidKaptname`: 단지명 filter.
- `searchYear`: 검색년도 in `YYYY`.
- `codeWay`: 입찰방법 code. Code sheet lists `00` 직접입찰, `01` 전자입찰.
- `bidTitle`: 입찰공고명 filter.
- `startDate` / `endDate`: date range filters for closing date or announcement date operations.
- `codeAuth`: 입찰종류 source code. Swagger lists `01` K-APT, `02` 조달청, `03` 아파트비드포유, `04` KG2B전자입찰, `05` 나이스아파트, `06` 이 아파트, `99` 기타민간업체.
- `bidState`: 입찰상태 code. Swagger lists `1` 신규공고, `2` 수정공고, `3` 재공고.
- `kaptCode`: 아파트/공동주택 단지코드.
- `regDate`: 등록일자 filter for 단지코드 조회.

## Code Sheet Notes

`코드정의서.xlsx` includes local domain code mappings for adapter validation and display:

- `state`: 입찰진행상황, including `1` 신규공고, `2` 수정공고, `3` 재공고, `4` 유찰, `5` 낙찰(계약완료), `6` 취소, `9` 낙찰무효, `10` 계약취소, `99` 낙찰취소후신규공고.
- `area`: 지역코드, including 서울 `11`, 부산 `26`, 대구 `27`, 인천 `28`, 광주 `29`, 대전 `30`, 울산 `31`, 세종 `36`, 경기 `41`, 강원 `42`, 충북 `43`, 충남 `44`, 전북 `45`, 전남 `46`, 경북 `47`, 경남 `48`, 제주 `50`.
- `code_classify_type_1`: 입찰 구분 타입1, `01` 주택관리업자, `02` 사업자.
- `code_classify_type_2`: 입찰 구분 타입2, including 공동주택위탁관리, 공사, 용역, 물품, 기타.
- `code_classify_type_3`: 입찰 구분 타입3, including 하자보수, 장기수선, 일반보수, 경비, 청소, 승강기유지, 전기안전관리, 소독, 회계감사.
- `code_kind`: 입찰종류, `01` 일반경쟁, `02` 제한경쟁, `03` 지명경쟁.
- `code_suc_way`: 낙찰방법, including 적격심사, 최저 낙찰, 최고 낙찰.
- `con_type`: 선정 방법, `01` 경쟁입찰, `02` 수의계약.

## Response Shape

- Common envelope: `header.resultCode`, `header.resultMsg`, `body.items`, `body.numOfRows`, `body.pageNo`, `body.totalCount`.
- Operation description says returned bid item fields include: `입찰 번호`, `단지코드`, `법정동시도코드`, `입찰제목`, `내용`, `입찰공고일`, `입찰마감일`, `단지명`, `입찰공고상태코드`, `입찰업체코드`, `입찰종류코드`, `입찰분류1코드`, `입찰분류2코드`, `입찰분류3코드`, `긴급입찰여부`, `입찰방법코드`, `낙찰방법코드`, `신용평가등급확인서 제출여부`, `현장설명 일시`, `현장설명 장소`, `관리(공사용역) 실적 증명서 제출여부`, `구비서류`, `서류제출마감일`, `입찰보증보험증권`, `지급조건`, `낙찰/유찰사유`, `첨부파일`.

## UMMAYA Adapter Reading

- Candidate primitive: `lookup`/`find`.
- Data domain: housing, apartment-management procurement and bid announcements.
- Live shape: data.go.kr REST with `serviceKey` query authentication.
- Tool boundary: read-only public-data lookup; no citizen transaction or write action.
- Suggested wrapper module name: `molit_apartment_bid_announcement_service`.
- Korean search hints: `공동주택 입찰`, `아파트 입찰공고`, `K-APT`, `입찰 마감일`, `입찰 상태`, `단지코드`.
- English search hints: `apartment bid announcement`, `K-APT procurement`, `housing bid`, `apartment management procurement`.

## Exclusion Check

This API is not in the already-completed exclusion set reported by the user on 2026-05-16:

- `15043459`, `15073861`, `15091886`, `15091910`
- `15098529`, `15098530`, `15098533`, `15098534`
- `15101360`, `15129394`, `15134761`, `15157485`
- `15158680`, `15158684`

It is also separate from the deferred set already documented in existing notes: NTS, EMS tracking, MOLEG SOAP services, MSIT project announcement, and MOJ foreign-resident status APIs.
