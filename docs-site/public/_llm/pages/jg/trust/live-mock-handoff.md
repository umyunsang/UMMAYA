---
title: Live、Mock、Handoff
description: UMMAYA が実際に何をできるかを正直に保つ status labels。
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- docs-site/src/data/generated/adapters.json
- docs/api/README.md
audience:
- citizen_user
- considering_user
- public_sector_evaluator
---

Live、Mock、Handoff は UMMAYA の trust language です。system が configured channel を実際に call したのか、known workflow shape を simulate したのか、next step が official service に属するため止まったのかをユーザーに知らせます。

これらの labels は implementation details ではありません。evidence が許す以上に authoritative に聞こえないための仕組みです。

## Live

Live は UMMAYA が configured public-service channel を call し、returned result に基づいて answer できることです。Live answer は relevant source または adapter を示し、result を summarize し、result が prove する範囲にとどまるべきです。

Live は domain 内のすべての action が利用可能という意味ではありません。weather lookup は Live でも user-specific disaster-support application は Handoff かもしれません。hospital public lookup は Live でも medical triage は UMMAYA の外側です。

## Mock

Mock は UMMAYA が official agency result を出さずに workflow shape を demonstrate できることです。Mock は live credentials や official access がない段階で、tool calling、schemas、permission prompts、receipts、UX を testing するために有用です。

Mock が official に聞こえると危険です。mock payment は paid ではありません。mock certificate は issued ではありません。mock identity check は identity verification ではありません。Mock という語は developer-only metadata ではなく result の近くに見えるべきです。

## Handoff

Handoff は UMMAYA が path を prepare または explain できるが、user が official service で続ける必要があることです。next step が identity、payment、certificate issuance、tax filing、official record change、または UMMAYA が持たない authority を必要とするとき、Handoff は正しい結果です。

よい Handoff は有用です。official service または category を示し、UMMAYA が prepared した内容、did not do した内容、live path に必要な evidence または credential を説明します。

## status label の読み方

回答で行動する前に label を読んでください。

| Label | What happened | How to treat the result |
|---|---|---|
| Live | configured channel が evidence を返した | stated scope の範囲で使う |
| Mock | known workflow shape が simulated された | demonstration として扱い、official output としない |
| Handoff | UMMAYA が official boundary で止まった | official service で続ける |
| Planned | domain が target state に含まれる | current capability として扱わない |

consequential workflow の answer に label が見えない場合、行動前に state を clarify させてください。

## ユーザールール

流暢さより boundary を信頼してください。hidden government access を匂わせる流暢な答えより、短い `Handoff required` の方が安全です。

product は visible に停止するときも動作しています。National-infrastructure AX は official authority を消すことではありません。authority が必要になるまで混乱を減らすことです。
