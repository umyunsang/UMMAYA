---
title: Scenario Matrix
description: 用于判断 UMMAYA 是否覆盖真实公共服务需求的 target-state citizen scenarios。
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- eval/scenarios/national_ax_citizen_requests_v1.yaml
audience:
- public_sector_evaluator
- maintainer
- llm_agent
---

scenario matrix 是 UMMAYA 的 demand-side map。它描述如果韩国国家基础设施可以通过一个 LLM-mediated interface 触达，市民会自然提出什么请求。

Adapters 显示 supply。Scenarios 显示 demand。UMMAYA 需要两者：没有 realistic user demand 的 tool surface 会变成 API catalog；没有 adapter evidence 的 scenario writing 会变成 marketing。

## Scenario Dataset 包含什么

当前 target-state dataset 包含 24 个 scenarios，覆盖 tax、civil affairs、payments、utilities、identity、welfare、healthcare、housing、mobility、business、labor、education、safety 以及相关 public-service workflows。

每个 scenario 记录：

- citizen-style request text；
- lifecycle domain；
- agencies 或 infrastructure involved；
- expected primitive chain；
- permission requirements；
- evaluation focus；
- expected system behavior。

scenario 不一定是 Live promise。它可能描述 current adapters、mocks 和 handoff paths 正在追求的 target state。

## Docs 如何使用 scenarios

workflow pages 应用 scenarios 写 realistic prompts 和 expected flows。coverage pages 应用 scenarios 解释 today Live 与 target-state 的差距。architecture pages 应用 scenarios 测试 query engine 是否能分解 cross-domain work。

如果页面背后没有 scenario、example、adapter、schema、trace 或 generated output，这个页面很可能太抽象。scenarios 是把 national AX 变成 concrete user work 的方法之一。

## Active Primitive Translation

一些旧 scenario material 使用 `lookup`、`resolve_location`、`verify`、`submit` 等标签。用户文档必须呈现当前名称：`find`、`locate`、`check`、`send`。

这不是 cosmetic translation。docs、system prompt、adapter metadata 和 reader examples 应使用同一 vocabulary，这样用户和 evaluator 才能从 prose 追到 tool behavior。

## Evaluation Use

evaluator 应询问每个 scenario 是否有可信 current state：Live、Mock、Handoff 或 Planned。没有 Live 支持的 scenario 仍可能有价值，但不能描述成 complete。

matrix 成功时，会同时暴露 ambition 和 gap。它应让 roadmap 更清楚，而不是隐藏到 target state 的距离。
