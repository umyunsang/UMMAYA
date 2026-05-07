# Infrastructure Survey: `submit` primitive

> **범위**: KOSMOS active primitive 중 `submit` (쓰기 트랜잭션 — 민원 신청, 납부, 증명서 발급, 등록, 신고, 접수)의 실제 카운터파트인 한국 국가 인프라 시스템의 **외부 계약(external contract) 표면 캡처**.
> **원칙**: drop-in replaceability — 라이브 자격증명 확보 시 `client` 레이어만 교체(`MockClient(fixtures) → LiveClient(base_url, auth)`)하고 harness는 불변. 따라서 본 조사는 request schema · response schema · error code · auth · rate limit · pagination · idempotency 의 **공개 문서 기반 역공학**에 집중한다.
> **작성일**: 2026-04-19. **전 소스 공개 문서만** (공공데이터포털, 기관 공식 페이지, 법령, 공개 GitHub). 추측 구간은 모두 "⚠️ OPAQUE" 로 명시.
> **대상 구현물 금지**: 본 문서는 계약 캡처이지 구현 설계가 아니다. 코드는 싣지 않는다 (OASIS WS-Security namespace 등 이미 공개된 식별자만 인용).

---

## Executive summary (mirrorability overview)

한국 공공 서비스의 `submit` 계열 인프라는 **두 개의 완전히 다른 계약 부족(contract tribes)** 으로 갈린다.

1. **"정부가 자신을 위해 설계한 쓰기 통로"** — 전자세금계산서(KEC XML), 행정정보공동이용(PISC), 홈택스/위택스/EDI, 전자소송, 4대보험 통합징수, 정부24 어디서나연계. 이들은 **기관간·사업자간 시스템 통합용**이기 때문에 ① XML/ebXML/SOAP 같은 구형이지만 강하게 규격화된 포맷, ② GPKI(행정전자서명) 혹은 공동인증서(구 공인인증서) PKI 요구, ③ 별도의 사업자/기관 가입·연계 신청 절차를 전제한다. **공개 문서로 스키마·메시지 구조의 존재와 일부 조각은 확인되지만, 전체 XSD/WSDL/OpenAPI 는 비공개 내지 가입 후 제공**이다.
2. **"시민이 직접 쓰는 웹 UI만 있는 쓰기 표면"** — 복지로 온라인 신청, 청원24, 국민동의청원, NEIS 대국민 증명서 발급, 지자체 전자민원창구. 이들은 **공식적으로 쓰기 Open API 가 존재하지 않는다** — `data.go.kr`·지자체 오픈데이터·NEIS 교육정보 개방 포털은 모두 **GET 조회 전용 Open API**만 노출한다. 쓰기는 로그인된 브라우저/앱 세션을 통해서만 가능하며 (간편인증 + 디지털원패스 + 공동인증서), **API 문서화가 아예 없다**.

따라서 KOSMOS `submit` mock adapter 는 **두 tribe 모두를 shape-identically mirror 해야 한다**:

- **Tribe 1 (기관용 쓰기 계약)** — mirrorability **3-4/5**: KEC XML 표준, `data.go.kr` 공통 응답 포맷, ebXML 메시지 헤더 구조가 공개되어 있어 **envelope shape 과 error-code enum** 은 정확히 미러 가능. 단 **개별 메시지의 field-by-field XSD** 는 가입 후에만 공개되므로 대표 필드 이름만 모델링하고 나머지는 `extension_xml: str` 슬롯으로 비우는 mock 설계가 불가피.
- **Tribe 2 (시민용 웹 전용)** — mirrorability **1-2/5**: 계약이 존재하지 않으므로 KOSMOS 입장에서는 "mock 이 곧 사실상의 표준" 이 된다. `submit(domain=bokjiro, verb=apply, service_id=…)` 처럼 **정부24 서비스 식별자(CappBizCD 등) + HTTP-form multipart** 형태를 추측 없이 **documented form field 이름 그대로** 쓰는 conservative envelope 만 유지한다.

**공통 시민용 인증 축** (정부24·홈택스·복지로·위택스·EDI·전자소송): 공동인증서(구 공인인증서) + 간편인증(카카오/네이버/토스/PASS/삼성PASS/KB/PAYCO/신한 등) + 디지털원패스(**2025-12-30 서비스 종료 예정** — 당장 mock 에 반영 필요). 기관간 축: GPKI 인증서 (기관용·개인용 구분, `gpki.go.kr` 인증관리센터 발급).

**핵심 gap matrix** (뒤 섹션 Unknowns matrix 와 교차): 전자세금계산서 SOAP endpoint URL·공식 XSD · 전자소송 서류제출 WSDL · 어디서나연계시스템 XML 서식 전문 · NHIS/NPS EDI 의 ebXML 바디 스키마 — 전부 기관 요청 후에만 공개. KOSMOS 는 지금 단계에서는 **shape-compatible 한 envelope 만 구현**하고, 기관 협업 진입 시 **field enrichment stage** 를 별도 epic 으로 분리하는 것이 합리적이다.

본 문서의 Systems catalog 는 13개 시스템을 다루고, 각 시스템마다 엔드포인트 패턴·요청/응답 shape·에러 포맷·인증·레이트·gap·소스를 섹션별로 캡처했다. Cross-cutting patterns 섹션은 모든 시스템을 관통하는 계약 패턴 6개를 요약한다.

---

## Systems catalog

