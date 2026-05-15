---
title: LLM-Readable Docs
description: 让 agent 不用 scraping site 就能检查 UMMAYA 的 generated documentation surfaces。
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- scripts/docs_generate.py
audience:
- llm_agent
- maintainer
- public_sector_evaluator
---

LLM-readable docs 给 agent 与 human readers 相同的 boundaries。UMMAYA 是 agentic infrastructure project，因此修改、评估或解释它的 agents 需要稳定的 machine-readable surfaces，用于读取 pages、adapters、workflows、environment variables 和 prompt metadata。

这些文件不应变成隐藏的第二套文档系统。它们由支撑 public docs site 的同一 content 和 source artifacts 生成。

## Outputs

docs generator 写入这些 surfaces：

| Path | Purpose |
|---|---|
| `/llms.txt` | compact page index for agents |
| `/llms-full.txt` | full text bundle for broader reading |
| `/_llm/index.json` | structured page metadata |
| `/_llm/pages.jsonl` | one page record per line |
| `/_llm/pages/*.md` | raw Markdown page copies |
| `/_llm/generated/*.json` | adapter, workflow, env-var, and prompt data |

agents 应优先使用这些文件，而不是 scraping rendered HTML，因为它们保留了 docs 的 intended structure 和 generated metadata。

## Why It Matters

UMMAYA agents 需要保留 national AX purpose、Live/Mock/Handoff labels、primitive names、adapter evidence 和 official handoff limits。如果 agent 读取 stale 或 partial docs，就可能写出过度声称 public-service authority 的代码或 prose。

因此 LLM-readable surface 是 safety tool。它把用户看到的同一 boundaries 交给 future agents。

## Freshness Rule

docs、adapter metadata、scenarios、configuration 或 prompt manifest 改变后，重新生成 surfaces：

```bash
npm run docs:generate
```

publish 前使用 check mode：

```bash
npm run docs:check
```

如果 check mode 失败，不要 deploy。stale generated files 会误导 human readers 和 LLM agents。

## Review Rule

generated files 可以告诉 agent 什么变了，但不能决定 prose 是否有说服力且安全。maintainer 仍需 review human pages 的 reader outcome、evidence、boundary 和 translation equivalence。

正确状态是 alignment：public page、raw Markdown copy、generated JSON 和 final deployed site 讲同一个故事。
