---
title: UMMAYA Docs
description: Korean national-infrastructure AX harness として UMMAYA を使い、評価し、拡張するための
  documentation。
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- docs/research/ummaya-docs-audience-audit-2026-05-15.md
- docs/vision.md
audience:
- non_user
- considering_user
- new_user
- public_sector_evaluator
---

UMMAYA は Korean national-infrastructure AX のための conversational agent harness です。user は one approachable query surface で public-service outcome を求め、system は decomposition、tool selection、permission boundaries、evidence、official handoff を処理します。

この documentation は四つの reader stages のために書かれています。UMMAYA が useful か判断する人、packaged CLI を初めて試す new users、claims が grounded か確認する evaluators、adapter surface を拡張する contributors です。

## Start Here

初めてなら Start section を順に読んでください。user problem、current capability、installation path、first successful session、prompt shape、query 後に起きることを説明します。

| Page | Use it when |
|---|---|
| [Why UMMAYA](/jg/start/why-ummaya/) | product purpose が必要なとき |
| [What UMMAYA Can Do Today](/jg/start/what-ummaya-can-do-today/) | current capability と limits を知りたいとき |
| [Quickstart](/jg/start/quickstart/) | CLI を install して run したいとき |
| [First Successful Session](/jg/start/first-successful-session/) | first run の success がどう見えるか知りたいとき |
| [What You Can Ask](/jg/start/what-you-can-ask/) | better prompts を書きたいとき |
| [What Happens After You Ask](/jg/start/what-happens-after-you-ask/) | user-level system loop を理解したいとき |

Start section は architecture が必要になる前に UMMAYA を理解可能にするべきです。

## protected work 前の Trust

identity、payments、certificates、welfare applications、tax filing、official record changes を試す前に Trust section を読んでください。これら workflows は UMMAYA が最も慎重でなければならない領域です。

Trust pages は Live、Mock、Handoff、permission、consent、data、credentials、local sessions、official handoff、explicit non-goals を説明します。public lookup と protected action、preparation と completion を区別するためです。

## Situation 別に使う

Use section は real public-service situations で整理されています。emergency and safety、moving and housing、welfare、tax and payments、identity and certificates、sessions and receipts、troubleshooting です。

各 page は同じ practical questions に答えるべきです。何を ask できるか、何が起きるべきか、UMMAYA がどこで act できるか、どこで stop しなければならないか、次に何をするかです。

## Coverage と Architecture を評価する

Coverage pages は current capability、adapter evidence、target-state scenarios、roadmap logic を示します。Architecture pages は UMMAYA がなぜ Claude Code-style harness を migrate するか、primitives がどう働くか、query engine が retrieval、tool calls、permission、stop reasons をどう coordinate するかを説明します。

supported か確認するには coverage を使います。system design が national AX goal を支えられるか確認するには architecture を使います。

## Build と Reference

Build pages は adapter authors と maintainers のためです。adapter authoring と、docs、generated metadata、deployment outputs を aligned に保つ LLMOps を説明します。

Reference pages は LLM-readable docs を expose し、future agents が human readers と同じ boundaries を inspect できるようにします。

## Reading Rule

page が capability claim をするたびに、state label と evidence を探してください。task が Live なら docs は何がそれを support するか言うべきです。Mock または Handoff なら、user が行動する前に boundary が visible であるべきです。
