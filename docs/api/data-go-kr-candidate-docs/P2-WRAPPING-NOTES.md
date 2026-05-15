# data.go.kr P2 Wrapping Notes

This is an intake artifact for issue #2797. It records application status,
captured documents, endpoint evidence, and wrapping blockers for the first-wave
P2 candidates. It is not an implementation spec and does not authorize code
changes by itself.

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
- External primary sources observed through Computer Use on 2026-05-16:
  CareerNet Open API Center and KDCA National Health Information Portal.

## Application Status

| data.go.kr ID | Candidate | Source type | Application status | Wrapping status |
|---|---|---|---|---|
| `15056641` | `교육부_커리어넷 직업정보` | `LINK`, external CareerNet key | Submitted through the CareerNet Open API Center on 2026-05-16 after the user completed login. Completion page said the request was submitted and the status page shows `대기`. No API key was visible before approval. | `find`; external CareerNet approval/key follow-up. Endpoint docs captured. |
| `15087442` | `질병관리청_국가건강정보포털` | `LINK`, external KDCA/OnePass flow | Submitted/registered through the KDCA portal on 2026-05-16 after the user completed login. Browser alert confirmed `정상적으로 등록되었습니다.` Approval/key issuance status was not shown on the submission screen. | `find`; external KDCA credential/approval follow-up plus endpoint-version mismatch to validate. |
| `15149906` | `법무부_장단기체류외국인 월별 체류외국인 현황 카운터 조회서비스` | data.go.kr REST | Submitted and approved in My Page. Account: development. Application date: 2026-05-16. Expiry: 2028-05-16. | `find` or `check`; live data.go.kr service key path. |
| `15074634` | `과학기술정보통신부_사업공고` | data.go.kr REST | Submitted and approved in My Page. Account: development. Application date: 2026-05-16. Expiry: 2028-05-16. | `find`; live data.go.kr service key path. |

## Reusable Korean Purpose Text

Use this when an external application form asks for a concise purpose:

```text
UMMAYA 프로젝트의 공공데이터 기반 한국 행정·공공서비스 API 래핑 모듈 검증 및 개발 목적입니다. 신청 API의 요청·응답 구조를 확인하고, 사용자 질의에 따라 공식 공개 데이터만 조회·요약하는 프로토타입 도구를 구현하기 위한 개발·테스트 용도로 활용합니다. 원본 데이터를 변경하거나 재판매하지 않으며, 활용 시 제공기관과 출처를 명시하겠습니다.
```

## Captured Artifacts

- `15056641/careernet-openapi-jobcenter.html`
- `15056641/submission-2026-05-16.md`
- `15056641/probes/careernet-jobinfo-no-key.headers.txt`
- `15056641/probes/careernet-jobinfo-no-key.body.txt`
- `15087442/KDCA17-HEALTH-API01-v1.2(20231130).hwp`
- `15087442/KDCA17-HEALTH-API01-v1.2(20231130).hwp.txt`
- `15087442/KDCA17-HEALTH-API01-v1.2(20231130).hwp5html.txt`
- `15087442/hwp5html/index.xhtml`
- `15087442/kdca-healthinfo-openapi-guidance.html`
- `15087442/kdca-healthinfo-openapi-apply.html`
- `15087442/submission-2026-05-16.md`
- `15087442/probes/kdca-healthinfo-hwp-endpoint-no-token.headers.txt`
- `15087442/probes/kdca-healthinfo-hwp-endpoint-no-token.body.txt`
- `15087442/probes/kdca-healthinfo-detail-no-token.headers.txt`
- `15087442/probes/kdca-healthinfo-detail-no-token.body.txt`
- `15087442/probes/kdca-healthsearch-new-no-key.headers.txt`
- `15087442/probes/kdca-healthsearch-new-no-key.body.txt`
- `15149906/data-go-kr-inline-swagger.json`
- `15074634/OpenApi활용가이드_과학기술정보통신부_사업공고_v1.0.docx`
- `15074634/OpenApi활용가이드_과학기술정보통신부_사업공고_v1.0.docx.txt`

`data-go-kr-catalog.json` files in these folders are URL inventory stubs, not
full API contracts.

## External-Key LINK Candidates

### `15056641` CareerNet Job Information

Official source pages:

- data.go.kr: `https://www.data.go.kr/data/15056641/openapi.do`
- CareerNet: `https://www.career.go.kr/cnet/front/openapi/openApiJobCenter.do`
- CareerNet application: `https://www.career.go.kr/cnet/front/openapi/openApiApply01Center.do`

Computer Use result:

- The job-information document page is public and was captured.
- The application page says login is required before OpenAPI key issuance.
- Career OnePass login requires credentials plus CAPTCHA. SNS Google login
  opened a Google account chooser where the known account was logged out.
