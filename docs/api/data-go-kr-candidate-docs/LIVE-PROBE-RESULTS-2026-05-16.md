# Live API Probe Results - 2026-05-16 KST

Direct `curl` probes were run after the first saved technical documents had aged
more than two hours. Secrets were injected only through local environment
variables and were redacted from saved probe artifacts.

Raw artifacts are under each candidate folder:
`docs/api/data-go-kr-candidate-docs/<data-go-kr-id>/probes/live-2026-05-16/`.

## Confirmed Callable

| ID | API | Endpoint probed | Result | Evidence |
|---|---|---|---|---|
| `15043459` | 금융위원회 기업 재무정보 | `/1160100/service/GetFinaStatInfoService_V2/getSummFinaStat_V2` with `crno=1746110000741`, `bizYear=2019`, `resultType=json` | HTTP 200, `resultCode=00`, `NORMAL SERVICE.`, data returned | `15043459/probes/live-2026-05-16/corporate-finance-summary.body.json` |
| `15073861` | AirKorea 대기오염정보 | `/B552584/ArpltnInforInqireSvc/getCtprvnRltmMesureDnsty` with `sidoName=서울`, `returnType=json`, `ver=1.0` | HTTP 200, `resultCode=00`, `NORMAL_CODE`, 서울 측정소 data returned | `15073861/probes/live-2026-05-16/airkorea-ctprvn.body.json` |
| `15091886` | 공정위 대규모기업집단 | `/1130000/appnGroupSttusList/appnGroupSttusListApi` with `presentnYear=202105` | HTTP 200, `resultCode=00`, `SUCCESS`, 71 rows | `15091886/probes/live-2026-05-16/ftc-large-group.body.xml` |
| `15091910` | 공정위 사용 가능 공개년월 | `/1130000/publicYmList/publicYmListApi` with `jobSeCode=0001`, `presentnYear=2021` | HTTP 200, `resultCode=00`, `SUCCESS` | `15091910/probes/live-2026-05-16/ftc-public-ym.body.xml` |
| `15098529` | TAGO 버스노선정보 | `/1613000/BusRouteInfoInqireService/getRouteNoList` with `cityCode=25`, `routeNo=5` | HTTP 200, `resultCode=00`, `NORMAL SERVICE.`, route rows returned | `15098529/probes/live-2026-05-16/tago-bus-route.body.xml` |
| `15098530` | TAGO 버스도착정보 | `/1613000/ArvlInfoInqireService/getSttnAcctoArvlPrearngeInfoList` with `cityCode=25`, `nodeId=DJB8001793` | HTTP 200, `resultCode=00`, `NORMAL SERVICE.`, valid zero-result shape | `15098530/probes/live-2026-05-16/tago-bus-arrival.body.xml` |
| `15098533` | TAGO 버스위치정보 | `/1613000/BusLcInfoInqireService/getRouteAcctoBusLcList` with `cityCode=25`, `routeId=DJB30300052` | HTTP 200, `resultCode=00`, `NORMAL SERVICE.`, valid zero-result shape | `15098533/probes/live-2026-05-16/tago-bus-location.body.xml` |
| `15098534` | TAGO 버스정류소정보 | `/1613000/BusSttnInfoInqireService/getSttnNoList` with `cityCode=25`, `nodeNm=전통시장`, `nodeNo=44810` | HTTP 200, `resultCode=00`, `NORMAL SERVICE.`, station row returned | `15098534/probes/live-2026-05-16/tago-bus-station.body.xml` |
| `15101360` | KEPCO 계약종별 전력사용량 | `https://bigdata.kepco.co.kr/openapi/v1/powerUsage/contractType.do` with `year=2020`, `month=11`, `metroCd=11`, `cityCd=110`, `cntrCd=100` | HTTP 200, JSON data returned | `15101360/probes/live-2026-05-16/kepco-contract-type.body.json` |
| `15129394` | 조달청 나라장터 입찰공고정보 | `/1230000/ad/BidPublicInfoService/getBidPblancListInfoServc` with `inqryDiv=2`, `bidNtceNo=R25BK00934017`, `type=json` | HTTP 200, `resultCode=00`, `정상`, bid row returned | `15129394/probes/live-2026-05-16/pps-bid-service.body.json` |
| `15134761` | 한국부동산원 부동산통계 | `https://www.reb.or.kr/r-one/openapi/SttsApiTbl.do` with `Type=json`, `pIndex=1`, `pSize=5` | HTTP 200, `INFO-000 정상 처리되었습니다.`, rows returned | `15134761/probes/live-2026-05-16/reb-stat-table.body.json` |
| `15157485` | 부산시설공단 장례비산출 | `/B552587/FuneralCostsService_v2/getFCAreaList_v2` with `resultType=json` | HTTP 200, `resultCode=00`, `NORMAL SERVICE.`, fee rows returned | `15157485/probes/live-2026-05-16/funeral-area-list.body.json` |
| `15158680` | 대학알리미 재정 현황 | `/B340014/FinancesService/getRegionalTuitionCrntSt` with `schlDivCd=02` | HTTP 200, `resultCode=00`, `NORMAL SERVICE.`, rows returned | `15158680/probes/live-2026-05-16/finance-regional-tuition.body.xml` |
| `15158684` | 대학정보공시 학생 현황 | `/B340014/StudentService/getRegionalForeignStudentCrntSt` with `schlDivCd=02` | HTTP 200, `resultCode=00`, `NORMAL SERVICE.`, rows returned | `15158684/probes/live-2026-05-16/student-regional-foreign.body.xml` |

