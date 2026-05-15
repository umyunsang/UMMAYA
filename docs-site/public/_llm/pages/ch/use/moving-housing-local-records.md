---
title: 搬家、住房与地方记录
description: 准备跨机构搬家和住房 workflow，而不假装已经修改 official records。
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- eval/scenarios/national_ax_citizen_requests_v1.yaml
audience:
- citizen_user
- considering_user
- public_sector_evaluator
---

搬家和住房任务展示了 UMMAYA 为什么存在。一次搬家可能同时触及 local records、address resolution、utility changes、housing documents、vehicle 或 parking rules、school district concerns 和 official record updates。用户不应在求助前先理解 agency map。

UMMAYA 可以把一个请求转成有序公共服务路径，让旅程变得可理解。但在 live channel、credential、consent 和 receipt path 证明 action 被授权前，它仍必须停止，不能说 official record 已经变更。

## 好的 prompt

请求 ordered path，并把 official boundary 写清楚。

```text
부산 사하구로 이사했어. 전입신고 전후로 확인해야 할 공공서비스 단계를 순서대로 정리하고, UMMAYA가 할 수 없는 공식 절차는 표시해줘.
```

这个 prompt 有效，因为它给出地点、life event 和 desired output。它请求 preparation 和 boundary marking，而不是 silent official submission。

## 预期流程

moving workflow 应从 user outcome 开始，然后 resolve location，并把 public guidance 与 protected record changes 分开。顺序重要，因为后续步骤依赖 resolved address 和 jurisdiction。

```text
User describes a move
  -> `locate` resolves address or administrative area
  -> `find` gathers public local-service guidance
  -> `check` identifies protected requirements or missing credentials
  -> `send` runs only if a live official channel and consent exist
  -> otherwise Handoff explains where to continue
```

如果 UMMAYA 无法 resolve location，应先问 clarifying question，而不是直接列 agencies。如果能 resolve location 但不能改记录，应提供 checklist 和 official handoff，而不是说搬家完成。

## 有用回答包含什么

有用回答应分开 preparation 和 execution。preparation 可以列 likely tasks、documents、agencies 和 timing。execution 必须标明什么是 Live、Mock 或 Handoff。

| Need | UMMAYA role | Boundary |
|---|---|---|
| Address or jurisdiction | `locate` | Must be clear enough for local guidance |
| Public moving checklist | `find` | Public information only |
| Eligibility or account-specific check | `check` | Consent and credential may be required |
| Official record change | `send` only with live authority | Otherwise Handoff |

这个结构让用户知道下一步，而不会把 checklist 混同为 official filing。

## UMMAYA 不应声称什么

除非 live adapter 返回 action evidence，UMMAYA 不应说它修改了 resident registration、utility account、vehicle record、school record、housing record 或 local government record。prepared path 不是 submitted form。mock receipt 不是 agency receipt。

安全的结尾应明确：`UMMAYA prepared the moving path and identified official steps, but did not change an official record in this session.` 这句话可能不够炫，但保持 workflow 可信。

## Recovery

如果 workflow 停下，UMMAYA 应告诉用户阻塞 progress 的缺失项：address ambiguity、no adapter、credential missing、consent not granted、protected channel unavailable 或 official Handoff。用户应带着下一个 official service 或下一轮要回答的具体问题离开。

moving workflow 很长，所以 context 很重要。后续 turn 恢复同一任务时，UMMAYA 应保留 resolved location、已经讨论的 checklist 和导致 stop 的 protected step。
