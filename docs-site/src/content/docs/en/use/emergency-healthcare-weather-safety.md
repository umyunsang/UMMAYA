---
title: Emergency, Healthcare, Weather, And Safety
description: Use UMMAYA for public safety information while keeping urgent and protected decisions on official channels.
llm_index: true
audience:
  - citizen_user
  - considering_user
  - public_sector_evaluator
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - docs-site/src/data/generated/adapters.json
  - eval/scenarios/national_ax_citizen_requests_v1.yaml
---

Emergency, healthcare, weather, and safety prompts are the best first use case for UMMAYA because they mostly begin with public information. A user can ask for nearby hospitals, public warnings, weather conditions, road hazards, or safety guidance without first knowing which agency or portal owns the data.

The boundary is just as important as the convenience. UMMAYA can help locate and summarize public information, but it must not diagnose, triage, dispatch emergency services, guarantee facility availability, or access personal medical records unless a live official path proves that authority.

## Good Prompts

A good safety prompt gives UMMAYA enough context to choose `locate` and `find` without asking for private data. The prompt should name the place, the situation, and the kind of public information needed.

```text
동아대 승학캠퍼스 근처에서 지금 갈 수 있는 응급실이나 야간 진료 정보를 공식 정보 기준으로 찾아줘.
```

```text
부산 사하구 오늘 호우나 도로 위험 정보가 있는지 공공 데이터 기준으로 확인해줘.
```

These prompts are useful because they ask for public lookup. They do not ask UMMAYA to judge symptoms, replace 119/112, access insurance data, or retrieve a personal hospital record.

## Expected Flow

UMMAYA should turn a safety prompt into a short, visible sequence. The system first resolves the place if the request contains a campus, district, address, or nearby expression. It then selects public safety, weather, road, emergency, or hospital adapters and calls only the relevant public lookup path.

```text
User asks with a place and safety need
  -> `locate` resolves the place
  -> `find` retrieves public safety or healthcare information
  -> the answer names the source, result, recency, and urgent official boundary
```

If the adapter is not configured or the public source cannot support the request, the correct result is not a confident guess. UMMAYA should explain the missing path and hand the user to the official emergency or public-service channel.

## What A Good Answer Contains

A good answer separates public evidence from urgent advice. It should say what public source or adapter shaped the result, what the result can support, what uncertainty remains, and what the user should do if the situation is urgent.

For example, a useful answer might say that public hospital lookup found nearby facilities, but that real-time acceptance, ambulance dispatch, and medical triage must be handled through official emergency channels. That distinction protects the user from mistaking a public lookup for a clinical decision.

## What UMMAYA Must Not Do

UMMAYA must not make medical, emergency, or personal-record claims that the tool result did not prove. It must not say a hospital will accept a patient unless a live source provides that state. It must not advise a user to delay emergency contact when the prompt suggests immediate danger.

The safe language is concrete: `public information says`, `the source returned`, `availability may change`, `call 119 or the official channel for urgent help`. The unsafe language is authoritative without evidence: `you are safe`, `this hospital will take you`, `you do not need emergency service`.

## Recovery

If the flow stops, the user should still leave with a usable next step. UMMAYA should name the missing evidence, show whether the stop was no adapter, no live result, protected data, or official Handoff, and point to the official route that can continue the work.

For safety pages, an honest stop is part of the product. It is better to say "UMMAYA found public guidance but cannot confirm emergency availability" than to create false certainty in a high-risk situation.
