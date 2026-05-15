---
title: "Docs のための LLMOps"
description: "UMMAYA が human docs、LLM-readable docs、generated metadata、deployment outputs を aligned に保つ方法。"
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

UMMAYA documentation は operated surface です。Human pages、LLM-readable indexes、generated adapter data、workflow cards、deployed static pages は同じ product state を説明しなければなりません。

docs LLMOps は drift を防ぐために存在します。adapter、scenario、primitive name、status label が変わったら、docs は regenerate され、publication 前に mismatch が visible になるべきです。

## Quality Loop

docs loop は writing loop と同じ論理です。prepare、organize、write、edit、rewrite、verify です。

```text
source artifacts change
  -> docs generator updates machine-readable surfaces
  -> human pages are reviewed for claim drift
  -> localized pages stay equivalent
  -> build verifies routes and search index
  -> Cloudflare Pages publishes the static site
```

この loop が重要なのは、LLM agents が human page より先に `llms.txt` と generated JSON を読む可能性があるためです。これら surfaces は disagree してはいけません。

capability label が変わるたびに loop を使います。一つの adapter promotion は user prose、coverage tables、LLM-readable JSON、localized pages、trust language を同時に変える可能性があります。

## Documentation Inputs

generator は stable project artifacts を使います。

| Input | Output use |
|---|---|
| docs-site Markdown pages | human docs and LLM raw page copies |
| `docs/api/**` frontmatter | adapter metadata |
| `eval/scenarios/national_ax_citizen_requests_v1.yaml` | workflow cards |
| `docs/configuration.md` | environment variable data |
| `prompts/manifest.yaml` | prompt manifest summary |

これら inputs は evidence surfaces です。page の claim をどの input も support できない場合、page は another source または weaker wording を必要とします。

## Generated Surfaces

`scripts/docs_generate.py` は次を書きます。

- `docs-site/public/llms.txt`;
- `docs-site/public/llms-full.txt`;
- `docs-site/public/_llm/index.json`;
- `docs-site/public/_llm/pages.jsonl`;
- `docs-site/public/_llm/pages/*.md`;
- `docs-site/public/_llm/generated/*.json`;
- `docs-site/src/data/generated/*.json`.

これら outputs は humans、LLM agents、CI が同じ state を inspect できるようにします。decorative exports ではありません。

## CI Rule

generated surfaces が stale または docs site が build できないとき、CI は fail するべきです。

```bash
npm run docs:generate
npm run docs:check
```

`docs:check` は check mode で generation を再実行し、Astro/Starlight site を build します。passing build は prose が良い証明ではありませんが、generated surfaces と routes が publish できる程度に coherent であることを示します。

prose audit は CI の前後に行います。CI は stale artifacts を捕まえ、writing skill は shallow、unsupported、overclaiming documentation を捕まえます。

## Writing Rule

generated data は writing を置き換えません。table は adapters を list できますが、page には reader claim、explanation、evidence、boundary、next action が必要です。

docs が thin に感じるとき、generated fields を先に増やさないでください。writing skill を使います。reader question を定義し、MECE axes を分け、Power 1-2-3-4 paragraphs を書き、generated evidence に接続します。

## Deployment Rule

publishing 後、representative localized routes と critical generated files を verify します。public site が local checks を通過した内容と同じ content を serve しているときだけ docs は有用です。

UMMAYA の deployment verification には少なくとも Start page 一つ、Trust page 一つ、Use page 一つ、generated LLM file 一つ、changed static asset を含めます。reader-facing と agent-facing surfaces が一緒に移動したことを確認するためです。