- After the user completed login, the OpenAPI key application form was submitted.
  The values were `서비스명=UMMAYA`,
  `서비스 URL 주소=https://github.com/umyunsang/UMMAYA`, service types
  `PC웹`, `모바일 웹`, and `모바일 앱(APP)`, usage reasons
  `서비스 연계를 통한 진로정보 제공` and `데이터 분석 및 연구`, usage API
  `직업정보`, and API 연계 주기 `실시간`.
- The submission confirmation page said the application result will be sent by
  email after administrator review. The application-status page shows
  `인증현황=대기`; no API key was visible at the time of capture.
- The page warns that this job-information API is provided only through
  2023-08 after the job-information reorganization. Treat this as a deprecation
  risk during later adapter classification.

Request contract:

- Method: GET
- Endpoint family:
  - `https://www.career.go.kr/cnet/openapi/getOpenApi.xml`
  - `https://www.career.go.kr/cnet/openapi/getOpenApi.json`
  - `https://www.career.go.kr/cnet/openapi/getOpenApi` with `contentType`
- Auth: query `apiKey`, issued by CareerNet after OpenAPI registration.
- Required params: `apiKey`, `svcType=api`, `svcCode`, `gubun`.
- `svcCode`: `JOB` list, `JOB_VIEW` detail, `JOB_TYPE` classification.
- `gubun`: `job_dic_list` CareerNet job dictionary classification,
  `job_apti_list` aptitude-type classification.
- Optional list params: `contentType`, `pgubn`, `category`, `thisPage`,
  `perPage`, `searchJobNm`.
- Required detail param: `jobdicSeq` when `svcCode=JOB_VIEW`.

Response fields visible in the official page include `content`, `totalCount`,
`job`, `jobdicSeq`, `profession`, `similarJob`, `summary`,
`equalemployment`, `possibility`, `prospect`, `salery`, `job_cod`,
`job_ctg_code`, and `aptd_type_code`. Detail response fields and code tables are
captured in `careernet-openapi-jobcenter.html`.

No-key probe:

- `GET /cnet/openapi/getOpenApi.json?...` returned HTTP 200 JSON:
  `{"result":{"content":[{"code":"-2","message":"인증키 없습니다."}]}}`.
- This proves the public endpoint shape and the external-key failure mode.

### `15087442` KDCA National Health Information Portal

Official source pages:

- data.go.kr: `https://www.data.go.kr/data/15087442/openapi.do`
- KDCA guidance:
  `https://health.kdca.go.kr/healthinfo/biz/health/portalUseGuidance/hlthinsReqst/hlthinsReqstMth.do?index=3`
- KDCA application:
  `https://health.kdca.go.kr/healthinfo/biz/health/portalUseGuidance/openApiReqst/openApiReqstRegist.do`

Computer Use result:

- The KDCA guidance tab documents a three-step content-provision flow and a
  separate OpenAPI registration screen.
- The actual registration form was reached. It requires privacy consent,
  content-use consent, an API service selection, and then a logged-in session.
- Selecting `Next` without a session produced the browser alert
  `로그인이 필요합니다.`.
- The Digital OnePass login route redirected to `saml.onepass.go.kr/login/check`
  and Chrome returned `ERR_CONNECTION_REFUSED`.
- After the user completed login, the form advanced to the application details
  step. The submitted values were `사용 목적=웹사이트 개발`,
  `사용 URL=https://github.com/umyunsang/UMMAYA`, `콘텐츠=고혈압`, and the
  reusable Korean UMMAYA purpose text above.
- Submission produced the browser alert `정상적으로 등록되었습니다.`. The page
  returned to the first OpenAPI request step after acknowledgement. No approval
  status or issued API token was visible on that screen.

HWP guide contract:

- Service ID: `KDCA-HEALTH-HealthInfo`
- Service name: `국가건강정보포털(건강정보 관련) 정보`
- Auth: service key/TOKEN issued by the KDCA portal when health information is
  requested.
- Interface: REST, XML, SSL.
- Operations:
  - `list`: health-information list lookup.
  - `view`: health-information detail lookup.
- List callback URL:
  `https://api.kdca.go.kr/api/provide/healthInfo?TOKEN=[KEY NO]`
- Detail callback URL:
  `https://api.kdca.go.kr/api/provide/healthInfo?TOKEN=[KEYNO]&cntntsSn=[cntntsSn]`
- Required request params:
  - `TOKEN`: service key.
  - `cntntsSn`: content serial number, required for detail lookup.
