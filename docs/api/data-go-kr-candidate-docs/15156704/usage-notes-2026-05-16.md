# 15156704 - 한국서부발전(주)_(AI친화)전력사용량 조회 서비스

## Application Status

- data.go.kr ID: `15156704`
- Provider: 한국서부발전(주)
- Category/source scope: 산업고용 / 공공기관
- Service type: REST OpenAPI
- Review type: 자동승인
- Application account: 개발
- Application date: 2026-05-16
- Approval evidence: 활용신청 현황 row showed `[승인] 한국서부발전(주)_(AI친화)전력사용량 조회 서비스`
- Expiration shown by portal: 2028-05-16
- Key handling: service key exists in the user's data.go.kr account after approval; do not store the key in repository files.

## Saved Source Artefacts

- `data-go-kr-detail.html`
- `data-go-kr-inline-swagger.json`
- `intake-record.json`

No separate attached technical document was listed in the captured intake record; the official contract is the inline Swagger embedded in the data.go.kr detail page.

## Official Description

This service exposes plant power-usage operation data from Korea Western Power. It returns plant name, unit name, tag name, tag generation time, tag value, unit, and `FLAG` values. The `FLAG` value marks whether a tag value falls below the configured minimum (`-1`), above the configured maximum (`1`), or within the normal range (`0`).

## Endpoint

```http
GET https://apis.data.go.kr/B552522/PowerUsageService/getPowerUsageService
```

The inline Swagger also lists `http` as a scheme, but the adapter should prefer `https`.

## Authentication

Use the data.go.kr issued service key as a query parameter.

| Parameter | Required | Description | Note |
|---|---:|---|---|
| `serviceKey` | yes | 공공데이터포털에서 받은 인증키 | The captured Swagger parameter name contains trailing whitespace as `serviceKey `. Normalize to `serviceKey` in client code and confirm by direct live `curl` after key propagation. |

## Request Parameters

| Parameter | Required | Description | Captured default/example |
|---|---:|---|---|
| `fromDate` | yes | 시작날짜 | `2024-12-03` |
| `toDate` | yes | 종료날짜 | `2024-12-04` |
| `plant` | yes | 발전소명 | `WTTATA` |
| `clsf_cd` | yes | 분류 코드 | `P4` |
| `hogi` | yes | 호기명 | `WTTATA10` |
| `tag` | yes | 태그명 | `T3.10M.10UM_NMW` |
| `pageNo` | no | 페이지번호 | `1` |
| `numOfRows` | no | 한 페이지 결과 수 | `20` |
| `type` | no | 응답데이터 포맷 | `JSON` |

Example shape, with the service key redacted:

```http
GET /B552522/PowerUsageService/getPowerUsageService?serviceKey={DATA_GO_KR_SERVICE_KEY}&fromDate=2024-12-03&toDate=2024-12-04&plant=WTTATA&clsf_cd=P4&hogi=WTTATA10&tag=T3.10M.10UM_NMW&pageNo=1&numOfRows=20&type=JSON
Host: apis.data.go.kr
Accept: application/json
```

## Response Shape

Top-level response:

- `header.resultMsg`: result message
- `header.resultCode`: result code
- `body.totalCount`: total result count
- `body.items.item`: power-usage record payload
- `body.pageNo`: page number
- `body.numOfRows`: result count per page

Item fields:

- `pwst_nm`: 발전소 명
- `meno_nm`: 호기 명
- `tag_nm`: 태그명
- `description`: 태그 설명
- `tag_data_crt_hr`: 태그 데이터 생성 시간
- `tag_data_nvl`: 태그 값
- `eng_unit`: 태그 단위
- `flag_cd`: FLAG

## Adapter Mapping Notes

- Candidate primitive: `find` or `lookup` style read-only operational-data lookup.
- Suggested tool intent: retrieve AI-friendly plant power-usage tag readings and flag abnormal values by plant/unit/tag/date range.
- Keep all required filters explicit; the official operation requires plant, classification code, unit, tag, and date range.
- Treat `flag_cd` as the primary machine-readable quality/anomaly indicator:
  - `-1`: below configured minimum
  - `0`: normal range
  - `1`: above configured maximum
- Preserve raw field names in the stored fixture, then expose Korean/English aliases only through the typed adapter layer if the active adapter spec requires it.
- Live contract probing should be done with direct `curl` after the key has propagated; do not run live probes in CI.
