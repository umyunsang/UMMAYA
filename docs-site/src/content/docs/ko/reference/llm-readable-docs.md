---
title: "LLM-Readable Docs"
description: "agent가 site scraping 없이 UMMAYA를 검사할 수 있게 하는 generated documentation surface입니다."
llm_index: true
audience:
  - llm_agent
  - maintainer
  - public_sector_evaluator
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - scripts/docs_generate.py
---

LLM-readable docs는 human reader가 보는 경계를 agent에게도 제공합니다. UMMAYA는 agentic infrastructure project이기 때문에, UMMAYA를 수정하거나 평가하거나 설명하는 agent는 page, adapter, workflow, environment variable, prompt metadata를 안정적인 machine-readable surface에서 읽을 수 있어야 합니다.

이 파일들은 숨겨진 두 번째 문서 시스템이 되면 안 됩니다. public docs site를 구성하는 같은 content와 source artifact에서 생성되어야 하며, human page와 다른 권한이나 capability를 말하면 안 됩니다.

## 출력

docs generator는 다음 표면을 작성합니다.

| 경로 | 목적 |
|---|---|
| `/llms.txt` | agent용 compact page index |
| `/llms-full.txt` | 더 넓은 reading을 위한 full text bundle |
| `/_llm/index.json` | structured page metadata |
| `/_llm/pages.jsonl` | line 단위 page record |
| `/_llm/pages/*.md` | raw Markdown page copy |
| `/_llm/generated/*.json` | adapter, workflow, env-var, prompt data |

agent는 rendered HTML을 scrape하기보다 이 파일들을 우선해야 합니다. 이 표면들은 문서가 의도한 구조와 generated metadata를 보존하고, route layout이나 theme 변경의 영향을 덜 받습니다.

## 중요한 이유

UMMAYA agent는 국가 인프라 AX 목적, Live/Mock/Handoff label, primitive 이름, adapter evidence, official handoff limit을 보존해야 합니다. agent가 오래되었거나 일부만 남은 문서를 읽으면 공공서비스 권한을 과장하는 코드나 prose를 작성할 수 있습니다.

따라서 LLM-readable surface는 편의 기능이 아니라 안전 도구입니다. 미래 agent에게 사용자가 보는 것과 같은 경계를 전달하고, "이 channel은 Live인지 Mock인지", "이 행동은 permission을 요구하는지", "여기서 official handoff가 필요한지"를 구조적으로 남깁니다.

## 최신성 규칙

docs, adapter metadata, scenario, configuration, prompt manifest가 바뀐 뒤에는 surface를 재생성합니다.

```bash
npm run docs:generate
```

publish 전에는 check mode를 사용합니다.

```bash
npm run docs:check
```

check mode가 실패하면 deploy하지 않습니다. stale generated file은 human reader뿐 아니라 LLM agent도 오해하게 만들 수 있습니다. 특히 adapter 상태가 Mock에서 Live로 바뀌거나, primitive 이름이 바뀌거나, trust wording이 바뀐 경우에는 generated file과 localized prose를 함께 확인해야 합니다.

## 검토 규칙

generated file은 agent에게 무엇이 바뀌었는지 알려줄 수 있지만, prose가 설득력 있고 안전한지는 결정하지 못합니다. maintainer는 human page의 reader outcome, evidence, boundary, translation equivalence를 계속 검토해야 합니다.

올바른 상태는 alignment입니다. public page, raw Markdown copy, generated JSON, final deployed site가 모두 같은 이야기를 해야 합니다. 하나라도 다른 상태를 말하면 그 차이를 수정한 뒤 다시 generate/check/deploy 루프를 실행합니다.
