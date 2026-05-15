---
title: "Agentic RAG And Query Engine"
description: "검색, 추론, 도구 호출, 권한, stop reason이 한 턴에서 협력하는 방식입니다."
llm_index: true
audience:
  - public_sector_evaluator
  - maintainer
  - llm_agent
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - docs/vision.md
  - docs/requirements/ummaya-migration-tree.md
  - docs/api/README.md
  - eval/scenarios/national_ax_citizen_requests_v1.yaml
---

UMMAYA는 문서 검색만 하는 RAG가 아니라 행동을 위한 검색을 사용합니다. 쿼리 엔진은 시민 요청을 받고, adapter 후보를 찾고, K-EXAONE이 primitive를 선택하게 하고, 호출을 검증하고, 권한을 확인하고, Live/Mock/Handoff 결과를 생성합니다.

이 페이지는 UMMAYA가 실제로 agentic한지, 아니면 검색 결과를 설명하는 chatbot인지 확인하려는 평가자와 maintainer를 위한 문서입니다. 답은 turn structure에 있습니다. Retrieval은 action surface를 좁히고, reasoning은 다음 bounded action을 고르고, tool execution은 evidence를 만들고, stop reason은 계속 진행할 수 있는지 결정합니다.

<figure class="architecture-diagram">
  <img src="/architecture/c4/structurizr-03-query-engine-core.svg" alt="최소 C4 component diagram: Context, Retrieve, Primitives, Validate, Gate, Dispatch, Stop." />
  <figcaption>Query engine view: context, retrieval, primitive choice, validation, permission, dispatch, stop은 서로 다른 control step입니다.</figcaption>
</figure>

## 한 턴의 상세 흐름

```text
1. 사용자가 public-service outcome을 질문합니다.
2. Context assembly가 session state, prior result, policy mode, runtime fact를 묶습니다.
3. Adapter retrieval이 domain, hint, primitive support, tier, schema, citation metadata로 후보를 rank합니다.
4. Prompt에는 관련 adapter set과 primitive contract만 들어갑니다.
5. K-EXAONE은 답변, 추가 질문, primitive call 중 하나를 선택합니다.
6. Query engine이 tool call envelope를 검증합니다.
7. Permission classification이 safe, consent-gated, blocked, Mock, Handoff를 결정합니다.
8. Adapter가 live 실행, mock replay, handoff material 중 하나를 반환합니다.
9. Tool result가 model conversation에 다시 투영됩니다.
10. Final answer는 evidence, boundary, next action을 말합니다.
```

중요한 것은 순서입니다. UMMAYA는 먼저 답변을 쓰고 source를 장식처럼 붙이면 안 됩니다. 최소 context를 모아 tool을 고르고, validation과 permission gate를 통과시킨 뒤, returned result로 답하거나 workflow가 왜 멈췄는지 설명해야 합니다.

<figure class="architecture-diagram">
  <img src="/architecture/c4/structurizr-04-public-lookup-flow.svg" alt="최소 C4 dynamic diagram: 시민이 묻고, UI가 route하고, Query Engine이 select하며, Adapters가 Public APIs를 호출하고 UI가 답합니다." />
  <figcaption>Public lookup view: `find`는 Live public channel에서 adapter evidence가 돌아온 뒤에만 답할 수 있습니다.</figcaption>
</figure>

<figure class="architecture-diagram">
  <img src="/architecture/c4/structurizr-05-protected-handoff-flow.svg" alt="최소 C4 dynamic diagram: 시민이 묻고, UI가 route하고, Query Engine이 permission을 check하며, Adapters가 Official Channels에 닿고 UI가 stop 또는 handoff합니다." />
  <figcaption>Protected action view: `check`와 `send`는 permission을 통과하거나, 완료를 가장하지 않고 Handoff에서 멈춰야 합니다.</figcaption>
</figure>

## 왜 Agentic RAG인가

일반적인 RAG는 문서를 검색해서 model이 답하게 합니다. UMMAYA는 tool candidate를 검색해서 model이 안전한 action을 선택하게 합니다. 답변은 tool result, permission event, stop reason이 알려진 뒤에 나옵니다.

이 차이는 국가 인프라에서 중요합니다. 문서 조각은 어떤 서비스가 존재한다고 알려줄 수 있습니다. 그러나 tool candidate는 schema, Live/Mock/Handoff status, credential requirement, citation, fixture, permission metadata를 함께 가질 수 있습니다. Model은 context를 읽는 것뿐 아니라 제한된 공공서비스 action 중 하나를 선택합니다.

## retrieval input

Retrieval은 한국어와 영어 `search_hint`, public-service domain, agency metadata, primitive support, Live/Mock/Handoff state, schema shape, policy citation, prior tool result를 사용할 수 있습니다.

