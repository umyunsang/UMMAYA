# 15098820 - 보건복지부_보건·복지현황_시도별 노인 취업알선 실적

## Application Status

- data.go.kr ID: `15098820`
- Provider: 보건복지부
- Category/source scope: 사회복지 / 중앙행정기관
- Service type: REST OpenAPI
- Review type: 심의
- Application account: 개발
- Application date: 2026-05-16
- Application evidence: 활용신청 현황 row showed `[신청] 보건복지부_보건·복지현황_시도별 노인 취업알선 실적`
- Approval status at collection time: pending review, not auto-approved
- Key handling: service key must be read from the user's data.go.kr account after approval; do not store the key in repository files.

## Saved Source Artefacts

- `data-go-kr-detail.html`
- `intake-record.json`
- `OpenAPI 활용가이드(보건·복지현황_시도별 노인 취업알선 실적).hwp`
- `OpenAPI 활용가이드(보건·복지현황_시도별 노인 취업알선 실적).hwp.txt`

The HWP guide is saved, but the plain-text extraction loses most table contents. The endpoint and field contract below are taken from the data.go.kr detail page's 상세기능, 요청변수, and 출력결과 tables captured in `data-go-kr-detail.html`.

## Official Description

This service provides Ministry of Health and Welfare statistics for city/province-level senior employment placement performance from 2015 through 2019. The portal notes that this statistical series ended as of the end of 2019. The source is 한국노인인력개발원 노인일자리업무시스템.

Domain definitions from the page:

- 취업알선: employment counseling and placement service for local seniors seeking work
- 장기취업: employment for 3 months or longer
- 단기취업: employment for 1 to 2 months

## Endpoint

```http
GET http://apis.data.go.kr/1352000/ODMS_STAT_48/callStat48Api
```

Service URL:

```http
http://apis.data.go.kr/1352000/ODMS_STAT_48
```

The portal detail page lists `http`. Prefer the official listed endpoint first; verify whether `https` is accepted only through a direct live `curl` after approval.

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
| `year` | no | 해당 년도 | `2016` |
| `dvsd` | no | 시도구분 | `경남` |

Example shape, with the service key redacted:

```http
GET /1352000/ODMS_STAT_48/callStat48Api?serviceKey={DATA_GO_KR_SERVICE_KEY}&pageNo=1&numOfRows=10&apiType=JSON&year=2016&dvsd=%EA%B2%BD%EB%82%A8
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

Record fields:

- `year`: 년도
- `dvsd`: 시도구분
- `stempMdtn`: 단기취업_알선
- `stempEmpl`: 단기취업_취업
- `ltepMdtn`: 장기취업_알선
- `ltepEmpl`: 장기취업_취업
- `ttlMdtn`: 계_알선
- `ttlEmpl`: 계_취업

## Adapter Mapping Notes

- Candidate primitive: `find` or `lookup` style read-only statistical lookup.
- Suggested tool intent: retrieve senior employment placement statistics by year and city/province, with separate short-term, long-term, and total mediation/employment counts.
- Treat `year` and `dvsd` as optional filters. Because the official time range is fixed at 2015-2019 and the series has ended, validate or document that out-of-range years may return empty results.
- Keep the Korean field names in adapter descriptions because the data is a Korean government statistical domain; expose raw English field keys in fixtures.
- Approval was still pending at collection time, so live probing should wait until the portal changes from `[신청]` to `[승인]`.
- Live contract probing should be done with direct `curl` after approval; do not run live probes in CI.
