---
title: LLMOps For Docs
description: How UMMAYA keeps human docs, LLM-readable docs, generated metadata, and deployment outputs aligned.
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

UMMAYA documentation is an operated surface. Human pages, LLM-readable indexes, generated adapter data, workflow cards, and deployed static pages must describe the same product state.

LLMOps for docs exists to prevent drift. If an adapter changes, a scenario changes, a primitive name changes, or a status label changes, the docs should regenerate and reveal the mismatch before publication.

## The Quality Loop

The docs loop follows the same logic as the writing loop: prepare, organize, write, edit, rewrite, and verify.

```text
source artifacts change
  -> docs generator updates machine-readable surfaces
  -> human pages are reviewed for claim drift
  -> localized pages stay equivalent
  -> build verifies routes and search index
  -> Cloudflare Pages publishes the static site
```

This loop matters because LLM agents may read `llms.txt` and generated JSON before reading the human page. Those surfaces must not disagree.

Use the loop whenever a capability label changes. A single adapter promotion can affect user prose, coverage tables, LLM-readable JSON, localized pages, and trust language at the same time.

## Documentation Inputs

The generator uses stable project artifacts:

| Input | Output use |
|---|---|
| docs-site Markdown pages | human docs and LLM raw page copies |
| `docs/api/**` frontmatter | adapter metadata |
| `eval/scenarios/national_ax_citizen_requests_v1.yaml` | workflow cards |
| `docs/configuration.md` | environment variable data |
| `prompts/manifest.yaml` | prompt manifest summary |

These inputs are evidence surfaces. If a page makes a claim that none of these inputs can support, the page needs another source or weaker wording.

## Generated Surfaces

`scripts/docs_generate.py` writes:

- `docs-site/public/llms.txt`;
- `docs-site/public/llms-full.txt`;
- `docs-site/public/_llm/index.json`;
- `docs-site/public/_llm/pages.jsonl`;
- `docs-site/public/_llm/pages/*.md`;
- `docs-site/public/_llm/generated/*.json`;
- `docs-site/src/data/generated/*.json`.

These outputs let humans, LLM agents, and CI inspect the same state. They are not decorative exports.

## CI Rule

CI should fail when generated surfaces are stale or the docs site cannot build.

```bash
npm run docs:generate
npm run docs:check
```

`docs:check` reruns generation in check mode and builds the Astro/Starlight site. A passing build does not prove the prose is good, but it proves the generated surfaces and routes are coherent enough to publish.

The prose audit still happens before or after CI. CI catches stale artifacts; the writing skill catches shallow, unsupported, or overclaiming documentation.

## Writing Rule

Generated data does not replace writing. A table can list adapters, but the page still needs a reader claim, explanation, evidence, boundary, and next action.

When docs feel thin, do not add more generated fields first. Apply the writing skill: define the reader question, split MECE axes, write Power 1-2-3-4 paragraphs, then point to generated evidence.

## Deployment Rule

After publishing, verify representative localized routes and critical generated files. The docs are only useful if the public site serves the same content that passed local checks.

For UMMAYA, deployment verification should include at least one Start page, one Trust page, one Use page, one generated LLM file, and any changed static asset. That confirms both reader-facing and agent-facing surfaces moved together.
