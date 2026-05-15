# 15126482 - 서울특별시교육청_평생학습포털 에버러닝 강좌정보 서비스

## Collection Status

- Source page: `https://www.data.go.kr/data/15126482/openapi.do`
- Captured contract: `data-go-kr-inline-swagger.json`
- Application status: submitted through data.go.kr and visible in `활용신청 현황` as `[승인] 서울특별시교육청_평생학습포털 에버러닝 강좌정보 서비스`.
- Application evidence captured from data.go.kr account list: 신청일 `2026-05-16`, 만료예정일 `2028-05-16`, 계정 `개발`.
- Application type shown by data.go.kr: `개발계정 | 활용신청`
- Review mode shown by data.go.kr: `자동승인`
- Usage period shown by data.go.kr: `승인일로부터 24개월 간 활용가능`
- License shown by data.go.kr: `이용허락범위 제한 없음`
- Selected functions on form: all listed detail functions selected.

## Request Base

- Protocols: `https`, `http`
- Host/service root: `apis.data.go.kr/7010000/everlearning`
- Operation: `GET /getLectureList`
- Auth parameter: `ServiceKey`
- Response media shown by Swagger: `application/xml`

Example shape:

```text
GET https://apis.data.go.kr/7010000/everlearning/getLectureList?ServiceKey={DATA_GO_KR_SERVICE_KEY}&pageNo=1&numOfRows=10
```

## Operation

| Operation | Meaning | Required query parameters | Optional query parameters |
| --- | --- | --- | --- |
| `GET /getLectureList` | 서울특별시교육청 평생학습포털 에버러닝 강좌 정보 조회 | `ServiceKey`, `pageNo`, `numOfRows` | `searchKeyword`, `searchOrganNm`, `searchTarget`, `searchCategory`, `searchPay`, `searchDayOfWeek`, `searchDayStartTm`, `searchSigungu`, `searchApplyStartYmd`, `searchApplyEndYmd`, `searchLectureStartYmd`, `searchLectureEndYmd` |

## Parameter Notes

- `pageNo`: page number.
- `numOfRows`: number of rows per page.
- `searchKeyword`: 강좌명 filter.
- `searchOrganNm`: 기관명 filter.
- `searchTarget`: 강좌대상 filter.
- `searchCategory`: 강좌분류 filter.
- `searchPay`: 수강료 filter.
- `searchDayOfWeek`: 강의요일 filter.
- `searchDayStartTm`: 강의시작시간 filter.
- `searchSigungu`: 운영지역 filter.
- `searchApplyStartYmd` / `searchApplyEndYmd`: 접수기간 start/end date filters.
- `searchLectureStartYmd` / `searchLectureEndYmd`: 강의기간 start/end date filters.

## Response Shape

- Header fields: `resultCode`, `resultMsg`, `numOfRows`, `pageNo`, `totalCnt`.
- Item fields include: `lectureId`, `lectureNm`, `place`, `teacherNm`, `materialNm`, `materialCost`, `lectureCost`, `contactInfo`, `lectureStartYmd`, `lectureEndYmd`, `applyStartYmd`, `applyEndYmd`, `applyStartTm`, `applyEndTm`, `dayOfWeek`, `organNm`, `organTelNo`, `categoryNm`, `sigunguNm`, `targetNm`, `lectureStatusNm`.

## UMMAYA Adapter Reading

- Candidate primitive: `lookup`/`find`.
- Data domain: education, lifelong-learning lecture/course discovery.
- Live shape: data.go.kr REST with `ServiceKey` query authentication.
- Tool boundary: read-only public-data lookup; no citizen transaction or write action.
- Suggested wrapper module name: `seoul_everlearning_lecture_service`.
- Korean search hints: `평생학습`, `에버러닝`, `서울시교육청 강좌`, `강좌 접수`, `평생교육 강좌`.
- English search hints: `lifelong learning lecture`, `Seoul education course`, `Everlearning`, `public course search`.

## Exclusion Check

This API is not in the already-completed exclusion set reported by the user on 2026-05-16:

- `15043459`, `15073861`, `15091886`, `15091910`
- `15098529`, `15098530`, `15098533`, `15098534`
- `15101360`, `15129394`, `15134761`, `15157485`
- `15158680`, `15158684`

It is also separate from the deferred set already documented in existing notes: NTS, EMS tracking, MOLEG SOAP services, MSIT project announcement, and MOJ foreign-resident status APIs.
