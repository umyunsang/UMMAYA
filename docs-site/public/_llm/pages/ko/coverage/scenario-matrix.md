---
title: Scenario Matrix
description: UMMAYA가 실제 public-service demand를 다루는지 판단하는 target-state citizen scenario입니다.
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- eval/scenarios/national_ax_citizen_requests_v1.yaml
audience:
- public_sector_evaluator
- maintainer
- llm_agent
---

scenario matrix는 UMMAYA의 demand-side map입니다. 한국 국가 인프라가 하나의 LLM-mediated interface로 접근 가능해졌을 때 시민이 자연스럽게 물어볼 일을 설명합니다.

adapter는 supply를 보여주고 scenario는 demand를 보여줍니다. UMMAYA에는 둘 다 필요합니다. 실제 사용자 수요 없는 tool surface는 API catalog가 되고, adapter evidence 없는 scenario writing은 marketing이 됩니다.

## Scenario Dataset에 포함된 것

현재 target-state dataset은 tax, civil affairs, payments, utilities, identity, welfare, healthcare, housing, mobility, business, labor, education, safety 등 24개 scenario를 포함합니다.

각 scenario는 다음을 기록합니다.

- citizen-style request text;
- lifecycle domain;
- agencies or infrastructure involved;
- expected primitive chain;
- permission requirements;
- evaluation focus;
- expected system behavior.

scenario는 반드시 Live promise가 아닙니다. current adapter, mock, handoff path가 향하는 target state를 설명할 수 있습니다.

## Docs가 Scenario를 사용하는 방식

workflow pages는 scenario를 사용해 realistic prompt와 expected flow를 작성해야 합니다. coverage pages는 scenario로 오늘 Live인 것과 target-state로 남은 것을 설명해야 합니다. architecture pages는 scenario로 query engine이 cross-domain work를 분해할 수 있는지 테스트해야 합니다.

page 뒤에 scenario, example, adapter, schema, trace, generated output 중 아무것도 없다면 그 page는 너무 추상적일 가능성이 큽니다. scenario는 national AX를 concrete user work로 바꾸는 방법 중 하나입니다.

## Active Primitive Translation

일부 older scenario material은 `lookup`, `resolve_location`, `verify`, `submit` 같은 label을 사용합니다. User docs는 active names인 `find`, `locate`, `check`, `send`로 보여줘야 합니다.

이 translation은 cosmetic하지 않습니다. docs, system prompt, adapter metadata, reader examples가 같은 vocabulary를 써야 request가 prose에서 tool behavior까지 trace됩니다.

## Evaluation Use

Evaluator는 각 scenario가 Live, Mock, Handoff, Planned 중 어떤 believable current state를 갖는지 확인해야 합니다. Live support가 없는 scenario도 가치가 있지만 complete로 설명되면 안 됩니다.

matrix는 ambition과 gap을 모두 드러낼 때 성공합니다. roadmap을 더 선명하게 만들어야지 target state까지의 거리를 숨기면 안 됩니다.
