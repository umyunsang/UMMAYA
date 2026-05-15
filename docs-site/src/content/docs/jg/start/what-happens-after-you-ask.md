---
title: "質問した後に起きること"
description: "query routing、tool calls、permission gates、final answers をユーザー視点で説明します。"
llm_index: true
audience:
  - new_user
  - active_user
  - public_sector_evaluator
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - docs/vision.md
  - docs-site/src/data/generated/adapters.json
---

質問した後、UMMAYA は記憶から文章だけを生成するべきではありません。依頼を controlled workflow に変換し、location を resolve し、adapter candidates を retrieve し、tools を call し、permission を求め、Handoff で停止し、または grounded answer を合成します。

このページは loop をユーザーの言葉で説明します。architecture pages はより深く扱いますが、ユーザーのルールは単純です。UMMAYA は何をしたか、どんな evidence を使ったか、どこで止まったかを示すべきです。

## 一つの turn を普通の言葉で見る

一つの turn は request から始まり、answer、question、または visible stop で終わります。

```text
You ask for a public-service outcome
  -> UMMAYA keeps the session context
  -> relevant adapters are selected
  -> the model chooses `locate`, `find`, `check`, `send`, or an answer
  -> arguments are validated
  -> permission and mode are checked
  -> a Live adapter runs, a Mock is replayed, or Handoff is produced
  -> the result is returned to the answer
```

一つの result が別の need を生む場合、loop は繰り返されます。moving workflow では checklist の前に location resolution が必要になり、protected submission step は official Handoff で止まることがあります。

## tools が重要な理由

tools は helpful explanation と grounded public-service path を分けます。chatbot は「たぶん正しい」ことを言えます。UMMAYA はどの public data、adapter metadata、schema、handoff boundary が回答を形作ったか示すべきです。

これはすべての回答が action になるという意味ではありません。正しい tool result が `no live path` や `official Handoff required` であることもあります。それでも unsupported answer より誠実です。

## permission が重要な理由

public lookup は modal permission prompt なしで進めることが多いです。protected actions は違います。identity、certificate、payment、filing、account-specific lookup、official record changes には explicit authority と evidence が必要です。

UMMAYA は permission classes を発明しません。adapter が policy metadata と citations を持ち、permission pipeline が boundary を enforcement します。boundary がない場合、system は official に聞こえるより停止するべきです。

## context が重要な理由

行政 work は多くの turn にまたがります。context layer は system prompt、session history、adapter candidates、tool results、permission state を model が使える大きさに保ちます。

context compression があるのは、national AX workflows が一回の lookup より長くなるためです。resolved location、selected adapter、Live/Mock/Handoff label、consent decision、result summary、stop reason を保存するべきです。

## 回答で見るべきもの

よい回答には次が含まれます。

- UMMAYA が理解した user intent；
- 使用した source または adapter；
- path が Live、Mock、Handoff のどれか；
- result または stop reason；
- official または user-controlled として残るもの；
- 次にすること。

これらが欠ける場合、回答は流暢でも national-infrastructure work には十分に inspectable ではありません。
