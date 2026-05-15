---
title: "税务、罚款、支付与公用事业账单"
description: "准备高后果 payment 和 filing workflows，而不把 mock path 误写成 official completion。"
llm_index: true
audience:
  - citizen_user
  - considering_user
  - public_sector_evaluator
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - eval/scenarios/national_ax_citizen_requests_v1.yaml
---

tax、fines、payments 和 utility bills 是 UMMAYA target state 的有力例子，因为它们常见、碎片化且后果重大。它们也很危险：如果 checklist、estimate、mock 或 handoff 听起来像 official filing 或 payment，用户可能受到真实损害。

有用的 UMMAYA 不隐藏这种区别。它可以解释 likely path、收集 public guidance、准备 required information，并显示哪里需要 consent 或 official login。除非 live official channel 返回 evidence，否则它不能声称 money was paid、tax return was filed 或 official record was changed。

## 好的 prompt

好的 prompt 要求 UMMAYA 准备路径并标出 boundary。

```text
자동차 과태료를 납부해야 하는지 확인하려고 해. 어떤 공식 경로와 준비물이 필요한지 정리하고, 실제 납부가 필요한 단계는 Handoff로 표시해줘.
```

```text
종합소득세 신고를 준비하려고 해. UMMAYA가 확인할 수 있는 공개 정보와 공식 홈택스에서 해야 하는 단계를 나눠서 알려줘.
```

这些 prompt 有效，因为它们区分 preparation 和 execution。如果用户要求 immediate payment 或 filing，UMMAYA 必须在使用 `send` 前要求 live authority、credential、consent 和 receipt evidence。

## 预期流程

payment 和 filing workflow 常从 public explanation 开始，但很快进入 protected state。UMMAYA 应保持这些层分离。

```text
User asks about tax, fine, payment, or utility work
  -> `find` retrieves public guidance or general path
  -> `check` may reveal that user-specific state requires authority
  -> `send` is allowed only with live official channel and consent
  -> Handoff if the next step must happen on the official service
```

正确 stop 不是失败。如果没有 live official channel，UMMAYA 应说它准备了路径，但没有 file、pay 或 change a record。

## 安全结果形状

final answer 应分成四部分：UMMAYA 找到了什么，哪些仍是 user-specific，哪个 official service 必须继续 workflow，UMMAYA 没有做什么。

| Need | Safe UMMAYA output | Unsafe output |
|---|---|---|
| Public filing guidance | steps, required documents, official service name | "your filing is done" |
| User-specific amount | consent-gated `check` or Handoff | guessed amount |
| Payment execution | live `send` with receipt evidence | mock payment described as paid |
| Receipt | Live receipt or clearly labeled mock receipt | unlabeled confirmation |

这种语言保护用户不把 false completion 当真，也给 evaluator 一个清楚测试：每个 completion word 都必须有 tool evidence。

## 为什么这里需要强语言

这个 domain 的错误回答会造成真实损害。用户可能错过 deadline，以为 fine 已 paid，以为 filing 已 accepted，或把 credentials 交到错误位置。因此 UMMAYA 应优先使用 explicit boundary wording，而不是 impressive phrasing。

使用 `prepared`、`identified`、`requires official login`、`not submitted`、`continue through the official service`。避免 `paid`、`filed`、`accepted`、`approved` 或 `changed`，除非 live result 证明了它。

## Recovery

当 protected payment 或 filing flow 停下时，回答仍应有用。它应告诉用户打开哪个 official service，准备什么 information，缺少什么 consent 或 credential，以及未来要让 UMMAYA live 执行该步骤需要什么 evidence。

target state 不是让 payment boundaries 消失，而是在 official authority 可见的同时让路径可理解。
