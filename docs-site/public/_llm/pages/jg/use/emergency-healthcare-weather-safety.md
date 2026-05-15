---
title: 緊急、医療、天気、安全
description: UMMAYA で公共安全情報を使い、緊急判断と protected decisions は official channels に残します。
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- docs-site/src/data/generated/adapters.json
- eval/scenarios/national_ax_citizen_requests_v1.yaml
audience:
- citizen_user
- considering_user
- public_sector_evaluator
---

emergency、healthcare、weather、safety prompts は UMMAYA の最初の use case として適しています。多くが public information から始まるからです。user は近くの hospitals、public warnings、weather conditions、road hazards、safety guidance を、どの agency や portal が data を持つか知らずに尋ねられます。

convenience と同じくらい boundary が重要です。UMMAYA は public information の locate と summarize を助けられますが、diagnose、triage、dispatch emergency services、facility availability を guarantee、personal medical records に access することは、live official path が authority を証明しない限りできません。

## よい prompt

よい safety prompt は private data を求めず、`locate` と `find` を選べるだけの context を与えます。場所、状況、必要な public information の種類を含めます。

```text
동아대 승학캠퍼스 근처에서 지금 갈 수 있는 응급실이나 야간 진료 정보를 공식 정보 기준으로 찾아줘.
```

```text
부산 사하구 오늘 호우나 도로 위험 정보가 있는지 공공 데이터 기준으로 확인해줘.
```

これらは public lookup を求めるため有用です。symptoms を判断させたり、119/112 を置き換えたり、insurance data や personal hospital record を取得させたりしません。

## 期待される flow

UMMAYA は safety prompt を短く visible な sequence に変えるべきです。request に campus、district、address、nearby expression が含まれる場合、まず place を resolve します。その後 public safety、weather、road、emergency、hospital adapters を選び、relevant public lookup path だけを call します。

```text
User asks with a place and safety need
  -> `locate` resolves the place
  -> `find` retrieves public safety or healthcare information
  -> the answer names the source, result, recency, and urgent official boundary
```

adapter が configured でない、または public source が request を support できない場合、正しい結果は confident guess ではありません。missing path を説明し、official emergency または public-service channel に hand off します。

## よい回答に含まれるもの

よい answer は public evidence と urgent advice を分けます。どの public source または adapter が result を形作ったか、その result が何を support できるか、どんな uncertainty が残るか、urgent な場合 user が何をするべきかを言います。

例えば public hospital lookup が nearby facilities を見つけても、real-time acceptance、ambulance dispatch、medical triage は official emergency channels で扱う必要があると示します。この区別は public lookup を clinical decision と誤解することを防ぎます。

## UMMAYA がしてはいけないこと

UMMAYA は tool result が prove していない medical、emergency、personal-record claims をしてはいけません。live source がその state を提供しない限り、hospital が patient を accept すると言ってはいけません。prompt が immediate danger を示す場合、emergency contact を遅らせる advice もしてはいけません。

safe language は具体的です。`public information says`、`the source returned`、`availability may change`、`call 119 or the official channel for urgent help`。unsafe language は evidence なしに authoritative です。`you are safe`、`this hospital will take you`、`you do not need emergency service`。

## Recovery

flow が止まっても、user は usable next step を持つべきです。UMMAYA は missing evidence を示し、stop が no adapter、no live result、protected data、official Handoff のどれかを説明し、work を続けられる official route を示します。

safety pages では honest stop も product の一部です。高リスク状況で false certainty を作るより、`UMMAYA found public guidance but cannot confirm emergency availability` と言う方がよいです。
