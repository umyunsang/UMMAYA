---
title: 現在の coverage
description: user task、status label、evidence source で UMMAYA の現在 capability を説明します。
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- docs-site/src/data/generated/adapters.json
- docs/api/README.md
- docs/api/verified-data-go-kr/README.md
- tests/unit/tools/test_registry_count_breakdown.py
audience:
- considering_user
- public_sector_evaluator
- maintainer
---

coverage は、UMMAYA が evidence を持って表現できる public-service path を意味します。domain 内のすべての task が today complete できるという意味ではありません。

coverage は user outcome と state label で読んでください。Live、Mock、Handoff、Planned は異なる promises であり、docs はそれらを曖昧にしてはいけません。

新しい [Live Adapters](/jg/coverage/live-adapters/) page は、既存の KMA、KOROAD、HIRA、NMC、NFA、MOHW surface と public-data expansion wave を一緒に説明します。count は単なる「三十個の新 API」ではなく、現在の registry evidence として 42 個の live `find` adapters と 5 個の live `locate` provider adapters と読んでください。

## Coverage Summary

| User outcome | Current state | Evidence source |
|---|---|---|
| Weather、forecast、warning、public safety、air-quality lookup | Live | configured された KMA、AirKorea、MOIS public-data adapters |
| Road、bus、subway accident/hazard/arrival/fare lookup | Live | configured された KOROAD、TAGO、DJTC public-data adapters |
| Hospital、emergency、AED、drug-information lookup | Live | configured された HIRA、NMC、NFA119、MFDS public adapters |
| Location と administrative area resolution | Live | configured された JUSO、Kakao、SGIS-style location adapters |
| Welfare、public jobs、business support、procurement lookup | public lookup は Live | configured された MOHW、MPM、MSS、MSIT、PPS public-data surfaces |
| Legal、public records、statistics、utility/public-corporation lookup | public lookup は Live | configured された MOJ、CCOURT、FTC、REB、KCUE、KEPCO、KSD、BFC、MOF adapters |
| Traffic fine payment と welfare application submission | Mock | shape-faithful `send` adapters |
| Digital OnePass、simple auth、mobile ID、certificates、MyData | Mock or Handoff | `check` mock adapters and scenario docs |
| Government24/Hometax final submissions | Handoff or target-state | official callable channel、credential、consent、artifacts が必要 |

この table は current-state map であり、すべての subtask への product promise ではありません。domain は target-state scenario に含まれていても today は Handoff であり得ます。

## coverage claim の読み方

強い coverage claim は user task、state label、evidence の三つを持ちます。`Healthcare is supported` は広すぎます。`Nearby public hospital lookup is Live where the configured public adapter returns evidence` の方がよい claim です。

この wording は public lookup、personal medical records、triage、emergency dispatch を同じ capability と誤解することを防ぎます。evaluator にも concrete artifact を与えます。

## evaluators が確認すべきこと

evaluators は false promotion を見ます。Mock を official completion として書く、protected workflow に consent evidence がない、public-data answer に source がない、target-state channels を current Live capability と書く page は wrong です。

adapter matrix、generated metadata、scenario matrix、architecture pages は一致するべきです。一つの surface が Live と言い別の surface が Handoff と言う場合、underlying evidence が reconciled されるまで documentation drift と扱います。

## users の次の行動

Live public lookup tasks から始め、trust pages を読んでから Mock または Handoff flows を試してください。binding official action が必要なら、UMMAYA が live authority と receipt evidence を示さない限り official service で続けます。
