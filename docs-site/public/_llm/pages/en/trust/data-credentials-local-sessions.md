---
title: Data, Credentials, And Local Sessions
description: What UMMAYA stores locally, what credentials mean, and how session evidence
  should remain inspectable.
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- specs/033-permission-v2-spectrum-consent-ledger/spec.md
- docs/vision.md
audience:
- citizen_user
- public_sector_evaluator
- maintainer
---

UMMAYA should keep user trust by making data, credentials, and session state understandable. A national-infrastructure assistant can be useful only if the user knows what is local, what belongs to a provider, and what was not sent to an official service.

This page explains the trust model at the user level. It is not a secret-storage specification, but it gives readers the questions they should ask before protected workflows.

## What The First Login Means

The first login or provider setup lets UMMAYA reach the model provider. It does not give UMMAYA government authority, identity credentials, certificate access, payment rights, or permission to change official records.

That distinction matters because provider access and public-service authority are different layers. A working model session can still stop at Handoff when the public-service step requires official login or consent.

## Credentials

Credentials should be treated as scoped authority, not convenience strings. If a workflow requires agency login, identity verification, certificate signing, payment authorization, or account-specific data, UMMAYA must show the boundary before proceeding.

The docs should never imply that UMMAYA has hidden credentials. If a credential path is not configured and validated, the correct language is Mock, Handoff, or Planned.

## Local Sessions

Local sessions help UMMAYA preserve context across long workflows. They may include request text, resolved location, selected adapter, status labels, tool summaries, permission state, stop reason, and final answer.

Local session state should support inspection. It should help the user or maintainer answer what happened, what evidence was returned, what was consented to, and where the workflow stopped.

## What To Check Before A Protected Flow

Before trying a protected flow, check three things:

| Question | Why it matters |
|---|---|
| Is the step Live, Mock, or Handoff? | Prevents fake completion |
| What credential or consent is required? | Shows whether UMMAYA has authority |
| What receipt or evidence will exist? | Makes the result inspectable |

If any answer is unclear, the safer action is to stop or continue through the official service.

## Recovery

If a session, credential, or receipt state is unclear, UMMAYA should downgrade its language. It can say it prepared, found, or explained a path. It should not say it filed, paid, verified, issued, or changed a record without visible evidence.

Trust comes from the ability to inspect the boundary after the answer, not only from the answer sounding helpful.
