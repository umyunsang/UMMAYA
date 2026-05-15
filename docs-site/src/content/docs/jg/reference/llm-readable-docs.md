---
title: "LLM-Readable Docs"
description: "agents が site scraping なしに UMMAYA を inspect できる generated documentation surfaces。"
llm_index: true
audience:
  - llm_agent
  - maintainer
  - public_sector_evaluator
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - scripts/docs_generate.py
---

LLM-readable docs は human readers と同じ boundaries を agents に与えます。UMMAYA は agentic infrastructure project なので、修正、評価、説明を行う agents は pages、adapters、workflows、environment variables、prompt metadata の stable machine-readable surfaces を必要とします。

これら files は hidden second documentation system になってはいけません。public docs site と同じ content と source artifacts から生成されるべきです。

## Outputs

docs generator は次の surfaces を書きます。

| Path | Purpose |
|---|---|
| `/llms.txt` | compact page index for agents |
| `/llms-full.txt` | full text bundle for broader reading |
| `/_llm/index.json` | structured page metadata |
| `/_llm/pages.jsonl` | one page record per line |
| `/_llm/pages/*.md` | raw Markdown page copies |
| `/_llm/generated/*.json` | adapter, workflow, env-var, and prompt data |

agents は rendered HTML を scraping するよりこれら files を優先するべきです。docs の intended structure と generated metadata を preserve するからです。

## Why It Matters

UMMAYA agents は national AX purpose、Live/Mock/Handoff labels、primitive names、adapter evidence、official handoff limits を preserve する必要があります。agent が stale または partial docs を読むと、public-service authority を overclaim する code や prose を書く可能性があります。

したがって LLM-readable surface は safety tool です。future agents に user が見るのと同じ boundaries を与えます。

## Freshness Rule

docs、adapter metadata、scenarios、configuration、prompt manifest が変わったら surfaces を regenerate します。

```bash
npm run docs:generate
```

publishing 前には check mode を使います。

```bash
npm run docs:check
```

check mode が fail したら deploy しないでください。stale generated files は human readers と LLM agents の両方を誤解させます。

## Review Rule

generated files は agent に何が変わったかを伝えられますが、prose が persuasive で safe かは決められません。maintainer は human pages の reader outcome、evidence、boundary、translation equivalence を review し続ける必要があります。

正しい状態は alignment です。public page、raw Markdown copy、generated JSON、final deployed site が同じ story を伝えるべきです。
