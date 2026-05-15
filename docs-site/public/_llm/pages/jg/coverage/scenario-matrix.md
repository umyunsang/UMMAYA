---
title: Scenario Matrix
description: UMMAYA が実際の public-service demand を覆うか判断する target-state citizen scenarios。
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- eval/scenarios/national_ax_citizen_requests_v1.yaml
audience:
- public_sector_evaluator
- maintainer
- llm_agent
---

scenario matrix は UMMAYA の demand-side map です。Korean national infrastructure が一つの LLM-mediated interface から到達できるなら、市民が自然に何を ask するかを示します。

Adapters は supply を示します。Scenarios は demand を示します。UMMAYA には両方が必要です。realistic user demand のない tool surface は API catalog になり、adapter evidence のない scenario writing は marketing になります。

## Scenario Dataset に含まれるもの

current target-state dataset は 24 scenarios を含み、tax、civil affairs、payments、utilities、identity、welfare、healthcare、housing、mobility、business、labor、education、safety、関連 public-service workflows を覆います。

各 scenario は次を記録します。

- citizen-style request text；
- lifecycle domain；
- agencies or infrastructure involved；
- expected primitive chain；
- permission requirements；
- evaluation focus；
- expected system behavior。

scenario は必ずしも Live promise ではありません。current adapters、mocks、handoff paths が向かう target state を描く場合があります。

## Docs が scenarios を使う方法

workflow pages は scenarios を使って realistic prompts と expected flows を書くべきです。coverage pages は scenarios を使って today Live と target-state の差を説明するべきです。architecture pages は scenarios を使って query engine が cross-domain work を decompose できるか試すべきです。

page の背後に scenario、example、adapter、schema、trace、generated output が一つもないなら、その page は抽象的すぎる可能性があります。scenarios は national AX を concrete user work に変える方法の一つです。

## Active Primitive Translation

古い scenario material には `lookup`、`resolve_location`、`verify`、`submit` などの labels が使われています。user docs は active names、`find`、`locate`、`check`、`send` を表示しなければなりません。

これは cosmetic ではありません。docs、system prompt、adapter metadata、reader examples が同じ vocabulary を使うことで、users と evaluators は request を prose から tool behavior へ trace できます。

## Evaluation Use

evaluators は各 scenario に believable current state、つまり Live、Mock、Handoff、Planned があるか尋ねるべきです。Live support がない scenario も価値がありますが、complete と説明してはいけません。

matrix が成功すると ambition と gap の両方が見えます。roadmap を sharper にするべきで、target state までの距離を隠すべきではありません。
