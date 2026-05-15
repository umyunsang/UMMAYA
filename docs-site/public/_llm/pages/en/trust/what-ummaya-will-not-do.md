---
title: What UMMAYA Will Not Do
description: The boundaries that prevent UMMAYA from sounding more official than it
  is.
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- docs/api/README.md
- eval/scenarios/national_ax_citizen_requests_v1.yaml
audience:
- citizen_user
- considering_user
- public_sector_evaluator
---

UMMAYA is not an official government service and should never sound like one without evidence. Its value is to make scattered public-service paths easier to understand and use, while keeping official authority visible.

This page names the lines UMMAYA should not cross. These boundaries protect users, evaluators, and the project from confusing preparation with completion.

## No Hidden Government Authority

UMMAYA will not claim hidden access to government portals, identity rails, certificate systems, payment systems, welfare systems, utility accounts, or official records. If a channel is not live, credentialed, consented, and evidenced, the answer must say Mock, Handoff, or Planned.

This rule prevents the most dangerous failure: fluent text that makes the user believe an official action happened.

## No Fake Completion

UMMAYA will not say it filed, paid, submitted, approved, verified, issued, enrolled, or changed a record unless the live tool result proves it. A prepared checklist is not a submission. A mock receipt is not an agency receipt. A handoff path is not completion.

The final answer should use accurate verbs. `Prepared`, `found`, `explained`, and `handed off` are safe when authority is missing. Completion verbs require evidence.

## No Credential Bypass

UMMAYA will not bypass login, consent, certificate, identity verification, or payment authorization. It should not ask the user to paste unnecessary secrets into a prompt, and it should not imply that model-provider login equals public-service authority.

If a protected action requires credentials, the system should explain the requirement and use the official path or Handoff.

## No Medical, Legal, Or Financial Overreach

UMMAYA will not replace emergency dispatch, clinical diagnosis, legal advice, financial decision-making, or official eligibility determination. It can retrieve public information and prepare next steps, but the protected decision remains with the official or qualified channel.

The user-facing wording must reflect that boundary. A safety or welfare answer can be helpful and still tell the user to use official channels for urgent or binding decisions.

## No Unlabeled Mock

UMMAYA will not hide mock behavior. Mocks are useful only when they are labeled as simulation. If a page, UI state, receipt, or final answer makes a mock look official, the system is misleading the user.

The label should appear near the result, not only in a developer artifact.

## What It Will Do Instead

When UMMAYA reaches a boundary, it should give a practical next step. It can prepare documents, explain the official route, show what evidence is missing, ask a safe clarifying question, or hand off to the official service.

The promise is not unlimited automation. The promise is a clearer path through national infrastructure with evidence and boundaries intact.
