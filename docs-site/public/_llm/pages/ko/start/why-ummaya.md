---
title: 왜 UMMAYA인가
description: UMMAYA가 국가 인프라 AX harness로 존재해야 하는 이유입니다.
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

UMMAYA는 사용자의 관점에서 한국 공공서비스 업무가 너무 흩어져 있기 때문에 존재합니다. 하나의 life event가 portal, agency, identity rail, certificate, payment, local record, welfare rule, healthcare data, safety source, public-data API를 동시에 건드릴 수 있습니다. 사용자는 outcome을 요청하기 전에 이 지도를 먼저 이해할 필요가 없어야 합니다.

UMMAYA의 목표는 대한민국 국가 인프라 AX입니다. 흩어진 public-service domain 위에 하나의 접근하기 쉬운 query surface를 만들고, 시스템이 decomposition, tool selection, permission boundary, evidence, official handoff를 처리하게 하는 것입니다.

## 사용자 문제

사용자 문제는 단지 공공서비스 웹사이트가 여러 곳에 있다는 것이 아닙니다. 더 깊은 문제는 사용자가 실제 필요를 agency, form, credential, portal의 언어로 번역해야만 업무를 시작할 수 있다는 점입니다.

예를 들어 “이사했어”는 address resolution, local government records, utilities, vehicle or parking rules, housing documents, official handoff를 포함할 수 있습니다. “지원이 필요해”는 welfare guidance, household documents, eligibility boundaries, application channels를 포함할 수 있습니다. 사용자의 intent는 한 문장이지만 infrastructure path는 multi-domain입니다.

UMMAYA는 official authority가 사라진 것처럼 말하지 않으면서 이 translation burden을 줄이도록 설계됩니다.

## 제품 주장

UMMAYA는 사람이 public-service outcome을 질문하고 무슨 일이 일어났는지 볼 수 있게 해야 합니다. 유용한 답변은 어떤 단계가 public lookup인지, 어떤 단계가 consent를 요구하는지, 어떤 단계가 Mock인지, 어떤 단계가 Handoff인지 보여줘야 합니다.

그래서 UMMAYA는 일반 chatbot이 아니라 agent harness입니다. chatbot은 evidence 없이도 service를 설명하며 권위적으로 들릴 수 있습니다. UMMAYA는 context, retrieval, primitive choice, validation, permission, adapter execution, stop reason으로 이어지는 controlled loop에 답변을 연결해야 합니다.

## 작동 방식

UMMAYA는 public-service channel과 policy-shaped workflow를 tool로 감쌉니다. model은 현재 `locate`, `find`, `check`, `send`라는 작은 primitive surface를 보고, adapter layer가 domain detail, schema, status, citation, permission metadata를 보유합니다.

query engine은 다음 단계가 location resolution인지, public lookup인지, protected checking인지, submission preparation인지, Handoff인지 결정합니다. 이 결정이 national AX의 핵심입니다. 사용자는 outcome으로 말하고, 시스템은 routing과 evidence를 처리합니다.

## 왜 Claude Code를 reference로 삼는가

Claude Code는 tool use, permission prompt, context assembly, session continuity, terminal UX를 하나의 working harness로 결합했기 때문에 reference입니다. UMMAYA는 이 harness pattern을 developer work에서 public-service work로 migration합니다.

허용된 swap은 좁습니다. model provider는 FriendliAI의 K-EXAONE으로, tool surface는 file, shell, git, code tools에서 한국 public-service tools로 바뀝니다. bounded tool use, permission, context, visible progress의 discipline은 유지되어야 합니다.

## 이 사이트가 증명해야 하는 것

이 사이트는 과장 없이 설득해야 합니다. UMMAYA가 오늘 무엇을 할 수 있는지, 무엇이 Mock 또는 Handoff인지, packaged CLI를 어떻게 설치하는지, 첫 성공 session이 어떤 모습인지, architecture가 public-service claim을 어떻게 grounded하게 만드는지 보여줘야 합니다.

문서가 UMMAYA를 official government service처럼 들리게 만들면 실패입니다. 반대로 일반 chatbot처럼 들리게 해도 실패입니다. 정확한 약속은 더 좁고 강합니다. 하나의 query surface, tool-backed evidence, visible boundaries, honest official handoff입니다.
