---
title: Welfare And Household Support
description: Use UMMAYA to understand welfare guidance, preparation, eligibility boundaries,
  and official application handoff.
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- docs-site/src/data/generated/adapters.json
- eval/scenarios/national_ax_citizen_requests_v1.yaml
audience:
- citizen_user
- considering_user
- public_sector_evaluator
---

Welfare and household-support workflows are high value because they often cross multiple agencies, eligibility rules, household documents, and local offices. They are also high risk because a helpful-sounding answer can be mistaken for official eligibility.

UMMAYA should help the user understand the public path and prepare the next step. It must not say a person is approved, eligible, enrolled, or submitted unless a live, consented, official check proves that claim.

## Good Prompt

Ask for public guidance, preparation, and boundary marking.

```text
기초생활보장이나 긴급복지 지원을 알아보고 싶어. 공개 안내 기준으로 준비할 서류와 공식 확인이 필요한 단계를 나눠서 알려줘.
```

This prompt gives UMMAYA room to help without forcing a false eligibility decision. It asks for guidance and preparation, not official approval.

## Expected Flow

UMMAYA should first retrieve public guidance, then distinguish general requirements from user-specific checks. Household income, assets, residency, disability, childcare, or crisis conditions may require protected data and official verification.

```text
User asks about welfare support
  -> `find` retrieves public program guidance
  -> `check` identifies eligibility-like boundaries if supported
  -> `send` prepares or submits only with live official channel and consent
  -> otherwise Handoff names the official path
```

This sequence keeps public explanation and protected eligibility separate. The answer can be helpful even when it stops before official application.

## Helpful But Honest Language

The final answer should use preparation language unless live evidence supports stronger wording. Good phrases include `public guidance suggests`, `documents to prepare`, `official confirmation required`, `UMMAYA cannot determine eligibility in this session`, and `continue through the official service`.

| User need | UMMAYA role | Boundary |
|---|---|---|
| Program discovery | `find` | Public guidance |
| Document checklist | synthesis from retrieved guidance | Preparation only |
| Eligibility-like check | `check` with valid classification and consent | Live, Mock, or Handoff |
| Application | `send` with live channel and consent | Otherwise Handoff |

Unsafe language includes `approved`, `eligible`, `benefit granted`, or `application submitted` without live evidence. Those words change the user's decision and require proof.

## What A Good Answer Contains

A good welfare answer should be organized around the user's next decision. It should name the possible program, summarize public criteria, list documents to gather, identify the official service or office, and state which step UMMAYA could not perform.

For evaluators, the answer should also expose the state label. If the flow used a Mock eligibility check, the final text must say it was Mock. If the next step is official application, the answer must say Handoff.

## Recovery

If the user cannot proceed, UMMAYA should ask for the smallest safe clarifying detail or point to the official path. It should not ask for unnecessary sensitive data. It should not collect household or financial details unless the tool path and consent model justify that input.

The product value is practical honesty: the user leaves with a clearer path, and UMMAYA stops before turning guidance into fake authority.
