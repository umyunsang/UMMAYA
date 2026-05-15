---
title: "Adapter Matrix"
description: "UMMAYA coverage、adapter status 和 primitive support 背后的 evidence ledger。"
llm_index: true
audience:
  - public_sector_evaluator
  - adapter_author
  - maintainer
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - docs-site/src/data/generated/adapters.json
  - docs/api/README.md
---

adapter matrix 是 user-facing coverage 背后的 evidence ledger。每个 adapter 把一个公共服务 channel 或 mockable shape 包装成一个 tool entry。没有这份 ledger，文档就只剩 claim。

普通用户不需要先读 adapter IDs，但 evaluator 和 contributor 需要。任何 Live statement 都应能追到一个 adapter 或 generated metadata entry，并说明 primitive、state、permission、schema 和 citation。

## 当前形状

generated adapter data 当前代表三大类：

- 面向 weather、road、hospital、emergency、welfare guidance 等 public lookup domains 的 live `find` adapters；
- 支持 `locate` 的 location 和 administrative-area adapters；
- 面向 identity、certificate、authentication、MyData、protected submission 或 payment-shaped workflows 的 mock `check` 或 `send` adapters。

这种划分对应 UMMAYA 的 trust model。Public lookup 往往可以更早 Live。Protected completion 需要更强 authority，通常会在官方 access 可用前保持 Mock 或 Handoff。

## 每个 adapter 必须携带什么

有用的 adapter 不只是 function。它必须携带足够 metadata，让 query engine、permission layer、docs 和 evaluator 对同一个事实达成一致。

| Field | Why it matters |
|---|---|
| tool ID | stable reference for docs, traces, and generated metadata |
| primitive | tells the model whether the path is `locate`, `find`, `check`, or `send` |
| tier | distinguishes Live, Mock, Handoff, or Planned state |
| permission tier | prevents protected work from becoming silent execution |
| schema path | validates arguments and output shape |
| citation or source | proves that the adapter follows an external boundary |

如果一个字段缺失，adapter 可能仍是代码，但还不能支撑强文档 claim。

## 这为什么对用户重要

matrix 保护用户不受 vague coverage language 误导。当页面说 UMMAYA 可以查找 public safety information，adapter evidence 应显示哪个 public lookup path 支撑这个 claim。当页面说 payment flow 是 Mock，matrix 应防止 final answer 听起来像账单已支付。

因此 adapter metadata 是 user trust 的一部分，而不只是 developer inventory。

## 在哪里检查

canonical adapter catalog 位于 `docs/api/README.md`。generated metadata 会复制到 `docs-site/src/data/generated/adapters.json` 和 `/_llm/generated/adapters.json`。

adapter 变更后运行：

```bash
npm run docs:generate
npm run docs:check
```

如果 generated metadata 变了而 prose 没变，publish 前必须 review 受影响页面。这就是 docs drift gate。
