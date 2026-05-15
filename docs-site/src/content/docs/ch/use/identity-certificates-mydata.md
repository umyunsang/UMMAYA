---
title: "身份、证书与 MyData"
description: "理解今天通常需要 Mock 或 official Handoff 的 identity-bound workflows。"
llm_index: true
audience:
  - citizen_user
  - considering_user
  - public_sector_evaluator
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - docs-site/src/data/generated/adapters.json
  - eval/scenarios/national_ax_citizen_requests_v1.yaml
---

身份、证书和 MyData 是韩国 national-infrastructure AX 的核心，也是 UMMAYA 必须最保守的领域。有用的 assistant 可以解释路径、帮助准备、展示 permission shape。它不能在没有 live official channel、credential、consent 和 evidence 时假装验证身份、签发证书、签署文件或读取个人数据。

本页面向想理解 UMMAYA 今天如何安全处理 identity-bound work 的用户。简短结论是：public explanations 有用，mock flows 可以展示形状，而 official Handoff 往往是正确停点。

## 好的 prompt

请求 preparation、official path explanation 或 permission boundary，而不是要求 UMMAYA 静默完成 protected action。

```text
주민등록등본 발급을 준비하려고 해. 필요한 인증 단계와 공식 서비스에서 이어서 해야 할 일을 정리해줘.
```

```text
MyData로 필요한 서류를 확인하는 흐름을 보여줘. 실제 개인 데이터 접근 없이 Mock 기준으로 어디서 consent가 필요한지 알려줘.
```

这些 prompt 有生产力，因为它们让 UMMAYA 能解释和准备，而不声称隐藏 authority。如果用户要求 “issue it now” 或 “log in for me”，系统应转向 permission 或 Handoff，而不是发明 access。

## 预期流程

Identity-bound work 通常从 `find` 开始，可能进入 `check`，并经常在 `send` 前停止。Public guidance 可以描述 official service 需要什么。Mock 可以展示 consent 和 schema shape。当缺少 live authority 时，Handoff 把用户送到 official service。

| Step | UMMAYA behavior | Boundary |
|---|---|---|
| Public explanation | `find` retrieves official guidance or known public material | Explanation only |
| Identity boundary | `check` exposes consent and credential requirements | Mock unless live authority exists |
| Certificate or MyData action | `send` only with official channel, credential, consent, and evidence | Otherwise Handoff |

重点是 sequence。UMMAYA 不应从 public explanation 跳到 “completed certificate issuance”。它应显示哪一步变成 protected，以及为什么 official path 必须接管。

## 必须可见的内容

identity answer 应告诉用户会涉及什么 data、需要什么 consent、哪个 system 是 official、UMMAYA 没有做什么。Live、Mock 或 Handoff label 应靠近 protected step，而不是藏在脚注里。

对 evaluator 来说，本页也是 contract。正确 flow 应留下证据，表明 adapter mode、permission decision 和 stop reason 与最终 wording 相符。如果 final answer 写着 “issued”，但 flow 只到 Mock，那么文档和产品语言都是错的。

## 为什么 Mock 仍重要

当 Mock 被清楚标注时，它很有价值。它让 UMMAYA 在 live credentials 或 official channels 可用前测试 consent prompts、schema validation、tool calling、receipts 和 handoff copy。

如果 mock 看起来 official，价值就消失了。mock identity verification 不是 identity verification。mock certificate result 不是 certificate。回答必须让这个差异无法被忽视。

## Recovery

UMMAYA hand off 时，用户应知道要带走什么：official service name、required authentication type、likely needed documents/data，以及 UMMAYA 无法执行的具体步骤。这样 Handoff 才是有用的，而不是躲避问题。

产品承诺不是 “UMMAYA 绕过 identity rails”。承诺是 “UMMAYA 减少混乱，直到 official identity rail 必须接管”。
