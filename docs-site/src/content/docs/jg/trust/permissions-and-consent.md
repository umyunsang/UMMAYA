---
title: "権限と同意"
description: "UMMAYA が public lookup と protected public-service actions をどう分けるか。"
llm_index: true
audience:
  - citizen_user
  - considering_user
  - public_sector_evaluator
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - specs/033-permission-v2-spectrum-consent-ledger/spec.md
  - docs/api/README.md
---

Permissions と consent は、見えない authority jump から user を守ります。UMMAYA は public information を直接 fetch できる場合がありますが、protected actions は system が進む前に visible decision を必要とします。

ルールは単純です。public lookup は便利でよい。protected action は明示的でなければならない。identity、certificates、payments、filings、account-specific data、welfare submissions、official record changes は ordinary search results のように扱えません。

## Public Lookup

Public lookup は最も低リスクな path です。adapter と source が support する場合、UMMAYA は location を resolve し、weather を fetch し、road information を retrieve し、public guidance を summarize できます。

public lookup でも grounding は必要です。answer はどの source または adapter が result を形作ったか、どんな uncertainty が残るかを言うべきです。Public は unlimited ではなく、workflow が user の protected authority を必要としないという意味です。

## Protected Actions

Protected actions は identity、money、benefits、records、rights に影響するため、より強い gate が必要です。UMMAYA は action class、adapter mode、credential requirement、user consent を確認してから進むべきです。

これらの条件が欠ける場合、正しい result は Mock または Handoff です。system は user が直接求めたからといって protected action を confident sentence に変換してはいけません。

## Consent Records

consent record は四つの質問に答えるべきです。何の action を許可するのか、なぜ必要なのか、どの adapter または official path が関わるのか、どんな result が出るのか。これがなければ consent は装飾です。

evaluator review では、consent record は mode と stop reason にも接続されるべきです。completion を主張する protected flow は live authority と evidence を示す必要があります。mock flow は mock のままだったことを示す必要があります。

## Safe Defaults

permission が不明なとき、UMMAYA は fail closed するべきです。推測せず、clarification を求めるか、stop するか、hand off します。identity、payment、certificates、tax、welfare applications、record changes では特に重要です。

safe defaults は product を遅く感じさせるかもしれませんが、inspectable にします。user は system がなぜ止まったか、どの official path が残るかを見られます。

## user が見るべきもの

user は protected work の後ではなく前に permission を見るべきです。answer は protected action、consent の理由、status label、consent または authority がない場合の next step を示すべきです。

UI または final answer がこの情報を隠すなら、docs はそれを trust gap と扱うべきです。UMMAYA の価値は visible boundaries に依存します。
