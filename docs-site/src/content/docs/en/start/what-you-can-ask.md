---
title: What You Can Ask
description: Prompt UMMAYA by public-service outcome, not by agency API or internal adapter name.
llm_index: true
audience:
  - new_user
  - active_user
  - public_sector_evaluator
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - docs-site/src/data/generated/adapters.json
  - eval/scenarios/national_ax_citizen_requests_v1.yaml
---

Ask UMMAYA for a public-service outcome, not for an internal adapter. The system should decide whether the request needs `locate`, `find`, `check`, `send`, or Handoff.

A good prompt gives the user situation, place or domain, desired result, and evidence expectation. It does not need to name the agency unless the agency itself is the user's requirement.

## The Best Prompt Shape

Use this shape when you are unsure:

```text
I am trying to <public-service outcome>.
Use official/public information where possible.
Show what UMMAYA can do now, what needs consent, and where I must continue officially.
```

This works because it gives UMMAYA enough context to choose tools while asking it to label boundaries. It also prevents the answer from sounding like hidden official access.

The best prompts are outcome-first and evidence-aware. They describe what the user is trying to accomplish, then ask UMMAYA to separate what can be done now from what requires official continuation.

## Example Prompts

| Situation | Prompt | Expected path |
|---|---|---|
| Emergency or healthcare lookup | `동아대 승학캠퍼스 근처 응급실이나 야간 진료 정보를 공식 정보 기준으로 찾아줘.` | `locate` then `find` |
| Weather or safety warning | `부산 사하구 오늘 호우나 도로 위험 정보가 있는지 공공 데이터 기준으로 확인해줘.` | `locate` then `find` |
| Moving preparation | `이사했어. 전입신고 전후로 확인해야 할 공공서비스 단계를 정리해줘.` | `find`, possible Handoff |
| Welfare preparation | `긴급복지 지원을 알아보고 싶어. 공개 안내와 공식 확인이 필요한 단계를 나눠줘.` | `find`, possible `check`, Handoff |
| Certificate or identity flow | `주민등록등본 발급 준비 단계와 공식 인증이 필요한 지점을 알려줘.` | `find`, Mock/ Handoff |
| Fine or payment preparation | `과태료 납부 경로와 UMMAYA가 실제로 할 수 없는 단계를 표시해줘.` | `find`, possible `check`, Handoff |

The expected path is not a guarantee of completion. It is a planning hint for how the query engine should decompose the request.

## Ask For Evidence

Add an evidence request when the result could affect a real decision.

```text
공식 정보 기준으로 찾아주고, 어떤 부분이 Live인지 Mock인지 Handoff인지 같이 표시해줘.
```

This sentence makes the answer easier to inspect. A strong UMMAYA answer should say which source, adapter result, scenario boundary, or official handoff shaped the response.

Evidence wording is especially useful for evaluators. It turns a fluent answer into a traceable one by forcing the response to expose state and source.

## Avoid These Prompt Shapes

Avoid prompts that ask UMMAYA to bypass authority:

- "log in for me";
- "issue this certificate now";
- "pay it without asking";
- "change my official record";
- "tell me my private account state without consent";
- "pretend this mock is official."

UMMAYA should refuse, ask for permission, or hand off when a prompt tries to cross those boundaries.

If you accidentally write one of these prompts, the correct recovery is not to persuade UMMAYA harder. Reframe the request as preparation, public lookup, or official handoff guidance.

## If The Answer Stops

A stop is often correct. If UMMAYA says Mock, treat the result as a simulation. If it says Handoff, continue on the official service. If it asks a clarifying question, answer only the minimum information needed to proceed safely.

The goal is not to force every prompt through. The goal is to move as far as evidence and authority allow, then stop visibly.
