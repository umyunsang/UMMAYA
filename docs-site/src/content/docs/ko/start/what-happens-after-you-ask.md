---
title: "질문한 뒤 일어나는 일"
description: "query routing, tool calls, permission gates, final answer를 사용자 수준에서 설명합니다."
llm_index: true
audience:
  - new_user
  - active_user
  - public_sector_evaluator
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - docs/vision.md
  - docs-site/src/data/generated/adapters.json
---

질문한 뒤 UMMAYA는 memory에서 prose만 생성하면 안 됩니다. request를 controlled workflow로 바꾸어 location을 해석하고, adapter candidate를 찾고, tool을 호출하고, permission을 묻고, Handoff에서 멈추거나 grounded answer를 합성할 수 있어야 합니다.

이 페이지는 loop를 사용자 언어로 설명합니다. architecture pages가 더 깊게 다루지만 user-level rule은 간단합니다. UMMAYA는 무엇을 했는지, 어떤 evidence를 썼는지, 어디서 멈췄는지 보여줘야 합니다.

## 한 turn을 쉽게 보면

한 turn은 request에서 시작해 answer, question, visible stop 중 하나로 끝납니다.

```text
사용자가 public-service outcome을 질문
  -> UMMAYA가 session context를 유지
  -> 관련 adapter가 선택됨
  -> model이 `locate`, `find`, `check`, `send`, 또는 answer를 선택
  -> arguments가 validation됨
  -> permission과 mode가 확인됨
  -> Live adapter 실행, Mock replay, 또는 Handoff 생성
  -> result가 answer로 돌아감
```

하나의 result가 또 다른 필요를 만들면 loop는 반복될 수 있습니다. 이사 workflow는 checklist 전에 location resolution이 필요할 수 있고, protected submission step은 official Handoff에서 멈출 수 있습니다.

## Tool이 중요한 이유

Tool은 helpful explanation과 grounded public-service path를 구분합니다. chatbot은 가능해 보이는 말을 할 수 있습니다. UMMAYA는 어떤 public data, adapter metadata, schema, handoff boundary가 answer를 만들었는지 보여줘야 합니다.

모든 answer가 action이 된다는 뜻은 아닙니다. 때로 올바른 tool result는 `no live path` 또는 `official Handoff required`입니다. 그래도 unsupported answer보다 정직합니다.

## Permission이 중요한 이유

public lookup은 modal permission prompt 없이 진행될 수 있습니다. protected action은 그렇지 않습니다. identity, certificate, payment, filing, account-specific lookup, official record change에는 explicit authority와 evidence가 필요합니다.

UMMAYA는 permission class를 발명하지 않습니다. adapter가 policy metadata와 citation을 가져야 하고 permission pipeline이 boundary를 enforce합니다. boundary가 없으면 official처럼 들리는 대신 멈춰야 합니다.

## Context가 중요한 이유

행정 업무는 여러 turn에 걸칠 수 있습니다. context layer는 system prompt, session history, adapter candidates, tool results, permission state를 model이 사용할 수 있을 만큼 compact하게 유지합니다.

Context compression은 national AX workflow가 single lookup보다 길 수 있기 때문에 존재합니다. 중요한 state인 resolved location, selected adapter, Live/Mock/Handoff label, consent decision, result summary, stop reason을 보존해야 합니다.

## 답변에서 보여야 하는 것

좋은 답변은 다음을 포함해야 합니다.

- UMMAYA가 사용자의 요구를 어떻게 이해했는지;
- 어떤 source 또는 adapter를 사용했는지;
- path가 Live, Mock, Handoff 중 무엇이었는지;
- 어떤 result 또는 stop reason이 돌아왔는지;
- 무엇이 official 또는 user-controlled로 남는지;
- 다음에 무엇을 해야 하는지.

이 요소가 없으면 답변이 fluent해도 national-infrastructure work에 충분히 inspectable하지 않습니다.
