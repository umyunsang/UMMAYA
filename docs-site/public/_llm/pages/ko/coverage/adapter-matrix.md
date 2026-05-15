---
title: Adapter Matrix
description: UMMAYA coverage, adapter status, primitive support의 evidence ledger입니다.
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- docs-site/src/data/generated/adapters.json
- docs/api/README.md
audience:
- public_sector_evaluator
- adapter_author
- maintainer
---

adapter matrix는 user-facing coverage 뒤에 있는 evidence ledger입니다. 각 adapter는 하나의 public-service channel 또는 mockable shape를 하나의 tool entry로 감쌉니다. 이 ledger가 없으면 문서는 claim에 불과합니다.

사용자가 adapter ID를 먼저 읽을 필요는 없습니다. 그러나 evaluator와 contributor는 읽어야 합니다. Live statement는 primitive, state, permission, schema, citation을 설명하는 adapter 또는 generated metadata entry로 trace되어야 합니다.

## Current Shape

generated adapter data는 크게 세 그룹을 나타냅니다.

- weather, road, hospital, emergency, welfare guidance 같은 public lookup domain의 live `find` adapter;
- `locate`를 지원하는 location과 administrative-area adapter;
- identity, certificate, authentication, MyData, protected submission, payment-shaped workflow를 위한 mock `check` 또는 `send` adapter.

이 구분은 UMMAYA trust model을 반영합니다. Public lookup은 더 일찍 Live가 될 수 있습니다. Protected completion은 더 강한 authority가 필요하므로 official access가 생기기 전까지 보통 Mock 또는 Handoff입니다.

## 각 Adapter가 가져야 할 것

유용한 adapter는 function만이 아닙니다. query engine, permission layer, docs, evaluator가 같은 판단을 할 만큼 metadata가 있어야 합니다.

| Field | 중요한 이유 |
|---|---|
| tool ID | docs, traces, generated metadata의 stable reference |
| primitive | path가 `locate`, `find`, `check`, `send` 중 무엇인지 표시 |
| tier | Live, Mock, Handoff, Planned state 구분 |
| permission tier | protected work가 silent execution이 되는 것을 방지 |
| schema path | arguments와 output shape 검증 |
| citation or source | UMMAYA가 authority를 발명하지 않았음을 증명 |

field가 빠지면 adapter는 code일 수 있지만 강한 documentation claim을 뒷받침할 준비가 된 것은 아닙니다.

## 사용자에게 중요한 이유

matrix는 vague coverage language로부터 사용자를 보호합니다. 페이지가 UMMAYA가 public safety information을 찾을 수 있다고 말하면 adapter evidence는 어떤 public lookup path가 그 claim을 지원하는지 보여야 합니다. payment flow가 Mock이라고 말하는 경우 matrix는 final answer가 paid bill처럼 들리는 것을 막아야 합니다.

그래서 adapter metadata는 developer inventory만이 아니라 user trust의 일부입니다.

## Inspect 위치

canonical adapter catalog는 `docs/api/README.md`에 있습니다. generated metadata는 `docs-site/src/data/generated/adapters.json`와 `/_llm/generated/adapters.json`로 복사됩니다.

adapter 변경 뒤에는 다음을 실행하세요.

```bash
npm run docs:generate
npm run docs:check
```

generated metadata가 바뀌었는데 prose가 바뀌지 않았다면 publish 전에 영향받는 page를 review해야 합니다. 이것이 docs drift gate입니다.
