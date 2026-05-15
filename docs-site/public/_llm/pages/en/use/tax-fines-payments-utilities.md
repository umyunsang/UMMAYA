---
title: Tax, Fines, Payments, And Utility Bills
description: Prepare consequential payment and filing workflows without confusing
  mock paths with official completion.
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- eval/scenarios/national_ax_citizen_requests_v1.yaml
audience:
- citizen_user
- considering_user
- public_sector_evaluator
---

Tax, fines, payments, and utility bills are persuasive examples of UMMAYA's target state because they are common, fragmented, and consequential. They are also dangerous if a checklist, estimate, mock, or handoff sounds like an official filing or payment.

The useful version of UMMAYA does not hide that distinction. It can explain the likely path, gather public guidance, prepare required information, and show where consent or official login is needed. It must not claim that money was paid, a tax return was filed, or an official record was changed unless a live official channel returned evidence.

## Good Prompts

Good prompts ask UMMAYA to prepare the path and mark the boundary.

```text
자동차 과태료를 납부해야 하는지 확인하려고 해. 어떤 공식 경로와 준비물이 필요한지 정리하고, 실제 납부가 필요한 단계는 Handoff로 표시해줘.
```

```text
종합소득세 신고를 준비하려고 해. UMMAYA가 확인할 수 있는 공개 정보와 공식 홈택스에서 해야 하는 단계를 나눠서 알려줘.
```

These prompts work because they distinguish preparation from execution. If the user asks for immediate payment or filing, UMMAYA should require live authority, credential, consent, and receipt evidence before using `send`.

## Expected Flow

Payment and filing workflows often begin with public explanation, then move quickly into protected state. UMMAYA should keep those layers separate.

```text
User asks about tax, fine, payment, or utility work
  -> `find` retrieves public guidance or general path
  -> `check` may reveal that user-specific state requires authority
  -> `send` is allowed only with live official channel and consent
  -> Handoff if the next step must happen on the official service
```

The correct stop is not a failure. If no live official channel exists, UMMAYA should say that it prepared the path but did not file, pay, or change a record.

## Safe Result Shape

The final answer should divide the result into four parts: what UMMAYA found, what remains user-specific, what official service must continue the workflow, and what UMMAYA did not do.

| Need | Safe UMMAYA output | Unsafe output |
|---|---|---|
| Public filing guidance | steps, required documents, official service name | "your filing is done" |
| User-specific amount | consent-gated `check` or Handoff | guessed amount |
| Payment execution | live `send` with receipt evidence | mock payment described as paid |
| Receipt | Live receipt or clearly labeled mock receipt | unlabeled confirmation |

This language protects users from acting on false completion. It also gives evaluators a clear test: every completion word must be backed by tool evidence.

## Why This Needs Strong Language

A false answer in this domain can create real harm. A user could miss a deadline, believe a fine was paid, assume a filing was accepted, or share credentials in the wrong place. UMMAYA should therefore prefer explicit boundary wording over impressive phrasing.

Use phrases like `prepared`, `identified`, `requires official login`, `not submitted`, and `continue through the official service`. Avoid `paid`, `filed`, `accepted`, `approved`, or `changed` unless the live result proves it.

## Recovery

When a protected payment or filing flow stops, the answer should still be useful. It should tell the user which official service to open, what information to prepare, what consent or credential is missing, and what evidence would be required for UMMAYA to perform that step live in the future.

The target state is not to make payment boundaries disappear. The target state is to make the path understandable while keeping official authority visible.
