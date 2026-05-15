# 15108420 - 국토교통부_마이홈포털 공공주택 모집공고 조회 서비스

## Collection Status

- Source page: `https://www.data.go.kr/data/15108420/openapi.do`
- Captured contract: `data-go-kr-inline-swagger.json`
- Downloaded technical document: `붙임1. 요청 파라미터 코드(공공주택 모집공고)_260331.xlsx` and extracted text `붙임1. 요청 파라미터 코드(공공주택 모집공고)_260331.xlsx.txt`
- Application status: submitted through data.go.kr and visible in `활용신청 현황` as `[승인] 국토교통부_마이홈포털 공공주택 모집공고 조회 서비스`.
- Application evidence captured from data.go.kr account list: 신청일 `2026-05-16`, 만료예정일 `2028-05-16`, 계정 `개발`.
- Application type shown by data.go.kr: `개발계정 | 활용신청`
- Review mode shown by data.go.kr: `자동승인`
- Usage period shown by data.go.kr: `승인일로부터 24개월 간 활용가능`
- License shown by data.go.kr: `이용허락범위 제한 없음`
- Selected functions on form: all listed detail functions selected.

## Request Base

- Protocols: `https`, `http`
- Host/service root: `apis.data.go.kr/1613000/HWSPR02`
- Auth parameter: `serviceKey`
- Common optional paging parameters: `pageNo`, `numOfRows`
- Response media shown by Swagger: JSON dataset, data.go.kr gateway endpoint.

Example shape:

```text
GET https://apis.data.go.kr/1613000/HWSPR02/rsdtRcritNtcList?serviceKey={DATA_GO_KR_SERVICE_KEY}&brtcCode=11&pageNo=1&numOfRows=10
```

## Operations

| Operation | Meaning | Required query parameters | Optional query parameters |
| --- | --- | --- | --- |
| `GET /rsdtRcritNtcList` | 공공임대주택 모집공고 조회 | `serviceKey` | `brtcCode`, `signguCode`, `numOfRows`, `pageNo`, `suplyTy`, `houseTy`, `lfstsTyAt`, `bassMtRntchrgSe`, `yearMtBegin`, `yearMtEnd` |
| `GET /ltRsdtRcritNtcList` | 공공분양주택 모집공고 조회 | `serviceKey` | `brtcCode`, `signguCode`, `numOfRows`, `pageNo`, `houseTy`, `yearMtBegin`, `yearMtEnd` |

## Parameter Notes

- `brtcCode`: 광역시도 코드. Code sheet examples include 서울 `11`, 부산 `26`, 대구 `27`, 인천 `28`, 광주 `29`, 대전 `30`, 울산 `31`, 세종 `36`, 경기 `41`, 충북 `43`, 충남 `44`, 전남 `46`, 경북 `47`, 경남 `48`, 제주 `50`, 강원특별자치도 `51`, 전북특별자치도 `52`.
- `signguCode`: 시군구 코드 scoped by `brtcCode`; the downloaded code sheet contains the complete region table.
- `houseTy`: 주택유형. Code sheet lists `11` 아파트, `12` 연립주택, `13` 다세대주택, `14` 단독주택, `15` 오피스텔, `16` 다가구주택.
- `suplyTy`: 공급유형 for public-rental search. Code sheet lists `01` 영구임대, `02` 국민임대, `03` 50년임대, `04` 매입임대, `05` 10년임대, `13` 6년임대, `06` 5년임대, `07` 장기전세, `08` 전세임대, `09` 매입임대, `10` 행복주택, `11` 공공지원민간임대, `12` 통합공공임대.
- `lfstsTyAt`: 전세형 모집 여부, `Y` or `N`.
- `bassMtRntchrgSe`: 월임대료 구분. Code sheet lists `01` 5만원 미만, `02` 5~10만원 미만, `03` 10~20만원 미만, `04` 20~30만원 미만, `05` 30만원 이상.
- `yearMtBegin` / `yearMtEnd`: 모집공고월 range in `YYYYMM`.

## Response Shape

- Common envelope: `header.resultCode`, `header.resultMsg`, `body.item`, `body.numOfRows`, `body.pageNo`, `body.totalCount`.
- Public-rental item fields include: `suplyHoCo`, `pblancId`, `houseSn`, `sttusNm`, `pblancNm`, `suplyInsttNm`, `houseTyNm`, `suplyTyNm`, `beforePblancId`, `rcritPblancDe`, `przwnerPresnatnDe`, `refrnc`, `url`, `pcUrl`, `mobileUrl`, `hsmpNm`, `brtcNm`, `signguNm`, `fullAdres`, `rnCodeNm`, `refrnLegaldongNm`, `pnu`, `heatMthdNm`, `totHshldCo`, `sumSuplyCo`, `rentGtn`, `enty`, `prtpay`, `surlus`, `mtRntchrg`, `beginDe`, `endDe`.
- Public-sale item fields include: `pblancId`, `houseSn`, `sttusNm`, `pblancNm`, `suplyInsttNm`, `houseTyNm`, `beforePblancId`, `rcritPblancDe`, `przwnerPresnatnDe`, `refrnc`, `url`, `pcUrl`, `mobileUrl`, `hsmpNm`, `brtcNm`, `signguNm`, `fullAdres`, `rnCodeNm`, `refrnLegaldongNm`, `pnu`, `heatMthdNm`, `sumSuplyCo`, `enty`, `prtpay`, `surlus`, `beginDe`, `endDe`.

## UMMAYA Adapter Reading

- Candidate primitive: `lookup`/`find`.
- Data domain: housing, public-rental and public-sale housing recruitment notices.
- Live shape: data.go.kr REST with `serviceKey` query authentication.
- Tool boundary: read-only public-data lookup; no citizen transaction or write action.
- Suggested wrapper module name: `molit_myhome_public_housing_notice_service`.
- Korean search hints: `마이홈`, `공공임대주택`, `공공분양주택`, `모집공고`, `행복주택`, `국민임대`, `영구임대`.
- English search hints: `public rental housing`, `public housing notice`, `MyHome housing`, `housing recruitment notice`, `Korean public housing`.

## Exclusion Check

This API is not in the already-completed exclusion set reported by the user on 2026-05-16:

- `15043459`, `15073861`, `15091886`, `15091910`
- `15098529`, `15098530`, `15098533`, `15098534`
- `15101360`, `15129394`, `15134761`, `15157485`
- `15158680`, `15158684`

It is also separate from the deferred set already documented in existing notes: NTS, EMS tracking, MOLEG SOAP services, MSIT project announcement, and MOJ foreign-resident status APIs.
