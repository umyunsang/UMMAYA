# 15156700 - 한국서부발전(주)_(AI친화)전기 설비 에너지 효율 정보 조회 서비스

## Application Status

- data.go.kr ID: `15156700`
- Provider: 한국서부발전(주)
- Category/source scope: 산업고용 / 공공기관
- Service type: REST OpenAPI
- Review type: 자동승인
- Application account: 개발
- Application date: 2026-05-16
- Approval evidence: 활용신청 현황 row showed `[승인] 한국서부발전(주)_(AI친화)전기 설비 에너지 효율 정보 조회 서비스`
- Expiration shown by portal: 2028-05-16
- Key handling: service key exists in the user's data.go.kr account after approval; do not store the key in repository files.

## Saved Source Artefacts

- `data-go-kr-detail.html`
- `data-go-kr-inline-swagger.json`
- `intake-record.json`

No separate attached technical document was listed in the captured intake record; the official contract is the inline Swagger embedded in the data.go.kr detail page.

## Official Description

This service exposes AI-friendly electric-equipment energy-efficiency readings from Korea Western Power. It queries by plant name, unit name, tag name, and tag data creation time, then returns tag value and `FLAG` values so callers can check whether plant equipment readings are within the configured operating range.

## Endpoint

```http
GET https://apis.data.go.kr/B552522/ElectricalEfficiencyService/getElectricalEfficiency
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
| `fromDate` | yes | 시작날짜 | `2024-10-01` |
| `toDate` | yes | 종료날짜 | `2024-10-02` |
| `plant` | yes | 발전소명 | `WTTATA` |
| `clsf_cd` | yes | 분류 코드 | `P3` |
| `hogi` | yes | 호기명 | `WTTATA07` |
| `tag` | yes | 태그명 | `T2.CM.0RW-FV02B.XB01` |
| `pageNo` | no | 페이지번호 | `1` |
| `numOfRows` | no | 한 페이지 결과 수 | `20` |
| `type` | no | 응답데이터 포맷 | `JSON` |

Example shape, with the service key redacted:

```http
GET /B552522/ElectricalEfficiencyService/getElectricalEfficiency?serviceKey={DATA_GO_KR_SERVICE_KEY}&fromDate=2024-10-01&toDate=2024-10-02&plant=WTTATA&clsf_cd=P3&hogi=WTTATA07&tag=T2.CM.0RW-FV02B.XB01&pageNo=1&numOfRows=20&type=JSON
Host: apis.data.go.kr
Accept: application/json
```

## Response Shape

Top-level response:

- `header.resultMsg`: result message
- `header.resultCode`: result code
- `body.totalCount`: total result count
- `body.items.item`: electric-equipment energy-efficiency record payload
- `body.pageNo`: page number
- `body.numOfRows`: result count per page

Item fields:

- `pwst_nm`: 발전소 명
- `meno_nm`: 호기 명
- `tag_nm`: 태그명
- `description`: 태그 설명
- `tag_data_crt_hr`: 태그 데이터 생성 시간
- `tag_data_nvl`: 태그 값
- `flag_cd`: FLAG

## Adapter Mapping Notes

- Candidate primitive: `find` or `lookup` style read-only operational-data lookup.
- Suggested tool intent: retrieve AI-friendly electric-equipment energy-efficiency tag readings and expose abnormal-range status for plant equipment by plant/unit/tag/date range.
- Keep all required filters explicit; the official operation requires plant, classification code, unit, tag, and date range.
- Treat `flag_cd` as the primary machine-readable range/status indicator. The detail page explains that tag values are compared against predefined minimum and maximum ranges; values below the minimum are `-1`, values within the normal range are `0`, and values above the maximum are `1`.
- Preserve raw field names in the stored fixture, then expose Korean/English aliases only through the typed adapter layer if the active adapter spec requires it.
- Live contract probing should be done with direct `curl` after the key has propagated; do not run live probes in CI.
