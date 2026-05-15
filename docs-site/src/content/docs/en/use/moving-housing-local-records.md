---
title: Moving, Housing, And Local Records
description: Prepare multi-agency move and housing workflows without pretending to change official records.
llm_index: true
audience:
  - citizen_user
  - considering_user
  - public_sector_evaluator
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - eval/scenarios/national_ax_citizen_requests_v1.yaml
---

Moving and housing tasks show why UMMAYA exists. A single move can touch local records, address resolution, utility changes, housing documents, vehicle or parking rules, school district concerns, and official record updates. A user should not need to know the agency map before asking for help.

UMMAYA can make this journey understandable by turning one request into an ordered public-service path. It must still stop before changing an official record unless a live channel, credential, consent, and receipt path prove that the action is authorized.

## Good Prompt

Ask for an ordered path and make the official boundary explicit.

```text
부산 사하구로 이사했어. 전입신고 전후로 확인해야 할 공공서비스 단계를 순서대로 정리하고, UMMAYA가 할 수 없는 공식 절차는 표시해줘.
```

This prompt works because it gives the place, the lifecycle event, and the desired output. It asks for preparation and boundary marking, not silent official submission.

## Expected Flow

A moving workflow should start with the user outcome, then resolve location and split public guidance from protected record changes. The order matters because later steps depend on the resolved address and jurisdiction.

```text
User describes a move
  -> `locate` resolves address or administrative area
  -> `find` gathers public local-service guidance
  -> `check` identifies protected requirements or missing credentials
  -> `send` runs only if a live official channel and consent exist
  -> otherwise Handoff explains where to continue
```

If UMMAYA cannot resolve the location, it should ask a clarifying question before listing agencies. If it can resolve the location but cannot change records, it should provide a checklist and official handoff rather than saying the move is complete.

## What A Useful Answer Contains

A useful answer should separate preparation from execution. The preparation part can list likely tasks, documents, agencies, and timing. The execution part must label what is Live, Mock, or Handoff.

| Need | UMMAYA role | Boundary |
|---|---|---|
| Address or jurisdiction | `locate` | Must be clear enough for local guidance |
| Public moving checklist | `find` | Public information only |
| Eligibility or account-specific check | `check` | Consent and credential may be required |
| Official record change | `send` only with live authority | Otherwise Handoff |

This structure helps the user know what to do next without confusing a checklist with an official filing.

## What UMMAYA Must Not Claim

UMMAYA must not say it changed a resident registration, utility account, vehicle record, school record, housing record, or local government record unless a live adapter returned evidence of that action. A prepared path is not a submitted form. A mock receipt is not an agency receipt.

The safe final sentence should be explicit: `UMMAYA prepared the moving path and identified official steps, but did not change an official record in this session.` That sentence may feel less impressive, but it keeps the workflow trustworthy.

## Recovery

If the workflow stops, UMMAYA should tell the user which missing item blocked progress: address ambiguity, no adapter, credential missing, consent not granted, protected channel unavailable, or official Handoff. The user should leave with a next official service or a specific question to answer in the next turn.

Moving workflows are long, so context matters. When a later turn resumes the same task, UMMAYA should preserve the resolved location, the already discussed checklist, and the protected step that caused the stop.
