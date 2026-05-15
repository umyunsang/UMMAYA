---
title: "数据、凭证与本地会话"
description: "UMMAYA 本地保存什么、credential 意味着什么，以及 session evidence 如何保持可检查。"
llm_index: true
audience:
  - citizen_user
  - public_sector_evaluator
  - maintainer
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - specs/033-permission-v2-spectrum-consent-ledger/spec.md
  - docs/vision.md
---

UMMAYA 必须通过可理解的数据、凭证和 session state 来维持用户信任。一个 national-infrastructure assistant 只有在用户知道什么是本地的、什么属于 provider、什么没有发送到 official service 时，才真正有用。

本页用用户层面的语言解释 trust model。它不是 secret-storage specification，但会给读者一个 checklist，让他们在尝试受保护 workflow 前知道该问什么。

## 第一次登录意味着什么

第一次 login 或 provider setup 让 UMMAYA 能访问 model provider。它不授予政府 authority、identity credentials、certificate access、payment rights，也不允许修改 official records。

这个区分很重要，因为 provider access 和 public-service authority 是不同层。模型会话可以正常工作，但当公共服务步骤需要 official login 或 consent 时，仍然会停在 Handoff。

## Credentials

Credentials 应被视为 scoped authority，而不是方便的字符串。如果 workflow 需要 agency login、identity verification、certificate signing、payment authorization 或 account-specific data，UMMAYA 必须在继续前显示 boundary。

文档不应暗示 UMMAYA 拥有隐藏凭证。如果 credential path 没有配置和验证，正确语言就是 Mock、Handoff 或 Planned。

## 本地会话

本地会话帮助 UMMAYA 在长 workflow 中保留 context。它可能包括 request text、resolved location、selected adapter、status labels、tool summaries、permission state、stop reason 和 final answer。

local session state 应支持 inspection。它应帮助用户或 maintainer 回答：发生了什么、返回了什么 evidence、同意了什么、workflow 在哪里停下。

## 受保护流程前要检查什么

尝试 protected flow 前，先检查三个问题：

| Question | Why it matters |
|---|---|
| 这一步是 Live、Mock 还是 Handoff？ | 防止 fake completion |
| 需要什么 credential 或 consent？ | 显示 UMMAYA 是否有 authority |
| 会产生什么 receipt 或 evidence？ | 让结果可检查 |

如果任何答案不清楚，更安全的动作是停止，或通过 official service 继续。

## Recovery

如果 session、credential 或 receipt 状态不清楚，UMMAYA 应降低措辞强度。它可以说 prepared、found、explained path。没有可见 evidence 时，不应说 filed、paid、verified、issued 或 changed a record。

信任来自回答之后仍能检查 boundary，而不仅是回答听起来有帮助。
