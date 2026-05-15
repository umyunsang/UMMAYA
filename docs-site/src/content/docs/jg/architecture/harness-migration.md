---
title: "Harness Migration"
description: "Claude Code の harness を国家インフラ AX に移す理由です。"
llm_index: true
audience:
  - citizen_user
  - considering_user
  - public_sector_evaluator
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - docs/vision.md
  - docs/requirements/ummaya-migration-tree.md
  - docs/api/README.md
  - eval/scenarios/national_ax_citizen_requests_v1.yaml
---

UMMAYA のアーキテクチャは、韓国の国家インフラには利用者向けの agent harness が必要だという判断から始まります。利用者は、その作業が政府24、Hometax、Wetax、地方自治体、本人確認、証明書、公共料金、天気情報、data.go.kr API のどれに属するのかを先に知る必要はありません。利用者は結果を言い、harness が分解し、証拠を集め、tool を呼び、必要な permission を示し、公式権限がないところで止まる必要があります。

Claude Code を参照する理由は、すでにこの harness 形を実証しているからです。利用者が outcome を述べ、システムが context を組み立て、model が境界付き tool を呼び、permission UI がリスクを見せ、session が文脈を保持し、terminal が検査可能な過程を表示します。UMMAYA はこの構造を public-service domain に移します。

以下の architecture diagram は、それぞれ一つの問いだけに答えます。Context view は「UMMAYA はどこに位置するのか」、loop view は「利用者が尋ねた直後に何が起きるのか」を示します。Primitive、retrieval、permission、stop reason は、より深いページで個別に拡大します。

<figure class="architecture-diagram">
  <img src="/architecture/c4/structurizr-01-national-ax-context.svg" alt="最小 C4 context diagram：Citizen asks UMMAYA; UMMAYA reasons with K-EXAONE and uses Public APIs or Official Channels." />
  <figcaption>Context view：一つの query surface、一つの model、二つの public-service boundary。</figcaption>
</figure>

## 許可された二つの swap

| Harness component | Claude Code | UMMAYA |
|---|---|---|
| Model provider | Claude family | FriendliAI Serverless 上の K-EXAONE |
| Tool surface | files, shell, git, code tools | 韓国 public-service adapter と official handoff path |

その周囲の discipline は安定して残ります。Query loop、tool-call protocol、permission request path、context assembly、terminal UI、session persistence、evidence-oriented debugging は、UMMAYA が勝手に再設計する部分ではなく、移植する骨格です。

<figure class="architecture-diagram">
  <img src="/architecture/c4/structurizr-02-query-loop.svg" alt="最小 C4 dynamic diagram：Citizen, UI, Query Engine, Sessions, Registry, K-EXAONE Client, K-EXAONE, Answer." />
  <figcaption>Query loop view：ask、route、context、select、reason、answer。</figcaption>
</figure>

これらの diagram は `docs/architecture/c4/workspace.dsl` から生成されます。Architecture model を変更した後は `npm run docs:c4` で再生成します。各 diagram は、一つの読者タスクを説明できる範囲に抑えます。

## 変わらないもの

変わらないのは operational loop です。Context を集め、境界付き action を選び、実行し、結果を conversation に戻し、解決または安全な停止まで繰り返します。この loop が chatbot transcript と agent harness を分けます。

UI の可視性も重要です。利用者は、UMMAYA がまず場所を解決し、次に公開情報を取得し、その後に保護された boundary に到達したことを見られるべきです。順序が見えなければ、final answer は便利に見えても検査できません。

## 変わるもの

UMMAYA が変えるのは risk model です。Developer harness は危険な shell command、file overwrite、project state を扱います。National-infrastructure harness は PIPA、本人確認、証明書、税務、支払い、公式記録、agency policy を扱います。

| Claude Code concern | UMMAYA concern | Discipline |
|---|---|---|
| Dangerous shell command | Protected public-service action | permission は明示的で policy citation が必要 |
| File overwrite | Official record change | live authority なしに完了を主張しない |
| Project memory | Citizen session context | local session は検査可能であるべき |
| Tool result | Public-service evidence or receipt | final answer は returned data に grounded であるべき |
| Context window | Long administrative workflow | context assembly と compression が判断理由を保持する |

## 一つの request での migration path

```text
利用者が outcome を質問
  -> query engine が intent と session context を保持
  -> retrieval が public-service adapter 候補を絞る
  -> K-EXAONE が locate、find、check、send を選ぶ
  -> permission pipeline が action を分類
  -> adapter が Live evidence、Mock evidence、Handoff material を返す
  -> UI が順序を見せ、final answer が boundary を明示する
```

この path は意図的に狭く作られています。本人確認、支払い、証明書発行、公式提出が必要なとき、UMMAYA はその boundary を自信ある文章の中に隠しません。尋ねる、止まる、または handoff します。

## Boundary

Live は設定済みの公式または公共サービスチャネルを呼び出し、その結果を根拠に答える状態です。Mock は形を忠実に示すが公式結果ではない状態です。Handoff は UMMAYA が準備はできるものの、利用者が公式サービスで続ける必要がある状態です。Harness migration は、portal 負担を下げながら検査可能性を失わない場合にだけ価値があります。
