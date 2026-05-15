---
title: データ、認証情報、ローカルセッション
description: UMMAYA がローカルに何を保存し、credentials が何を意味し、session evidence がどう検査可能であるべきか。
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- specs/033-permission-v2-spectrum-consent-ledger/spec.md
- docs/vision.md
audience:
- citizen_user
- public_sector_evaluator
- maintainer
---

UMMAYA は data、credentials、session state を理解可能にすることで user trust を守るべきです。national-infrastructure assistant は、何が local で、何が provider に属し、何が official service に送られていないかをユーザーが分かる場合にだけ有用です。

このページは user level の trust model を説明します。secret-storage specification ではありませんが、protected workflows の前に読者が問うべき questions を示します。

## 最初の login が意味すること

最初の login または provider setup は UMMAYA が model provider に到達できるようにします。government authority、identity credentials、certificate access、payment rights、official records を変更する permission を与えるものではありません。

この区別は重要です。provider access と public-service authority は別の layer だからです。model session が正常でも、public-service step が official login または consent を要求すると Handoff で止まります。

## Credentials

credentials は便利な文字列ではなく scoped authority として扱うべきです。workflow が agency login、identity verification、certificate signing、payment authorization、account-specific data を必要とする場合、UMMAYA は続行前に boundary を示さなければなりません。

docs は UMMAYA が hidden credentials を持つと示唆してはいけません。credential path が configured and validated でない場合、正しい言葉は Mock、Handoff、Planned です。

## Local Sessions

local sessions は長い workflow で context を保つために使われます。request text、resolved location、selected adapter、status labels、tool summaries、permission state、stop reason、final answer を含むことがあります。

local session state は inspection を支えるべきです。user や maintainer が、何が起きたか、どんな evidence が返ったか、何に consent したか、どこで workflow が止まったかを理解できる必要があります。

## protected flow 前の確認

protected flow の前に三つを確認します。

| Question | Why it matters |
|---|---|
| step は Live、Mock、Handoff のどれか | fake completion を防ぐ |
| どの credential または consent が必要か | UMMAYA に authority があるか示す |
| どの receipt または evidence が残るか | result を inspectable にする |

どれかが不明なら、より安全な行動は停止するか official service で続けることです。

## Recovery

session、credential、receipt state が不明なら、UMMAYA は言葉を弱めるべきです。prepared、found、explained path とは言えます。visible evidence なしに filed、paid、verified、issued、changed a record とは言うべきではありません。

trust は回答が helpful に聞こえることだけでなく、回答後に boundary を inspect できることから生まれます。
