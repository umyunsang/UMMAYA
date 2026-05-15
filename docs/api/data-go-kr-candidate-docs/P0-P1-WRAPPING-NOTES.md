# data.go.kr P0/P1 Wrapping Notes

This is an intake artifact for issue #2797. It records the evidence needed before
turning the first-wave P0/P1 candidates into UMMAYA adapters. It is not an
implementation spec and does not authorize code changes by itself.

## Reference Bootstrap

- UMMAYA thesis/docs: `docs/vision.md` keeps `data.go.kr` as one adapter family
  inside the wider national public-service tool surface, and the active
  primitive surface is `find`, `locate`, `send`, and `check`.
- Tool-system requirements: `docs/requirements/ummaya-migration-tree.md` L1-B
  requires each agency callable module to be classified as Live, Mock, or
  OPAQUE/scenario-only, with adapter-level policy citations.
- Existing adapter catalog: `docs/api/README.md` documents the seven-section
  adapter template, fixture-first tests, and the rule that live public API calls
  stay out of CI.
- CC restored source: `.references/claude-code-sourcemap/restored-src/src/Tool.ts`
  and `.references/claude-code-sourcemap/restored-src/src/tools/MCPTool/MCPTool.ts`
  remain the tool-contract reference for later Spec Kit planning.
- External primary sources: official `data.go.kr` detail pages, the NTS Swagger
  URL, the KEPCO power-data portal, and the REB R-ONE Open API pages observed on
  2026-05-15 through Computer Use.
- Live-call constraint: no live API contract call was made in this intake pass.
  Later implementation needs direct sanitized `curl` evidence for endpoint,
  credential, params, response status, zero-result shape, and response schema.

## Local Secret Inventory

The user-provided external-domain keys were stored only in local `.env`, which
is ignored by git and set to owner-only permissions.

| Domain | Env var to use later | Do not commit |
|---|---|---|
| REB R-ONE real-estate statistics | `UMMAYA_REB_REAL_ESTATE_STATS_API_KEY` | yes |
| KEPCO power-data portal | `UMMAYA_KEPCO_POWER_DATA_API_KEY` | yes |

`data.go.kr` OpenAPI candidates should continue to use the existing
`UMMAYA_DATA_GO_KR_API_KEY` convention unless the candidate is a `LINK` API that
delegates authentication to another agency domain.

## Evidence Matrix

| data.go.kr ID | Candidate | Doc status | Credential source | Current wrapping note |
|---|---|---|---|---|
| `15081808` | `국세청_사업자등록정보 진위확인 및 상태조회 서비스` | No downloadable data.go.kr reference document, but official Swagger captured from `infuser.odcloud.kr` | data.go.kr service key | `check` is likely better than `find`; endpoint requires POST JSON body. |
| `15158684` | `한국대학교육협의회 대학정보공시 학생 현황_GW` | No reference document file; inline Swagger captured from the data.go.kr page | data.go.kr service key | `find`; many school/year and regional statistics endpoints. |
| `15158680` | `한국대학교육협의회_대학알리미 재정 현황_GW` | No reference document file; inline Swagger captured from the data.go.kr page | data.go.kr service key | `find`; school/year and regional finance statistics endpoints. |
| `15157485` | `부산시설공단_장례비산출 정보 조회 서비스` | No reference document file; inline Swagger captured from the data.go.kr page | data.go.kr service key | `find`; fee lookup plus cost-calculation endpoint. |
| `15101360` | `한국전력공사_계약종별 전력사용량` | data.go.kr reference PPTX captured; real endpoint details observed in KEPCO portal | KEPCO power-data key | `find`; `LINK` API, not data.go.kr-hosted. |
| `15134761` | `한국부동산원_부동산통계 조회 서비스` | data.go.kr DOCX captured; REB Open API list and development guide captured | REB R-ONE key | `find`; `LINK` API, not data.go.kr-hosted. |

## Captured Artifacts

- `15081808/nts-businessman-v1.swagger.json`
- `15158684/data-go-kr-inline-swagger.json`
- `15158680/data-go-kr-inline-swagger.json`
- `15157485/data-go-kr-inline-swagger.json`
- `15101360/전력데이터개방포털 Open-API 사용 매뉴얼.pptx`
- `15101360/kepco-contract-type-guide.html`
- `15134761/기술문서_부동산통계 Open API 서비스_240905.docx`
- `15134761/reb-openapi-list.html`
- `15134761/reb-openapi-dev-guide.html`

`data-go-kr-openapi.json` files are schema.org catalog metadata, not full
request/response OpenAPI contracts. For data.go.kr pages with empty reference
documents, prefer the `data-go-kr-inline-swagger.json` files.

## No-Reference-Document Candidates

### `15158684` University Student Status

Official source page: `https://www.data.go.kr/data/15158684/openapi.do`

