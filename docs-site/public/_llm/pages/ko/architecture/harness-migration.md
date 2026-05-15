---
title: Harness Migration
description: Claude Code 하네스 구조를 개발자 작업에서 국가 인프라 작업으로 옮기는 이유입니다.
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- docs/vision.md
- docs/requirements/ummaya-migration-tree.md
- docs/api/README.md
- eval/scenarios/national_ax_citizen_requests_v1.yaml
audience:
- public_sector_evaluator
- maintainer
- llm_agent
---

UMMAYA의 아키텍처는 제품 주장에서 시작합니다. 대한민국 국가 인프라는 사용자-facing agent harness가 필요합니다. Claude Code는 사용자가 결과를 말하면 context를 조립하고, tool을 호출하고, permission을 묻고, session state를 보존하고, terminal UX를 제공하는 reference입니다.

이 migration은 비유가 아니라 제어 구조의 선택입니다. Claude Code는 어려운 도메인도 사용자가 outcome을 말하고, harness가 context를 모으고, model이 제한된 tool을 호출하고, UI가 신뢰 가능한 evidence를 보여주면 쓸 수 있게 된다는 것을 증명했습니다. UMMAYA는 같은 구조를 국가 인프라 작업으로 옮깁니다. 여기서 tool은 파일과 shell command가 아니라 공공서비스 channel, 공식 handoff path, 정책 형태를 반영한 mock입니다.

아래 architecture diagram은 각각 하나의 질문만 답합니다. Context view는 “UMMAYA가 어디에 놓이는가?”를 답하고, loop view는 “사용자가 물으면 처음에 무엇이 일어나는가?”를 답합니다. Primitive, retrieval, permission, stop reason은 더 깊은 페이지에서 따로 확대합니다.

<figure class="architecture-diagram">
  <img src="/architecture/c4/structurizr-01-national-ax-context.svg" alt="최소 C4 context diagram: 시민이 UMMAYA에 묻고, UMMAYA는 K-EXAONE으로 추론하며 Public APIs 또는 Official Channels를 사용합니다." />
  <figcaption>Context view: 하나의 query surface, 하나의 model, 두 개의 공공서비스 boundary.</figcaption>
</figure>

## 설계 주장

UMMAYA는 사용자에게는 하나의 query surface처럼 느껴져야 하지만, 내부적으로는 엄격한 public-service client처럼 동작해야 합니다. 사용자는 이 일이 정부24인지, 홈택스인지, 위택스인지, 지자체인지, 인증 rail인지, 증명서 provider인지, 공공요금 기관인지, 날씨 source인지, data.go.kr API인지 알아야 할 필요가 없습니다. Harness가 관련 channel을 찾고, boundary를 드러내고, 권한이 없는 일을 완료한 것처럼 말하기 전에 멈춰야 합니다.

그래서 아키텍처는 API 목록이 아니라 harness에서 시작합니다. Portal 목록은 사용자의 부담을 다른 화면으로 옮길 뿐입니다. Harness는 여러 turn에 걸쳐 사용자의 의도를 보존하고, tool result를 이어받고, 필요한 순간 consent를 묻고, workflow가 왜 Live, Mock, Handoff가 되었는지 설명할 수 있습니다.

## 두 가지 swap

| 구성 | Claude Code | UMMAYA |
|---|---|---|
| 모델 provider | Claude 계열 | FriendliAI Serverless의 K-EXAONE |
| 도구 표면 | 파일, shell, git, code tools | 한국 공공서비스 adapter와 official handoff |

나머지 harness discipline은 개념적으로 안정적으로 유지됩니다. Query loop, tool-call protocol, permission request path, context assembly, terminal UI, session persistence, evidence-oriented debugging은 UMMAYA가 함부로 재설계할 부분이 아니라 이식해야 할 골격입니다.

<figure class="architecture-diagram">
  <img src="/architecture/c4/structurizr-02-query-loop.svg" alt="최소 C4 dynamic diagram: Citizen, UI, Query Engine, Sessions, Registry, K-EXAONE Client, K-EXAONE, Answer." />
  <figcaption>Query loop view: ask, route, context, select, reason, answer.</figcaption>
</figure>

이 diagram들은 `docs/architecture/c4/workspace.dsl`에서 생성됩니다. Architecture model을 바꾼 뒤에는 `npm run docs:c4`로 다시 생성합니다. 각 diagram은 하나의 독자 과제를 설명할 만큼만 작게 유지합니다.

