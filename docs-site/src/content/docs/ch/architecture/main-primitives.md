---
title: "Main Primitives"
description: "为什么 UMMAYA 只把小型 action vocabulary 暴露给模型。"
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

`locate`, `find`, `check`, and `send` keep the model-facing surface small while adapters carry domain detail, citations, schemas, and permission rules. 这个 primitive layer 是用户句子和分散国家基础设施之间的压缩点：用户不需要说 API 名，模型也不需要在 prompt 里看到所有机构操作。

<figure class="architecture-diagram">
  <img src="/architecture/c4/structurizr-03-query-engine-core.svg" alt="最小 C4 component diagram：Context, Retrieve, Primitives, Validate, Gate, Dispatch, Stop." />
  <figcaption>Primitive view：retrieval 缩小范围，primitive 选择动词，validation 和 gate 限制 action。</figcaption>
</figure>

## Primitive summary

| Primitive | Meaning | User wording | Boundary |
|---|---|---|---|
| `locate` | 解析地点、地址、坐标、行政区域 | 附近、这个地址、这个区 | 通常是公开信息，除非输入或 provider 改变风险 |
| `find` | 通过选定 adapter 获取公开信息 | 查找、显示、按官方信息 | fetch-only，候选 adapter 先被检索 |
| `check` | 检查条件或受保护 workflow | 我是否符合、条件是否满足 | 可能需要 classification 和 consent |
| `send` | 在允许时准备或执行提交/缴费/申请 | 提交、申请、缴费、请求 | 需要 live 官方 channel、credential、consent、evidence |

## 为什么 primitive 要小

国家基础设施的 domain 太宽，不能把每个机构动词都放进模型 prompt。更多 root verbs 看起来更丰富，但会把机构权限、credential、政策和 receipt 要求隐藏起来。UMMAYA 把这些知识放在 adapter 里，让每个 domain 自己携带 evidence 和 permission boundary。

```text
用户表达
  -> intent/context assembly
  -> adapter retrieval
  -> primitive choice
  -> schema validation
  -> permission classification
  -> Live, Mock, or Handoff result
```

Primitive 不是 adapter。`find` 不是互联网搜索，而是通过选定 adapter 获取公开信息。`send` 不是执行用户要求的一切提交，而是在官方 channel、credential、consent 和 evidence 都成立时准备或执行。

## Domain knowledge belongs in adapters

| Layer | Belongs there | Must not leak there |
|---|---|---|
| Primitive | 稳定 action shape 和 input/output envelope | 机构特定 policy 或 credential logic |
| Adapter | endpoint、schema、citation、fixture、Live/Mock/Handoff status | 没有证据的 hidden recovery path |
| Permission pipeline | consent gate 和 protected-action classification | UMMAYA 自造的 authority |
| Final answer | grounded result、boundary、next action | 未被 tool result 支撑的 claim |

## Boundary

如果 arguments invalid，primitive call 应该在 validation 阶段失败。如果 adapter 是 Mock，答案必须标注 Mock。如果没有官方 channel，`send` 应该产生 Handoff material，而不是伪造完成。
