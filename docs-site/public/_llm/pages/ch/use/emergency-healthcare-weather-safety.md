---
title: 应急、医疗、天气与安全
description: 用 UMMAYA 查找公共安全信息，同时把紧急和受保护决定留在 official channels。
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- docs-site/src/data/generated/adapters.json
- eval/scenarios/national_ax_citizen_requests_v1.yaml
audience:
- citizen_user
- considering_user
- public_sector_evaluator
---

应急、医疗、天气和安全 prompt 是 UMMAYA 最好的第一类用例，因为它们通常从公共信息开始。用户可以询问附近医院、公共 warning、weather conditions、road hazards 或 safety guidance，而不必先知道哪个 agency 或 portal 拥有数据。

便利性和边界同样重要。UMMAYA 可以帮助 locate 和 summarize public information，但不能诊断、分诊、调度 emergency services、保证 facility availability，或访问 personal medical records，除非 live official path 证明了这些 authority。

## 好的 prompt

好的 safety prompt 给 UMMAYA 足够 context 来选择 `locate` 和 `find`，但不要求 private data。prompt 应说明地点、情况和需要的公共信息类型。

```text
동아대 승학캠퍼스 근처에서 지금 갈 수 있는 응급실이나 야간 진료 정보를 공식 정보 기준으로 찾아줘.
```

```text
부산 사하구 오늘 호우나 도로 위험 정보가 있는지 공공 데이터 기준으로 확인해줘.
```

这些 prompt 有用，因为它们请求 public lookup。它们不要求 UMMAYA 判断症状、替代 119/112、访问保险数据或检索个人医院记录。

## 预期流程

UMMAYA 应把 safety prompt 转成短而可见的 sequence。系统先在请求包含 campus、district、address 或 nearby expression 时 resolve place。然后选择 public safety、weather、road、emergency 或 hospital adapters，并只调用相关 public lookup path。

```text
User asks with a place and safety need
  -> `locate` resolves the place
  -> `find` retrieves public safety or healthcare information
  -> the answer names the source, result, recency, and urgent official boundary
```

如果 adapter 未配置，或 public source 不支持请求，正确结果不是自信猜测。UMMAYA 应解释缺失路径，并把用户 hand off 到 official emergency 或 public-service channel。

## 好回答包含什么

好回答会把 public evidence 和 urgent advice 分开。它应说明哪个 public source 或 adapter 影响了结果、该结果能支持什么、仍有什么 uncertainty，以及如果情况紧急用户应怎么做。

例如，有用回答可以说 public hospital lookup 找到附近设施，但 real-time acceptance、ambulance dispatch 和 medical triage 必须通过 official emergency channels 处理。这个区分防止用户把 public lookup 当成 clinical decision。

## UMMAYA 不应做什么

UMMAYA 不应做 tool result 没有证明的 medical、emergency 或 personal-record claim。除非 live source 提供状态，否则不应说某医院会接收病人。prompt 暗示 immediate danger 时，也不应建议用户延迟联系 emergency channel。

安全语言是具体的：`public information says`、`the source returned`、`availability may change`、`call 119 or the official channel for urgent help`。不安全语言是在没有 evidence 时显得权威：`you are safe`、`this hospital will take you`、`you do not need emergency service`。

## Recovery

如果 flow 停下，用户仍应得到可用下一步。UMMAYA 应说明缺失 evidence，显示 stop 是 no adapter、no live result、protected data 还是 official Handoff，并指向可继续工作的 official route。

对 safety 页面来说，诚实 stop 是产品的一部分。说 “UMMAYA found public guidance but cannot confirm emergency availability” 比在高风险场景中制造虚假确定性更好。
