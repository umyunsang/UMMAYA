---
title: UMMAYA 不会做什么
description: 这些边界防止 UMMAYA 听起来比它实际更 official。
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- docs/api/README.md
- eval/scenarios/national_ax_citizen_requests_v1.yaml
audience:
- citizen_user
- considering_user
- public_sector_evaluator
---

UMMAYA 不是官方政府服务，在没有 evidence 时不应听起来像官方服务。它的价值是让分散的公共服务路径更容易理解和使用，同时保持 official authority 可见。

本页列出 UMMAYA 不应跨越的线。这些边界保护用户、evaluator 和项目，避免把 preparation 和 completion 混为一谈。

## 没有隐藏政府 authority

UMMAYA 不会声称隐藏访问政府门户、identity rails、certificate systems、payment systems、welfare systems、utility accounts 或 official records。如果 channel 不是 live、credentialed、consented、evidenced，回答必须说 Mock、Handoff 或 Planned。

这条规则防止最危险的失败：流畅文本让用户相信官方动作已经发生。

## 没有假完成

UMMAYA 不会说它 filed、paid、submitted、approved、verified、issued、enrolled 或 changed a record，除非 live tool result 证明了这一点。prepared checklist 不是 submission。mock receipt 不是 agency receipt。handoff path 不是 completion。

final answer 应使用准确动词。缺少 authority 时，`Prepared`、`found`、`explained`、`handed off` 是安全词。completion verbs 需要 evidence。

## 不绕过凭证

UMMAYA 不会绕过 login、consent、certificate、identity verification 或 payment authorization。它不应要求用户把不必要的 secrets 粘贴进 prompt，也不应暗示 model-provider login 等于 public-service authority。

如果 protected action 需要 credentials，系统应解释该要求，并使用 official path 或 Handoff。

## 不越界提供医疗、法律或金融判断

UMMAYA 不会替代 emergency dispatch、clinical diagnosis、legal advice、financial decision-making 或 official eligibility determination。它可以检索公共信息并准备下一步，但受保护的决定仍属于 official 或 qualified channel。

用户-facing wording 必须反映这个 boundary。safety 或 welfare answer 可以有帮助，同时告诉用户紧急或 binding decisions 要走 official channels。

## 没有未标注 Mock

UMMAYA 不会隐藏 mock behavior。Mocks 只有在清楚标成 simulation 时才有价值。如果 page、UI state、receipt 或 final answer 让 mock 看起来 official，系统就在误导用户。

label 应出现在 result 附近，而不只是 developer artifact。

## 它会做什么

当 UMMAYA 到达 boundary，它应给出实际下一步。它可以准备 documents、解释 official route、显示缺失 evidence、提出安全的 clarifying question，或 hand off 到 official service。

承诺不是无限 automation。承诺是通过 national infrastructure 的路径更清晰，同时 evidence 和 boundaries 保持完整。
