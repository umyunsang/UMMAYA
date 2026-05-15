---
title: Sessions, Receipts, And History
description: Understand how UMMAYA keeps long workflows inspectable across sessions,
  receipts, and context compression.
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- specs/033-permission-v2-spectrum-consent-ledger/spec.md
audience:
- citizen_user
- public_sector_evaluator
- maintainer
---

Sessions, receipts, and history make UMMAYA inspectable after the first answer. National AX workflows can span several turns: a location is resolved, public information is fetched, a protected boundary appears, the user returns later, and the system must remember why it stopped.

The purpose is not to store everything forever. The purpose is to preserve enough structured evidence for the user, evaluator, or maintainer to understand what happened, what was allowed, what was Mock, and what still requires an official path.

## Sessions

A session should keep the working context for a public-service flow: the user's request, resolved location, selected adapter, permission state, tool result, stop reason, and final answer. Without this continuity, a multi-step public-service task becomes a repeated conversation instead of a workflow.

When available, resume with a command like:

```bash
ummaya resume <session-id>
```

The resumed session should not silently upgrade authority. If a previous turn stopped at Handoff, the next turn should still know that the protected step was not completed.

## Receipts

A receipt should make permission and action state visible. It should identify the adapter, mode, purpose, timestamp, policy citation, outcome, and whether the result was Live or Mock.

A mock receipt is not an agency receipt. It is evidence that UMMAYA simulated a workflow shape. The receipt must label that state so the user does not confuse a mock with official completion.

| Receipt field | Why it matters |
|---|---|
| Adapter and primitive | Shows what tool path ran |
| Mode | Distinguishes Live, Mock, and Handoff |
| Purpose | Explains why the action was attempted |
| Permission or consent state | Shows whether protected work was allowed |
| Outcome and stop reason | Explains what happened and what did not |

## History

History should help the user answer practical questions: what did I ask, what public information was found, what step required consent, what official service remains, and what should I do next.

History should not hide sensitive data inside a friendly transcript. If protected data appears, it must follow the same local-session and consent rules as the runtime flow. If a field is unnecessary for future reasoning or inspection, it should not be retained just because it is convenient.

## Context Compression

Context compression supports long sessions by keeping useful state while preventing the model context from becoming unmanageable. It should compress the reasoning surface, not erase the evidence boundary.

If compression removes detail from the model prompt, generated outputs and receipts still need enough structure for inspection. The compressed context should preserve the resolved location, adapter result summary, permission decision, Live/Mock/Handoff state, and stop reason.

## Recovery

If a session cannot resume or a receipt is missing, UMMAYA should say what evidence is unavailable and avoid making completion claims. A missing receipt should turn strong wording into cautious wording: prepared, found, suggested, or handed off, not filed, paid, issued, or approved.
