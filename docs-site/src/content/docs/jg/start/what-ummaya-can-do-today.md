---
title: "UMMAYA が今日できること"
description: "current capability を user task、status label、evidence boundary で説明します。"
llm_index: true
audience:
  - considering_user
  - new_user
  - public_sector_evaluator
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - docs-site/src/data/generated/adapters.json
  - eval/scenarios/national_ax_citizen_requests_v1.yaml
---

UMMAYA はすでに core national AX pattern を示せます。ユーザーが public-service outcome を求め、system が intent を解釈し、tool path を選び、visible status boundary を持つ回答を返します。現在の surface は public lookup、location-dependent information、preparation flows に最も強いです。

protected actions は、live authority、credentials、official callable channels、consent、evidence が揃うまで、多くが Mock または Handoff です。この制限は隠しません。それは product trust model の一部です。

## ユーザータスク別の現在能力

internal adapter name ではなく task で読んでください。final protected action が live でなくても、task は今日有用な場合があります。

| User task | Current state | What UMMAYA should do |
|---|---|---|
| nearby hospitals や emergency-related public information を探す | Live for public lookup adapters | place を resolve し、public healthcare/emergency adapters を call し、source-backed results を summarize |
| weather、forecast、warning、road、safety information を確認する | Live for public-data adapters | public data を retrieve し、recency と uncertainty を示し、personal-account claims を避ける |
| addresses、coordinates、administrative areas を resolve する | Live for location adapters | public-service lookup の前に location を normalize |
| welfare information と preparation を調べる | Live for public guidance、Mock/Handoff for protected applications | guidance を find し、documents を prepare し、official eligibility boundaries を mark |
| identity、certificate、MyData、authentication flows を試す | Mock or Handoff | verification を主張せず expected consent shape を見せる |
| fines を pay、applications を submit、tax を file、official records を change する | Mock or Handoff unless a live channel is configured | prepare、label、または hand off；evidence なしに official completion を言わない |

重要語は state です。Live public lookup と Mock protected workflow はどちらも有用ですが、意味が異なり、final answer の言葉も異なるべきです。

## 最初に試すべきもの

安全な public lookup から始めます。場所を与え、official public information を求めます。

```text
동아대 승학캠퍼스 근처 응급실이나 야간 진료 정보를 공식 정보 기준으로 찾아줘.
```

この prompt は場所を与え、公共情報を求め、identity verification、payment、filing、issuance、official record change を要求しないため、よい最初のテストです。

## Live、Mock、Handoff の読み方

Live は UMMAYA が configured channel を call し、result に基づいて回答できることです。Mock は workflow shape を示せるが official agency result ではないことです。Handoff は safe callable path がなく、user が official service で続ける必要があることです。

この区別は法律的脚注ではありません。ユーザーが見ているものが evidence、simulation、next official step のどれかを示します。回答はユーザーが行動する前に state を見せるべきです。

## target-state とは何か

target-state scenario dataset は tax、civil affairs、payments、utilities、identity、welfare、healthcare、housing、mobility、business、labor、education、safety、immigration、legal、personal-data workflows を含みます。これらすべてが today live ではありません。

それらは national AX system が最終的に扱うべき範囲と、official channels が成熟するまで UMMAYA が gap をどう label するかを定義します。domain は goal の一部でありながら、today complete と説明されないことがあります。

## 次のステップ

capability を読んだ後、[Quickstart](/jg/start/quickstart/) で packaged CLI を install し、public lookup を一つ実行します。その後 protected workflows を試す前に [Live, Mock, And Handoff](/jg/trust/live-mock-handoff/) を読んでください。
