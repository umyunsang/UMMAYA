---
title: "Sessions、Receipts、History"
description: "UMMAYA が sessions、receipts、context compression で長い workflows を inspectable に保つ方法。"
llm_index: true
audience:
  - citizen_user
  - public_sector_evaluator
  - maintainer
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - specs/033-permission-v2-spectrum-consent-ledger/spec.md
---

Sessions、receipts、history は、最初の answer の後も UMMAYA を inspectable にします。National AX workflows は複数 turn にまたがります。location が resolved され、public information が fetched され、protected boundary が現れ、user が後で戻り、system はなぜ止まったか覚えている必要があります。

目的はすべてを永遠に保存することではありません。user、evaluator、maintainer が何が起き、何が allowed され、何が Mock で、何が official path を必要とするか理解できるだけの structured evidence を残すことです。

## Sessions

session は public-service flow の working context を保つべきです。user request、resolved location、selected adapter、permission state、tool result、stop reason、final answer です。これがなければ multi-step public-service task は workflow ではなく repeated conversation になります。

利用できる場合は次のように resume します。

```bash
ummaya resume <session-id>
```

resumed session は authority を silently upgrade してはいけません。前の turn が Handoff で止まったなら、次の turn でも protected step が complete していないことを知っている必要があります。

## Receipts

receipt は permission と action state を visible にするべきです。adapter、mode、purpose、timestamp、policy citation、outcome、result が Live か Mock かを識別します。

mock receipt は agency receipt ではありません。workflow shape を simulate した UMMAYA の evidence です。user が mock を official completion と混同しないよう state を label しなければなりません。

| Receipt field | Why it matters |
|---|---|
| Adapter and primitive | Shows what tool path ran |
| Mode | Distinguishes Live, Mock, and Handoff |
| Purpose | Explains why the action was attempted |
| Permission or consent state | Shows whether protected work was allowed |
| Outcome and stop reason | Explains what happened and what did not |

## History

history は practical questions に答えるためのものです。何を ask したか、どんな public information が found されたか、どの step が consent を要求したか、どの official service が残るか、次に何をするべきかです。

history は sensitive data を friendly transcript の中に隠すべきではありません。protected data が現れるなら、runtime flow と同じ local-session と consent rules に従います。future reasoning または inspection に不要な field は、便利だからという理由だけで retain しません。

## Context Compression

context compression は useful state を保ちながら model context を manageable にし、長い sessions を支えます。reasoning surface を compress するべきで、evidence boundary を消すべきではありません。

compression が model prompt から detail を取り除く場合でも、generated outputs と receipts は inspection に十分な structure を持つ必要があります。compressed context は resolved location、adapter result summary、permission decision、Live/Mock/Handoff state、stop reason を preserve するべきです。

## Recovery

session が resume できない、または receipt が missing の場合、UMMAYA はどの evidence が unavailable か言い、completion claims を避けるべきです。missing receipt は強い wording を cautious wording に変えます。prepared、found、suggested、handed off であり、filed、paid、issued、approved ではありません。
