---
title: UMMAYA 今天能做什么
description: 按用户任务、状态标签和证据边界解释当前 capability。
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- docs-site/src/data/generated/adapters.json
- eval/scenarios/national_ax_citizen_requests_v1.yaml
audience:
- considering_user
- new_user
- public_sector_evaluator
---

UMMAYA 今天已经可以展示核心 national AX pattern：用户请求一个公共服务结果，系统解析 intent，选择 tool path，并用可见状态边界回答。当前能力最强的是 public lookup、location-dependent information 和 preparation flows。

在 live authority、credentials、official callable channels、consent 和 evidence 可用之前，protected actions 大多仍是 Mock 或 Handoff。这个限制不会被隐藏；它是产品 trust model 的一部分。

## 按用户任务看当前能力

按 task 阅读这个表，而不是按内部 adapter 名称阅读。即使最终 protected action 还不是 live，一个 task 今天也可能有用。

| User task | Current state | What UMMAYA should do |
|---|---|---|
| 查找附近医院或 emergency-related public information | Live for public lookup adapters | resolve place，调用 public healthcare/emergency adapters，并总结 source-backed results |
| 查看 weather、forecast、warning、road 或 safety information | Live for public-data adapters | 取回 public data，说明 recency/uncertainty，避免 personal-account claims |
| 解析 addresses、coordinates 或 administrative areas | Live for location adapters | 在 public-service lookup 前 normalize location |
| 了解 welfare information 和 preparation | Live for public guidance，Mock/Handoff for protected applications | 查找 guidance，准备 documents，并标出 official eligibility boundaries |
| 尝试 identity、certificate、MyData 或 authentication flows | Mock or Handoff | 展示 expected consent shape，不声称 verification |
| 支付 fines、提交 applications、file tax 或修改 official records | Mock or Handoff unless a live channel is configured | prepare、label 或 hand off；没有 evidence 时绝不声称 official completion |

关键词是 state。Live public lookup 和 Mock protected workflow 都有价值，但含义不同，final answer 的语气也必须不同。

## 先尝试什么

从安全的 public lookup 开始。给出地点，并要求官方公共信息。

```text
동아대 승학캠퍼스 근처 응급실이나 야간 진료 정보를 공식 정보 기준으로 찾아줘.
```

这个 prompt 是好的第一项测试，因为它给出地点、请求公共信息，并不要求 UMMAYA 进行身份验证、支付、申报、签发或修改官方记录。

## 如何理解 Live、Mock 和 Handoff

Live 表示 UMMAYA 可以调用配置好的 channel，并把回答建立在返回结果上。Mock 表示 workflow shape 可以被演示，但不是官方机构结果。Handoff 表示用户必须在 official service 中继续，因为 UMMAYA 没有安全的 callable path。

这不是法律脚注。它告诉用户自己看到的是 evidence、simulation 还是 next official step。回答应在用户行动前让状态可见。

## 什么是 target-state

target-state scenario dataset 覆盖 tax、civil affairs、payments、utilities、identity、welfare、healthcare、housing、mobility、business、labor、education、safety、immigration、legal 和 personal-data workflows。这些 scenario 今天并不全部 live。

它们定义了 national AX system 最终必须处理的范围，也定义了官方 channel 成熟前 UMMAYA 应如何标出 gap。一个 domain 可以属于目标，而不被虚假描述成 today complete。

## 下一步

读完 capability 后，在 [Quickstart](/ch/start/quickstart/) 安装 packaged CLI 并运行一个 public lookup。之后，在测试 protected workflows 前阅读 [Live, Mock, And Handoff](/ch/trust/live-mock-handoff/)。
