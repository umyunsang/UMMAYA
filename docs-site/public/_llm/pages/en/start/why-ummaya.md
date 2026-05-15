---
title: Why UMMAYA
description: Why UMMAYA exists as a national-infrastructure AX harness.
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- docs/vision.md
- docs/requirements/ummaya-migration-tree.md
- eval/scenarios/national_ax_citizen_requests_v1.yaml
audience:
- non_user
- considering_user
- public_sector_evaluator
---

UMMAYA exists because Korean public-service work is fragmented from the user's point of view. A single life event can touch portals, agencies, identity rails, certificates, payments, local records, welfare rules, healthcare data, safety sources, and public-data APIs. The user should not have to understand that map before asking for an outcome.

UMMAYA's goal is Korean national-infrastructure AX: one approachable query surface over scattered public-service domains. The system should decompose the request, choose tools, ask for permission when needed, return evidence, and stop honestly when the official path must take over.

## The User Problem

The user problem is not only that public-service websites exist in many places. The deeper problem is that the user must translate a real-life need into the language of agencies, forms, credentials, and portals before any work can begin.

For example, "I moved" may involve address resolution, local government records, utilities, vehicle or parking rules, housing documents, and official handoff. "I need support" may involve welfare guidance, household documents, eligibility boundaries, and application channels. The user's intent is one sentence, but the infrastructure path is multi-domain.

UMMAYA is designed to absorb that translation burden without pretending that official authority disappears.

## The Product Claim

UMMAYA should let a person ask for a public-service outcome and then see what happened. A useful answer should show which step was public lookup, which step required consent, which step was Mock, and which step became Handoff.

That is why UMMAYA is an agent harness rather than a general chatbot. A chatbot can explain a service and still sound authoritative without evidence. UMMAYA must connect the answer to a controlled loop: context, retrieval, primitive choice, validation, permission, adapter execution, and stop reason.

## The Mechanism

UMMAYA wraps public-service channels and policy-shaped workflows as tools. The model sees a small primitive surface, currently `locate`, `find`, `check`, and `send`, while the adapter layer carries domain detail, schema, status, citation, and permission metadata.

The query engine decides whether the next step is location resolution, public lookup, protected checking, submission preparation, or Handoff. That decision is the core of national AX: the user speaks in outcomes, while the system handles routing and evidence.

## Why Claude Code Is The Reference

Claude Code is the reference because it joins tool use, permission prompts, context assembly, session continuity, and terminal UX into one working harness. UMMAYA migrates that harness pattern from developer work to public-service work.

The sanctioned swaps are narrow. K-EXAONE on FriendliAI replaces the model provider, and Korean public-service tools replace files, shell, git, and code tools. The discipline around bounded tool use, permission, context, and visible progress should remain.

## What This Site Must Prove

This site must persuade without overclaiming. It should show what UMMAYA can do today, what is Mock or Handoff, how to install the packaged CLI, what a first successful session looks like, and how the architecture keeps public-service claims grounded.

If the docs make UMMAYA sound like an official government service, they fail. If they make UMMAYA sound like a normal chatbot, they also fail. The correct promise is narrower and stronger: one query surface, tool-backed evidence, visible boundaries, and honest official handoff.
