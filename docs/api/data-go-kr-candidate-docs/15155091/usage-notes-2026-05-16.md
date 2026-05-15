# 15155091 - 행정안전부_생활_목욕장업 조회서비스

## Application Status

- data.go.kr ID: `15155091`
- Provider: 행정안전부
- Category/source scope: 식품건강 / 국가행정기관
- Service type: REST OpenAPI
- Review type: 자동승인
- Application account: 개발
- Application date: 2026-05-16
- Expiry date: 2028-05-16
- Application evidence: 활용신청 현황 row showed `[승인] 행정안전부_생활_목욕장업 조회서비스`
- Key handling: service key must be read from the user's data.go.kr account when probing locally; do not store the key in repository files.

## Saved Source Artefacts

- `data-go-kr-detail.html`
- `data-go-kr-inline-swagger.json`
- `intake-record.json`
- `개방자치단체코드_영업상태코드.xlsx`
- `개방자치단체코드_영업상태코드.xlsx.txt`

The endpoint and schema contract are captured from the inline Swagger block in `data-go-kr-inline-swagger.json`. The XLSX reference contains the `OPN_ATMY_GRP_CD` local-government code list and `SALS_STTS_CD` business-status code list.

## Official Description

This service provides public bath licensing data for bathhouses, jjimjilbangs, saunas, and related facilities. It includes licensing date, business status, business place name, road/lot address, facility attributes, and coordinate fields.

Portal notes:

- Nationally aggregated public-data-standard licensing records from local governments.
- Data is normalized with the same format and terminology across local governments.
- Coordinate system: Bessel central-origin TM without correction factor, EPSG:5174.
- Legal-domain contact listed by the portal: 보건복지부 생활보건팀 / 044-202-2856.

## Endpoints

Base URL:

```http
https://apis.data.go.kr/1741000/public_baths
```

The Swagger lists both `https` and `http`; prefer `https` first.

Current-state lookup:

```http
GET /info
```

History lookup:

```http
GET /history
```

## Authentication

Use the data.go.kr issued service key as a query parameter.

| Parameter | Required | Description |
|---|---:|---|
| `serviceKey` | yes | 공공데이터포털에서 받은 인증키 |

## Request Parameters

Shared required parameters:

| Parameter | Required | Description |
|---|---:|---|
| `serviceKey` | yes | 공공데이터포털에서 받은 인증키 |
| `pageNo` | yes | 페이지번호 |
| `numOfRows` | yes | 한 페이지 결과 수, max `100` |

Shared optional parameters:

| Parameter | Description |
|---|---|
| `returnType` | 응답 데이터 타입, typically `json` or `xml` |
| `cond[LCPMT_YMD::GTE]` | 인허가일자 이상, `YYYYMMDD` |
| `cond[LCPMT_YMD::LT]` | 인허가일자 미만, `YYYYMMDD` |
| `cond[SALS_STTS_CD::EQ]` | 영업상태코드와 일치 |
| `cond[DAT_UPDT_PNT::GTE]` | 데이터갱신시점 이상, `YYYYMMDDHHMMSS` |
| `cond[DAT_UPDT_PNT::LT]` | 데이터갱신시점 미만, `YYYYMMDDHHMMSS` |
| `cond[OPN_ATMY_GRP_CD::EQ]` | 개방자치단체코드 |
| `cond[BPLC_NM::LIKE]` | 사업장명 포함 검색 |

`/info` additional optional parameters:

| Parameter | Description |
|---|---|
| `cond[SWEATRM_YN::EQ]` | 발한실여부와 일치 |
| `cond[ROAD_NM_ADDR::LIKE]` | 도로명주소 포함 검색 |

`/history` additional required parameter:

| Parameter | Required | Description |
|---|---:|---|
| `cond[BASE_DATE::EQ]` | yes | 데이터기준일자, `YYYYMMDD`; portal says `2026-01-01` through the day before lookup |

For `/history`, `cond[OPN_ATMY_GRP_CD::EQ]` is also marked required in the Swagger.

Example current-state query, with the service key redacted:

