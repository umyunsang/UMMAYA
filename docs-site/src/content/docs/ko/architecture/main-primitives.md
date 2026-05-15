---
title: "Main Primitives"
description: "도메인 세부사항은 adapter가 담당하고 모델에는 작은 동사 표면만 노출합니다."
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

UMMAYA는 작은 primitive surface를 사용합니다. 모든 기관 동사를 모델 prompt에 올리기에는 국가 인프라 도메인이 너무 넓기 때문입니다.

Primitive layer는 시민 문장과 흩어진 국가 인프라 사이의 compression point입니다. 이 layer는 두 실패를 동시에 막습니다. 사용자는 기관 API 이름으로 말할 필요가 없어야 하고, model은 모든 부처 operation을 prompt에 넣지 않아도 되어야 합니다. UMMAYA는 작은 root vocabulary를 유지하고, 현재 turn에 필요한 adapter detail만 retrieval로 주입합니다.

<figure class="architecture-diagram">
  <img src="/architecture/c4/structurizr-03-query-engine-core.svg" alt="최소 C4 component diagram: Context, Retrieve, Primitives, Validate, Gate, Dispatch, Stop." />
  <figcaption>Primitive view: retrieval이 표면을 좁히고, primitive가 동사를 고르며, validation과 gate가 action을 제한합니다.</figcaption>
</figure>

## Primitive 요약

| Primitive | 의미 | 사용자 표현 | 경계 |
|---|---|---|
| `locate` | 장소, 주소, 좌표, 행정구역 해석 | 근처, 이 주소, 이 동네 | 입력이나 provider가 위험을 바꾸지 않으면 대체로 공개 |
| `find` | 선택된 adapter로 공개 정보 fetch | 찾아줘, 보여줘, 공식 정보 기준으로 | fetch-only, adapter retrieval이 먼저 일어남 |
| `check` | 조건 확인 또는 보호 workflow | 내가 대상인지, 조건이 맞는지 | classification과 consent가 필요할 수 있음 |
| `send` | 허용된 channel로 준비/제출 | 신청, 제출, 납부, 요청 | live 공식 channel, credential, consent, evidence 필요 |

## 왜 primitive는 작아야 하는가

사용자는 agency API를 알 필요가 없습니다. Model도 모든 agency surface를 외우면 안 됩니다. Retrieval이 관련 adapter를 찾고 현재 turn에 필요한 description을 주입합니다. Model은 workflow를 앞으로 움직일 수 있는 가장 작은 primitive를 선택합니다.

이 선택은 tradeoff입니다. Root verb를 많이 만들면 처음에는 풍부해 보입니다. 하지만 `pay`, `issue_certificate`, `apply_for_welfare`, `change_address` 같은 verb는 기관별 authority, credential, policy, receipt 요구사항을 숨깁니다. UMMAYA는 그 세부사항을 adapter에 둡니다. 그래야 각 domain이 자기 evidence와 permission boundary를 가질 수 있습니다.

## primitive가 실제 action이 되는 과정

```text
사용자 표현
  -> intent와 context assembly
  -> adapter retrieval
  -> primitive choice
  -> schema validation
  -> permission classification
  -> Live, Mock, Handoff result
```

Primitive는 adapter가 아닙니다. `find`는 "인터넷 전체 검색"이 아니라 "선택된 adapter를 통한 공개 정보 fetch"입니다. `send`는 "사용자가 말한 모든 제출을 수행"이 아니라 "공식 권한, credential, consent, evidence가 있을 때만 wrapped channel을 준비하거나 실행"한다는 뜻입니다.

## 예시 timeline

```text
사용자가 가까운 응급 정보를 질문
  -> `locate`가 장소를 정규화
  -> `find`가 응급/병원 adapter를 호출
  -> final answer가 result와 urgent official boundary를 명시
```

```text
사용자가 증명서 발급을 요청
  -> `find`가 공개 안내를 찾을 수 있음
  -> `check`가 mock identity boundary를 보여줄 수 있음
  -> live 발급 authority가 없으면 Handoff
```

```text
사용자가 복지 지원을 질문
  -> `find`가 공개 제도 정보를 가져옴
  -> `check`가 classified path로만 요건을 확인
  -> `send`가 공식 경로 checklist를 준비하거나 Handoff에서 멈춤
```

## domain knowledge가 위치하는 곳

| Layer | 그곳에 있어야 하는 것 | 새면 안 되는 것 |
|---|---|---|
| Primitive | 안정적인 action shape와 input/output envelope | 부처별 policy나 credential logic |
| Adapter | 기관 endpoint, schema, citation, fixture, Live/Mock/Handoff 상태 | 증거 없는 hidden recovery path |
| Permission pipeline | consent gate와 protected-action classification | UMMAYA가 발명한 authority |
| Final answer | grounded result, boundary, next action | tool result로 뒷받침되지 않는 claim |

이 분리는 UMMAYA를 확장 가능하게 만듭니다. 기관 하나를 더하는 일은 evidence-bearing adapter 하나를 추가하고 등록하는 일이어야 합니다. 공공서비스 workflow마다 model에게 새 root verb를 가르치는 일이 되어서는 안 됩니다.

## schema discipline

각 primitive는 구조화된 envelope를 사용합니다. 현재 `find` contract는 fetch-only입니다. Candidate search는 호출 전에 일어납니다. 이렇게 해야 hidden search mode가 문서화되지 않은 두 번째 tool system이 되는 것을 막을 수 있습니다.

이 discipline은 실패할 때 가장 중요합니다. Argument가 invalid이면 primitive call은 validation에서 실패해야 합니다. Adapter가 Mock이면 답변은 Mock이라고 말해야 합니다. 공식 channel이 없으면 `send`는 가짜 완료가 아니라 Handoff material이 되어야 합니다. 작은 verb surface는 모든 호출이 schema, evidence, visible stop condition에 묶일 때만 유용합니다.
