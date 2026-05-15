---
title: Identity, Certificates, And MyData
description: Understand identity-bound workflows that usually require Mock or official
  Handoff today.
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- docs-site/src/data/generated/adapters.json
- eval/scenarios/national_ax_citizen_requests_v1.yaml
audience:
- citizen_user
- considering_user
- public_sector_evaluator
---

Identity, certificates, and MyData are central to Korean national-infrastructure AX, but they are also the domains where UMMAYA must be most conservative. A useful assistant can explain the path, prepare the user, and demonstrate the permission shape. It cannot pretend to verify identity, issue a certificate, sign a document, or read personal data without a live official channel, credential, consent, and evidence.

This page is for users who want to understand what UMMAYA can safely do around identity-bound work today. The short version is: public explanations can be useful, mock flows can show the shape, and official Handoff is often the correct stopping point.

## Good Prompt

Ask for preparation, official path explanation, or permission boundary instead of asking UMMAYA to silently complete a protected action.

```text
주민등록등본 발급을 준비하려고 해. 필요한 인증 단계와 공식 서비스에서 이어서 해야 할 일을 정리해줘.
```

```text
MyData로 필요한 서류를 확인하는 흐름을 보여줘. 실제 개인 데이터 접근 없이 Mock 기준으로 어디서 consent가 필요한지 알려줘.
```

These prompts are productive because they let UMMAYA explain and prepare without claiming hidden authority. If a user asks "issue it now" or "log in for me", the system should move to permission or Handoff, not invent access.

## Expected Flow

Identity-bound work usually starts with `find`, may move to `check`, and often stops before `send`. Public guidance can describe what the official service requires. Mock can demonstrate the consent and schema shape. Handoff sends the user to the official service when live authority is missing.

| Step | UMMAYA behavior | Boundary |
|---|---|---|
| Public explanation | `find` retrieves official guidance or known public material | Explanation only |
| Identity boundary | `check` exposes consent and credential requirements | Mock unless live authority exists |
| Certificate or MyData action | `send` only with official channel, credential, consent, and evidence | Otherwise Handoff |

The important point is sequence. UMMAYA should not jump from a public explanation to "completed certificate issuance." It should show which step became protected and why the official path must take over.

## What Must Be Visible

An identity answer should tell the user what data would be involved, what consent would be required, which system is official, and what UMMAYA did not do. The visible answer should label Live, Mock, or Handoff near the protected step, not hide it in a footnote.

For evaluators, this page is also a contract. A correct flow should leave evidence that the adapter mode, permission decision, and stop reason matched the final wording. If the final answer says "issued" but the flow only reached Mock, the documentation and product language are wrong.

## Why Mocks Still Matter

Mocks are valuable when they are unmistakably labeled. They let UMMAYA test the UX of consent prompts, schema validation, tool calling, receipts, and handoff copy before live credentials or official channels are available.

The value disappears if the mock looks official. A mock identity verification is not identity verification. A mock certificate result is not a certificate. The answer must make that difference impossible to miss.

## Recovery

When UMMAYA hands off, the user should know what to carry forward: the official service name, required authentication type, documents or data likely needed, and the exact step UMMAYA could not perform. That makes Handoff useful instead of evasive.

The product promise is not "UMMAYA bypasses identity rails." The promise is "UMMAYA reduces confusion until the official identity rail must take over."
