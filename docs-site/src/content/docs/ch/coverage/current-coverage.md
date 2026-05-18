---
title: "当前覆盖范围"
description: "按用户任务、状态标签和证据来源说明 UMMAYA 当前 capability。"
llm_index: true
audience:
  - considering_user
  - public_sector_evaluator
  - maintainer
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - docs-site/src/data/generated/adapters.json
  - docs/api/README.md
  - docs/api/verified-data-go-kr/README.md
  - tests/unit/tools/test_registry_count_breakdown.py
---

coverage 指 UMMAYA 能用 evidence 表达的公共服务路径。它不表示一个 domain 中的每个 task 今天都可以完成。

请按 user outcome 和 state label 阅读 coverage。Live、Mock、Handoff、Planned 是不同承诺，文档不能把它们混在一起。

新的 [Live Adapters](/ch/coverage/live-adapters/) 页面把既有 KMA、KOROAD、HIRA、NMC、NFA、MOHW surface 与 public-data expansion wave 放在一起说明。数量应按当前 registry evidence 阅读：42 个 live `find` adapters 和 5 个 live `locate` provider adapters，而不只是“三十个新 API”。

## Coverage Summary

| User outcome | Current state | Evidence source |
|---|---|---|
| Weather、forecast、warning、public safety、air-quality lookup | Live | configured 时的 KMA、AirKorea、MOIS public-data adapters |
| Road、bus、subway accident/hazard/arrival/fare lookup | Live | configured 时的 KOROAD、TAGO、DJTC public-data adapters |
| Hospital、emergency、AED、drug-information lookup | Live | configured 时的 HIRA、NMC、NFA119、MFDS public adapters |
| Location 和 administrative area resolution | Live | configured 时的 JUSO、Kakao、SGIS-style location adapters |
| Welfare、public jobs、business support、procurement lookup | public lookup 为 Live | configured 时的 MOHW、MPM、MSS、MSIT、PPS public-data surfaces |
| Legal、public records、statistics、utility/public-corporation lookup | public lookup 为 Live | configured 时的 MOJ、CCOURT、FTC、REB、KCUE、KEPCO、KSD、BFC、MOF adapters |
| Traffic fine payment 和 welfare application submission | Mock | shape-faithful `send` adapters |
| Digital OnePass、simple auth、mobile ID、certificates、MyData | Mock or Handoff | `check` mock adapters 和 scenario docs |
| Government24/Hometax final submissions | Handoff or target-state | 需要 official callable channel、credential、consent 和 artifacts |

这张表是 current-state map，不是对每个 subtask 的产品承诺。一个 domain 可以出现在 target-state scenario 中，同时今天仍是 Handoff。

## 如何阅读 coverage claim

强 coverage claim 有三部分：user task、state label、evidence。`Healthcare is supported` 太宽。`Nearby public hospital lookup is Live where the configured public adapter returns evidence` 是更好的 claim。

这种 wording 防止用户把 public lookup、personal medical records、triage 和 emergency dispatch 当成同一种 capability。它也给 evaluator 一个具体 artifact 可查。

## Evaluators 应检查什么

evaluator 应查找 false promotion。若页面把 Mock 描述成 official completion、protected workflow 没有 consent evidence、public-data answer 没有 source、或把 target-state channels 当成 current Live capability，它就是错的。

adapter matrix、generated metadata、scenario matrix 和 architecture pages 应一致。如果一个 surface 写 Live，另一个写 Handoff，在 reconciled underlying evidence 前，都应视为 documentation drift。

## 用户下一步

先从 Live public lookup tasks 开始。阅读 trust pages 后，再尝试 Mock 或 Handoff flows。如果你需要 binding official action，除非 UMMAYA 显示 live authority 和 receipt evidence，否则继续通过 official service 办理。