- Response fields include `CODE`, `MESSAGE`, `LCLASSN`, `NUMOFROWS`,
  `CNTNTSCLSN`, `CNTNTS_CL_NM`, and detail fields such as `CNTNTSSN`,
  `CNTNTSCLSN`, `CNTNTSCLNM`, `CNTNTSCLCN`.

Current website form contract:

- `apiSvcCode=1` is labeled `건강정보검색`.
- The form option includes `refrn1Cn=/healthinfo/openapi/svcNew/healthSearchListApi.do`.
- Step 2, visible in source after login gating, requires user type, purpose,
  optional URL, usage text, and content selection. The source submits to
  `/healthinfo/biz/health/portalUseGuidance/openApiReqst/openApiReqstRegistNew.do`
  or `/openApiReqstRegistAjax.do` depending on the flow.

No-key probes:

- `https://api.kdca.go.kr/api/provide/healthInfo` returned HTTP 201 XML with
  `CODE=S001` and a health-info content body even without `TOKEN`.
- `https://api.kdca.go.kr/api/provide/healthInfo?cntntsSn=5684` returned
  HTTP 201 XML with the `직장탈출증` detail body even without `TOKEN`.
- `https://health.kdca.go.kr/healthinfo/openapi/svcNew/healthSearchListApi.do`
  returned HTTP 200 HTML error text: `필수요청 파라메터가 없습니다.`

Wrapping implication: the HWP contract and the current website registration
option do not fully match. Before implementation, validate which endpoint is the
supported post-approval endpoint and whether the older `api.kdca.go.kr` endpoint
intentionally allows no-token access.

## data.go.kr REST Candidates

### `15149906` MOJ Stay-Person Counter

Official source page: `https://www.data.go.kr/data/15149906/openapi.do`

- Type: REST
- Format: XML
- Approval: development account approved on 2026-05-16.
- Host: `apis.data.go.kr/1270000/stay_person_counter`
- Path: `/getstaypersoncounter`
- Method: GET
- Auth: query `serviceKey`
- Response format: XML
- Full captured contract: `15149906/data-go-kr-inline-swagger.json`

Request params:

| Param | Required | Meaning |
|---|---:|---|
| `serviceKey` | yes | data.go.kr service key |
| `pageNo` | yes | page number |
| `numOfRows` | yes | rows per page |
| `startYm` | no | period-search start month, `YYYYMM` |
| `endYm` | no | period-search end month, `YYYYMM` |
| `searchYm` | no | single-search month, `YYYYMM` |
| `eNum` | no | category filter: `1` short-term stay, `2` long-term residence, `3` long-term registration |

Important validation rule from Swagger responses: do not send both
single-search and period-search params together, or the API can return a date
parameter duplicate error.

Response fields include `resultCode`, `resultMsg`, `stayYear`, `stayMonth`,
`division`, `staycount`, `totalCount`, `pageNo`, and `numOfRows`.

### `15074634` MSIT Business Announcements

Official source page: `https://www.data.go.kr/data/15074634/openapi.do`

- Type: REST
- Format: XML and JSON.
- Approval: development account approved on 2026-05-16.
- Service URL in guide: `http://apis.data.go.kr/1721000/msitannouncementinfo`
- WADL: `http://apis.data.go.kr/1721000/msitannouncementinfo?_wadl&type=xml`
- Callback/path:
  `http://apis.data.go.kr/1721000/msitannouncementinfo/businessAnnouncMentList`
- Method: GET
- Auth: query `serviceKey`
- Full captured guide:
  `15074634/OpenApi활용가이드_과학기술정보통신부_사업공고_v1.0.docx`

Request params:

| Param | Required | Meaning |
|---|---:|---|
| `serviceKey` | yes | data.go.kr service key |
| `numOfRows` | yes | rows per page |
| `pageNo` | yes | page number |
| `returnType` | no | `xml` default, `json` allowed |

Response fields include `resultCode`, `resultMsg`, `numOfRows`, `pageNo`,
`totalCount`, `subject`, `viewUrl`, `deptName`, `managerName`, `managerTel`,
`pressDt`, `fileName`, and `fileUrl`.

## Spec Kit Follow-Up

Recommended first implementation order:

1. `15074634` as `find`: data.go.kr credential exists and the guide is complete.
2. `15149906` as `find` or `check`: data.go.kr credential exists and Swagger is complete; enforce the single-vs-period date rule.
3. `15056641` as `find`: only after CareerNet key issuance or as a Mock shape from the captured page if the API is deprecated.
4. `15087442` as `find`: only after deciding whether to wrap the HWP `api.kdca.go.kr` contract, the newer `healthSearchListApi.do` contract, or both as separate compatibility layers.

No live credentialed API calls were made in this intake pass. The saved probes
are no-key endpoint checks only and must not be copied into CI as live tests.
