# 15144259 - 한국무역보험공사_수출결제정보

## Application Status

- data.go.kr ID: `15144259`
- Provider: 한국무역보험공사
- Category/source scope: 재정금융 / 공공기관
- Service type: REST OpenAPI
- Review type: 자동승인
- Application account: 개발
- Application date: 2026-05-16
- Approval evidence: 활용신청 현황 row showed `[승인] 한국무역보험공사_수출결제정보`
- Expiration shown by portal: 2028-05-16
- Key handling: service key exists in the user's data.go.kr account after approval; do not store the key in repository files.

## Saved Source Artefacts

- `data-go-kr-detail.html`
- `data-go-kr-catalog.json`
- `data-go-kr-inline-swagger.json`
- `intake-record.json`
- `국가코드 및 업종대중분류코드.xlsx`
- `국가코드 및 업종대중분류코드.xlsx.txt`

## Official Description

The API provides export payment trend data derived from Korea Trade Insurance Corporation payment-information holdings. It exposes country/industry payment terms, payment period, overdue rate, and overdue-period statistics for export-market analysis.

## Endpoint

```http
GET https://apis.data.go.kr/B552696/exportPayment/getPaymentInfo
```

The inline Swagger also lists `http` as a scheme, but the adapter should prefer `https`.

## Authentication

Use the data.go.kr issued service key as a query parameter.

| Parameter | Required | Description |
|---|---:|---|
| `serviceKey` | yes | 공공데이터포털에서 받은 인증키 |

## Request Parameters

| Parameter | Required | Description | Notes |
|---|---:|---|---|
| `ctryCd` | no | 국가코드 | Code list is saved in `국가코드 및 업종대중분류코드.xlsx`; example: `450` = 미국. |
| `industryLagCd` | no | 업종 대분류 코드 | Code list is saved in the same XLSX; example: `22` = 고무 및 플라스틱제품 제조업. |
| `industryMidCd` | no | 업종 중분류 코드 | Swagger notes this is used when an industry large code is supplied. Code list is saved in the same XLSX. |

Example shape, with the service key redacted:

```http
GET /B552696/exportPayment/getPaymentInfo?serviceKey={DATA_GO_KR_SERVICE_KEY}&ctryCd=450&industryLagCd=22&industryMidCd=22259
Host: apis.data.go.kr
Accept: application/json
```

## Response Shape

Top-level response:

- `header.resultCode`: result code
- `header.resultMsg`: result message
- `body.items.item`: payment statistics payload
- `body.totalCount`: total result count

Main payload fields:

- `lastUpdateDate`: final update date
- `yearList[]`: years included in the response
- `paymentTerms[]`: payment-term buckets
  - `CODE`
  - `CODE_NM`
  - `PAYMENT_TERMS[]`
    - `YEAR`
    - `CNT`
    - `VALUE`
- `averagePaymentPeriod[]`: average payment period by year
  - `YEAR`
  - `VALUE`
- `latePaymentRate[]`: overdue rate by year
  - `YEAR`
  - `VALUE`
- `averagelatePaymentPeriod[]`: average overdue period by year; note the upstream field casing/typo is `averagelatePaymentPeriod`.
  - `YEAR`
  - `VALUE`
- `paymentPeriod[]`: payment-period buckets
  - `CODE`
  - `CODE_NM`
  - `PAYMENT_PERIOD[]`
    - `YEAR`
    - `CNT`
    - `VALUE`

## Result Codes

| Code | Meaning |
|---|---|
| `200` | 성공 |
| `3` | 데이터 없음 |
| `10` | 잘못된 요청 파라메터 에러 |
| `11` | 필수요청 파라메터 없음 |
| `98` | 기타 에러 |

## Adapter Mapping Notes

- Candidate primitive: `find` or `lookup` style read-only statistics lookup.
- Suggested tool intent: retrieve export payment-risk statistics by country and industry code.
- Fail closed on missing `serviceKey`; never fall back to stored or hardcoded keys.
- Preserve upstream field names in raw response, especially `averagelatePaymentPeriod`, then expose normalized aliases only in a typed adapter layer if a spec explicitly requires it.
- The code-list XLSX should be treated as a local reference artefact for parameter validation and documentation, not as a substitute for live endpoint validation.
- Live contract probing should be done with direct `curl` after the key has propagated; do not run live probes in CI.
