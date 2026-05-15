---
title: "引っ越し、住宅、地方記録"
description: "official records を変更したふりをせず、multi-agency move と housing workflows を準備します。"
llm_index: true
audience:
  - citizen_user
  - considering_user
  - public_sector_evaluator
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - eval/scenarios/national_ax_citizen_requests_v1.yaml
---

moving と housing tasks は UMMAYA が存在する理由をよく示します。一つの move が local records、address resolution、utility changes、housing documents、vehicle/parking rules、school district concerns、official record updates に触れることがあります。user は help を求める前に agency map を知る必要はありません。

UMMAYA は一つの request を ordered public-service path に変え、この journey を理解しやすくできます。ただし live channel、credential、consent、receipt path が action の authority を prove しない限り、official record を changed と言ってはいけません。

## よい prompt

ordered path を求め、official boundary を明示します。

```text
부산 사하구로 이사했어. 전입신고 전후로 확인해야 할 공공서비스 단계를 순서대로 정리하고, UMMAYA가 할 수 없는 공식 절차는 표시해줘.
```

この prompt は place、lifecycle event、desired output を与えます。silent official submission ではなく preparation と boundary marking を求めているため有効です。

## 期待される flow

moving workflow は user outcome から始め、location を resolve し、public guidance と protected record changes を分けるべきです。later steps は resolved address と jurisdiction に依存するため、順序が重要です。

```text
User describes a move
  -> `locate` resolves address or administrative area
  -> `find` gathers public local-service guidance
  -> `check` identifies protected requirements or missing credentials
  -> `send` runs only if a live official channel and consent exist
  -> otherwise Handoff explains where to continue
```

UMMAYA が location を resolve できない場合、agencies を列挙する前に clarifying question を尋ねるべきです。location は resolve できるが records を change できない場合、complete と言わず checklist と official handoff を提供します。

## 有用な回答に含まれるもの

有用な answer は preparation と execution を分けます。preparation は likely tasks、documents、agencies、timing を list できます。execution は何が Live、Mock、Handoff か label しなければなりません。

| Need | UMMAYA role | Boundary |
|---|---|---|
| Address or jurisdiction | `locate` | Must be clear enough for local guidance |
| Public moving checklist | `find` | Public information only |
| Eligibility or account-specific check | `check` | Consent and credential may be required |
| Official record change | `send` only with live authority | Otherwise Handoff |

この structure は checklist を official filing と混同せず、user に next step を示します。

## UMMAYA が主張してはいけないこと

live adapter が action evidence を返さない限り、UMMAYA は resident registration、utility account、vehicle record、school record、housing record、local government record を changed と言ってはいけません。prepared path は submitted form ではありません。mock receipt は agency receipt ではありません。

safe final sentence は explicit であるべきです。`UMMAYA prepared the moving path and identified official steps, but did not change an official record in this session.` これは派手ではありませんが workflow を trustworthy にします。

## Recovery

workflow が止まったら、UMMAYA は何が progress を blocked したか示すべきです。address ambiguity、no adapter、credential missing、consent not granted、protected channel unavailable、official Handoff などです。user は next official service または next turn の specific question を持って終えるべきです。

moving workflows は長いため context が重要です。後の turn で同じ task を再開する場合、resolved location、既に話した checklist、stop を生んだ protected step を preserve するべきです。
