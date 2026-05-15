# 15098825 - 보건복지부_보건·복지현황_등록장애인 수

## Application Status

- data.go.kr ID: `15098825`
- Provider: 보건복지부
- Category/source scope: 사회복지 / 국가행정기관
- Service type: REST OpenAPI
- Review type: 자동승인
- Application account: 개발
- Application date: 2026-05-16
- Expiry date: 2028-05-16
- Application evidence: 활용신청 현황 row showed `[승인] 보건복지부_보건·복지현황_등록장애인 수`
- Key handling: service key must be read from the user's data.go.kr account when probing locally; do not store the key in repository files.

## Saved Source Artefacts

- `data-go-kr-detail.html`
- `intake-record.json`
- `OpenAPI 활용가이드(보건·복지현황_등록장애인 수).hwp`
- `OpenAPI 활용가이드(보건·복지현황_등록장애인 수).hwp.txt`

The HWP guide is saved, but the plain-text extraction loses most table contents. The endpoint and field contract below are taken from the data.go.kr detail page's 상세기능, 요청변수, and 출력결과 tables captured in `data-go-kr-detail.html`.

## Official Description

This service provides Ministry of Health and Welfare registered-disability statistics by city/province and year from 2015 through 2024. The portal description says the source data is entered by local governments and extracted from 행복e음, the social security information system.

Portal notes:

- 조사대상: 각 시도의 등록 장애인
- 조사시기: 매년말 기준
- 등록 장애인: 장애인복지법 제32조에 따른 등록 장애인
- 등록 장애유형: 장애정도 판정기준에 따른 15개 장애유형

## Endpoint

```http
GET http://apis.data.go.kr/1352000/ODMS_STAT_17/callStat17Api
```

Service URL:

```http
http://apis.data.go.kr/1352000/ODMS_STAT_17
```

The portal detail page lists `http`. Prefer the official listed endpoint first; verify whether `https` is accepted only through a direct live `curl` after the data.go.kr key has propagated.

## Authentication

Use the data.go.kr issued service key as a query parameter.

| Parameter | Required | Description |
|---|---:|---|
| `serviceKey` | yes | 공공데이터포털에서 받은 인증키 |

## Request Parameters

| Parameter | Required | Description | Captured sample |
|---|---:|---|---|
| `serviceKey` | yes | 공공데이터포털에서 받은 인증키 | redacted |
| `pageNo` | yes | 페이지번호 | `1` |
| `numOfRows` | yes | 한 페이지 결과 수, maximum `500` | `10` |
| `apiType` | no | 결과형식, `XML` or `JSON` | `XML` |
| `year` | no | 해당 년도 | `2019` |
| `dvsd` | no | 시도구분 | `충남` |

Example shape, with the service key redacted:

```http
GET /1352000/ODMS_STAT_17/callStat17Api?serviceKey={DATA_GO_KR_SERVICE_KEY}&pageNo=1&numOfRows=10&apiType=JSON&year=2019&dvsd=%EC%B6%A9%EB%82%A8
Host: apis.data.go.kr
Accept: application/json
```

## Response Shape

Top-level/page fields:

- `resultCode`: 결과코드, sample `00`
- `resultMsg`: 결과메시지, sample `NORMAL SERVICE`
- `numOfRows`: 한 페이지당 표출 데이터 수
- `pageNo`: 페이지번호
- `totalCount`: 해당 API에서 제공하는 데이터 전체 건수

Record identity fields:

- `year`: 년도
- `dvsd`: 시도구분

Total fields:

- `sumTtl`: 총계_계
- `maleSum`: 총계_남
- `sumFml`: 총계_여

Disability-type count fields follow the same male/female/total pattern:

- 지체장애: `phdsMale`, `phdsFml`, `phdsTtl`
- 시각장애: `vsimpMale`, `vsimpFml`, `vsimpTtl`
- 청각장애: `deafMale`, `deafFml`, `deafTtl`
- 언어장애: `lngdsMale`, `lngdsFml`, `lngdsTtl`
- 지적장애: `indsbMale`, `indsbFml`, `indsbTtl`
- 자폐성장애: `atsdsMale`, `atsdsFml`, `atsdsTtl`
- 정신장애: `mtdsrMale`, `mtdsrFml`, `mtdsrTtl`
- 신장장애: `kdflrMale`, `kdflrFml`, `kdflrTtl`
- 심장장애: `mpdsrMale`, `mpdsrFml`, `mpdsrTtl`
- 호흡기장애: `rspdsMale`, `rspdsFml`, `rspdsTtl`
- 간장애: `ldsrMale`, `ldsrFml`, `ldsrTtl`
- 안면장애: `blddsMale`, `blddsFml`, `blddsTtl`
- 장루요루장애: `stdsrMale`, `stdsrFml`, `stdsrTtl`
- 뇌전증장애: `epdsrMale`, `epdsrFml`, `epdsrTtl`
- 뇌병변장애: `crbpyMale`, `crbpyFml`, `crbpyTtl`

## Adapter Mapping Notes

- Candidate primitive: `find` or `lookup` style read-only statistical lookup.
- Suggested tool intent: retrieve registered-disability counts by year and city/province, preserving the raw disability-type count fields in the output fixture.
- Treat `year` and `dvsd` as optional filters. The official description lists the current coverage as 2015-2024; document or validate out-of-range years before presenting empty results as absence of data.
- Keep Korean disability-type labels in adapter descriptions because the data is a Korean welfare statistics domain; expose raw English field keys in fixtures.
- Live contract probing should be done with direct `curl` after key propagation; do not run live probes in CI.