Retrieval output은 final answer가 아닙니다. 그것은 model의 decision space를 좁힙니다. Model이 국가 인프라 전체 surface를 prompt 안에 들고 있을 필요가 없게 만듭니다.

| Retrieval signal | 중요한 이유 |
|---|---|
| 한국어/영어 `search_hint` | 시민은 일상 한국어로 묻지만 adapter는 안정적인 metadata가 필요함 |
| Primitive support | 후보가 `locate`, `find`, `check`, `send` 중 무엇을 지원하는지 알아야 함 |
| Live/Mock/Handoff state | 답변이 execution authority를 과장하지 않게 함 |
| Schema shape | Model이 그럴듯한 intent가 아니라 valid arguments를 내야 함 |
| Policy citation | Protected action에는 UMMAYA가 발명한 권한이 아니라 외부 boundary가 필요함 |
| Prior results | 이후 step이 location, agency, receipt context를 재사용해야 함 |

## query engine의 책임

Query engine은 orchestration만 담당하지 않습니다. Control을 담당합니다. 다음 event가 model call인지, tool call인지, permission request인지, stop reason인지, final answer인지 결정하는 loop를 소유합니다. 이 책임이 공공서비스 workflow를 inspect 가능하게 만듭니다.

| 책임 | engine이 확인하는 것 | 생략하면 생기는 실패 |
|---|---|---|
| Context assembly | session state, prior result, current request, policy mode | model이 일을 반복하거나 법적 순서를 잃음 |
| Candidate narrowing | 관련 adapter와 primitive contract | prompt는 커지지만 decision quality는 좋아지지 않음 |
| Tool-call validation | envelope, schema, required field, type constraint | invalid public-service request가 adapter에 도달 |
| Permission gate | public lookup, protected action, Handoff 구분 | 권한이 없는 데 authorized처럼 들림 |
| Result projection | compact evidence를 conversation에 되돌림 | final text가 tool result와 분리됨 |
| Stop decision | complete, ask user, retry, Mock, Handoff, error | loop가 돌거나 가짜 completion을 만듦 |

## tool calling은 contract다

UMMAYA의 tool calling은 단순한 function-call 편의 기능이 아닙니다. 각 call은 model, primitive envelope, selected adapter, permission pipeline 사이의 contract입니다. Model은 action을 제안합니다. Engine은 그 제안의 shape를 검증합니다. Adapter는 evidence를 만들거나 거부합니다. UI는 무엇이 일어났는지 보여줍니다.

이 contract 때문에 UMMAYA는 넓은 domain을 지원하면서도 model에게 무제한 권한을 주지 않을 수 있습니다. `locate`는 "동아대 승학캠퍼스 근처" 같은 표현을 location context로 바꿀 수 있습니다. `find`는 선택된 adapter를 통해 공개 emergency/weather data를 가져올 수 있습니다. `check`는 보호된 eligibility boundary를 드러낼 수 있습니다. `send`는 channel과 consent가 정당할 때만 official continuation을 준비할 수 있습니다.

## Agentic RAG의 실패 mode

이 아키텍처는 실패가 보일 때만 유용합니다. UMMAYA는 다음을 first-class outcome으로 취급해야 합니다.

- 관련 adapter를 찾지 못함;
- 후보는 있지만 요청 operation이 Handoff-only임;
- model이 invalid arguments를 제안함;
- adapter가 없는 credential이나 consent를 요구함;
- live channel이 usable result를 반환하지 않음;
- response가 Mock evidence이므로 반드시 label이 필요함;
- 다음 turn 전에 context compression이 필요함;
- 공식 service가 workflow를 이어받아야 함.

각 실패는 traceable reason을 남겨야 합니다. User-facing answer는 짧을 수 있지만, system record는 어떤 layer가 workflow를 멈췄는지 보여야 합니다.

## Stop reason

명확한 stop reason은 system을 debuggable하고 safe하게 만듭니다.

- no adapter found;
- invalid arguments;
- permission denied;
- credential missing;
- protected channel unavailable;
- adapter error;
- max iterations or budget reached;
- official Handoff required.

Stop reason은 사용자나 평가자가 어느 layer에서 flow가 막혔는지 알 수 있을 때 유용합니다.

## traceability

강한 UMMAYA answer는 request, adapter selection, primitive call, permission decision, tool result, final text까지 추적 가능해야 합니다. Final answer가 loop로 추적되지 않으면 ungrounded로 취급해야 합니다.

Trace는 문서에도 필요합니다. Architecture prose는 target state가 바람직하다는 이유만으로 capability를 주장하면 안 됩니다. Adapter metadata, scenario coverage, schema files, generated LLM-readable outputs, CI checks, visible terminal behavior를 가리켜야 합니다. 이것이 query engine이 runtime에서 따르는 규칙의 documentation 버전입니다. Evidence에서 답하고, evidence가 멈추는 곳에서 멈춥니다.
