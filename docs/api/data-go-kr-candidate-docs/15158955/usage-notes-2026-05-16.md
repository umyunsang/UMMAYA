# 15158955 - 한국대학교육협의회_대학 학과 정보_GW

## Collection Status

- Source page: `https://www.data.go.kr/data/15158955/openapi.do`
- Captured contract: `data-go-kr-inline-swagger.json`
- Application status: submitted through data.go.kr and visible in `활용신청 현황` as `[승인] 한국대학교육협의회_대학 학과 정보_GW`.
- Application evidence captured from data.go.kr account list: 신청일 `2026-05-16`, 만료예정일 `2028-05-16`, 계정 `개발`.
- Application type shown by data.go.kr: `개발계정 | 활용신청`
- Review mode shown by data.go.kr: `자동승인`
- Usage period shown by data.go.kr: `승인일로부터 24개월 간 활용가능`
- License shown by data.go.kr: `이용허락범위 제한 없음`
- Selected functions on form: all listed detail functions selected.

## Request Base

- Protocols: `https`, `http`
- Host: `apis.data.go.kr`
- Service root: `/B340014/BasicInformationService_1`
- Auth parameter: `serviceKey`
- Common optional paging parameters: `pageNo`, `numOfRows`

Example shape:

```text
GET https://apis.data.go.kr/B340014/BasicInformationService_1/{operation}?serviceKey={DATA_GO_KR_SERVICE_KEY}&pageNo=1&numOfRows=10
```

## Operations

| Operation | Meaning | Required query parameters | Optional query parameters |
| --- | --- | --- | --- |
| `GET /getCodeByLargeSeries` | 표준분류 대계열 코드조회 | `serviceKey`, `svyYr` | `pageNo`, `numOfRows`, `cdid`, `cdnm` |
| `GET /getUniversityMajorCode` | 학교별학과 코드조회 | `serviceKey`, `svyYr`, `schlId` | `pageNo`, `numOfRows`, `schlMjrId` |
| `GET /getCodeByMiddleSeries` | 표준분류 중계열 코드조회 | `serviceKey`, `svyYr` | `pageNo`, `numOfRows`, `cdid`, `cdnm` |
| `GET /getCodeBySeriesSystem` | 표준분류 계열체계 조회 | `serviceKey`, `svyYr` | `pageNo`, `numOfRows`, `srsLclftCd`, `srsMclftCd`, `srsSclftCd` |
| `GET /getCodeByPrincipalSchoolBranchSchool` | 본분교 코드조회 | `serviceKey` | `pageNo`, `numOfRows`, `cdid`, `cdnm` |
| `GET /getCodeByLessonTerm` | 수업연한 코드조회 | `serviceKey` | `pageNo`, `numOfRows`, `cdid`, `cdnm` |
| `GET /getCodeByDegreeCourse` | 학위과정 코드조회 | `serviceKey` | `pageNo`, `numOfRows`, `cdid`, `cdnm` |
| `GET /getCodeByDayAndNight` | 주야간 코드조회 | `serviceKey` | `pageNo`, `numOfRows`, `cdid`, `cdnm` |
| `GET /getCodeByCollege` | 단과대학 코드조회 | `serviceKey` | `pageNo`, `numOfRows`, `cdid`, `cdnm` |
| `GET /getCodeByMajorStatus` | 학과상태 코드조회 | `serviceKey` | `pageNo`, `numOfRows`, `cdid`, `cdnm` |
| `GET /getCodeByMajorCharacter` | 학과특성 코드조회 | `serviceKey` | `pageNo`, `numOfRows`, `cdid`, `cdnm` |
| `GET /getCodeByOneselfSeries` | 대학자체계열 코드조회 | `serviceKey` | `pageNo`, `numOfRows`, `cdid`, `cdnm` |
| `GET /getCodeBySmallSeries` | 표준분류 소계열 코드조회 | `serviceKey`, `svyYr` | `pageNo`, `numOfRows`, `cdid`, `cdnm` |

## Parameter Notes

- `svyYr`: 조사년도. Year-scoped classification and major-code operations require it.
- `schlId`: 학교ID. Required only for `getUniversityMajorCode`.
- `schlMjrId`: 학교학과ID filter for `getUniversityMajorCode`.
- `cdid`: operation-specific code filter.
- `cdnm`: operation-specific Korean code-name filter.
- `srsLclftCd`: 표준분류 대계열 코드.
- `srsMclftCd`: 표준분류 중계열 코드.
- `srsSclftCd`: 표준분류 소계열 코드.

## UMMAYA Adapter Reading

- Candidate primitive: `lookup`/`find`.
- Data domain: education, university department/classification reference data.
- Live shape: data.go.kr REST with `serviceKey` query authentication.
- Tool boundary: read-only public-data lookup; no citizen transaction or write action.
- Suggested wrapper module name: `kcue_basic_information_service`.
- Korean search hints: `대학 학과`, `대학 학과 코드`, `표준분류 계열`, `학교별 학과`, `단과대학 코드`.
- English search hints: `university major code`, `Korean university department`, `higher education classification`, `KCUE`.

## Exclusion Check

This API is not in the already-completed exclusion set reported by the user on 2026-05-16:

- `15043459`, `15073861`, `15091886`, `15091910`
- `15098529`, `15098530`, `15098533`, `15098534`
- `15101360`, `15129394`, `15134761`, `15157485`
- `15158680`, `15158684`

It is also separate from the deferred set already documented in existing notes: NTS, EMS tracking, MOLEG SOAP services, MSIT project announcement, and MOJ foreign-resident status APIs.
