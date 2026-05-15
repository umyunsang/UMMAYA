---
title: "Agentic RAG And Query Engine"
description: "检索、推理、工具调用、权限和 stop reason 如何在一个 UMMAYA turn 中协作。"
llm_index: true
audience:
  - citizen_user
  - considering_user
  - public_sector_evaluator
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - docs/vision.md
  - docs/requirements/ummaya-migration-tree.md
  - docs/api/README.md
  - eval/scenarios/national_ax_citizen_requests_v1.yaml
---

UMMAYA uses retrieval for actions, not only for prose. Query engine 接收用户 outcome，检索 adapter candidates，让 K-EXAONE 选择 primitive，验证调用，检查权限，执行 Live/Mock behavior，或产生 Handoff。Final answer 必须从这些 evidence 合成。

<figure class="architecture-diagram">
  <img src="/architecture/c4/structurizr-03-query-engine-core.svg" alt="最小 C4 component diagram：Context, Retrieve, Primitives, Validate, Gate, Dispatch, Stop." />
  <figcaption>Query engine view：context、retrieval、primitive choice、validation、permission、dispatch、stop 是分开的 control steps。</figcaption>
</figure>

## One turn in detail

```text
1. 用户提出 public-service outcome。
2. Context assembly 包装 session state、prior results、policy mode、runtime facts。
3. Adapter retrieval 根据 domain、hint、primitive support、tier、schema、citation metadata 排名候选。
4. Prompt 只接收相关 adapter set 和 primitive contracts。
5. K-EXAONE 选择 answer、ask question 或 call primitive。
6. Query engine 验证 tool call envelope。
7. Permission classification 决定 safe、consent-gated、blocked、Mock 或 Handoff。
8. Adapter live run、mock replay 或 emit handoff material。
9. Tool results 被投回 model conversation。
10. Final answer 说明 evidence、boundary、next action。
```

UMMAYA 不应该先写答案再用 source 装饰。它应该先收集足够 context，选择工具，通过 validation 和 permission gate，然后从返回结果回答，或说明 workflow 为什么停止。

<figure class="architecture-diagram">
  <img src="/architecture/c4/structurizr-04-public-lookup-flow.svg" alt="最小 C4 dynamic diagram：Citizen asks, UI routes, Query Engine selects, Adapters call Public APIs, and UI answers." />
  <figcaption>Public lookup view：`find` 只有在 Live public channel 返回 adapter evidence 之后才能回答。</figcaption>
</figure>

<figure class="architecture-diagram">
  <img src="/architecture/c4/structurizr-05-protected-handoff-flow.svg" alt="最小 C4 dynamic diagram：Citizen asks, UI routes, Query Engine checks permission, Adapters reach Official Channels, and UI stops or hands off." />
  <figcaption>Protected action view：`check` 和 `send` 必须通过 permission，否则要在 Handoff 停止，而不是假装完成。</figcaption>
</figure>

## Why this is agentic RAG

传统 RAG 检索文档，让模型回答。UMMAYA 检索 tool candidates，让模型选择安全 action。Document snippet 只能说明服务存在；tool candidate 可以携带 schema、Live/Mock/Handoff status、credential requirement、citation、fixture 和 permission metadata。

| Retrieval signal | Why it matters |
|---|---|
| Korean/English `search_hint` | 用户用自然韩语提问，adapter 需要稳定 metadata |
| Primitive support | Engine 必须知道候选支持 `locate`、`find`、`check` 还是 `send` |
| Live/Mock/Handoff state | 防止答案夸大执行权限 |
| Schema shape | 模型必须给出 valid arguments |
| Policy citation | Protected action 需要外部边界，而不是 UMMAYA 自造权限 |
| Prior results | 后续步骤可以复用 location、agency、receipt context |

## Query engine responsibilities

| Responsibility | Engine checks | Failure if skipped |
|---|---|---|
| Context assembly | session、prior results、current request、policy mode | 模型重复工作或丢失合法顺序 |
| Candidate narrowing | relevant adapters and primitive contracts | prompt 变大但决策不更好 |
| Tool-call validation | envelope、schema、required fields、type constraints | invalid request 到达 adapter |
| Permission gate | public lookup、protected action、Handoff | 系统听起来像有权限但其实没有 |
| Result projection | compact evidence back into conversation | final text 与 tool result 脱节 |
| Stop decision | complete、ask user、retry、Mock、Handoff、error | loop 空转或伪造完成 |

## Stop reasons

UMMAYA treats visible failure as part of the architecture: no adapter found, invalid arguments, permission denied, credential missing, protected channel unavailable, adapter error, max iterations or budget reached, official Handoff required.

## Boundary

UMMAYA 不会伪造身份验证、证书签发、付款、提交、税务申报或官方记录变更。没有 live 官方渠道、credential、consent 和证据时，正确结果是 Mock 或 Handoff。无法从 request 追踪到 adapter selection、primitive call、permission decision、tool result 和 final text 的答案，应被视为 ungrounded。
