---
title: Domain Roadmap
description: UMMAYA が domains を target-state scenario から mock、live capability へ進める方法。
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- eval/scenarios/national_ax_citizen_requests_v1.yaml
- docs/api/README.md
audience:
- considering_user
- public_sector_evaluator
- maintainer
---

domain roadmap は UMMAYA が overclaim せずに成長する方法を説明します。domain は live になる前から national AX に重要であり得ますが、docs は current state を honest に label しなければなりません。

roadmap は wish list ではありません。scenario、mock、live、そして official channels と credentials が利用可能になるにつれて richer live workflows へ進む promotion ladder です。

## Target Domains

UMMAYA の target map は agency org charts ではなく citizen work に従います。

| Domain | Target user work |
|---|---|
| Safety and healthcare | find public safety, hospital, emergency, weather, and hazard information |
| Housing and local records | prepare moving, address, housing, and local-service workflows |
| Welfare and household support | find guidance, prepare documents, expose eligibility boundaries |
| Tax, fines, payments, utilities | prepare filings, payment paths, receipt expectations, and official handoff |
| Identity, certificates, MyData | explain official paths, consent points, and protected data flows |
| Labor, education, immigration, legal | map multi-agency guidance and target-state workflows |

この table は demand を定義します。すべての row が today Live だとは言いません。

## Promotion Logic

public shape を責任を持って mirror できるほど clear になったとき、domain は scenario から Mock に移ります。Mock から Live へ移るには、official callable channel、必要な credential path、schema、permission metadata、sanitized request/response artifact、test strategy が必要です。

promotion rule は docs が ambition を false current-state claim に変えるのを防ぎます。target-state domain は official channel がない間も Handoff として価値を持ちます。

## Planned Domains が重要な理由

National AX は full citizen journey で評価されます。student portfolio project は today every protected system を live-complete できませんが、caller architecture、evidence ladder、各 domain の honest gap を示せます。

Planned domains は query engine、adapter model、permission UX、docs に future-facing test を与えます。また UMMAYA がより complete になるには public infrastructure が callable、consented、LLM-safe channels を提供する必要があることを示します。

## Roadmap Evidence

roadmap claims は少なくとも一つの artifact に trace するべきです。target-state scenario、adapter metadata、public API documentation、policy citation、schema、fixture、issue/spec などです。何もない場合、その domain は planned capability ではなく research target と書くべきです。

この evidence rule は roadmap を contributors に有用にします。次の action が research、mock adapter、live credential validation、permission design、docs update のどれかを示すからです。

## Next Step

roadmap は [Current Coverage](/jg/coverage/current-coverage/) と [Adapter Matrix](/jg/coverage/adapter-matrix/) と一緒に使います。三つで、users が何を必要とするか、UMMAYA が今何をできるか、promotion を正当化する evidence は何かを答えます。