| # | 시스템 | URL | `submit` 의미 | 계약 공개도 | Mirrorability |
|---|---|---|---|---|---|
| 1 | 정부24 | [gov.kr](https://www.gov.kr/) | 민원 신청·증명서 발급 신청 | **중간** (Open API 는 조회 전용 + 민원24 XML 서식) | 2/5 |
| 2 | 홈택스 | [hometax.go.kr](https://hometax.go.kr/) | 부가세·종소세 전자신고, 세금 납부 | **낮음** (웹 폼/앱 전용) | 1/5 |
| 3 | 위택스 | [wetax.go.kr](https://www.wetax.go.kr/) | 지방세 신고·납부 | **매우 낮음** (조회 Open API 없음) | 1/5 |
| 4 | 건강보험공단 EDI | [edi.nhis.or.kr](https://edi.nhis.or.kr/) | 4대보험 자격 취득/상실/변경 신고 | **중간** (ebXML·웹EDI 가입 절차 공개) | 3/5 |
| 5 | 국민연금 EDI | [edi.nps.or.kr](https://edi.nps.or.kr/) | 사업장 가입자 자격·소득 신고 | **중간** (EDI 가이드북 2026 PDF 공개) | 3/5 |
| 6 | 복지로 | [bokjiro.go.kr](https://www.bokjiro.go.kr/) | 50종 복지서비스 온라인 신청 | **매우 낮음** (웹 전용) | 1/5 |
| 7 | NEIS 대국민 | [neis.go.kr](https://www.neis.go.kr/) | 학적·증명서 발급 신청 | **매우 낮음** (조회 Open API 만 `open.neis.go.kr`) | 1/5 |
| 8 | 고용24 / 워크넷 | [work24.go.kr](https://www.work24.go.kr/) | 이력서 등록·구인신청·HRD 신청 | **중간** (조회 Open API 공개, 쓰기 비공개) | 2/5 |
| 9 | 전자소송 | [ecfs.scourt.go.kr](https://ecfs.scourt.go.kr/) | 민사/지급명령 서류제출 | **낮음** (연계 API 가입 필수) | 2/5 |
| 10 | 국민동의청원 | [petitions.assembly.go.kr](https://petitions.assembly.go.kr/) | 청원 등록·동의 | **매우 낮음** (API 없음) | 1/5 |
| 11 | 청원24 | [cheongwon.go.kr](https://www.cheongwon.go.kr/) | 청원 등록 (구 국민제안 대체) | **낮음** (공개청원 결과만 GET API 로 개방) | 2/5 |
| 12 | 전자세금계산서 (eSero/홈택스) | [esero.go.kr](https://www.esero.go.kr/) + [hometax.go.kr](https://hometax.go.kr/) | 세금계산서 발급·국세청 전송 | **높음** (KEC XML v3.0 표준·법령 고시) | 4/5 |
| 13 | 지자체 전자민원 (서울 응답소 등) | [minwon.seoul.go.kr](https://minwon.seoul.go.kr/), [eungdapso.seoul.go.kr](https://eungdapso.seoul.go.kr/), [gg.go.kr](https://www.gg.go.kr/) 등 | 시·도 민원 접수 | **매우 낮음** (Open Data 조회만) | 1/5 |
| 14 | 전자문서 유통 통합포털 (행안부) | [gdoc.go.kr](https://gdoc.go.kr/) | 기관간 전자문서 유통 (간접 관련) | **높음** (표준 고시, ebMS 메시징) | 3/5 |
| 15 | 행정정보공동이용 (PISC) | [share.go.kr](https://www.share.go.kr/) | 신청 첨부서류 대체 (간접 submit 삭감) | **중간** (표준 API 배포, 가입 후) | 3/5 |

---

## Per-system deep dives

### 1. 정부24 (gov.kr)

정부24는 행정안전부가 운영하는 대민 민원 종합 포털로, 중앙부처·지자체 민원의 신청·발급·안내를 통합한다. 민원24 (구)와 시스템이 통합되며 **"어디서나 민원"** 서비스를 핵심으로 가진다.

#### Endpoints (관찰 가능한 웹 URL 패턴)

- `https://www.gov.kr/mw/AA020InfoCappView.do?HighCtgCD={ctg}&CappBizCD={bizId}&tp_seq={seq}` — 민원 상세·신청 진입 URL. `CappBizCD` (예: `14600000296` = 국민연금 사업장가입자 자격취득 신고) 가 **서비스 식별자 역할**.
- `https://www.gov.kr/search/applyMw` — 민원 검색·신청 엔트리.
- `https://www.gov.kr/openapi/info` — Open API 신청 안내 (조회 계열만).
- `https://www.gov.kr/etc/AA090_info_11_08.jsp` — "공통기반지원서비스의 어디서나연계시스템" 도움말.
- Open API 항목: [행정안전부_대한민국 공공서비스(혜택) 정보](https://www.data.go.kr/data/15113968/openapi.do) — **GET only**.

#### Request contract — 민원신청 (정부24 어디서나 민원)

공개 문서의 기술자: "민원24시스템을 통해 접수한 민원정보는 **표준화된 XML서식** 으로 다운로드 받을 수 있도록 자료를 제공한 후 **어디서나연계시스템의 특정 API를 호출**한다." (출처: [정부24 도움말](https://www.gov.kr/etc/AA090_info_11_08.jsp))

| 파라미터 | 의미 | 타입 |
|---|---|---|
| `HighCtgCD` | 상위 분류 코드 | string |
| `CappBizCD` | 서비스 유형 식별자 | string (10-자리 숫자 관찰) |
| `tp_seq` | 신청 유형 일련번호 | string |
| `ctgFile` | 첨부 파일 | multipart |
| `userIdntfSe` | 본인 확인 방식 | enum (간편인증/공동인증서) |

⚠️ OPAQUE — 실제 POST body, 세션 키, CSRF 토큰, XML 서식 상세는 **공개되지 않는다**. `어디서나연계시스템 API` 의 WSDL/XSD 는 행정안전부 내부 문서.

#### Response contract

증명서 발급 건은 **PDF/HWP/XML 서식 다운로드** 링크 + 처리 상태 (`접수됨`, `처리중`, `완료`, `반려`) 조회 ID 로 구성. Open API 경로는 **조회 전용**이며, 응답 공통 래퍼는 `data.go.kr` 표준을 따른다 (Cross-cutting patterns 섹션 참조).

#### Error format

민원 신청 자체의 에러 코드 체계는 **공개되지 않음** (⚠️ OPAQUE). 공통 조회 Open API 는 `data.go.kr` 표준 에러 코드 00/10/11/20/22/30 등 사용.

#### Auth

간편인증 12종 (네이버·카카오·토스·PASS·삼성PASS·KB·PAYCO·신한·농협·하나·우리·NH), 공동인증서, 금융인증서, 디지털원패스 (2025-12-30 종료). 출처: [정부24 간편인증 공지](https://www.gov.kr/portal/ntcItm/79665), [행안부 통합인증](https://www.mois.go.kr/frt/sub/a06/b04/easyCertification/screen.do).

#### Rate / pagination

Open API: `pageNo`, `numOfRows` (Cross-cutting pattern 1 참조). 민원 신청 자체 rate limit: ⚠️ OPAQUE.

#### Drop-in mirrorability: **2/5**

서비스 식별자(`CappBizCD`)와 본인인증 메커니즘은 관찰 가능하나 실제 신청 API 의 body·response 가 비공개. Mock 은 `CappBizCD`·`HighCtgCD`·`tp_seq` envelope + "어디서나연계시스템 XML 서식" 자리표시자 + 상태머신 enum `접수됨/처리중/완료/반려/보완요청` 수준으로 제한.

#### Gaps

- ⚠️ OPAQUE: 어디서나연계시스템 XML 서식 전문 (행안부 요청 필요).
- ⚠️ OPAQUE: 민원신청 POST 엔드포인트와 세션·토큰 프로토콜.
- ⚠️ OPAQUE: 민원 상태 실시간 조회 API (웹훅/폴링 여부 불명).

#### Sources

- [정부24 민원신청 포털](https://www.gov.kr/search/applyMw)
- [정부24 Open API 안내](https://www.gov.kr/openapi)
- [공공서비스 공동활용 OpenApi 신청](https://www.gov.kr/openapi/info)
- [어디서나연계시스템 도움말](https://www.gov.kr/etc/AA090_info_11_08.jsp)
- [정부24 민원 상세 URL 예시 (국민연금 자격취득)](https://www.gov.kr/mw/AA020InfoCappView.do?HighCtgCD=A05007&CappBizCD=14600000296)

---

### 2. 홈택스 (hometax.go.kr)

국세청이 운영하는 종합 국세 포털. 부가가치세·종합소득세·원천세·법인세 전자신고, 현금영수증 등록, 세금 납부, 전자세금계산서 발급·수정 등 세무 쓰기 트랜잭션의 핵심 소비자다.

#### Endpoints (관찰된 URL shape)

- `https://www.hometax.go.kr/websquare/websquare.html?w2xPath=/ui/pp/index_pp.xml&tmIdx={idx}&tm2lIdx={sub}` — WebSquare 기반 메뉴 라우팅. 예: 종소세 신고 `tmIdx=41&tm2lIdx=4103000000`.
- `https://mob.tbht.hometax.go.kr/jsonAction.do?actionId={id}` — 손택스(모바일) JSON 액션 엔드포인트. `actionId=UTBRNAA130F001` (부가세 신고도움), `UTBETFAA01F001` (전자세금계산서 자료신청) 등.
- `https://mob.tbet.hometax.go.kr/jsonAction.do?actionId=...` — 전자세금계산서 모듈 별도 서브도메인.

#### Request contract

⚠️ OPAQUE — 공식 공개 API 없음. 관찰된 것은 **내부용 jsonAction `actionId` 라우팅**: POST body 로 암호화된 세션 + `actionId` 별 파라미터 번들. 필드명·타입은 기업용 세무 SW (Bill36524, SmartBill, WEHAGO T, PopBill, CODEF 등) 의 리버스 엔지니어링으로만 추정 가능.

전자신고 파일 업로드 경로: 회계 SW 에서 생성한 **전자신고 파일(.01 ~ .04 확장자)** 을 홈택스 웹 업로드 폼으로 제출. 파일 포맷은 **국세청 고시 표준 XML/고정폭 레코드 혼합**이며 상세 스키마는 비공개.

#### Response contract

홈택스 UI 반환은 HTML + WebSquare JSON 프래그먼트. 공식 응답 스키마 문서 없음.

#### Error format

⚠️ OPAQUE (공개 오류 코드표 없음). 사용자 대면 에러는 국세청 고객센터 126 안내로 라우팅.

#### Auth

공동인증서 (구 공인인증서) 필수 (종소세·부가세 전자신고), 간편인증 2025-09 매뉴얼 공개 — 민간인증서 사용자 매뉴얼 ([hometax.speedycdn.net PDF](https://hometax.speedycdn.net/dn_dir/webdown/%EA%B0%84%ED%8E%B8%EC%9D%B8%EC%A6%9D%EB%A1%9C%EA%B7%B8%EC%9D%B8%EC%9E%90%EC%84%B8%ED%9E%88%EB%B3%B4%EA%B8%B0.pdf)). 사업자는 **전자세금용 공동인증서** 별도 발급 (은행/한국정보인증/한국전자인증 등).

#### Rate / pagination

신고 기간 (1월·5월·7월 특정 일자) 집중으로 회계 SW 벤더의 queue·retry 관측치가 존재하나 **공식 rate limit 명시 없음**.

#### Drop-in mirrorability: **1/5**

공식 API 경로 비공개. Mock 은 shape-wise 로는 전자세금계산서(섹션 12)의 KEC XML 포맷만 정확히 미러하고, 일반 전자신고는 "opaque file upload endpoint" 로 추상화.

#### Gaps

- ⚠️ OPAQUE: 전자신고 파일 (.01~.04) 상세 포맷 (국세청 내부 표준).
- ⚠️ OPAQUE: 전자신고 에러코드 및 처리 상태 colling API.
- ⚠️ OPAQUE: 납부 API (카드·계좌이체·간편결제 라우팅).

#### Sources

- [국세청 홈택스 메인](https://www.hometax.go.kr/)
- [종합소득세 신고 페이지](https://hometax.go.kr/websquare/websquare.html?w2xPath=/ui/pp/index_pp.xml&tmIdx=41&tm2lIdx=4103000000&tm3lIdx=4103020000)
- [간편인증 사용자 매뉴얼 PDF](https://hometax.speedycdn.net/dn_dir/webdown/%EA%B0%84%ED%8E%B8%EC%9D%B8%EC%A6%9D%EB%A1%9C%EA%B7%B8%EC%9D%B8%EC%9E%90%EC%84%B8%ED%9E%88%EB%B3%B4%EA%B8%B0.pdf)
- [국세청 공지사항: OpenAPI 변경 안내](https://www.data.go.kr/bbs/ntc/selectNotice.do?originId=NOTICE_0000000003116)

---

### 3. 위택스 / 이택스 (wetax.go.kr)

행정안전부 주관 전국 지방세 통합 포털. 재산세·자동차세·주민세·취득세 등 지방세 조회·신고·납부. 서울시만 `etax.seoul.go.kr` 로 분리.

#### Endpoints

- `https://www.wetax.go.kr/main.do` — 포털 진입.
- `https://www.wetax.go.kr/etr/incmMain.do` — 개인지방소득세 신고 간소화.
- `https://www.wetax.go.kr/static/sim/SimpleNc2.html` — 전국 지방세 신고·납부 서비스 간소화 랜딩.

#### Request / Response / Error / Auth / Rate

⚠️ **OPAQUE 전부** — 위택스는 **Open API 가 존재하지 않는다**. 공공데이터포털에 `wetax` 검색 결과 해당 카탈로그 없음. 로그인은 공동인증서·간편인증 사용이 관찰되지만 프로토콜 상세 비공개.

#### Drop-in mirrorability: **1/5**

Mock adapter 는 **도메인 지식 기반 유추**: 지방세 청구서 스키마 (납세자식별번호·지자체코드·과세대상·세목·세액·납기·납부방법) + 고지서 ID + 상태 enum `미납/납부완료/분납/체납` 수준에서 추상화.

#### Gaps

- ⚠️ OPAQUE: 전체 API 표면 (신고서 제출, 납부, 환급, 전자송달).
- ⚠️ OPAQUE: 지자체 간 라우팅 규칙 (시·군·구 코드 매핑).
- ⚠️ OPAQUE: 서울시 `etax.seoul.go.kr` 과의 분리 배경 및 cross-system 동기화 여부.

#### Sources

- [위택스 메인](https://www.wetax.go.kr/main.do)
- [개인지방소득세 전용 서비스](https://www.wetax.go.kr/etr/incmMain.do)
- [정부24 위택스 안내](https://www.gov.kr/portal/service/serviceInfo/PTR000052095)

---

### 4. 국민건강보험공단 EDI (edi.nhis.or.kr)

사업장이 4대보험 (건강보험·국민연금·고용보험·산재보험) 취득·상실·변경·급여 등을 전자적으로 신고하는 창구. 징수 업무는 **건보공단 통합** (4대보험 중계서버 통해 타 공단과 정보공유).

#### Endpoints

- `https://edi.nhis.or.kr/` — 웹 EDI 진입.
- `https://edi.nhis.or.kr/homeapp/wep/o/serviceGuide.do` — 서비스 가이드.
- `https://edi.nhis.or.kr/homeapp/wep/o/certificateReg.do` — 공동인증서 등록.
- `https://si4n.nhis.or.kr/` — 사회보험 통합징수 포털.

#### Request contract

문서: "건보공단 EDI 는 ebXML 기반 메시징 엔진" (유관 정부 전자문서 유통 기술 인용). 웹EDI 가입 6단계 매뉴얼 공개:

1. 사업장 회원가입
2. 사업장 신청서 작성
3. 약관 동의
4. 사업자등록 정보 입력
5. 웹EDI 접속 후 인증서 등록 버튼
6. 공동인증서로 인증 완료

전송 파일: **정형화된 신고서식 (엑셀 템플릿 + XML 변환) 업로드** 또는 웹 폼 직접 입력. 대표 신고 종류:

| 신고서 | 의미 |
|---|---|
| 자격 취득 신고 | 입사 |
| 자격 상실 신고 | 퇴사 |
| 내용 변경 신고 | 주민번호·이름·부양가족 변경 |
| 기준소득월액 변경 | 소득 변경 |
| 피부양자 자격 신고 | 가족 등록·말소 |

#### Response contract

접수증 (접수번호 + 처리예정일) + 결과 회신 (승인·반려·보완요청). ⚠️ OPAQUE — ebXML 응답 메시지의 exact shape 은 비공개.

#### Error format

입력 단계 실시간 검증 (e.g. 주민번호 체크섬·고용일 미래 불가·소득 범위) 존재. 코드표 비공개.

#### Auth

공동인증서 필수 (사업자·개인). 브라우저 요구사항: 팝업 차단 해제, NHIS 도메인 신뢰 사이트 추가, IE7 관리자 모드 — 레거시 ActiveX 잔존 흔적.

#### Rate / pagination

⚠️ OPAQUE. 월말·월초 집중.

#### Drop-in mirrorability: **3/5**

신고 종류 목록·입력 필드 리스트·결과 상태 enum 이 UI/매뉴얼에서 관찰 가능. ebXML envelope 골격(SOAP 1.1 + WS-Security) 은 표준이라 미러 가능. 단 **body XSD 는 기관 제공 후에만** 실체화.

#### Gaps

- ⚠️ OPAQUE: ebXML body XSD (각 신고서별).
- ⚠️ OPAQUE: 4대보험 중계서버 라우팅 메타데이터.
- ⚠️ OPAQUE: 결과 회신 poll 주기 또는 push 프로토콜.

#### Sources

- [국민건강보험 EDI](https://edi.nhis.or.kr/)
- [EDI 서비스 가이드](https://edi.nhis.or.kr/homeapp/wep/o/serviceGuide.do)
- [웹EDI 가입·업무처리 매뉴얼 PDF (2022)](https://waf-e.dubuplus.com/yesinsa.dubuplus.com/joon2you@naver.com/O18Bg3Z/DubuDisk/www/2022%EB%85%84%20%EC%97%85%EB%AC%B4%EC%B2%98%EB%A6%AC_%EB%A7%A4%EB%89%B4%EC%96%BC(%EA%B1%B4%EA%B0%95%EB%B3%B4%ED%97%98).pdf)
- [사회보험 통합징수 포털](https://si4n.nhis.or.kr/)
- [정부24 건강보험 EDI 안내](https://www.gov.kr/portal/service/serviceInfo/PTR000050381)
- [KR101439809B1 건강보험 웹edi 시스템 특허](https://patents.google.com/patent/KR101439809B1/ko)

---

### 5. 국민연금 EDI (edi.nps.or.kr)

사업장 단위 국민연금 신고 전용. 2026년 가이드북 PDF 공식 공개.

#### Endpoints

- `https://edi.nps.or.kr/` — EDI 포털.
- `https://edi.nps.or.kr/cm/main/guide/edi_guide.pdf` — **2026년 EDI 서비스 가이드북 PDF**.
- `https://edi.nps.or.kr/cm/main/guide/edi_workguide_new.pdf` — 사업장 실무안내 PDF.

#### Request contract

웹EDI 는 회원가입 없이 **공동인증서 로그인만으로 이용 가능** (이 점 NHIS 와 차이). 신고 업무 목록:

- 자격취득 신고 (입사)
- 자격상실 신고 (퇴사)
- 내용변경 (이름·주민번호·보험료 부담)
- 기준소득월액 변경
- 납부예외 신청
- 소득 총액 신고

입력 방식: 웹 폼 직접 입력 또는 **Excel 템플릿 업로드** (건보·고용·산재 일괄 신고 경로). 국민연금 웹EDI 업무대행서비스 처리기준 (2022.7.4 고시) 별도 존재.

#### Response contract

접수증 + 결과 회신. 실시간 검증 (입력오류).

#### Error format

⚠️ OPAQUE — 공식 에러 코드표 미공개.

#### Auth

공동인증서 (사업장 명의). 간편인증 일부 허용 (가이드북 확인 필요 — fetch 실패로 **본 섹션은 PDF 재조회 예정**).

#### Rate / pagination

신고 기한 익월 15일. ⚠️ OPAQUE.

#### Drop-in mirrorability: **3/5**

가이드북·실무안내 PDF 존재로 업무 목록·필드 이름·상태머신 추출 가능. Body 스키마는 NHIS 와 유사 추정.

#### Gaps

- ⚠️ OPAQUE: EDI 메시지 XSD.
- ⚠️ OPAQUE: 업무대행서비스 위임 토큰 포맷.

#### Sources

- [국민연금 EDI](https://edi.nps.or.kr/)
- [2026 EDI 서비스 가이드북 PDF](https://edi.nps.or.kr/cm/main/guide/edi_guide.pdf)
- [사업장 실무안내 PDF](https://edi.nps.or.kr/cm/main/guide/edi_workguide_new.pdf)
- [정부24 국민연금 자격취득·상실 신고](https://www.gov.kr/mw/AA020InfoCappView.do?HighCtgCD=A05007&CappBizCD=14600000296&tp_seq=)
- [웹EDI 업무대행서비스 처리기준 공지](https://www.nps.or.kr/pnsinfo/databbs/getOHAF0272M1Detail.do?menuId=MN24001000&pstId=ET202200000000026998&hmpgCd=&hmpgBbsCd=BS20240094&sortSe=FR&pageIndex=1&searchText=&searchGbu=)

---

### 6. 복지로 (bokjiro.go.kr)

보건복지부 운영. 중앙부처 360여 개 사업 + 지자체 4000여 종 복지 서비스 안내 + **온라인 신청 50종**.

#### Endpoints

- `https://www.bokjiro.go.kr/` — 메인.
- `https://online.bokjiro.go.kr/apl/popup/selectAplApplBfAttnItemInfP.do` — 온라인신청 전 확인 사항 팝업.
- `https://blog.bokjiro.go.kr/1345` — 복지서비스 신청 절차 (공식 블로그, 공개 절차 인용).

#### Request contract

신청 흐름 (공개 블로그 설명): 복지로 접속 → 서비스신청 → 복지서비스신청 → 복지급여 신청 → 동의 → 신청서 작성 → 첨부서류 → 제출. 자격 모의계산 존재.

#### Response contract

신청 접수증·진행 상태 (접수/검토/결정/지급 또는 반려). ⚠️ OPAQUE.

#### Error format

⚠️ OPAQUE.

#### Auth

공동인증서·간편인증·디지털원패스 (2025-12-30 종료 예정).

#### Rate / pagination

⚠️ OPAQUE.

#### Drop-in mirrorability: **1/5**

복지 온라인 신청 50종 목록은 공개되나, 각 신청의 body 필드·첨부·상태머신은 UI 관찰로만 추정.

#### Gaps

- ⚠️ OPAQUE: 온라인 신청 50종 각각의 신청서 필드 정의.
- ⚠️ OPAQUE: 지자체 4000종 서비스 라우팅 메커니즘 (행정정보공동이용 연계 추정).
- ⚠️ OPAQUE: 상태 알림 (SMS/카카오톡) 연계 API.

#### Sources

- [복지로](http://www.bokjiro.go.kr/)
- [복지로 온라인신청 팝업](https://online.bokjiro.go.kr/apl/popup/selectAplApplBfAttnItemInfP.do)
- [복지로 온라인 신청 절차 블로그](https://blog.bokjiro.go.kr/1345)
- [보건복지부 온라인 신청 확대 보도자료](https://www.mohw.go.kr/board.es?mid=a10503000000&bid=0027&tag=&act=view&list_no=376773&cg_code=)
- [한국사회보장정보원 자원정보서비스 현황 (data.go.kr)](https://www.data.go.kr/data/15001839/openapi.do)

---

### 7. NEIS 대국민서비스 (neis.go.kr)

교육부/시도교육청의 학생·학부모·학교 통합 교육행정정보시스템. 증명서(재학·졸업·생활기록부·건강기록부 등) 발급·확인 주체.

#### Endpoints

- `https://www.neis.go.kr/` — 대국민.
- `https://open.neis.go.kr/` — **교육정보 개방 포털** (조회 Open API 전용).
- `https://open.neis.go.kr/portal/guide/apiIntroPage.do` — API 소개.
- `https://open.neis.go.kr/portal/guide/apiGuidePage.do` — 개발자 가이드 (상세 스펙 별도 다운로드).

#### Request contract (증명서 발급)

⚠️ OPAQUE — 증명서 발급·신청은 **대국민 웹 UI 전용**. `open.neis.go.kr` Open API 는 **조회(학교기본정보·학사일정 등) 전용**이며 쓰기 기능 없음.

#### Response contract

Open API 조회: JSON/XML, UTF-8. PDF 증명서 다운로드.

#### Error format

Open API: `data.go.kr` 표준 에러 코드 패턴 추정 ⚠️ 확정 인용 없음.

#### Auth

**Open API 인증키**: Google/Naver/Daum 포털 소셜 로그인 후 MyPage 에서 즉시 발급 (별도 회원가입 없음).
대국민 증명 발급: 공동인증서·간편인증·금융인증서.

#### Rate / pagination

⚠️ OPAQUE — 명세서 별도 다운로드 필요.

#### Drop-in mirrorability: **1/5** (submit 한정)

조회용 Open API 는 미러 용이하나, `submit` primitive 는 대국민 증명서 발급 · 학적 변동 신청이 핵심인데 **공식 API 부재**. Mock 은 학교 코드 (`ATPT_OFCDC_SC_CODE`, `SD_SCHUL_CODE`) + 증명서 종류 enum 만 envelope 에 반영.

#### Gaps

- ⚠️ OPAQUE: 대국민 증명서 신청/발급 API 존재 여부.
- ⚠️ OPAQUE: 학적 변동 (전학·자퇴) 신청 프로토콜.

#### Sources

- [NEIS 대국민](https://www.neis.go.kr/)
- [나이스 교육정보 개방 포털](https://open.neis.go.kr/)
- [Open API 소개](https://open.neis.go.kr/portal/guide/apiIntroPage.do)
- [개발자 가이드](https://open.neis.go.kr/portal/guide/apiGuidePage.do)
- [공공데이터포털 NEIS 학교기본정보](https://www.data.go.kr/data/15122275/openapi.do)
- [GitHub neis-api Node.js 라이브러리](https://github.com/my-school-info/neis-api) (비공식 wrapper)

---

### 8. 고용24 / 워크넷 (work24.go.kr)

고용노동부·고용정보원 통합 포털. 워크넷·고용보험·HRD-net 등 9개 시스템 통합.

#### Endpoints

- `https://www.work24.go.kr/` — 메인.
- `https://m.work24.go.kr/cm/e/a/0110/selectOpenApiIntro.do` — Open API 소개.
- `https://eis.work24.go.kr/eisps/opiv/selectOpivList.do` — 고용행정통계 Open API 가이드.
- `https://lod.work.go.kr/openAPI_guide.do` — LOD Open API 가이드.
- 공공데이터포털 워크넷 목록: [채용정보 채용목록 및 상세정보](https://www.data.go.kr/data/3038225/openapi.do), [직무데이터사전](https://www.data.go.kr/data/15088880/openapi.do).

#### Request contract (조회)

- HTTP 기반 + XML 응답 (UTF-8).
- 인증키(기업회원 가입 후 발급), 호출유형, 반환형식, 시작페이지, 출력건수.
- 채용정보 파라미터: 근무지역·직종·임금형태·급여·학력·경력·고용형태.

#### Request contract (submit — 이력서 등록·구직 신청)

⚠️ OPAQUE — 쓰기 API 는 **공식 Open API 목록에 없음**. UI 전용. 모바일 `m.work24.go.kr/wk/a/b/2100/resumeMngMain.do` (이력서 관리) 경로는 로그인 세션 의존.

#### Response contract

조회 API: 구인인증번호·회사명·채용제목·급여·근무지역 등 XML.

#### Error format

⚠️ 부분 공개 — 인증키 무효·IP 미등록 등 공통 오류 (`data.go.kr` 표준 에러 체계 추정).

#### Auth

기업 회원 가입 → 인증키 발급 → 관리자 검토 → 부여. 인증키 양도 금지.

#### Rate / pagination

⚠️ OPAQUE (숫자 미공개).

#### Drop-in mirrorability: **2/5**

조회 API 는 4/5 수준으로 미러 가능. `submit` (이력서 등록 등) 은 1/5. 합산 2/5.

#### Gaps

- ⚠️ OPAQUE: 이력서 등록·구직 신청 API (비공개).
- ⚠️ OPAQUE: HRD-net 훈련과정 신청 API.
- ⚠️ OPAQUE: 고용보험 실업급여 신청 API.

#### Sources

- [고용24 메인](https://www.work24.go.kr/)
- [Open API 소개](https://m.work24.go.kr/cm/e/a/0110/selectOpenApiIntro.do)
- [고용행정통계 Open API 가이드](https://eis.work24.go.kr/eisps/opiv/selectOpivList.do)
- [워크넷 LOD 가이드](https://lod.work.go.kr/openAPI_guide.do)
- [공공데이터포털 워크넷 채용](https://www.data.go.kr/data/3038225/openapi.do)
- [공공데이터포털 워크넷 직무](https://www.data.go.kr/data/15088880/openapi.do)

---

### 9. 전자소송 (ecfs.scourt.go.kr)

대법원 전자소송포털. 민사본안·지급명령·가사·행정·특허 등 서류 제출.

#### Endpoints

- `https://ecfs.scourt.go.kr/` — 전자소송 진입.
- `https://ecfs.scourt.go.kr/psp/index.on?m=PSPA13M01` — 민사 서류제출.
- `https://ecfs.scourt.go.kr/psp/index.on?m=PSPA13M03` — 지급명령(독촉) 신청.
- `https://ecfs.scourt.go.kr/psp/index.on?m=PSPA13M04` — 전체서류.
- `https://ecfs.scourt.go.kr/psp/index.on?m=PSP720M24` — 양식모음.
- `https://openapi.scourt.go.kr/kgso202m01.do` — **사법정보공유포털 이용안내 및 절차**.
- `https://openapi.scourt.go.kr/kgso301m01.do` — 연계 API 목록.

#### Request contract

⚠️ OPAQUE — `ecfs.scourt.go.kr` 서류제출은 웹 UI + 법원 고유 양식(HWP/PDF) 첨부. 전자접수 API 는 **연계 API** 로만 제공되고 개별 기관/변호사사무소 단위 신청. 담당자: `publicapi@scourt.go.kr`. 오픈 API 는 "추후 업데이트 예정" 상태.

#### Response contract

접수증 (사건번호·접수일시 + 전자문서 파일해시). ⚠️ OPAQUE.

#### Error format

⚠️ OPAQUE.

#### Auth

공동인증서 (사용자·변호사), 개인은 간편인증 확대 중.

#### Rate / pagination

⚠️ OPAQUE.

#### Drop-in mirrorability: **2/5**

양식모음이 URL 로 노출되어 사건 유형 목록 + 서류 제목 enum 추출 가능. 서류 업로드 multipart + 수수료 결제 envelope 골격은 추정 가능하나 exact field 는 비공개.

#### Gaps

- ⚠️ OPAQUE: 서류제출 API WSDL/OpenAPI (연계 API 담당자 접촉 필요).
- ⚠️ OPAQUE: 전자서명·타임스탬프 세부 포맷.
- ⚠️ OPAQUE: 수수료 결제 라우팅.

#### Sources

- [전자소송포털](https://ecfs.scourt.go.kr/)
- [민사본안 서류제출](https://ecfs.scourt.go.kr/psp/index.on?m=PSPA13M01)
- [지급명령 신청](https://ecfs.scourt.go.kr/psp/index.on?m=PSPA13M03)
- [양식모음](https://ecfs.scourt.go.kr/psp/index.on?m=PSP720M24)
- [사법정보공유포털 이용안내](https://openapi.scourt.go.kr/kgso202m01.do)
- [연계 API 목록](https://openapi.scourt.go.kr/kgso301m01.do)

---

### 10. 국민동의청원 (petitions.assembly.go.kr)

국회 전자청원. 2020-01 도입. 30일 내 5만 명 동의 시 소관위원회 회부. 2025-03 기준 2106건 등록, 268건(12.7%) 회부.

#### Endpoints

- `https://petitions.assembly.go.kr/` — 메인.

#### Request contract

⚠️ OPAQUE — 공식 API 없음. 청원 등록 필드(제목·내용·카테고리·첨부) + 실명 인증 (본인확인 기관 연계) 이 UI 에서 관찰.

#### Response contract

공개 후 30일 타이머 + 동의 수 카운터. 회부 여부 공개.

#### Error format

⚠️ OPAQUE.

#### Auth

본인확인 (SMS·카카오·PASS 등 민간 본인확인 기관).

#### Rate / pagination

⚠️ OPAQUE.

#### Drop-in mirrorability: **1/5**

Mock envelope: 청원 제목·내용·카테고리·청원인·동의 수·상태(`등록/공개/기간만료/회부/검토완료`) 수준.

#### Gaps

- ⚠️ OPAQUE: 동의 카운터 API.
- ⚠️ OPAQUE: 소관위 회부 트리거 로직 (수동/자동).

#### Sources

- [국회전자청원](https://petitions.assembly.go.kr/)
- [국민동의청원 나무위키](https://namu.wiki/w/%EA%B5%AD%EB%AF%BC%EB%8F%99%EC%9D%98%EC%B2%AD%EC%9B%90)
- [국회 전자청원제도 학술논문](https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART002730562)

---

### 11. 청원24 (cheongwon.go.kr)

행정안전부가 2022-12-23 오픈한 행정부 청원 포털. 청와대 국민청원(구) 대체 + 국민제안 통합. 청원법 제10조 근거.

#### Endpoints

- `https://www.cheongwon.go.kr/` — 메인.
- `https://cheongwon.go.kr/portal/login` — 로그인.
- `https://cheongwon.go.kr/portal/petition/open/view` — 공개청원 목록.
- 공개청원 결과 오픈 데이터: [공공데이터포털 15145171 - 공개청원 내용 및 처리결과](https://www.data.go.kr/data/15145171/fileData.do).

#### Request contract (submit)

⚠️ OPAQUE. UI 기반. 접수 → 청원심의위 → 90일 처리.

#### Response contract

공개청원 결과는 **공공데이터포털 파일데이터** 로 개방: 일자·제목·처리기관·내용·처리결과 필드. JSON/XML REST API 제공 (파일 다운로드 형태).

#### Error format

⚠️ OPAQUE.

#### Auth

공동인증서·간편인증.

#### Rate / pagination

90일 처리 기한. 기타 ⚠️ OPAQUE.

#### Drop-in mirrorability: **2/5**

처리결과 API 는 미러 가능 (GET), 접수 API 는 비공개.

#### Gaps

- ⚠️ OPAQUE: 청원 접수 API.
- ⚠️ OPAQUE: 처리 상태 실시간 조회 API (파일 스냅샷만 존재).

#### Sources

- [청원24](https://www.cheongwon.go.kr/)
- [청원24 오픈 보도자료](https://www.korea.kr/news/policyNewsView.do?newsId=148908954)
- [행안부 청원24 안내](https://www.mois.go.kr/frt/bbs/type002/commonSelectBoardArticle.do?bbsId=BBSMSTR_000000000205&nttId=97036)
- [공개청원 공공데이터 카탈로그](https://www.data.go.kr/data/15145171/fileData.do)

---

### 12. 전자세금계산서 (eSero + hometax)

가장 **공개도가 높은** 시스템. KEC XML v3.0 표준, 행정규칙 (행정안전부·국세청 공동 고시), 공개 검증 샘플 코드까지 존재.

#### Endpoints

- `https://www.esero.go.kr/` — eSero (무료 발급 포털).
- `https://hometax.go.kr/` — 홈택스 (전송 결과 조회 + 발급).
- SOAP 전송 URL: **실서비스 경로 ⚠️ OPAQUE** (사업자 등록 후 제공). 단 테스트/검증용 GitHub 샘플은 SOAP namespace 와 WS-Security 호출 구조를 명확히 보여준다.

#### Request contract

**KEC XML v3.0** — 2008 부가세법 개정 → 2009 개발 → 2010 시범 → 2011 전면 시행. 전자세금계산서는 **생성·발급·전송된 XML 파일 자체** 가 원본이다. 필수 요소:

- `kec` namespace (`http://www.kec.or.kr/standard/Tax/`).
- 공급자·공급받는자 사업자등록번호, 작성일자, 품목, 공급가액, 부가세.
- 공급자 공인(공동)인증서 개인키로 해시값 서명 → 전자서명 생성.
- SOAP 전송 시 **OASIS WS-Security** 준수 (Username/Password 또는 X.509 Token Profile).

#### Response contract

국세청 서버 → **접수증 응답 메시지** (접수번호 + 결과코드 + 타임스탬프). XML.

#### Error format

행정규칙 고시: [전자(세금)계산서 시스템을 구축·운영하는 사업자가 지켜야 할 사항 및 표준 인증에 관한 고시](https://www.law.go.kr/LSW/admRulLsInfoP.do?admRulSeq=2100000229172) — 검증 실패 (스키마·서명·사업자 상태) 시 재전송 절차 규정. 코드표 ⚠️ 법령상 존재, 전문 PDF 다운로드 필요.

#### Auth

**전자세금용 공동인증서** (일반 은행 인증서와 구분). 발급처: 한국정보인증·한국전자인증·KB·우리은행·NH·코스콤 등. 국세청/전자세금계산서 사이트에서만 사용 가능.

#### Rate / pagination

발급 즉시 전송 의무. ⚠️ RATE 명시 없음.

#### Idempotency

**자연적 idempotency key**: 공급자 사업자번호 + 작성일자 + 승인번호 (국세청 부여). 재전송 시 동일 키로 중복 회피.

#### Drop-in mirrorability: **4/5**

- XML 표준 + 법령 + 공개 샘플 (GitHub ruseel/kr-etax-sample) → shape·namespace·서명 루틴까지 미러 가능.
- 실 endpoint URL 과 정부인증서 체인만 mock 에서 placeholder.

#### Gaps

- ⚠️ OPAQUE: 운영 SOAP URL (사업자 등록 필요).
- ⚠️ OPAQUE: 전체 error code 표 (고시 본문 PDF 인용 필요).
- ⚠️ OPAQUE: 수정세금계산서·역발행 메시지의 별도 RPC 이름.

#### Sources

- [국세청 전자세금계산서 제도의 이해 PDF (공공데이터포털)](https://www.data.go.kr/data/15050750/fileData.do)
- [법령: 표준 인증 고시](https://www.law.go.kr/LSW/admRulLsInfoP.do?admRulSeq=2100000229172)
- [GitHub ruseel/kr-etax-sample (검증 샘플)](https://github.com/ruseel/kr-etax-sample)
- [GitHub SubmitWithSOAP.java (발췌)](https://github.com/ruseel/kr-etax-sample/blob/master/src/main/java/com/barostudio/SubmitWithSOAP.java)
- [XML 표준 전자세금계산서의 개발과 유통 (KCI 논문)](https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART001582079)
- [전자(세금)계산서 자료신청 (손택스 모바일)](https://mob.tbet.hometax.go.kr/jsonAction.do?actionId=UTBETFAA01F001)
- [KT-NET FAQ: XML 다운로드](https://webcs.ktnet.com/introduce/FaqView.do?num=240)
- [특허 KR101053097B1 전자세금계산서 발급 장치/방법](https://patents.google.com/patent/KR101053097B1/ko)
- [Storecove e-invoicing in South Korea (영문 규제 요약)](https://www.storecove.com/blog/en/e-invoicing-in-south-korea-regulations/)
- [ClearTax Korea e-Invoice guide (영문)](https://www.cleartax.com/kr/e-invoicing-south-korea)

---

### 13. 지자체 전자민원 (서울 응답소 · 경기도 · 부산 등)

`minwon.seoul.go.kr`, `eungdapso.seoul.go.kr`, `gg.go.kr`, `data.seoul.go.kr` 등.

#### Endpoints

- `https://minwon.seoul.go.kr/` — 서울시 온라인 민원.
- `https://eungdapso.seoul.go.kr/` — 응답소(고충·제안 전담, 02-2133-7930).
- `https://eungdapso.seoul.go.kr/req/rectify/rectify.do` — 건의·질의 민원신청.
- `https://data.seoul.go.kr/together/guide/useGuide.do` — 서울 열린데이터광장 Open API 가이드.
- `https://www.gg.go.kr/contents/contents.do?ciIdx=1230&menuId=2994` — 경기도 민원 신청 안내.

#### Request contract

⚠️ OPAQUE — 모든 지자체가 **조회 Open API 만 개방** (도로·버스·주차장 등). 민원 접수는 UI 전용. 서울 열린데이터광장은 Java/JavaScript/cURL/Python/Node.js 예제 제공 (GET 중심).

#### Response contract

조회: JSON/XML. 쓰기: 미공개.

#### Error format

⚠️ OPAQUE.

#### Auth

시민 간편인증·공동인증서·서울 특화 '서울 시민 로그인' 세션.

#### Rate / pagination

⚠️ OPAQUE.

#### Drop-in mirrorability: **1/5**

민원 카테고리 enum + 신청서 필드 (제목·내용·첨부·담당부서 자동 라우팅) 만 추상화.

#### Gaps

- ⚠️ OPAQUE: 시·도별 민원 라우팅 API.
- ⚠️ OPAQUE: 응답소 고충 분류 모델.
- ⚠️ OPAQUE: 민원서류 발급 (주민등록등본 등) 은 **정부24 로 위임**되는 경우가 대부분.

#### Sources

- [서울시 온라인 민원](https://minwon.seoul.go.kr/)
- [서울 응답소 메인](https://eungdapso.seoul.go.kr/main.do)
- [응답소 건의·질의 민원](https://eungdapso.seoul.go.kr/req/rectify/rectify.do)
- [서울 열린데이터광장 가이드](https://data.seoul.go.kr/together/guide/useGuide.do)
- [경기도 민원 신청 안내](https://www.gg.go.kr/contents/contents.do?ciIdx=1230&menuId=2994)

---

### 14. 전자문서 유통 통합포털 (gdoc.go.kr)

행정안전부 "정부 전자문서 유통 표준" (고시 제2024-27호, 2024-04-15 개정). **기관간 전자문서 교환** 의 상위 표준. `submit` 과 간접 관련: 민원 접수 결과 증명서·공문이 이 프로토콜로 기관간 전달됨.

#### Endpoints

- `https://gdoc.go.kr/` — 포털.

#### Request / Response contract

**ebMS (ebXML Messaging Services) 기반**. SOAP 1.1 + WS-Security + WS-ReliableMessaging 프로파일. 문서 자체는 XML 메타데이터 + 바이너리 첨부 (HWP/PDF/XML).

#### Error format

정부 전자문서 유통 표준 본문 고시 [행안부 고시 2024-27호](https://www.mois.go.kr/frt/bbs/type001/commonSelectBoardArticle.do?bbsId=BBSMSTR_000000000016&nttId=108651) 에 규정.

#### Auth

GPKI 기관 인증서 (계층적 발급 — 관인 보유 행정기관 단위).

#### Rate / pagination

표준상 재시도·확인응답 규정 (ebMS).

#### Drop-in mirrorability: **3/5**

표준 자체는 공개. 단 실제 메시지 샘플은 기관 내부 문서.

#### Gaps

- ⚠️ OPAQUE: `gdoc.go.kr` 실 endpoint 및 가입 기관 리스트.
- ⚠️ OPAQUE: GPKI 인증서 발급 후 테스트 환경 URL.

#### Sources

- [전자문서유통 통합포털](https://gdoc.go.kr/)
- [정부 전자문서 유통 표준 고시 2024-27호](https://www.mois.go.kr/frt/bbs/type001/commonSelectBoardArticle.do?bbsId=BBSMSTR_000000000016&nttId=108651)
- [고시 2019-12호 (U-LEX 법률우주)](https://www.ulex.co.kr/%EB%B2%95%EB%A5%A0/2100000175981-2033361-%EC%A0%95%EB%B6%80)
- [행정기관간 문서유통 표준안 PDF](https://www.mois.go.kr/cmm/fms/FileDown.do?atchFileId=FILE_000000000049308&fileSn=0)

---

### 15. 행정정보공동이용 (PISC — share.go.kr)

행정안전부 운영. 민원 신청 시 **첨부서류를 대체**하는 백본 — "서류 없는 민원" 정책의 축. `submit` primitive 가 호출되면 그 배후에서 PISC 조회가 일어나 신청인 제출 부담을 줄인다.

#### Endpoints

- `https://www.share.go.kr/` — 메인 (정확히는 PISE 플랫폼).
- `https://www.share.go.kr/fa/fa010/newFa/piscIs/ruleGuide.jsp` — 지침 및 가이드.

#### Request contract

**표준 API** (GPKI 기반 암호/복호). 실시간 정보조회 API + 일괄 데이터 배포 (**ESB_AGENT v4.0**) 경로 이원화. 2026년 표준 자격확인서 이용신청 가이드 별도 PDF 배포.

#### Response contract

조회 결과 XML. 이용기관 간 암호화 채널.

#### Error format

⚠️ OPAQUE — 별도 가입자 매뉴얼.

#### Auth

GPKI 기관 인증서 + 표준보안 API 발급.

#### Rate / pagination

⚠️ OPAQUE.

#### Drop-in mirrorability: **3/5**

표준 문서 존재 → 아키텍처·envelope 미러 가능. 필드 레벨 XSD 는 가입 후.

#### Gaps

- ⚠️ OPAQUE: ESB_AGENT v4.0 설치 요구사항 상세.
- ⚠️ OPAQUE: 실시간 조회 API 의 개별 서비스 코드(주민등록등본·가족관계증명 등) 목록.
- ⚠️ OPAQUE: 공공 마이데이터 포털 ([adm.mydata.go.kr](https://adm.mydata.go.kr/images/guide02.pdf)) 와의 중복·보완 관계.

#### Sources

- [행정정보공동이용시스템](https://www.share.go.kr/)
- [PISC 지침·가이드](https://www.share.go.kr/fa/fa010/newFa/piscIs/ruleGuide.jsp)
- [행안부 행정정보 공유](https://www.mois.go.kr/frt/sub/a06/b02/digitalOpendataSharing/screen.do)
- [정부24 행정정보공동이용 소개](https://www.gov.kr/etc/AA090_g4c_admin.jsp?Mcode=12000)
- [GPKI 인증관리센터](https://www.gpki.go.kr/)
- [공공 마이데이터 업무포털 가이드 PDF](https://adm.mydata.go.kr/images/guide02.pdf)

---

## Cross-cutting patterns

여러 시스템을 관통하는 계약 패턴. KOSMOS mock adapter 의 공통 베이스 클래스 설계에 직접 재사용 가능하다.

### Pattern 1 — `data.go.kr` 공통 오픈 API 에러 코드 표 (조회 계열)

조회 Open API 는 거의 전부 이 표준을 따른다 (홈택스·고용24·NEIS·공공데이터포털·문화포털·KOSIS 등 동일). 쓰기 API 는 확정 아니지만 같은 계열 응답 구조를 재사용할 가능성이 높다.

| 코드 | 이름 | HTTP 유사 |
|---|---|---|
| 00 | NORMAL SERVICE | 200 |
| 01 | APPLICATION ERROR | 500 |
| 02 | DB_ERROR | 500 |
| 03 | NODATA ERROR | 404 |
| 04 | HTTP ERROR | 502 |
| 05 | SERVICETIMEOUT ERROR | 504 |
| 10 | INVALID REQUEST PARAMETER ERROR | 400 |
| 11 | MANDATORY REQUEST PARAMETERS ERROR | 400 |
| 12 | NO OPENAPI SERVICE ERROR | 404 |
| 20 | SERVICE ACCESS DENIED ERROR | 403 |
| 21 | TEMPORARILY DISABLE THE SERVICEKEY ERROR | 403 |
| 22 | LIMITED NUMBER OF SERVICE REQUESTS EXCEEDS ERROR | 429 |
| 30 | SERVICE KEY IS NOT REGISTERED ERROR | 401 |
| 31 | DEADLINE HAS EXPIRED ERROR | 401 |
| 32 | UNREGISTERED IP ERROR | 403 |
| 33 | UNSIGNED CALL ERROR | 401 |
| 99 | UNKNOWN ERROR | 500 |

응답 래퍼 shape (JSON / XML 양쪽):

```
response
 ├── header
 │    ├── resultCode  (string, 2-자리 숫자)
 │    └── resultMsg   (string, 메시지)
 └── body
      ├── items       (array or "items" wrapper)
      ├── numOfRows   (int)
      ├── pageNo      (int)
      └── totalCount  (int)
```

출처: [문화포털 Open API 가이드](https://www.culture.go.kr/industry/apiGuideA.do), [공공데이터 포털 이용가이드](https://www.data.go.kr/ugs/selectPublicDataUseGuideView.do), [세종통계 Open API 사용방법](https://www.sejong.go.kr/stat/content.do?key=1911210373402).

### Pattern 2 — `serviceKey` 기반 인증 + 쿼리 파라미터 공통

`data.go.kr` 계열은 공통적으로:

- `serviceKey` (URL-encoded, 공공데이터포털에서 발급).
- `pageNo` (기본 1).
- `numOfRows` (기본 10).
- `dataType` (`JSON` or `XML`, 일부 API 만 지원).

타 파라미터는 서비스별.

출처: [공공데이터 이용가이드](https://www.data.go.kr/ugs/selectPublicDataUseGuideView.do), [n8n 공공데이터 API 한글가이드](https://wikidocs.net/291697), [공공데이터포털 CLI GitHub](https://github.com/JeHwanYoo/data-go-kr).

### Pattern 3 — 이중 PKI 계층 (시민용 · 기관용)

- **시민용 PKI — 공동인증서 (구 공인인증서)**. 은행·KISA 체인. 홈택스·위택스·EDI·복지로·정부24·전자소송 모두 최종 권위 있는 수단.
- **기관용 PKI — GPKI (행정전자서명)**. `gpki.go.kr` 인증관리센터 발급. 관인 보유 행정기관 단위 계층. 행정정보공동이용·전자문서유통·기관간 연계 API 에 필수.
- **대체 수단** — 간편인증 12종 (민간 전자서명 사업자 기반), 금융인증서, 디지털원패스 (**2025-12-30 종료 예정 — 마이그레이션 필요**).

출처: [GPKI 인증관리센터](https://www.gpki.go.kr/), [GPKI 주요 업무](https://www.gpki.go.kr/jsp/centerIntro/mainBusiness/service/searchService_02.jsp), [GPKI 행정전자서명 발급 가이드 PDF](https://gpki.go.kr/upload/download/13_Gov_Renewal_Guide.pdf), [디지털원패스 FAQ](https://www.onepass.go.kr/faq), [간편인증 (행안부)](https://www.mois.go.kr/frt/sub/a06/b04/easyCertification/screen.do).

### Pattern 4 — XML 표준 우위 · JSON 보조

기관간 쓰기 계약은 대부분 XML (KEC, ebXML, 전자문서유통 ebMS, PISC 표준 API). Open API 조회 계열은 XML 응답이 **디폴트**, JSON 은 후발. 고용24 Open API 는 여전히 XML-only 명시. KOSMOS `submit` mock 의 직렬화 계층은 **XML 우선 + JSON 보조** 로 설계해야 실제 교체 시 cost 가 낮다.

출처: [워크넷 Open API 소개](https://m.work24.go.kr/cm/e/a/0110/selectOpenApiIntro.do), [KEC XML 표준 논문](https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART001582079).

### Pattern 5 — SOAP / WS-Security + ebXML messaging envelope

전자세금계산서(KEC), 전자문서유통(gdoc), PISC, 건보·연금 EDI 모두 **SOAP 1.1 + OASIS WS-Security** 를 envelope 로 쓴다. ebXML Messaging Services (ebMS 2.0/3.0) 가 신뢰전송 층을 담당 (재전송·확인응답·중복 검증). KOSMOS mock 은 이 계층을 **공통 `EbxmlEnvelope` 모델** 로 추출 가능:

- `SOAP-ENV:Envelope/Header/wsse:Security/{UsernameToken | BinarySecurityToken(X.509)}`.
- `eb:MessageHeader` with `From/To/CPAId/ConversationId/Service/Action/MessageData{MessageId, Timestamp}`.
- `eb:AckRequested`, `eb:Acknowledgment` 쌍.

출처: [OASIS WS-Security 관련 인용 (KEC 샘플 GitHub)](https://github.com/ruseel/kr-etax-sample), [정부 전자문서 유통 표준 고시](https://www.mois.go.kr/frt/bbs/type001/commonSelectBoardArticle.do?bbsId=BBSMSTR_000000000016&nttId=108651).

### Pattern 6 — 상태머신 enum (접수·처리·완료)

UI 관찰 및 민원처리 법령상 **공통 상태머신** 이 반복된다:

```
접수됨 → 처리중 → (보완요청 ↔ 재제출) → 완료 ∨ 반려 ∨ 취소
```

+ 시한 필드 (청원 90일, 민원 통상 14일, EDI 익월 15일, 전자소송 사건별). KOSMOS mock 의 공통 `SubmitResult` pydantic 모델은 이 enum + `deadline_at: datetime` + `receipt_id: str` + `attached_artifacts: list[FileRef]` 로 통일 가능.

출처: [청원24 처리 절차 (청원법 10조)](https://www.cheongwon.go.kr/), [정부24 민원처리법 안내](https://www.gov.kr/search/applyMw), [민원서비스 (공공데이터포털)](https://www.data.go.kr/dataset/15000896/openapi.do).

---

## Unknowns matrix

공개 문서로 **확정 불가** 한 항목을 시스템 × 계약 차원 교차표로 요약. KOSMOS 가 기관 협업 진입 시 질의해야 할 우선순위다.

| 시스템 | Endpoint URL | Request XSD / JSON schema | Response schema | Error code 표 | Auth 프로토콜 | Rate limit | Idempotency |
|---|---|---|---|---|---|---|---|
| 정부24 민원신청 | ⚠️ | ⚠️ | ⚠️ | ⚠️ | OK (간편/공동인증서) | ⚠️ | ⚠️ |
| 홈택스 전자신고 | ⚠️ | ⚠️ | ⚠️ | ⚠️ | OK (공동인증서) | ⚠️ | ⚠️ |
| 위택스 | ⚠️ | ⚠️ | ⚠️ | ⚠️ | OK | ⚠️ | ⚠️ |
| NHIS EDI | OK (portal URL) | ⚠️ (각 신고서 body) | Partial (접수증 개념) | ⚠️ | OK (공동인증서) | ⚠️ | ⚠️ |
| NPS EDI | OK | Partial (가이드북 PDF) | Partial | ⚠️ | OK | ⚠️ | ⚠️ |
| 복지로 | Partial | ⚠️ | ⚠️ | ⚠️ | OK | ⚠️ | ⚠️ |
| NEIS 대국민 | ⚠️ (조회만 OK) | ⚠️ | ⚠️ | Partial (조회 표준) | OK | ⚠️ | ⚠️ |
| 고용24 submit | ⚠️ | ⚠️ | ⚠️ | ⚠️ | OK | ⚠️ | ⚠️ |
| 전자소송 서류제출 | ⚠️ (연계 API 가입) | ⚠️ | Partial (접수증) | ⚠️ | OK | ⚠️ | ⚠️ |
| 국민동의청원 | OK (웹) | ⚠️ | ⚠️ | ⚠️ | Partial | ⚠️ | ⚠️ |
| 청원24 | OK (웹) + 결과 GET | ⚠️ (접수) | OK (결과 스냅샷) | ⚠️ | OK | ⚠️ | ⚠️ |
| 전자세금계산서 | ⚠️ (운영 URL) | **OK (KEC XML v3.0 표준)** | Partial | Partial (법령 규정) | **OK** (세금용 공동인증서) | ⚠️ | **OK** (공급자·작성일·승인번호) |
| 지자체 전자민원 | OK | ⚠️ | ⚠️ | ⚠️ | OK | ⚠️ | ⚠️ |
| 전자문서 유통 | OK (gdoc) | Partial (고시 본문) | Partial | Partial | OK (GPKI) | Partial (ebMS 재시도) | OK (ebMS MessageId) |
| PISC (행정정보공동이용) | OK (share.go.kr) | Partial (표준 API 개념) | Partial | ⚠️ | OK (GPKI) | ⚠️ | ⚠️ |

범례: OK = 공개 문서로 확정 / Partial = 표준/개념 공개, 개별 상세 비공개 / ⚠️ = OPAQUE.

---

## 기관 협업 priorities (gap 기반)

위 unknowns matrix 에서 ⚠️ 가 가장 많은 순으로 드라이브할 때:

1. **홈택스 · 위택스** (전자신고 파일 포맷, 납부 API) — 국세청·행안부 지방세정책과 접촉.
2. **정부24 어디서나연계시스템** — 행안부 디지털정부국 (민원24 담당).
3. **전자소송** — 법원행정처 `publicapi@scourt.go.kr` (가입 문의).
4. **전자세금계산서 운영 URL + 전체 error 표** — 국세청 전자세원과.
5. **EDI 메시지 XSD (NHIS/NPS)** — 두 공단 정보화실.
6. **PISC 실시간 조회 API 서비스 코드 목록** — 행안부 디지털안전정책과.

각 항목에 대해 **shape-compatible mock 부터 먼저 구현** 하고, 자격증명 확보 후 fixture-replay 에서 live-replay 로 전환하는 drop-in 경로를 유지한다.

---

## References (전 인용 URL 집계)

### 공식 정부·기관 포털
1. [정부24](https://www.gov.kr/)
2. [정부24 Open API 안내](https://www.gov.kr/openapi)
3. [정부24 Open API 신청](https://www.gov.kr/openapi/info)
4. [정부24 민원신청](https://www.gov.kr/search/applyMw)
5. [정부24 어디서나연계시스템 도움말](https://www.gov.kr/etc/AA090_info_11_08.jsp)
6. [정부24 행정정보공동이용 소개](https://www.gov.kr/etc/AA090_g4c_admin.jsp?Mcode=12000)
7. [정부24 국민연금 자격취득·상실](https://www.gov.kr/mw/AA020InfoCappView.do?HighCtgCD=A05007&CappBizCD=14600000296)
8. [정부24 위택스 안내](https://www.gov.kr/portal/service/serviceInfo/PTR000052095)
9. [정부24 건강보험 EDI 안내](https://www.gov.kr/portal/service/serviceInfo/PTR000050381)
10. [정부24 나이스플러스 안내](https://www.gov.kr/portal/service/serviceInfo/PTR000050144)
11. [홈택스 메인](https://www.hometax.go.kr/)
12. [홈택스 종합소득세 신고](https://hometax.go.kr/websquare/websquare.html?w2xPath=/ui/pp/index_pp.xml&tmIdx=41&tm2lIdx=4103000000&tm3lIdx=4103020000)
13. [홈택스 자료실](https://hometax.go.kr/websquare/websquare.html?w2xPath=%2Fui%2Fpp%2Findex_pp.xml&tmIdx=16&tm2lIdx=1602000000&tm3lIdx=)
14. [손택스 부가세 신고도움](https://mob.tbht.hometax.go.kr/jsonAction.do?actionId=UTBRNAA130F001)
15. [손택스 전자세금계산서 자료신청](https://mob.tbet.hometax.go.kr/jsonAction.do?actionId=UTBETFAA01F001)
16. [홈택스 간편인증 매뉴얼 PDF](https://hometax.speedycdn.net/dn_dir/webdown/%EA%B0%84%ED%8E%B8%EC%9D%B8%EC%A6%9D%EB%A1%9C%EA%B7%B8%EC%9D%B8%EC%9E%90%EC%84%B8%ED%9E%88%EB%B3%B4%EA%B8%B0.pdf)
17. [국세청 메인](https://nts.go.kr/)
18. [국세청 OpenAPI 변경 공지](https://www.data.go.kr/bbs/ntc/selectNotice.do?originId=NOTICE_0000000003116)
19. [위택스](https://www.wetax.go.kr/main.do)
20. [위택스 개인지방소득세](https://www.wetax.go.kr/etr/incmMain.do)
21. [위택스 간소화 페이지](https://www.wetax.go.kr/static/sim/SimpleNc2.html)
22. [국민건강보험 EDI](https://edi.nhis.or.kr/)
23. [NHIS EDI 서비스 가이드](https://edi.nhis.or.kr/homeapp/wep/o/serviceGuide.do)
24. [NHIS EDI 공동인증서 등록](https://edi.nhis.or.kr/homeapp/wep/o/certificateReg.do)
25. [사회보험 통합징수 포털](https://si4n.nhis.or.kr/)
26. [국민건강보험공단](https://www.nhis.or.kr/)
27. [국민연금 EDI](https://edi.nps.or.kr/)
28. [국민연금 EDI 가이드북 2026 PDF](https://edi.nps.or.kr/cm/main/guide/edi_guide.pdf)
29. [국민연금 EDI 사업장 실무안내 PDF](https://edi.nps.or.kr/cm/main/guide/edi_workguide_new.pdf)
30. [국민연금공단 웹EDI 업무대행 처리기준](https://www.nps.or.kr/pnsinfo/databbs/getOHAF0272M1Detail.do?menuId=MN24001000&pstId=ET202200000000026998&hmpgCd=&hmpgBbsCd=BS20240094&sortSe=FR&pageIndex=1&searchText=&searchGbu=)
31. [복지로](http://www.bokjiro.go.kr/)
32. [복지로 온라인신청 팝업](https://online.bokjiro.go.kr/apl/popup/selectAplApplBfAttnItemInfP.do)
33. [복지로 공식 블로그](https://blog.bokjiro.go.kr/1345)
34. [보건복지부 온라인 신청 확대 보도](https://www.mohw.go.kr/board.es?mid=a10503000000&bid=0027&tag=&act=view&list_no=376773&cg_code=)
35. [한국사회보장정보원 대민포털](https://www.ssis.or.kr/lay1/S1T756C779/contents.do)
36. [NEIS 대국민서비스](https://www.neis.go.kr/)
37. [NEIS 교육정보 개방 포털](https://open.neis.go.kr/)
38. [NEIS Open API 소개](https://open.neis.go.kr/portal/guide/apiIntroPage.do)
39. [NEIS 개발자 가이드](https://open.neis.go.kr/portal/guide/apiGuidePage.do)
40. [고용24 메인](https://www.work24.go.kr/)
41. [고용24 Open API 소개](https://m.work24.go.kr/cm/e/a/0110/selectOpenApiIntro.do)
42. [고용24 고용행정통계 Open API 가이드](https://eis.work24.go.kr/eisps/opiv/selectOpivList.do)
43. [워크넷 LOD Open API 가이드](https://lod.work.go.kr/openAPI_guide.do)
44. [워크넷 이력서 관리 모바일](https://m.work24.go.kr/wk/a/b/2100/resumeMngMain.do)
45. [전자소송포털](https://ecfs.scourt.go.kr/)
46. [전자소송 민사 서류제출](https://ecfs.scourt.go.kr/psp/index.on?m=PSPA13M01)
47. [전자소송 지급명령](https://ecfs.scourt.go.kr/psp/index.on?m=PSPA13M03)
48. [전자소송 양식모음](https://ecfs.scourt.go.kr/psp/index.on?m=PSP720M24)
49. [사법정보공유포털 이용안내](https://openapi.scourt.go.kr/kgso202m01.do)
50. [사법정보공유포털 연계 API](https://openapi.scourt.go.kr/kgso301m01.do)
51. [국회전자청원](https://petitions.assembly.go.kr/)
52. [청원24](https://www.cheongwon.go.kr/)
53. [청원24 오픈 보도자료](https://www.korea.kr/news/policyNewsView.do?newsId=148908954)
54. [행안부 청원24 소개](https://www.mois.go.kr/frt/bbs/type002/commonSelectBoardArticle.do?bbsId=BBSMSTR_000000000205&nttId=97036)
55. [eSero (전자세금계산서 무료 포털) — 본문 내 `www.esero.go.kr` 인용 (Storecove 규제 요약 참조)](https://www.storecove.com/blog/en/e-invoicing-in-south-korea-regulations/)
56. [서울시 온라인 민원](https://minwon.seoul.go.kr/)
57. [서울 응답소](https://eungdapso.seoul.go.kr/main.do)
58. [서울 응답소 건의·질의 민원](https://eungdapso.seoul.go.kr/req/rectify/rectify.do)
59. [서울 열린데이터광장 Open API 가이드](https://data.seoul.go.kr/together/guide/useGuide.do)
60. [경기도 민원 신청 안내](https://www.gg.go.kr/contents/contents.do?ciIdx=1230&menuId=2994)
61. [전자문서유통 통합포털](https://gdoc.go.kr/)
62. [행정정보공동이용시스템](https://www.share.go.kr/)
63. [PISC 지침 및 가이드](https://www.share.go.kr/fa/fa010/newFa/piscIs/ruleGuide.jsp)
64. [행안부 행정정보 공유](https://www.mois.go.kr/frt/sub/a06/b02/digitalOpendataSharing/screen.do)
65. [GPKI 인증관리센터](https://www.gpki.go.kr/)
66. [GPKI 인증서 발급](https://www.gpki.go.kr/jsp/certInfo/step/issue/cert_info.jsp)
67. [GPKI 인증서 소개](https://gpki.go.kr/jsp/certInfo/certIntro/eSignature/searchEsignature.jsp)
68. [GPKI 주요 업무 · 활용 서비스](https://www.gpki.go.kr/jsp/centerIntro/mainBusiness/service/searchService_02.jsp)
69. [GPKI 행정전자서명 발급 가이드 PDF](https://gpki.go.kr/upload/download/13_Gov_Renewal_Guide.pdf)
70. [디지털원패스 메인](https://www.onepass.go.kr/)
71. [디지털원패스 소개](https://www.onepass.go.kr/about)
72. [디지털원패스 연계방법](https://www.onepass.go.kr/cnguide)
73. [디지털원패스 이용가능 서비스](https://www.onepass.go.kr/siteList)
74. [디지털원패스 FAQ (종료 공지)](https://www.onepass.go.kr/faq)
75. [행안부 통합인증 (Any-ID)](https://www.mois.go.kr/frt/sub/a06/b04/easyCertification/screen.do)
76. [공공 마이데이터 업무포털 가이드 PDF](https://adm.mydata.go.kr/images/guide02.pdf)

### 법령·고시
77. [법령: 전자(세금)계산서 표준 인증 고시](https://www.law.go.kr/LSW/admRulLsInfoP.do?admRulSeq=2100000229172)
78. [행안부 고시 2024-27호 정부 전자문서 유통 표준](https://www.mois.go.kr/frt/bbs/type001/commonSelectBoardArticle.do?bbsId=BBSMSTR_000000000016&nttId=108651)
79. [행안부 고시 2019-12호 (U-LEX 사본)](https://www.ulex.co.kr/%EB%B2%95%EB%A5%A0/2100000175981-2033361-%EC%A0%95%EB%B6%80)
80. [행정기관간 문서유통 표준안 PDF](https://www.mois.go.kr/cmm/fms/FileDown.do?atchFileId=FILE_000000000049308&fileSn=0)
81. [모바일 전자정부 서비스 관리 지침 PDF](https://www.mois.go.kr/cmm/fms/FileDown.do?atchFileId=FILE_000000000051594&fileSn=0)
82. [전자정부서비스 호환성 준수지침 (국가법령정보센터)](https://www.law.go.kr/admRulLsInfoP.do?admRulSeq=2100000108833)

### 공공데이터포털 (data.go.kr) 카탈로그
83. [공공데이터포털 메인](https://www.data.go.kr/)
84. [공공데이터 이용가이드](https://www.data.go.kr/ugs/selectPublicDataUseGuideView.do)
85. [행정안전부 공공서비스 정보 API](https://www.data.go.kr/data/15113968/openapi.do)
86. [민원조회서비스](https://www.data.go.kr/dataset/15000896/openapi.do)
87. [행정안전부 공개청원 내용 및 처리결과](https://www.data.go.kr/data/15145171/fileData.do)
88. [한국사회보장정보원 자원정보서비스 현황](https://www.data.go.kr/data/15001839/openapi.do)
89. [NEIS 학교기본정보](https://www.data.go.kr/data/15122275/openapi.do)
90. [NEIS 학사일정](https://www.data.go.kr/data/15137088/openapi.do?recommendDataYn=Y)
91. [워크넷 채용정보](https://www.data.go.kr/data/3038225/openapi.do)
92. [워크넷 직무데이터사전](https://www.data.go.kr/data/15088880/openapi.do)
93. [국세청 전자(세금)계산서 제도의 이해 PDF](https://www.data.go.kr/data/15050750/fileData.do)
94. [공공데이터 개방 포털 영문 예시](https://www.data.go.kr/en/data/15000442/openapi.do)
95. [공공데이터포털 QnA](https://www.data.go.kr/bbs/qna/selectQnaList.do)
96. [공공데이터포털 개발자 네트워크](https://www.data.go.kr/bbs/dnb/selectDeveloperNetworkListView.do)

### 학술·특허·2차 자료
97. [XML 표준 전자세금계산서의 개발과 유통 (KCI 논문)](https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART001582079)
98. [KR101053097B1 전자세금계산서 발급 장치/방법 특허](https://patents.google.com/patent/KR101053097B1/ko)
99. [KR101439809B1 건강보험 웹EDI 시스템 특허](https://patents.google.com/patent/KR101439809B1/ko)
100. [국회 전자청원제도 학술논문 (KCI)](https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART002730562)
101. [국회 국민동의청원 운영현황 (KCI)](https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART003236892)
102. [국민동의청원 나무위키](https://namu.wiki/w/%EA%B5%AD%EB%AF%BC%EB%8F%99%EC%9D%98%EC%B2%AD%EC%9B%90)
103. [정부24 나무위키](https://namu.wiki/w/%EC%A0%95%EB%B6%8024)
104. [eGovFrame Wiki — 외부기관 연계신청](https://www.egovframe.go.kr/wiki/doku.php?id=egovframework:%EC%99%B8%EB%B6%80%EA%B8%B0%EA%B4%80_%EC%97%B0%EA%B3%84%EC%8B%A0%EC%B2%AD)
105. [eGovFrame Wiki — GPKI 인증서 로그인](https://www.egovframe.go.kr/wiki/doku.php?id=egovframework:gpki_%EC%9D%B8%EC%A6%9D%EC%84%9C_%EB%A1%9C%EA%B7%B8%EC%9D%B8)
106. [eGovFrame Wiki — 디지털원패스 컴포넌트](https://www.egovframe.go.kr/wiki/doku.php?id=egovframework:com:v4.0:uat:%EB%94%94%EC%A7%80%ED%84%B8%EC%9B%90%ED%8C%A8%EC%8A%A4)

### 2차 해설·가이드 (Mirrorability 검증용)
107. [n8n 공공데이터 API 한글 가이드](https://wikidocs.net/291697)
108. [공공데이터포털 CLI (JeHwanYoo)](https://github.com/JeHwanYoo/data-go-kr)
109. [Public APIs for Korean Services (yybmion)](https://github.com/yybmion/public-apis-4Kr)
110. [neis-api Node.js 라이브러리](https://github.com/my-school-info/neis-api)
111. [ruseel/kr-etax-sample — 전자세금계산서 검증 코드](https://github.com/ruseel/kr-etax-sample)
112. [ruseel/kr-etax-sample — SubmitWithSOAP.java (SOAP 구조 인용)](https://github.com/ruseel/kr-etax-sample/blob/master/src/main/java/com/barostudio/SubmitWithSOAP.java)
113. [문화포털 Open API 가이드 (공통 에러 코드 인용)](https://www.culture.go.kr/industry/apiGuideA.do)
114. [세종통계포털 Open API 사용방법](https://www.sejong.go.kr/stat/content.do?key=1911210373402)
115. [KOSIS 공유서비스](https://kosis.kr/openapi/community/community_02Detail.jsp?p_id=3)
116. [보건의료빅데이터개방시스템 Open API 이용안내](https://opendata.hira.or.kr/op/opc/selectOpenApiInfoView.do)
117. [k-water 공공데이터 개방포털 가이드](https://opendata.kwater.or.kr/open/data/guide/view.do)
118. [한국산업인력공단 Open API](https://openapi.hrdkorea.or.kr/main)
119. [Storecove e-invoicing in South Korea (영문)](https://www.storecove.com/blog/en/e-invoicing-in-south-korea-regulations/)
120. [ClearTax e-invoicing in South Korea (영문)](https://www.cleartax.com/kr/e-invoicing-south-korea)
121. [KT-NET 전자세금계산서 FAQ](https://webcs.ktnet.com/introduce/FaqView.do?num=240)
122. [Bill36524 전자세금용 공인인증서](https://www.bill36524.com/html/certificate.html)
123. [국세청 공인인증센터](https://hometax.go.kr/websquare/websquare.html?w2xPath=%2Fui%2Fpp%2Findex_pp.xml&tmIdx=25)
124. [큰마음 세무회계 전자세금용 공인인증서 가이드](https://bigmindtax.com/bigmindtax-customer-guide/issue-public-certificate/)
125. [WEHAGO T 전자세금계산서 발행](https://wehagothelp.zendesk.com/hc/ko/articles/360000299561--%EC%A0%84%EC%9E%90%EC%84%B8%EA%B8%88%EA%B3%84%EC%82%B0%EC%84%9C-%EC%A0%84%EC%9E%90%EC%84%B8%EA%B8%88%EA%B3%84%EC%82%B0%EC%84%9C-%EB%B0%9C%ED%96%89)
126. [Smartbill 전자세금계산서 FAQ](http://www.smartbill.co.kr/Cs/faq/dtl.aspx?flag=l&no=710)

### 공지 · 공개자료
127. [250930 공공데이터포털 오픈API 대체서비스 안내 PDF](https://www.scribd.com/document/926853673/250930-%EA%B3%B5%EA%B3%B5%EB%8D%B0%EC%9D%B4%ED%84%B0%ED%8F%AC%ED%84%B8-%EC%98%A4%ED%94%88API-%EB%8C%80%EC%B2%B4%EC%84%9C%EB%B9%84%EC%8A%A4-%EC%95%88%EB%82%B4-125%EC%A2%85-%EA%B3%B5%EC%A7%80%EC%9A%A9)
128. [행정안전부 공공데이터 제공신청](https://www.mois.go.kr/frt/sub/a02/openInfoList/screen.do)
129. [국가기록원 OpenAPI 사용안내](https://www.archives.go.kr/next/newsearch/openAPI01.do)
130. [국가송무정보시스템 GPKI 인증 안내](https://www.songmu.go.kr/uat/uia/egovGpkiIssu.do)

---

> **End of survey.** 본 문서는 공개 문서만을 근거로 한다. `⚠️ OPAQUE` 로 표기된 gap 은 전부 기관 협업/가입 진행 후 확인해야 하며, mock adapter 구현 단계에서는 envelope·상태머신·에러 코드 enum 만을 미러하고, 불확실한 body 필드는 `extension_xml: str` 또는 `payload: dict[str, Any]` 슬롯 (프로젝트 규칙 `Any` 금지로 인해 `dict[str, JsonValue]` 등 명시적 타입)으로 비워 둔다. 자격증명·실 URL 확보 시 `client` 레이어만 교체하면 harness 는 그대로 재사용된다는 drop-in 원칙을 유지한다.