## Reachable But Not Yet Callable

| ID | API | Probe result | Wrapping blocker |
|---|---|---|---|
| `15000122` | 법제처 생활법령검색 SOAP | WSDL HTTP 200. HTTPS SOAP `getSearchGroupList` returned HTTP 200 with `returnCode=30`, `SERVICE KEY IS NOT REGISTERED ERROR.` | Endpoint and SOAP envelope shape are known, but the current data.go.kr key is not registered for this service. |
| `15000215` | 법제처 생활법령정보 SOAP | WSDL HTTP 200. HTTPS SOAP `getLifeClassList` returned HTTP 200 with `returnCode=30`, `SERVICE KEY IS NOT REGISTERED ERROR.` | Same service-key registration blocker as `15000122`. |
| `15000241` | EMS 행방조회 | GET returned HTTP 200. With sample tracking numbers, response had `successYN=N`, `returnCode=99`; without key it returned `returnCode=10`. | Endpoint is alive and the key path changes behavior, but no successful tracking-data sample is confirmed yet. Need a currently valid EMS number or provider sample. |
| `15081808` | 국세청 사업자 상태조회 | POST `/api/nts-businessman/v1/status` returned HTTP 400 with `{"code":-5,"msg":"API 서버 오류가 발생하였습니다."}`. No-key control returned HTTP 401. | Endpoint and required POST body are known, but approved-key calls still hit upstream `-5`. Recheck later or inspect odcloud/service-specific approval state. |
| `15074634` | 과기정통부 사업공고 | Official endpoint `/1721000/msitannouncementinfo/businessAnnouncMentList` returned HTTP 400 `Request Blocked`; WADL returned HTTP 500 `Unexpected errors`. | Officially documented endpoint is currently gateway-blocked. Keep as blocked until a working sample from data.go.kr UI or provider is found. |
| `15149906` | 법무부 체류외국인 현황 카운터 | data.go.kr gateway returned HTTP 502 `Error forwarding request to backend server`; direct backend URL from Swagger entered a 307 redirect loop. | Contract is known, but the provider backend/gateway is not currently callable through `curl`. |

## Not Live-Probed

| ID | API | Reason |
|---|---|---|
| `15000032` | EMS 신청 저장 서비스 | The API is `addEMS`/`setEMSCancel`, i.e. submit/cancel behavior. The saved PDF and data.go.kr detail page do not expose a complete base URL, and sending fake data could create or cancel a real EMS request. Treat as `send` candidate, but do not live-call until the provider supplies a sandbox or explicit test endpoint. |
| `15056641` | CareerNet 직업정보 | External CareerNet key is still pending approval. Existing no-key probe already proves endpoint/error shape: `인증키 없습니다.` |
| `15087442` | KDCA 국가건강정보포털 | External KDCA token was not visible after submission. Existing no-token probes show the older `api.kdca.go.kr/api/provide/healthInfo` endpoint currently returns content, but the registered website flow and HWP contract still need post-approval reconciliation. |

## Curl Templates

Use these templates for later adapter fixture capture. Replace only the env var
names at runtime; never commit resolved key values.

```bash
curl -sS "https://apis.data.go.kr/1160100/service/GetFinaStatInfoService_V2/getSummFinaStat_V2?pageNo=1&numOfRows=1&resultType=json&crno=1746110000741&bizYear=2019&serviceKey=${UMMAYA_DATA_GO_KR_API_KEY}"

curl -sS -G "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getCtprvnRltmMesureDnsty?serviceKey=${UMMAYA_DATA_GO_KR_API_KEY}" \
  --data-urlencode "sidoName=서울" \
  --data-urlencode "pageNo=1" \
  --data-urlencode "numOfRows=5" \
  --data-urlencode "returnType=json" \
  --data-urlencode "ver=1.0"

curl -sS "https://bigdata.kepco.co.kr/openapi/v1/powerUsage/contractType.do?year=2020&month=11&metroCd=11&cityCd=110&cntrCd=100&apiKey=${UMMAYA_KEPCO_POWER_DATA_API_KEY}&returnType=json"

curl -sS "https://www.reb.or.kr/r-one/openapi/SttsApiTbl.do?KEY=${UMMAYA_REB_REAL_ESTATE_STATS_API_KEY}&Type=json&pIndex=1&pSize=5"
```