## 유지되는 것

유지되는 부분은 operational loop입니다. Context를 모으고, 제한된 action을 고르고, 실행하고, 결과를 conversation에 되돌리고, 해결되거나 안전하게 멈출 때까지 반복합니다. 이 구조가 chatbot transcript와 agent harness를 가르는 핵심입니다.

UI의 가시성도 유지되어야 합니다. 사용자는 UMMAYA가 먼저 장소를 해석했고, 그 다음 공개 정보를 조회했고, 그 다음 보호된 boundary에 도달했다는 순서를 볼 수 있어야 합니다. 이 순서가 보이지 않으면 최종 답변은 편리해 보여도 검증 가능하지 않습니다.

## 바뀌는 것

UMMAYA는 위험 모델을 바꿉니다. 개발자 harness는 파일 overwrite, 위험한 shell command, project state 손상을 걱정합니다. 국가 인프라 harness는 PIPA, 신원 확인, 증명서 발급, 세금 신고, 납부, 공식 기록 변경, 기관별 consent를 걱정합니다. 구조는 익숙하지만 결과는 civic합니다.

| Claude Code 관심사 | UMMAYA 관심사 | 필요한 discipline |
|---|---|---|
| 위험한 shell command | 보호된 공공서비스 action | permission은 명시적이고 정책 citation이 있어야 함 |
| 파일 overwrite | 공식 기록 변경 | live authority 없이는 완료를 주장하지 않음 |
| project memory | citizen session context | local persistence가 inspect 가능해야 함 |
| tool result | 공공서비스 evidence 또는 receipt | final answer가 returned data에 grounded 되어야 함 |
| permission prompt | consent와 agency boundary | UI가 무엇을 허용하는지 보여야 함 |
| context window | 긴 행정 workflow | context assembly와 compression이 결정을 보존해야 함 |

## 한 요청에서의 migration path

```text
시민이 outcome을 질문
  -> query engine이 intent와 session context를 보존
  -> retrieval이 가능한 public-service adapter를 좁힘
  -> K-EXAONE이 locate, find, check, send 중 하나를 선택
  -> permission pipeline이 action을 classification
  -> adapter가 Live evidence, Mock evidence, Handoff material을 반환
  -> UI가 순서를 보여주고 final answer가 boundary를 명시
```

이 path는 의도적으로 좁습니다. Workflow가 신원, 납부, 증명서 발급, 공식 제출 권한을 요구하면 harness는 그 boundary를 자신감 있는 문장 안에 숨기지 않습니다. 묻거나, 멈추거나, handoff합니다.

## 왜 새로 만들지 않고 migration하는가

Public-service agent는 느슨한 chatbot이면 안 됩니다. Tool을 호출하고, permission을 처리하고, context를 보존하고, 안전하게 멈추고, 사용자가 무슨 일이 있었는지 볼 수 있어야 합니다. Claude Code는 개발자 도메인에서 이 harness 문제를 이미 풀었기 때문에 가장 강한 reference입니다. UMMAYA의 thesis는 이 harness를 citizen-facing national AX로 옮길 수 있다는 것입니다.

UMMAYA의 독창성은 PIPA, 신원, 인증서, 납부, 기관 정책 citation, Live/Mock/Handoff label, official handoff path, Korean-first 공공서비스 언어를 이 구조에 맞춘 데 있습니다. 이것들은 장식이 아닙니다. Model이 공공서비스 tool을 쓰면서도 실제 권한보다 더 authoritative하게 들리지 않게 하는 조건입니다.

## discipline이 무너지면 실패한다

UI가 설득력 있어도 query loop가 tool evidence를 잃으면 migration은 실패합니다. Mock이 official처럼 들리면 실패합니다. Protected action이 consent를 우회하면 실패합니다. 긴 session에서 이전 agency step이 왜 멈췄는지 잃어버리면 실패합니다.

이 페이지의 기준은 간단합니다. UMMAYA는 사용자의 portal 부담을 줄이면서도 사용자가 무슨 일이 일어났는지 이해할 수 있는 능력을 줄이면 안 됩니다. Harness migration은 national AX를 더 쉽고 더 안전하게 만들 때만 가치가 있습니다.
