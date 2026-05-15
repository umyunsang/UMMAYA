---
title: 무엇을 물어볼 수 있나
description: agency API나 internal adapter 이름이 아니라 public-service outcome으로 UMMAYA에
  질문합니다.
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- docs-site/src/data/generated/adapters.json
- eval/scenarios/national_ax_citizen_requests_v1.yaml
audience:
- new_user
- active_user
- public_sector_evaluator
---

UMMAYA에는 internal adapter가 아니라 public-service outcome을 질문하세요. 시스템이 request에 `locate`, `find`, `check`, `send`, 또는 Handoff가 필요한지 결정해야 합니다.

좋은 prompt는 사용자 상황, 장소나 domain, 원하는 결과, evidence expectation을 줍니다. 사용자의 요구 자체가 특정 기관일 때가 아니라면 agency 이름을 몰라도 됩니다.

## 가장 좋은 prompt 형태

확신이 없으면 이 형태를 사용하세요.

```text
I am trying to <public-service outcome>.
Use official/public information where possible.
Show what UMMAYA can do now, what needs consent, and where I must continue officially.
```

이 형태는 UMMAYA가 tool을 선택할 수 있는 context를 주면서 boundary label을 요구합니다. hidden official access처럼 들리는 답변도 줄입니다.

가장 좋은 prompt는 outcome-first이고 evidence-aware입니다. 사용자가 달성하려는 일을 설명하고, 지금 가능한 일과 official continuation이 필요한 일을 나눠 달라고 요청합니다.

## 예시 프롬프트

| 상황 | Prompt | Expected path |
|---|---|---|
| 응급 또는 의료 lookup | `동아대 승학캠퍼스 근처 응급실이나 야간 진료 정보를 공식 정보 기준으로 찾아줘.` | `locate` then `find` |
| 날씨 또는 안전 경보 | `부산 사하구 오늘 호우나 도로 위험 정보가 있는지 공공 데이터 기준으로 확인해줘.` | `locate` then `find` |
| 이사 준비 | `이사했어. 전입신고 전후로 확인해야 할 공공서비스 단계를 정리해줘.` | `find`, possible Handoff |
| 복지 준비 | `긴급복지 지원을 알아보고 싶어. 공개 안내와 공식 확인이 필요한 단계를 나눠줘.` | `find`, possible `check`, Handoff |
| 증명서 또는 신원 flow | `주민등록등본 발급 준비 단계와 공식 인증이 필요한 지점을 알려줘.` | `find`, Mock/Handoff |
| 과태료 또는 납부 준비 | `과태료 납부 경로와 UMMAYA가 실제로 할 수 없는 단계를 표시해줘.` | `find`, possible `check`, Handoff |

expected path는 completion guarantee가 아닙니다. query engine이 request를 어떻게 분해해야 하는지 보여주는 planning hint입니다.

## Evidence 요청하기

결과가 실제 decision에 영향을 줄 수 있으면 evidence request를 추가하세요.

```text
공식 정보 기준으로 찾아주고, 어떤 부분이 Live인지 Mock인지 Handoff인지 같이 표시해줘.
```

이 문장은 답변을 inspect하기 쉽게 만듭니다. 강한 UMMAYA answer는 어떤 source, adapter result, scenario boundary, official handoff가 response를 만들었는지 말해야 합니다.

evidence wording은 evaluator에게 특히 유용합니다. fluent answer를 traceable answer로 바꾸기 때문입니다.

## 피해야 할 prompt 형태

UMMAYA에 authority bypass를 요구하는 prompt는 피하세요.

- "log in for me";
- "issue this certificate now";
- "pay it without asking";
- "change my official record";
- "tell me my private account state without consent";
- "pretend this mock is official."

UMMAYA는 이런 prompt가 boundary를 넘으려 할 때 refuse, permission request, 또는 Handoff해야 합니다.

실수로 이런 prompt를 썼다면 더 강하게 밀어붙이는 것이 복구가 아닙니다. request를 preparation, public lookup, official handoff guidance로 다시 구성하세요.

## 답변이 멈추면

stop은 자주 올바른 결과입니다. UMMAYA가 Mock이라고 말하면 simulation으로 다루세요. Handoff라고 말하면 official service에서 이어가세요. clarifying question을 묻는다면 안전하게 진행하는 데 필요한 최소 정보만 답하세요.

목표는 모든 prompt를 억지로 통과시키는 것이 아닙니다. evidence와 authority가 허용하는 만큼 이동하고, 그 지점에서 visible하게 멈추는 것입니다.
