---
title: 문서를 위한 LLMOps
description: UMMAYA가 human docs, LLM-readable docs, generated metadata, deployment
  output을 같은 상태로 유지하는 방식입니다.
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- scripts/docs_generate.py
- .github/workflows/docs.yml
audience:
- maintainer
- llm_agent
- public_sector_evaluator
---

UMMAYA 문서는 운영되는 표면입니다. 사람이 읽는 페이지, LLM-readable index, generated adapter data, workflow card, 배포된 static page는 같은 제품 상태를 설명해야 합니다.

문서를 위한 LLMOps는 drift를 막기 위해 존재합니다. 어댑터, scenario, primitive 이름, status label이 바뀌면 문서는 재생성되어야 하고, publication 전에 불일치가 드러나야 합니다.

## 품질 루프

문서 루프는 글쓰기 루프와 같은 원리로 움직입니다. 준비하고, 조직하고, 쓰고, 편집하고, 다시 쓰고, 검증합니다.

```text
source artifacts change
  -> docs generator updates machine-readable surfaces
  -> human pages are reviewed for claim drift
  -> localized pages stay equivalent
  -> build verifies routes and search index
  -> Cloudflare Pages publishes the static site
```

이 루프가 중요한 이유는 LLM agent가 human page보다 `llms.txt`와 generated JSON을 먼저 읽을 수 있기 때문입니다. 그 표면들이 서로 다른 말을 하면, 미래 agent는 UMMAYA의 현재 권한보다 큰 주장을 코드나 문서에 다시 넣을 수 있습니다.

capability label이 바뀔 때마다 이 루프를 사용합니다. 어댑터 하나의 Live 승격도 사용자 prose, coverage table, LLM-readable JSON, localized page, trust language를 동시에 바꿀 수 있습니다.

## 문서 입력

generator는 안정적인 프로젝트 artifact를 입력으로 사용합니다. 이 입력은 "문서가 무엇을 근거로 말하는가"를 보여주는 증거 표면입니다.

| 입력 | 출력에서 쓰이는 곳 |
|---|---|
| docs-site Markdown pages | human docs와 LLM raw page copy |
| `docs/api/**` frontmatter | adapter metadata |
| `eval/scenarios/national_ax_citizen_requests_v1.yaml` | workflow card |
| `docs/configuration.md` | environment variable data |
| `prompts/manifest.yaml` | prompt manifest summary |

페이지가 이 입력 중 어디에서도 뒷받침되지 않는 주장을 한다면, 그 페이지는 별도 source를 추가하거나 표현을 약하게 바꿔야 합니다. 문서의 설득력은 강한 표현이 아니라 근거와 경계가 같은 방향을 가리킬 때 생깁니다.

## 생성되는 표면

`scripts/docs_generate.py`는 다음 파일을 씁니다.

- `docs-site/public/llms.txt`;
- `docs-site/public/llms-full.txt`;
- `docs-site/public/_llm/index.json`;
- `docs-site/public/_llm/pages.jsonl`;
- `docs-site/public/_llm/pages/*.md`;
- `docs-site/public/_llm/generated/*.json`;
- `docs-site/src/data/generated/*.json`.

이 출력들은 사람, LLM agent, CI가 같은 상태를 검사하게 해줍니다. 장식용 export가 아닙니다. 특히 UMMAYA처럼 국가 인프라 AX를 다루는 프로젝트에서는 오래된 generated file 하나가 과장된 capability claim으로 이어질 수 있습니다.

## CI 규칙

CI는 generated surface가 오래되었거나 docs site가 build되지 않을 때 실패해야 합니다.

```bash
npm run docs:generate
npm run docs:check
```

`docs:check`는 generation을 check mode로 다시 실행하고 Astro/Starlight site를 build합니다. build 통과가 prose 품질을 증명하지는 않습니다. 그러나 generated surface와 route가 publish 가능한 정도로 일관되어 있음을 확인합니다.

prose audit는 CI 전후에 별도로 해야 합니다. CI는 stale artifact를 잡고, writing skill은 얕은 설명, unsupported claim, overclaiming documentation을 잡습니다.

## 글쓰기 규칙

generated data는 글쓰기를 대체하지 않습니다. table은 adapter를 나열할 수 있지만, 페이지에는 여전히 reader claim, explanation, evidence, boundary, next action이 필요합니다.

문서가 얇게 느껴질 때는 generated field를 먼저 늘리지 않습니다. writing skill을 적용합니다. reader question을 정하고, MECE 축을 나누고, Power 1-2-3-4 paragraph를 작성한 뒤, generated evidence를 연결합니다.

이 규칙은 번역에도 적용됩니다. 한국어, 영어, 중국어, 일본어 페이지는 fallback이 아니라 같은 구조와 같은 경계를 가진 first-class documentation이어야 합니다.

## 배포 규칙

publish 뒤에는 대표 localized route와 핵심 generated file을 확인해야 합니다. 문서는 local check를 통과한 내용이 public site에서도 같은 형태로 제공될 때만 의미가 있습니다.

UMMAYA 배포 검증은 최소한 Start page 하나, Trust page 하나, Use page 하나, generated LLM file 하나, 변경된 static asset 하나를 포함해야 합니다. 이렇게 해야 reader-facing surface와 agent-facing surface가 함께 이동했음을 확인할 수 있습니다.