- Type: REST
- Format: XML
- Approval: development auto-approval, operation auto-approval
- Traffic observed: development 1,000 calls/day
- Host: `apis.data.go.kr/B340014/StudentService`
- Method: GET
- Auth: query `serviceKey`
- Common optional params: `pageNo`, `numOfRows`
- Full captured contract: `15158684/data-go-kr-inline-swagger.json`

Representative paths:

- `/getComparisonFreshmanChanceBalanceSelectionRatio`
- `/getRegionalFreshmanChanceBalanceSelectionRatio`
- `/getComparisonFreshmanEnsureCrntSt`
- `/getRegionalFreshmanEnsureCrntSt`
- `/getNoticeFreshmanDrafteesRate`
- `/getComparisonForeignDropOutCrntSt`
- `/getRegionalForeignDropOutCrntSt`
- `/getComparisonForeignStudentCrntSt`
- `/getRegionalForeignStudentCrntSt`
- `/getComparisonEntranceModelLastRegistrationRatio`
- `/getRegionalEntranceModelLastRegistrationRatio`
- `/getComparisonEnrolledStudentCrntSt`
- `/getRegionalEnrolledStudentCrntSt`
- `/getNoticeEnrolledStudentDrafteesRate`
- `/getComparisonEnrolledStudentEnsureRate`
- `/getRegionalEnrolledStudentEnsureRate`
- `/getComparisonEnrolledStudent`
- `/getRegionalEnrolledStudent`
- `/getComparisonInsideFixedNumberFreshmanCompetitionRate`
- `/getRegionalInsideFixedNumberFreshmanCompetitionRate`
- `/getRegionalGraduateEnterFindJobCrntSt`
- `/getNoticeGraduateEmploymentRate`
- `/getComparisonDropOutStudentCrntSt`
- `/getRegionalDropOutStudentCrntSt`
- `/getNoticeStudentsWastageRate`
- `/getComparisonStudentOnALeaveOfAbsence`
- `/getRegionalStudentOnALeaveOfAbsence`

Parameter pattern:

- University comparison endpoints require `serviceKey`, `schlId`, and `svyYr`.
- Regional endpoints require `serviceKey` and `schlDivCd`.
- Some notice endpoints require `serviceKey`, `svyYr`, and `schlId`.
- `getRegionalGraduateEnterFindJobCrntSt` optionally accepts `indctId`.

### `15158680` University Finance Status

Official source page: `https://www.data.go.kr/data/15158680/openapi.do`

- Type: REST
- Format: XML
- Approval: development auto-approval, operation auto-approval
- Traffic observed: development 1,000 calls/day
- Host: `apis.data.go.kr/B340014/FinancesService`
- Method: GET
- Auth: query `serviceKey`
- Common optional params: `pageNo`, `numOfRows`
- Full captured contract: `15158680/data-go-kr-inline-swagger.json`

Paths and required params:

- `/getComparisonTuitionCrntSt`: `serviceKey`, `schlId`, `svyYr`
- `/getComparisonScholarshipBenefitCrntSt`: `serviceKey`, `schlId`, `svyYr`
- `/getComparisonEducationalExpensesReductionCrntSt`: `serviceKey`, `schlId`, `svyYr`; optional `indctId`
- `/getRegionalEducationalExpensesReductionCrntSt`: `serviceKey`, `schlDivCd`; optional `indctId`
- `/getComparisonEducationExpensesLoanCrntSt`: `serviceKey`, `schlId`, `svyYr`
- `/getComparisonEducationExpensesLoanUseStudentRatioTuition`: `serviceKey`, `schlId`, `svyYr`
- `/getRegionalTuitionCrntSt`: `serviceKey`, `schlDivCd`
- `/getRegionalScholarshipBenefitCrntSt`: `serviceKey`, `schlDivCd`
- `/getRegionalEducationExpensesLoanCrntSt`: `serviceKey`, `schlDivCd`
- `/getRegionalEducationExpensesLoanUseStudentRatioTuition`: `serviceKey`; optional `schlDivCd`

### `15157485` Busan Funeral Cost Lookup

Official source page: `https://www.data.go.kr/data/15157485/openapi.do`

- Type: REST
- Format: JSON+XML
- Approval: development auto-approval, operation auto-approval
- Traffic observed: development 1,000 calls/day
- Host: `apis.data.go.kr/B552587/FuneralCostsService_v2`
- Method: GET
- Auth: query `serviceKey`
- Common required params: `serviceKey`, `pageNo`, `numOfRows`
- Format selector: optional `resultType` (`json` or `xml`, default appears to be XML)
- Full captured contract: `15157485/data-go-kr-inline-swagger.json`

Paths:

- `/getFCAreaList_v2`: funeral hall facility usage fee list
- `/getFCGoods_v2`: funeral goods list; optional `fc_gubun`
- `/getFCItem_v2`: basic coffin/enbalming item prices; optional `fc_gubun`
- `/getFCOffering_v2`: offering list; optional `fc_gubun`
- `/getFCGPrice_v2`: guest-service cost list; optional `fc_gubun`
- `/getFCTotal_v2`: funeral cost calculation; optional `fc_gubun`, `goods`,
  `d_gubun`, `mourning_m`, `mourning_w`, `guest`, `offering`, `area`

