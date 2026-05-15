---
title: Scenario Matrix
description: Target-state citizen scenarios used to judge whether UMMAYA covers real public-service demand.
llm_index: true
audience:
  - public_sector_evaluator
  - maintainer
  - llm_agent
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - eval/scenarios/national_ax_citizen_requests_v1.yaml
---

The scenario matrix is UMMAYA's demand-side map. It describes what citizens would naturally ask if Korean national infrastructure were reachable through one LLM-mediated interface.

Adapters show supply. Scenarios show demand. UMMAYA needs both: a tool surface without realistic user demand becomes an API catalog, and scenario writing without adapter evidence becomes marketing.

## What The Scenario Dataset Contains

The current target-state dataset includes 24 scenarios across tax, civil affairs, payments, utilities, identity, welfare, healthcare, housing, mobility, business, labor, education, safety, and related public-service workflows.

Each scenario records:

- citizen-style request text;
- lifecycle domain;
- agencies or infrastructure involved;
- expected primitive chain;
- permission requirements;
- evaluation focus;
- expected system behavior.

The scenario is not necessarily a Live promise. It may describe the target state that current adapters, mocks, and handoff paths are working toward.

## How Docs Use Scenarios

Workflow pages should use scenarios to write realistic prompts and expected flows. Coverage pages should use scenarios to explain what is Live today and what remains target-state. Architecture pages should use scenarios to test whether the query engine can decompose cross-domain work.

If a page has no scenario, example, adapter, schema, trace, or generated output behind it, the page is probably too abstract. Scenarios are one way to turn national AX into concrete user work.

## Active Primitive Translation

Some older scenario material uses labels such as `lookup`, `resolve_location`, `verify`, and `submit`. User docs must render the active names: `find`, `locate`, `check`, and `send`.

This translation is not cosmetic. The docs, system prompt, adapter metadata, and reader examples should use the same vocabulary so that users and evaluators can trace a request from prose to tool behavior.

## Evaluation Use

Evaluators should ask whether each scenario has a believable current state: Live, Mock, Handoff, or Planned. A scenario without Live support can still be valuable, but it must not be described as complete.

The matrix is successful when it exposes both ambition and gap. It should make the roadmap sharper, not hide the distance to the target state.
