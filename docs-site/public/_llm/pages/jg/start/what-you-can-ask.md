---
title: 何を質問できるか
description: agency API や internal adapter name ではなく、public-service outcome で UMMAYA
  に prompt します。
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- docs-site/src/data/generated/adapters.json
- eval/scenarios/national_ax_citizen_requests_v1.yaml
audience:
- new_user
- active_user
- public_sector_evaluator
---

UMMAYA には internal adapter ではなく public-service outcome を依頼します。system は request が `locate`、`find`、`check`、`send`、または Handoff を必要とするか判断するべきです。

よい prompt は user situation、place または domain、desired result、evidence expectation を与えます。agency 自体が要件でない限り、agency 名を先に言う必要はありません。

## 最良の prompt 形

迷ったらこの形を使います。

```text
I am trying to <public-service outcome>.
Use official/public information where possible.
Show what UMMAYA can do now, what needs consent, and where I must continue officially.
```

この形は、UMMAYA が tools を選ぶのに十分な context を与え、同時に boundaries を label するよう求めます。hidden official access のように聞こえる回答を防ぎます。

最良の prompt は outcome-first で evidence-aware です。何を達成したいかを述べ、その後、今できることと official continuation が必要なことを分けるよう求めます。

## 例

| Situation | Prompt | Expected path |
|---|---|---|
| Emergency or healthcare lookup | `동아대 승학캠퍼스 근처 응급실이나 야간 진료 정보를 공식 정보 기준으로 찾아줘.` | `locate` then `find` |
| Weather or safety warning | `부산 사하구 오늘 호우나 도로 위험 정보가 있는지 공공 데이터 기준으로 확인해줘.` | `locate` then `find` |
| Moving preparation | `이사했어. 전입신고 전후로 확인해야 할 공공서비스 단계를 정리해줘.` | `find`, possible Handoff |
| Welfare preparation | `긴급복지 지원을 알아보고 싶어. 공개 안내와 공식 확인이 필요한 단계를 나눠줘.` | `find`, possible `check`, Handoff |
| Certificate or identity flow | `주민등록등본 발급 준비 단계와 공식 인증이 필요한 지점을 알려줘.` | `find`, Mock/ Handoff |
| Fine or payment preparation | `과태료 납부 경로와 UMMAYA가 실제로 할 수 없는 단계를 표시해줘.` | `find`, possible `check`, Handoff |

expected path は completion guarantee ではありません。query engine が request をどう分解するかの planning hint です。

## evidence を求める

結果が real decision に影響する場合は evidence request を加えます。

```text
공식 정보 기준으로 찾아주고, 어떤 부분이 Live인지 Mock인지 Handoff인지 같이 표시해줘.
```

この一文は回答を inspect しやすくします。強い UMMAYA answer は、どの source、adapter result、scenario boundary、official handoff が response を形作ったか言うべきです。

evaluator にとって evidence wording は特に有用です。fluent answer に state と source を露出させ、traceable な answer に変えます。

## 避けるべき prompt

authority を bypass させる prompt は避けます。

- "log in for me";
- "issue this certificate now";
- "pay it without asking";
- "change my official record";
- "tell me my private account state without consent";
- "pretend this mock is official."

このような boundary を越える prompt では、UMMAYA は refuse、ask permission、または hand off するべきです。

誤ってこう書いた場合、UMMAYA をさらに説得するのではなく、preparation、public lookup、official handoff guidance として書き直します。

## 回答が止まったら

stop は正しいことが多いです。UMMAYA が Mock と言うなら simulation として扱います。Handoff と言うなら official service で続けます。clarifying question を出したら、安全に進めるための最小情報だけ答えます。

目的はすべての prompt を通すことではありません。evidence と authority が許す範囲まで進み、必要な場所で visible に停止することです。