## External-Key LINK Candidates

### `15101360` KEPCO Contract-Type Power Usage

Official data.go.kr page: `https://www.data.go.kr/data/15101360/openapi.do`

Official KEPCO portal page observed through Computer Use:
`https://bigdata.kepco.co.kr/cmsmain.do?scode=S01&pcode=000493&pstate=cntr&redirect=Y`

- data.go.kr type: `LINK`
- External portal requires logged-in KEPCO power-data access and a separate
  40-character `apiKey`.
- Local env var: `UMMAYA_KEPCO_POWER_DATA_API_KEY`
- Method: GET or POST
- Endpoint: `https://bigdata.kepco.co.kr/openapi/v1/powerUsage/contractType.do`
- Encoding: UTF-8
- Response formats: JSON, XML

Request params:

| Param | Required | Meaning |
|---|---:|---|
| `year` | yes | 조회연도, `YYYY` |
| `month` | yes | 조회월, `MM` |
| `metroCd` | no | 시도코드; omitted means all metropolitan/provincial regions |
| `cityCd` | no | 시군구코드; omitted means all cities/counties/districts |
| `cntrCd` | no | 계약종별; e.g. `100` 주택용, `200` 일반용 |
| `apiKey` | yes | KEPCO-issued API key |
| `returnType` | no | `json` or `xml`; omitted defaults to JSON |

Sample shape from official guide:

```text
https://bigdata.kepco.co.kr/openapi/v1/powerUsage/contractType.do?year=2020&month=11&metroCd=11&cityCd=110&cntrCd=100&apiKey=xxx&returnType=json
```

Response fields observed in the guide include `totData`, `data`, `year`,
`month`, `metro`, `city`, `cntr`, `custCnt`, `powerUsage`, `bill`,
`unitCost`, and `cntrPwr`.

### `15134761` REB Real-Estate Statistics

Official data.go.kr page: `https://www.data.go.kr/data/15134761/openapi.do`

Official REB pages observed through Computer Use:

- `https://www.reb.or.kr/r-one/portal/openapi/openApiListPage.do`
- `https://www.reb.or.kr/r-one/portal/openapi/openApiDevPage.do`

- data.go.kr type: `LINK`
- External portal uses REB R-ONE authentication and a separate `KEY`.
- Local env var: `UMMAYA_REB_REAL_ESTATE_STATS_API_KEY`
- Base endpoint: `https://www.reb.or.kr/r-one/openapi`
- The DOCX service table marks REST GET. The REB web guide describes
  RESTful GET/POST URL-parameter usage; implement GET first unless a live probe
  proves POST equivalence.
- Common params: `KEY`, `Type`, `pIndex`, `pSize`
- `Type`: `xml` or `json`; default `xml`
- `pIndex`: page number; default `1`
- `pSize`: page size; default `100`

REB Open API list contains three services:

| Service | Endpoint | Required business params |
|---|---|---|
| 서비스 통계목록 | `SttsApiTbl.do` | optional `STATBL_ID` |
| 통계 세부항목 목록 | `SttsApiTblItm.do` | required `STATBL_ID`; optional `ITM_TAG` |
| 통계 조회 조건 설정 | `SttsApiTblData.do` | required `STATBL_ID`, `DTACYCLE_CD`; optional `WRTTIME_IDTFR_ID`, `GRP_ID`, `CLS_ID`, `ITM_ID`, `START_WRTTIME`, `END_WRTTIME` |

Sample shapes from official guide:

```text
https://www.reb.or.kr/r-one/openapi/SttsApiTbl.do?KEY=인증키&STATBL_ID=A_2024_00900
https://www.reb.or.kr/r-one/openapi/SttsApiTblItm.do?KEY=인증키&STATBL_ID=A_2024_00900&ITM_TAG=분류
https://www.reb.or.kr/r-one/openapi/SttsApiTblData.do?KEY=인증키&STATBL_ID=A_2024_00900&DTACYCLE_CD=YY&CLS_ID=510008&START_WRTTIME=2022&END_WRTTIME=2023
```

Guide error codes include missing required value, invalid key, over-1,000-row
request, daily traffic exceeded, invalid page index type, service not found,
server/database errors, normal result, admin key restriction, and no data.

## Spec Kit Follow-Up

Before implementation, create or update a Spec Kit artifact that chooses a small
slice. Recommended first implementation order:

1. `15081808` as `check` because it verifies business identity/status.
2. `15157485` as a narrow `find` adapter because its contract is small.
3. `15101360` and `15134761` as separate external-key `find` adapters after
   direct live `curl` validation with redacted keys.
4. `15158684` and `15158680` only after deciding whether to expose many
   operation IDs as one broad adapter, several indicator-group adapters, or a
   registry-generated family.
