---
title: "第一次成功会话"
description: "第一次运行应当显示什么，以及它绝不能声称什么。"
llm_index: true
audience:
  - new_user
  - considering_user
  - public_sector_evaluator
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - docs-site/src/data/generated/adapters.json
---

UMMAYA 的第一次成功会话只证明一条范围很窄、但很关键的路径：打包后的命令能够启动，模型提供方能够访问，查询引擎能够处理一个市民请求，并且最终回答会诚实标出 Live、Mock 或 Handoff 状态。

它不证明 UMMAYA 可以完成所有受保护的公共服务行为。第一次运行应当测试安全的公共查询，而不是身份认证、支付、证书签发、报税或官方记录变更。

## 第一次会话时间线

成功的第一次会话应当让用户看得懂发生了什么。具体 UI 可以演进，但顺序应保持清晰。

```text
1. `ummaya` 命令启动。
2. 如果需要，用户完成 provider setup 或 sign-in。
3. 用户提出一个公共服务问题。
4. UMMAYA 通过 query engine 路由请求。
5. 一个 public adapter 运行，或系统解释为什么没有安全的 live action。
6. 最终回答总结 result、state、boundary 和 next action。
```

重点不是动画或品牌露出，而是可追溯性。可见回答必须能追到 tool-backed path，或追到清楚的 stop reason。

## 合适的第一次 prompt

选择有用但低风险的请求。

```text
동아대 승학캠퍼스 근처 응급실이나 야간 진료 정보를 공식 정보 기준으로 찾아줘.
```

这个 prompt 给出地点，请求公共信息，并要求 official/public grounding。它不要求身份验证、支付、证书签发、申报或个人账户数据。

## 回答应该显示什么

好的回答应该给用户足够结构来判断下一步是否可信。它应包括公共服务路径、该步骤是 Live/Mock/Handoff、支撑回答的 source 或 adapter result，以及下一步行动。

如果 UMMAYA 找不到 live public path，Handoff 仍然可以是正确结果。产品在拒绝编造官方访问能力时，反而是在正常工作。

## 不应该发生什么

第一次会话不应声称 UMMAYA 已经签发证书、验证身份、支付账单、提交税表、修改官方记录或读取个人账户数据。这些动作需要 official callable channel、credential、explicit consent 和 evidence。

回答也应避免含糊的权威语气。`officially completed`、`verified`、`submitted`、`paid` 这样的词需要 live proof。没有证明时，更安全的词是 `prepared`、`found`、`explained` 或 `handed off`。

## 如果第一次会话失败

用可见症状决定下一步。如果命令不存在，回到 Quickstart。如果 sign-in 失败，先修 provider setup。如果 prompt 返回 Mock 或 Handoff，先读状态标签，不要立刻当成失败。如果 public lookup 失败，换成更清楚的地点和一个公共信息需求。

第一次会话的成功标准不是假装完成最困难的受保护动作，而是 UMMAYA 的回答诚实、可检查。

## 下一步

完成第一次 public lookup 后，阅读 [What You Can Ask](/ch/start/what-you-can-ask/) 来写更好的 prompt，再阅读 [Live, Mock, And Handoff](/ch/trust/live-mock-handoff/) 后再尝试受保护 workflow。
