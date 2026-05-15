---
title: "公式 Handoff"
description: "UMMAYA が official service だけが完了できる boundary に達したとき起きるべきこと。"
llm_index: true
audience:
  - citizen_user
  - considering_user
  - public_sector_evaluator
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - docs/api/README.md
  - eval/scenarios/national_ax_citizen_requests_v1.yaml
---

Official Handoff は、UMMAYA が政府のふりをせずに有用であり続ける方法です。workflow が identity verification、certificate issuance、payment、filing、application submission、official record change に達した場合、安全な結果は path を prepare して止まることです。

Handoff は放棄のように感じられるべきではありません。よい handoff は何が prepared され、何が official として残り、official service に何を持ち込むべきかを伝えます。

## よい Handoff に含まれるもの

よい Handoff answer は五つの要素を含みます。

| Piece | Purpose |
|---|---|
| Official continuation path | 本当の authority がどこにあるか示す |
| Prepared context | UMMAYA がすでに resolved/found した内容を保つ |
| Missing authority | UMMAYA が止まった理由を説明する |
| Required evidence or credential | official step が必要とするものを示す |
| Next action | stop を usable plan に変える |

answer が `go to the official site` だけなら薄すぎます。live proof なしに `completed` と言うなら unsafe です。

## 例

```text
UMMAYA prepared the certificate issuance path and identified the official authentication step.
It did not verify identity or issue the certificate in this session.
Continue through the official certificate service with your required authentication method.
```

この wording は preparation と completion を分け、何が起きなかったかも伝えるので有用です。

## Handoff が product feature である理由

Handoff は limitation に見えるかもしれませんが、safety design の一部です。National-infrastructure work は legal authority、personal data、money、official records を横断します。authority を prove できない system は clear に止まるべきです。

UMMAYA がその stop 前に confusion を減らせば、user は利益を得ます。route を explain し、documents を prepare し、likely consent points を identify し、official step の context を preserve できます。

## Handoff が Live になる条件

Handoff path が Live になるには、official callable channel、credential path、schema、permission metadata、sanitized artifacts、adapter behavior を証明する tests が必要です。target state が望ましいという理由で docs が Handoff domain を Live に promote してはいけません。

promotion は user の trust decision を変えます。だから wording が変わる前に evidence が変わる必要があります。

## Recovery

Handoff 後に続けたい user に対し、UMMAYA は bypass ではなく official service の準備を助けます。何を持っていくか、どの login または certificate が必要か、どの previous context を再利用するかを summarize できます。

正しい close は実用的です。`UMMAYA stopped here because official authority is required; here is the next official step.`
