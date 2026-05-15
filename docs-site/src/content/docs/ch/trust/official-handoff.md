---
title: "官方 Handoff"
description: "当 UMMAYA 到达只有 official service 能完成的边界时应发生什么。"
llm_index: true
audience:
  - citizen_user
  - considering_user
  - public_sector_evaluator
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - docs/api/README.md
  - eval/scenarios/national_ax_citizen_requests_v1.yaml
---

Official Handoff 让 UMMAYA 在不假装自己是政府的情况下保持有用。当 workflow 到达 identity verification、certificate issuance、payment、filing、application submission 或 official record change 时，最安全的结果通常是准备路径，然后停止。

Handoff 不应像放弃用户。好的 handoff 会告诉用户已经准备了什么，哪些仍然属于 official authority，以及应该把哪些信息带到 official service。

## 好的 Handoff 包含什么

好的 Handoff answer 应包含五部分：

| Piece | Purpose |
|---|---|
| Official continuation path | 告诉用户真正 authority 在哪里 |
| Prepared context | 保留 UMMAYA 已解析或找到的内容 |
| Missing authority | 解释 UMMAYA 为什么停止 |
| Required evidence or credential | 告诉用户 official step 需要什么 |
| Next action | 把 stop 变成可执行计划 |

如果回答只说 “go to the official site”，它太薄。如果没有 live proof 却说 “completed”，它不安全。

## 示例

```text
UMMAYA prepared the certificate issuance path and identified the official authentication step.
It did not verify identity or issue the certificate in this session.
Continue through the official certificate service with your required authentication method.
```

这个表达有用，因为它把 preparation 和 completion 分开，也告诉用户没有发生什么。

## 为什么 Handoff 是产品功能

Handoff 看起来像限制，但它是 safety design 的一部分。National-infrastructure work 涉及 legal authority、personal data、money 和 official records。不能证明 authority 的系统应清楚停止。

用户仍然受益，因为 UMMAYA 在停止前减少了混乱。系统可以解释 route、准备 documents、识别可能的 consent points，并为 official step 保留 context。

## Handoff 如何变成 Live

只有当项目拥有 official callable channel、credential path、schema、permission metadata、sanitized artifacts，以及证明 adapter behavior 的 tests 时，Handoff path 才能成为 Live。文档不应因为 target state 很理想，就把 Handoff domain promoted to Live。

promotion 会改变用户的 trust decision。因此 evidence 必须先改变，wording 才能改变。

## Recovery

如果用户在 Handoff 后想继续，UMMAYA 应帮助他们为 official service 做准备，而不是绕过它。它可以总结需要携带什么、可能需要什么 login 或 certificate、以及哪些 previous context 应被复用。

正确的结尾很实际：`UMMAYA stopped here because official authority is required; here is the next official step.`
