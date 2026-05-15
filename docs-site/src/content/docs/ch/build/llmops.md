---
title: "面向文档的 LLMOps"
description: "UMMAYA 如何保持 human docs、LLM-readable docs、generated metadata 和 deployment outputs 对齐。"
llm_index: true
audience:
  - maintainer
  - llm_agent
  - public_sector_evaluator
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - scripts/docs_generate.py
  - .github/workflows/docs.yml
---

UMMAYA documentation 是被运营的 surface。Human pages、LLM-readable indexes、generated adapter data、workflow cards 和 deployed static pages 必须描述同一个 product state。

docs LLMOps 的目的就是防止 drift。如果 adapter、scenario、primitive name 或 status label 改变，docs 应重新生成，并在 publication 前暴露 mismatch。

## Quality Loop

docs loop 与 writing loop 遵循同一逻辑：prepare、organize、write、edit、rewrite、verify。

```text
source artifacts change
  -> docs generator updates machine-readable surfaces
  -> human pages are reviewed for claim drift
  -> localized pages stay equivalent
  -> build verifies routes and search index
  -> Cloudflare Pages publishes the static site
```

这个 loop 重要，因为 LLM agents 可能先读 `llms.txt` 和 generated JSON，再读 human page。这些 surfaces 不能互相矛盾。

capability label 改变时都使用这个 loop。一个 adapter promotion 可能同时影响 user prose、coverage tables、LLM-readable JSON、localized pages 和 trust language。

## Documentation Inputs

generator 使用稳定 project artifacts：

| Input | Output use |
|---|---|
| docs-site Markdown pages | human docs and LLM raw page copies |
| `docs/api/**` frontmatter | adapter metadata |
| `eval/scenarios/national_ax_citizen_requests_v1.yaml` | workflow cards |
| `docs/configuration.md` | environment variable data |
| `prompts/manifest.yaml` | prompt manifest summary |

这些 inputs 是 evidence surfaces。如果页面声称的内容没有这些 input 支撑，就需要另一个 source 或更弱 wording。

## Generated Surfaces

`scripts/docs_generate.py` 写入：

- `docs-site/public/llms.txt`;
- `docs-site/public/llms-full.txt`;
- `docs-site/public/_llm/index.json`;
- `docs-site/public/_llm/pages.jsonl`;
- `docs-site/public/_llm/pages/*.md`;
- `docs-site/public/_llm/generated/*.json`;
- `docs-site/src/data/generated/*.json`.

这些 outputs 让人类、LLM agents 和 CI 检查同一状态。它们不是装饰性 exports。

## CI Rule

CI 应在 generated surfaces stale 或 docs site 无法 build 时失败。

```bash
npm run docs:generate
npm run docs:check
```

`docs:check` 会在 check mode 中重新运行 generation，并 build Astro/Starlight site。build 通过不能证明 prose 好，但证明 generated surfaces 和 routes 足够 coherent，可以 publish。

prose audit 仍需要在 CI 前后执行。CI 抓 stale artifacts；writing skill 抓 shallow、unsupported 或 overclaiming documentation。

## Writing Rule

generated data 不替代 writing。table 可以列 adapters，但页面仍需要 reader claim、explanation、evidence、boundary 和 next action。

当 docs 感觉 thin 时，不要先添加更多 generated fields。先应用 writing skill：定义 reader question，分出 MECE axes，写 Power 1-2-3-4 paragraphs，再指向 generated evidence。

## Deployment Rule

publish 后验证代表性的 localized routes 和关键 generated files。只有 public site 提供的内容与 local checks 通过的内容一致，docs 才真正有用。

UMMAYA 的 deployment verification 至少应包含一个 Start page、一个 Trust page、一个 Use page、一个 generated LLM file，以及任何 changed static asset。这样能确认 reader-facing 和 agent-facing surfaces 一起移动。
