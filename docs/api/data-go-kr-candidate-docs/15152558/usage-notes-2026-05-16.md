# 15152558 - 국회 국회사무처_법률안 제안이유 및 주요내용

## Intake

- Source: data.go.kr OpenAPI detail page, LINK type.
- Provider: 국회 국회사무처.
- Category: 일반공공행정 - 법제.
- Data format: XML on data.go.kr metadata; National Assembly endpoint supports `xml` and `json` via `Type`.
- Update cycle: 실시간.
- License: data.go.kr says 이용허락범위 제한 없음.
- data.go.kr application action: the normal `활용신청` form is not present because this is a LINK API. The data.go.kr `바로가기` button was clicked from the logged-in Chrome session; this is the official LINK action path exposed by the detail page.
- Verification note: after the LINK click, `활용신청 현황` search for `법률안 제안이유` returned 0 rows. Treat this as a LINK-style candidate whose callable contract is hosted and keyed by the National Assembly Open API portal, not a data.go.kr service-key approval row.

## Saved Source Files

- `data-go-kr-detail.html`: data.go.kr detail page.
- `data-go-kr-catalog.json`: schema.org metadata from data.go.kr.
- `data-go-kr-inline-swagger.json`: data.go.kr inline Swagger placeholder; paths are empty for this LINK item.
- `open-assembly-service-page.html`: official National Assembly Open API detail page.
- `open-assembly-openapi-meta.json`: official dynamic metadata returned by `selectOpenApiMeta.do`.
- `법률안_제안이유_및_주요내용_오픈API명세서.xlsx`: official downloaded Open API specification.
- `법률안_제안이유_및_주요내용_오픈API명세서.xlsx.txt`: text extraction from the downloaded specification.
- `selectNaOpenApi.js`: National Assembly Open API page script that documents metadata/spec download behavior.

## Endpoint

```text
GET https://open.assembly.go.kr/portal/openapi/BPMBILLSUMMARY
```

The same endpoint appears in both the rendered National Assembly page and the downloaded specification.

## Authentication

- Parameter: `KEY`
- Type: `STRING`
- Required: yes
- Meaning: National Assembly Open API authentication key.
- Sample docs default: `sample key`.

Do not store a real key in this repository.

## Required Base Parameters

| Name | Type | Required | Description | Default in docs |
| --- | --- | --- | --- | --- |
| `KEY` | `STRING` | yes | 인증키 | `sample key` |
| `Type` | `STRING` | yes | 호출 문서 형식: `xml` or `json` | `xml` |
| `pIndex` | `INTEGER` | yes | 페이지 위치 | `1`; sample key fixed to `1` |
| `pSize` | `INTEGER` | yes | 페이지 당 요청 숫자 | `100`; sample key fixed to `5` |

## Required Domain Parameter

| Name | Type | Required | Description | Example |
| --- | --- | --- | --- | --- |
| `BILL_NO` | `STRING` | yes | 의안번호 | `2126626` in the official sample URL |

## Official Sample URL Shape

```text
https://open.assembly.go.kr/portal/openapi/BPMBILLSUMMARY?KEY=<KEY>&Type=json&pIndex=1&pSize=100&BILL_NO=<BILL_NO>
```

The dynamic metadata file includes a sample URI with `BILL_NO=2126626`; the visible UI may omit the base parameters from the abbreviated sample link, but the downloaded specification marks all base parameters as required.

## Response Fields

| Field | Description |
| --- | --- |
| `BILL_NO` | 의안번호 |
| `BILL_NAME` | 의안명 |
| `BILL_ID` | 의안ID |
| `SUMMARY` | 주요내용 |
| `AGE` | 대수 |

## Error And Info Codes

| Tag | Code | Meaning |
| --- | --- | --- |
| `ERROR` | `300` | 필수 값 누락 |
| `ERROR` | `290` | 인증키 유효하지 않음 |
| `ERROR` | `337` | 일별 트래픽 제한 초과 |
| `ERROR` | `310` | 서비스 미확인; `SERVICE` 확인 필요 |
| `ERROR` | `333` | 요청위치 값 타입 오류 |
| `ERROR` | `336` | 1회 최대 1,000건 초과 |
| `ERROR` | `500` | 서버 오류 |
| `ERROR` | `600` | 데이터베이스 연결 오류 |
| `ERROR` | `601` | SQL 문장 오류 |
| `ERROR` | `990` | 인증서 폐기 |
| `INFO` | `000` | 정상 처리 |
| `INFO` | `300` | 관리자에 의해 인증키 사용 제한 |
| `INFO` | `200` | 데이터 없음 |

## Adapter Notes

- Primitive fit: `lookup`.
- Live readiness: possible when a valid National Assembly Open API key is available.
- `BILL_NO` is mandatory, so this adapter should either accept a known bill number or compose with a separate bill-search/list adapter before calling this detail endpoint.
- Do not model this as a data.go.kr service-key API. It is a data.go.kr cataloged LINK API whose callable surface is the National Assembly Open API portal.
