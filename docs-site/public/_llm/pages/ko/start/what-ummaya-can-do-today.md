---
title: UMMAYA가 오늘 할 수 있는 일
description: 현재 capability를 user task, status label, evidence boundary로 설명합니다.
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- docs-site/src/data/generated/adapters.json
- eval/scenarios/national_ax_citizen_requests_v1.yaml
audience:
- considering_user
- new_user
- public_sector_evaluator
---

UMMAYA는 이미 core national AX pattern을 보여줄 수 있습니다. 사용자가 public-service outcome을 묻고, 시스템이 intent를 해석하고, tool path를 선택하고, visible status boundary가 있는 답변을 반환하는 흐름입니다. 현재 표면은 public lookup, location-dependent information, preparation flow에서 가장 강합니다.

Protected action은 live authority, credentials, official callable channels, consent, evidence가 준비되기 전까지 대부분 Mock 또는 Handoff입니다. 이 제한은 숨기지 않습니다. 제품의 trust model입니다.

## 사용자 task별 현재 capability

이 표는 internal adapter name이 아니라 task 기준으로 읽어야 합니다. final protected action이 live가 아니어도 task는 오늘 유용할 수 있습니다.

| User task | Current state | UMMAYA 동작 |
|---|---|---|
| 근처 병원 또는 응급 관련 공개 정보 찾기 | public lookup adapter는 Live | 장소 해석, public healthcare/emergency adapter 호출, source-backed result 요약 |
| 날씨, 예보, 경보, 도로, 안전 정보 확인 | public-data adapter는 Live | public data 조회, recency와 uncertainty 명시, personal-account claim 회피 |
| 주소, 좌표, 행정구역 해석 | location adapter는 Live | public-service lookup 전에 location normalization |
| 복지 정보와 준비 단계 탐색 | public guidance는 Live, protected application은 Mock/Handoff | guidance 조회, 문서 준비, official eligibility boundary 표시 |
| 신원, 증명서, MyData, 인증 flow 시도 | Mock 또는 Handoff | official verification 주장 없이 consent shape 표시 |
| 과태료 납부, 신청 제출, 세금 신고, official record 변경 | live channel 없으면 Mock 또는 Handoff | prepare, label, handoff; evidence 없이 official completion 주장 금지 |

중요한 단어는 state입니다. Live public lookup과 Mock protected workflow는 둘 다 유용할 수 있지만 의미가 다르며 final answer에서도 다르게 들려야 합니다.

## 먼저 시도할 것

safe public lookup으로 시작하세요. 장소를 주고 공식 공개 정보를 요청합니다.

```text
동아대 승학캠퍼스 근처 응급실이나 야간 진료 정보를 공식 정보 기준으로 찾아줘.
```

이 prompt는 첫 테스트로 좋습니다. 장소를 주고, 공개 정보를 요청하며, identity verification, payment, filing, certificate issuance, official record change를 요구하지 않습니다.

## Live, Mock, Handoff 읽는 법

Live는 UMMAYA가 configured channel을 호출하고 result에 grounded하게 답할 수 있다는 뜻입니다. Mock은 workflow shape를 demonstration할 수 있지만 official agency result가 아니라는 뜻입니다. Handoff는 UMMAYA가 safe callable path를 갖고 있지 않아 사용자가 official service에서 이어가야 한다는 뜻입니다.

이 구분은 법적 footnote가 아닙니다. 사용자가 evidence, simulation, official next step 중 무엇을 보고 있는지 알려줍니다. 답변은 사용자가 행동하기 전에 이 state를 보여줘야 합니다.

## Target-State란 무엇인가

target-state scenario dataset은 tax, civil affairs, payments, utilities, identity, welfare, healthcare, housing, mobility, business, labor, education, safety, immigration, legal, personal-data workflow를 다룹니다. 이 scenario가 모두 오늘 live라는 뜻은 아닙니다.

그 dataset은 national AX system이 결국 처리해야 할 것과, official channel이 성숙하기 전까지 UMMAYA가 gap을 어떻게 label해야 하는지를 정의합니다. 어떤 domain은 목표에 포함될 수 있지만 오늘 완료된 capability로 설명되면 안 됩니다.

## 다음 단계

capability를 읽은 뒤 [Quickstart](/ko/start/quickstart/)에서 packaged CLI를 설치하고 public lookup 하나를 실행하세요. 그 다음 protected workflow를 테스트하기 전에 [Live, Mock, And Handoff](/ko/trust/live-mock-handoff/)를 읽으세요.
