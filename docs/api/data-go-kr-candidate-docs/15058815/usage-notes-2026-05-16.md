# 15058815 - 조달청_나라장터 공공데이터개방표준서비스

## Application Status

- Portal: data.go.kr
- Application status: 승인
- Application date: 2026-05-16
- Expiration date: 2028-05-16
- Account: 개발
- Evidence page: data.go.kr 마이페이지 > 활용신청 현황

## Local Source Artifacts

- `data-go-kr-inline-swagger.json`
- `조달청_OpenAPI참고자료_나라장터_공공데이터개방표준서비스_1.2.docx`
- `조달청_OpenAPI참고자료_나라장터_공공데이터개방표준서비스_1.2.docx.txt`

## UMMAYA Adapter Candidate

- Proposed module id: `pps_nara_standard_procurement_service`
- Candidate primitive: `lookup`
- Korean search hints: 나라장터, 입찰공고, 낙찰정보, 계약정보, 공공데이터 개방표준, 조달청
- English search hints: Nara procurement, public procurement bid, contract award, Korean procurement, PPS
- Domain fit: national procurement discovery and contract lookup.

## Endpoint

- Base URL: `https://apis.data.go.kr/1230000/ao/PubDataOpnStdService`
- Alternate scheme in Swagger: `http`
- Authentication parameter: `serviceKey`
- JSON response option: set `type=json`
- Common envelope:
  - `header.resultCode`
  - `header.resultMsg`
  - `body.items`
  - `body.numOfRows`
  - `body.pageNo`
  - `body.totalCount`

## Operations

### GET /getDataSetOpnStdBidPblancInfo

Dataset-standard bid notice lookup.

Required parameters:

- `serviceKey`
- `bidNtceBgnDt`: bid notice start datetime, `YYYYMMDDHHMM`
- `bidNtceEndDt`: bid notice end datetime, `YYYYMMDDHHMM`

Optional parameters:

- `pageNo`
- `numOfRows`
- `type`: use `json` for JSON

Constraints and notes:

- The reference document states the bid notice datetime range is limited to one month.
- Swagger marks only `serviceKey` as required, but the provider document marks `bidNtceBgnDt` and `bidNtceEndDt` as required; the adapter should validate all three.

Representative response fields:

- `bidNtceNo`
- `bidNtceOrd`
- `refNtceNo`
- `refNtceOrd`
- `ppsNtceYn`
- `bidNtceNm`
- `bidNtceSttusNm`
- `bidNtceDate`
- `bidNtceBgn`
- `bsnsDivNm`
- `intrntnlBidYn`
- `cmmnCntrctYn`
- `cmmnReciptMethdNm`
- `elctrnBidYn`
- `cntrctCnclsSttusNm`
- `cntrctCnclsMthdNm`
- `bidwinrDcsnMthdNm`
- `ntceInsttNm`
- `ntceInsttCd`
- `dmndInsttNm`
- `dmndInsttCd`

### GET /getDataSetOpnStdScsbidInfo

Dataset-standard successful bid lookup.

Required parameters:

- `serviceKey`
- `bsnsDivCd`: business division code.

Business division code values:

- `1`: 물품
- `2`: 외자
- `3`: 공사
- `5`: 용역

Optional parameters:

- `pageNo`
- `numOfRows`
- `type`: use `json` for JSON
- `opengBgnDt`: opening start datetime, `YYYYMMDDHHMM`
- `opengEndDt`: opening end datetime, `YYYYMMDDHHMM`

Constraints and notes:

- The reference document states the opening datetime range is limited to one week.

Representative response fields:

- `bidNtceNo`
- `bidNtceOrd`
- `bidNtceNm`
- `bsnsDivNm`
- `cntrctCnclsSttusNm`
- `cntrctCnclsMthdNm`
- `bidwinrDcsnMthdNm`
- `ntceInsttNm`
- `ntceInsttCd`
- `dmndInsttNm`
- `dmndInsttCd`
- `sucsfLwstlmtRt`
- `presmptPrce`
- `rsrvtnPrce`
- `bssAmt`
- `opengDate`
- `opengTm`
- `opengRsltDivNm`
- `opengRank`
- `bidprcCorpBizrno`
- `bidprcCorpNm`
- `bidprcCorpCeoNm`
- `bidprcAmt`
- `bidprcRt`
- `bidprcDate`
- `bidprcTm`
- `sucsfYn`
- `dqlfctnRsn`
- `fnlSucsfAmt`
- `fnlSucsfRt`
- `fnlSucsfDate`
- `fnlSucsfCorpNm`
- `fnlSucsfCorpCeoNm`
- `fnlSucsfCorpOfclNm`
- `fnlSucsfCorpBizrno`
- `fnlSucsfCorpAdrs`
- `fnlSucsfCorpContactTel`
- `dataBssDate`

### GET /getDataSetOpnStdCntrctInfo

Dataset-standard contract lookup.

Required parameters:

- `serviceKey`
- `cntrctCnclsBgnDate`: contract conclusion start date, `YYYYMMDD`
- `cntrctCnclsEndDate`: contract conclusion end date, `YYYYMMDD`

Optional parameters:

- `pageNo`
- `numOfRows`
- `type`: use `json` for JSON
- `insttDivCd`
- `insttCd`

Constraints and notes:

- Swagger marks only `serviceKey` as required, but the reference document marks the contract date range as required; the adapter should validate all three required fields.
- The provider document notes the query range was reduced from one month to one week.

Representative response fields:

- `cntrctNo`
- `untyCntrctNo`
- `cntrctOrd`
- `cntrctNm`
- `bsnsDivNm`
- `cntrctCnclsSttusNm`
- `cntrctCnclsMthdNm`
- `lngtrmCtnuDivNm`
- `cmmnCntrctYn`
- `cntrctCnclsDate`
- `cntrctPrd`
- `cntrctAmt`
- `ttalCntrctAmt`
- `cntrctInfoUrl`
- `bidNtceNo`
- `bidNtceOrd`
- `bidNtceNm`
- `opengDate`
- `opengTm`
- `rsrvtnPrce`
- `prvtcntrctRsn`
- `bidNtceUrl`
- `cntrctInsttDivNm`
- `cntrctInsttNm`
- `cntrctInsttCd`
- `cntrctInsttChrgDeptNm`
- `cntrctInsttOfclNm`
- `cntrctInsttOfclTel`
- `cntrctInsttOfcl`
- `dmndInsttDivNm`
- `dmndInsttNm`
- `dmndInsttCd`
- `dmndInsttOfclDeptNm`
- `dmndInsttOfclNm`
- `dmndInsttOfclTel`
- `dmndInsttOfclEmailAdrs`
- `rprsntCorpNm`
- `dmstcCorpYn`
- `rprsntCorpCeoNm`
- `rprsntCorpOfclNm`
- `rprsntCorpBizrno`

## Adapter Notes

- Store the portal service key only through the runtime secret channel; do not commit keys.
- The adapter should expose operation-specific request models because the required date fields and range limits differ by operation.
- Use `type=json` for live probes and fixtures unless XML coverage is explicitly needed later.
- The first live probe should use a very small `numOfRows` value and a narrow recent date range that satisfies the documented range limits.