```http
GET /1741000/public_baths/info?serviceKey={DATA_GO_KR_SERVICE_KEY}&pageNo=1&numOfRows=10&returnType=json&cond%5BSALS_STTS_CD%3A%3AEQ%5D=01&cond%5BOPN_ATMY_GRP_CD%3A%3AEQ%5D=6110000_ALL
Host: apis.data.go.kr
Accept: application/json
```

Example history query:

```http
GET /1741000/public_baths/history?serviceKey={DATA_GO_KR_SERVICE_KEY}&pageNo=1&numOfRows=10&returnType=json&cond%5BBASE_DATE%3A%3AEQ%5D=20260101&cond%5BOPN_ATMY_GRP_CD%3A%3AEQ%5D=6110000_ALL
Host: apis.data.go.kr
Accept: application/json
```

## Reference Codes

Business status codes from the saved XLSX:

| Code | Meaning |
|---|---|
| `01` | 영업/정상 |
| `02` | 휴업 |
| `03` | 폐업 |
| `04` | 취소/말소/만료/정지/중지 |
| `05` | 제외/삭제/전출 |
| `06` | 기타 |

Local-government code examples from the saved XLSX:

| Code | Meaning |
|---|---|
| `6110000_ALL` | 서울특별시 전체 |
| `6260000_ALL` | 부산광역시 전체 |
| `6410000_ALL` | 경기도 전체 |
| `6110000` | 서울특별시 |
| `3220000` | 서울강남구 |

Use the saved XLSX text for the full local-government code table.

## Response Shape

Top-level envelope:

- `response.header.resultCode`
- `response.header.resultMsg`
- `response.body.dataType`
- `response.body.numOfRows`
- `response.body.pageNo`
- `response.body.totalCount`
- `response.body.items.item[]`

Major item fields:

- Identity/status: `OPN_ATMY_GRP_CD`, `MNG_NO`, `BPLC_NM`, `SALS_STTS_CD`, `SALS_STTS_NM`, `DTL_SALS_STTS_CD`, `DTL_SALS_STTS_NM`
- Address/contact: `ROAD_NM_ZIP`, `ROAD_NM_ADDR`, `LOTNO_ADDR`, `LCTN_ZIP`, `TELNO`
- Licensing/dates: `LCPMT_YMD`, `CLSBIZ_YMD`, `LAST_MDFCN_PNT`, `DAT_UPDT_SE`, `DAT_UPDT_PNT`
- Facility attributes: `SNTTN_BZSTAT_NM`, `BZSTAT_SE_NM`, `BTHRM_CNT`, `SWEATRM_YN`, `LCTN_AREA`, `MLT_UTZTN_BSNSSP_YN`
- Building/floor fields: `BLDG_PSN_SE_NM`, `BLDG_GRND_FLR_CNT`, `BLDG_UDGD_FLR_CNT`, `USE_BGNG_GRND_FLR`, `USE_ED_GRND_FLR`, `USE_BGNG_UDGD_FLR`, `USE_ED_UDGD_FLR`
- Staff counts: `ML_PRCTR_CNT`, `FML_PRCTR_CNT`
- Conditional permission: `CNDNAL_PRMSN_BGNG_YMD`, `CNDNAL_PRMSN_END_YMD`, `CNDNAL_PRMSN_DCLR_RSN`
- Coordinates: `CRD_INFO_X`, `CRD_INFO_Y` in EPSG:5174 as noted by the portal.

## Adapter Mapping Notes

- Candidate primitive: `find` or `locate`.
- Suggested tool intent: search public bath licensing records by local-government code, business status, business name, address, license date, update window, and optional historical base date.
- Keep both `/info` and `/history` as one adapter if the tool exposes a `mode` or `history_base_date`; otherwise split into current and historical lookup operations internally under the same data.go.kr service.
- `returnType=json` should be used for adapter fixtures unless XML parity needs to be checked.
- Preserve raw uppercase field keys in live fixtures, then add a normalized internal mapping only after direct `curl` probes prove the exact response envelope.
- Live contract probing should be done with direct `curl` after key propagation; do not run live probes in CI.
