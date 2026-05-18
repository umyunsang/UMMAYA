---
title: "Adapter Matrix"
description: "UMMAYA coverage、adapter status、primitive support の背後にある evidence ledger。"
llm_index: true
audience:
  - public_sector_evaluator
  - adapter_author
  - maintainer
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - docs-site/src/data/generated/adapters.json
  - docs/api/README.md
  - docs/api/verified-data-go-kr/README.md
---

adapter matrix は user-facing coverage の背後にある evidence ledger です。各 adapter は一つの public-service channel または mockable shape を一つの tool entry として wrap します。この ledger がなければ、docs は claims だけになります。

users が adapter IDs を最初に読む必要はありませんが、evaluators と contributors は読む必要があります。Live statement は primitive、state、permission、schema、citation を説明する adapter または generated metadata entry に trace できるべきです。

## Current Shape

generated adapter data は現在三つの broad groups を表します。

- weather、road、bus、hospital、emergency、welfare guidance、jobs、procurement、legal/public records、statistics など public lookup domains の 42 個の live `find` adapters；
- `locate` を support する location と administrative-area adapters；
- identity、certificate、authentication、MyData、protected submission、payment-shaped workflows の mock `check` または `send` adapters。

registry count evidence は別に、4 個の main primitive surfaces（`find`、`locate`、`check`、`send`）と non-core adapter registry entries を検証します。この split は UMMAYA の trust model を反映します。Public lookup は早く Live になり得ます。Protected completion はより強い authority を必要とし、official access が得られるまで Mock または Handoff に残ることが多いです。user-task grouping は [Live Adapters](/jg/coverage/live-adapters/) で読み、canonical row-level evidence はこの matrix と `docs/api/README.md` で確認します。

## 各 adapter が持つべきもの

有用な adapter は function だけではありません。query engine、permission layer、docs、evaluator が同じ事実に同意できる metadata を持つ必要があります。

| Field | Why it matters |
|---|---|
| tool ID | stable reference for docs, traces, and generated metadata |
| primitive | tells the model whether the path is `locate`, `find`, `check`, or `send` |
| tier | distinguishes Live, Mock, Handoff, or Planned state |
| permission tier | prevents protected work from becoming silent execution |
| schema path | validates arguments and output shape |
| citation or source | proves that the adapter follows an external boundary |

field が欠けている場合、adapter は code ではあっても strong documentation claim を支える準備はできていません。

## users に重要な理由

matrix は vague coverage language から users を守ります。page が public safety information を find できると言うなら、adapter evidence はどの public lookup path が claim を support するか示すべきです。page が payment flow は Mock と言うなら、matrix は final answer が paid bill のように聞こえるのを防ぐべきです。

だから adapter metadata は developer inventory だけでなく user trust の一部です。

## Inspect する場所

canonical adapter catalog は `docs/api/README.md` にあります。generated metadata は catalog rows と individual adapter front matter を merge し、`docs-site/src/data/generated/adapters.json` と `/_llm/generated/adapters.json` にコピーされます。

adapter changes 後に実行します。

```bash
npm run docs:generate
npm run docs:check
```

generated metadata が変わり prose が変わらない場合、publish 前に affected pages を review します。これが docs drift gate です。
