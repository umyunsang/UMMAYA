---
title: "权限与同意"
description: "UMMAYA 如何区分 public lookup 和 protected public-service actions。"
llm_index: true
audience:
  - citizen_user
  - considering_user
  - public_sector_evaluator
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - specs/033-permission-v2-spectrum-consent-ledger/spec.md
  - docs/api/README.md
---

Permissions 和 consent 保护用户，防止系统在不可见处跳到更高 authority。UMMAYA 往往可以直接获取公共信息，但 protected actions 需要用户在系统继续之前做出可见决定。

规则很简单：public lookup 可以便利；protected action 必须明确。身份、证书、支付、申报、账户特定数据、welfare submissions 和 official record changes 不能像普通搜索结果一样处理。

## Public Lookup

Public lookup 是最低风险路径。当 adapter 和 source 支持时，UMMAYA 可以 resolve location、fetch weather、retrieve road information 或 summarize public guidance。

即使是 public lookup 也需要 grounding。回答应说明哪个 source 或 adapter 影响了结果，以及还存在什么 uncertainty。Public 不是无限制；它只是意味着 workflow 不需要用户的 protected authority。

## Protected Actions

Protected actions 需要更强 gate，因为它们可能影响 identity、money、benefits、records 或 rights。UMMAYA 应在继续前检查 action class、adapter mode、credential requirement 和 user consent。

如果这些条件缺失，正确结果是 Mock 或 Handoff。系统不应因为用户直接要求，就把 protected action 转成 confident sentence。

## Consent Records

consent record 应回答四个问题：允许什么 action，为什么需要它，涉及哪个 adapter 或 official path，会产生什么 result。没有这些细节，consent 就只是装饰。

对 evaluator 来说，consent record 还应连接 mode 和 stop reason。声称完成的 protected flow 必须显示 live authority 和 evidence。mock flow 必须显示它保持在 mock。

## 安全默认值

permission 不清楚时，UMMAYA 应 fail closed。它应请求澄清、停止或 hand off，而不是猜测。这对 identity、payment、certificates、tax、welfare applications 和 record changes 尤其重要。

安全默认值可能让产品感觉慢一些，但会让它可检查。用户能看到系统为什么停下，以及剩下的 official path 是什么。

## 用户应看到什么

用户应在 protected work 之前看到 permission，而不是之后。回答应命名 protected action、consent 理由、status label，以及 consent 或 authority 不可用时的下一步。

如果 UI 或 final answer 隐藏这些信息，文档应把它视为 trust gap。UMMAYA 的价值依赖 visible boundaries。
