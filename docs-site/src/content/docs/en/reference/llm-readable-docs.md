---
title: LLM-Readable Docs
description: The generated documentation surfaces that let agents inspect UMMAYA without scraping the site.
llm_index: true
audience:
  - llm_agent
  - maintainer
  - public_sector_evaluator
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - scripts/docs_generate.py
---

LLM-readable docs give agents the same boundaries that human readers see. UMMAYA is an agentic infrastructure project, so agents that modify, evaluate, or explain it need stable machine-readable surfaces for pages, adapters, workflows, environment variables, and prompt metadata.

These files should not become a hidden second documentation system. They are generated from the same content and source artifacts that power the public docs site.

## Outputs

The docs generator writes these surfaces:

| Path | Purpose |
|---|---|
| `/llms.txt` | compact page index for agents |
| `/llms-full.txt` | full text bundle for broader reading |
| `/_llm/index.json` | structured page metadata |
| `/_llm/pages.jsonl` | one page record per line |
| `/_llm/pages/*.md` | raw Markdown page copies |
| `/_llm/generated/*.json` | adapter, workflow, env-var, and prompt data |

Agents should prefer these files over scraping rendered HTML because they preserve the docs' intended structure and generated metadata.

## Why It Matters

UMMAYA agents need to preserve national AX purpose, Live/Mock/Handoff labels, primitive names, adapter evidence, and official handoff limits. If an agent reads stale or partial docs, it may write code or prose that overclaims public-service authority.

The LLM-readable surface is therefore a safety tool. It gives future agents the same boundaries the user sees.

## Freshness Rule

After docs, adapter metadata, scenarios, configuration, or prompt manifest changes, regenerate the surfaces:

```bash
npm run docs:generate
```

Use check mode before publishing:

```bash
npm run docs:check
```

If check mode fails, do not deploy. Stale generated files can mislead both human readers and LLM agents.

## Review Rule

Generated files can tell an agent what changed, but they cannot decide whether the prose is persuasive or safe. A maintainer should still review the human pages for reader outcome, evidence, boundary, and translation equivalence.

The correct state is alignment: public page, raw Markdown copy, generated JSON, and final deployed site all tell the same story.
