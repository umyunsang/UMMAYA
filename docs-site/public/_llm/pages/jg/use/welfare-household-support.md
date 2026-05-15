---
title: 福祉と世帯支援
description: UMMAYA で welfare guidance、preparation、eligibility boundaries、official
  application handoff を理解します。
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- docs-site/src/data/generated/adapters.json
- eval/scenarios/national_ax_citizen_requests_v1.yaml
audience:
- citizen_user
- considering_user
- public_sector_evaluator
---

welfare と household-support workflows は価値が高いです。multiple agencies、eligibility rules、household documents、local offices をまたぐことが多いからです。同時に、helpful-sounding answer が official eligibility と誤解される危険も高いです。

UMMAYA は user が public path を理解し next step を prepare するのを助けるべきです。live、consented、official check が prove しない限り、approved、eligible、enrolled、submitted と言ってはいけません。

## よい prompt

public guidance、preparation、boundary marking を求めます。

```text
기초생활보장이나 긴급복지 지원을 알아보고 싶어. 공개 안내 기준으로 준비할 서류와 공식 확인이 필요한 단계를 나눠서 알려줘.
```

この prompt は false eligibility decision を強制せず、UMMAYA に help する余地を与えます。official approval ではなく guidance と preparation を求めます。

## 期待される flow

UMMAYA はまず public guidance を retrieve し、general requirements と user-specific checks を分けるべきです。household income、assets、residency、disability、childcare、crisis conditions は protected data と official verification を必要とする場合があります。

```text
User asks about welfare support
  -> `find` retrieves public program guidance
  -> `check` identifies eligibility-like boundaries if supported
  -> `send` prepares or submits only with live official channel and consent
  -> otherwise Handoff names the official path
```

この sequence は public explanation と protected eligibility を分けます。official application の前で止まっても、answer は helpful でいられます。

## helpful だが honest な language

live evidence がより強い wording を支えない限り、final answer は preparation language を使うべきです。よい phrases は `public guidance suggests`、`documents to prepare`、`official confirmation required`、`UMMAYA cannot determine eligibility in this session`、`continue through the official service` です。

| User need | UMMAYA role | Boundary |
|---|---|---|
| Program discovery | `find` | Public guidance |
| Document checklist | synthesis from retrieved guidance | Preparation only |
| Eligibility-like check | `check` with valid classification and consent | Live, Mock, or Handoff |
| Application | `send` with live channel and consent | Otherwise Handoff |

`approved`、`eligible`、`benefit granted`、`application submitted` は live evidence なしに unsafe です。これらの words は user decision を変えるため proof が必要です。

## よい回答に含まれるもの

よい welfare answer は user の next decision を中心に organizing されるべきです。possible program を name し、public criteria を summarize し、gather すべき documents を list し、official service または office を identify し、UMMAYA が perform できなかった step を state します。

evaluator にとって、answer は state label も expose すべきです。flow が Mock eligibility check を使ったなら final text は Mock と言う必要があります。next step が official application なら answer は Handoff と言う必要があります。

## Recovery

user が proceed できない場合、UMMAYA は最小限の safe clarifying detail を ask するか official path を示すべきです。不必要な sensitive data を求めてはいけません。tool path と consent model が justify しない限り、household または financial details を collect してはいけません。

product value は practical honesty です。user はより明確な path を得て、UMMAYA は guidance が fake authority に変わる前に停止します。
