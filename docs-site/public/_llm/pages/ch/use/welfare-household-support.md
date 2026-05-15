---
title: 福利与家庭支持
description: 用 UMMAYA 理解 welfare guidance、preparation、eligibility boundaries 和 official
  application handoff。
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- docs-site/src/data/generated/adapters.json
- eval/scenarios/national_ax_citizen_requests_v1.yaml
audience:
- citizen_user
- considering_user
- public_sector_evaluator
---

welfare 和 household-support workflows 价值很高，因为它们常常跨越多个 agencies、eligibility rules、household documents 和 local offices。它们也高风险，因为一个听起来有帮助的回答可能被误解为 official eligibility。

UMMAYA 应帮助用户理解 public path 并准备下一步。除非 live、consented、official check 证明某项 claim，否则它不能说某人 approved、eligible、enrolled 或 submitted。

## 好的 prompt

请求 public guidance、preparation 和 boundary marking。

```text
기초생활보장이나 긴급복지 지원을 알아보고 싶어. 공개 안내 기준으로 준비할 서류와 공식 확인이 필요한 단계를 나눠서 알려줘.
```

这个 prompt 给 UMMAYA 帮助空间，同时不强迫它做 false eligibility decision。它请求 guidance 和 preparation，而不是 official approval。

## 预期流程

UMMAYA 应先 retrieve public guidance，再区分 general requirements 和 user-specific checks。household income、assets、residency、disability、childcare 或 crisis conditions 可能需要 protected data 和 official verification。

```text
User asks about welfare support
  -> `find` retrieves public program guidance
  -> `check` identifies eligibility-like boundaries if supported
  -> `send` prepares or submits only with live official channel and consent
  -> otherwise Handoff names the official path
```

这个 sequence 把 public explanation 和 protected eligibility 分开。即使在 official application 前停止，回答仍可以有帮助。

## 有帮助但诚实的语言

除非 live evidence 支持更强措辞，final answer 应使用 preparation language。好的表达包括 `public guidance suggests`、`documents to prepare`、`official confirmation required`、`UMMAYA cannot determine eligibility in this session`、`continue through the official service`。

| User need | UMMAYA role | Boundary |
|---|---|---|
| Program discovery | `find` | Public guidance |
| Document checklist | synthesis from retrieved guidance | Preparation only |
| Eligibility-like check | `check` with valid classification and consent | Live, Mock, or Handoff |
| Application | `send` with live channel and consent | Otherwise Handoff |

没有 live evidence 时，`approved`、`eligible`、`benefit granted` 或 `application submitted` 都是不安全语言。这些词会改变用户决定，需要 proof。

## 好回答包含什么

好的 welfare answer 应围绕用户下一步决定组织。它应命名可能 program，总结 public criteria，列出要收集的 documents，识别 official service 或 office，并说明 UMMAYA 无法执行的 step。

对 evaluator 来说，回答也应暴露 state label。如果 flow 使用 Mock eligibility check，final text 必须说它是 Mock。如果下一步是 official application，回答必须说 Handoff。

## Recovery

如果用户无法继续，UMMAYA 应要求最小的安全澄清信息，或指向 official path。它不应请求不必要的 sensitive data。除非 tool path 和 consent model 能证明有必要，否则不应收集 household 或 financial details。

产品价值是 practical honesty：用户带着更清楚的路径离开，UMMAYA 在 guidance 变成 fake authority 前停止。
