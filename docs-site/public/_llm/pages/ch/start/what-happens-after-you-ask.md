---
title: 你提问之后会发生什么
description: 以用户语言解释 query routing、tool call、permission gate 和 final answer。
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- docs/vision.md
- docs-site/src/data/generated/adapters.json
audience:
- new_user
- active_user
- public_sector_evaluator
---

你提问之后，UMMAYA 不应只凭记忆生成一段流畅文本。它会把请求转成受控 workflow：可能 resolve location、retrieve adapter candidates、call tools、ask permission、stop at Handoff，或合成有依据的回答。

本页用用户语言解释这个循环。architecture 页面会更深入，但用户层面的规则很简单：UMMAYA 应显示它做了什么、用了什么 evidence、在哪里停下。

## 一个 turn 的普通语言版本

一个 turn 从你的请求开始，以回答、追问或可见 stop 结束。

```text
You ask for a public-service outcome
  -> UMMAYA keeps the session context
  -> relevant adapters are selected
  -> the model chooses `locate`, `find`, `check`, `send`, or an answer
  -> arguments are validated
  -> permission and mode are checked
  -> a Live adapter runs, a Mock is replayed, or Handoff is produced
  -> the result is returned to the answer
```

当一个结果产生另一个需求时，这个 loop 可以重复。搬家 workflow 可能先需要 location resolution，再生成 checklist；受保护 submission step 可能会停在 official Handoff。

## 为什么 tools 重要

tools 区分了“有帮助的解释”和“有依据的公共服务路径”。普通 chatbot 可以说某件事可能是真的。UMMAYA 应显示哪一份 public data、adapter metadata、schema 或 handoff boundary 影响了回答。

这并不意味着每个回答都会变成 action。有时正确的 tool result 是 “no live path” 或 “official Handoff required”。这仍然比没有依据的回答更诚实。

## 为什么 permission 重要

public lookup 往往可以不用 modal permission prompt。protected action 不行。身份、证书、支付、申报、账户特定查询和官方记录变更都需要明确 authority 和 evidence。

UMMAYA 不发明 permission classes。adapter 必须携带 policy metadata 和 citations，permission pipeline 会执行边界。如果边界缺失，系统应停止，而不是听起来像官方完成。

## 为什么 context 重要

行政工作可能跨很多轮对话。context layer 会把 system prompt、session history、adapter candidates、tool results、permission state 压缩到模型可用的范围内。

context compression 存在，是因为 national AX workflow 可能比一次 lookup 更长。它应保留关键状态：resolved location、selected adapter、Live/Mock/Handoff label、consent decision、result summary 和 stop reason。

## 回答中应该看到什么

好的回答应包含：

- UMMAYA 理解你想做什么；
- 使用了什么 source 或 adapter；
- 路径是 Live、Mock 还是 Handoff；
- 返回了什么 result 或 stop reason；
- 哪些部分仍然 official 或 user-controlled；
- 下一步做什么。

如果这些要素缺失，回答可能仍然流畅，但不足以支撑 national-infrastructure work。
