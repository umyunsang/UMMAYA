---
title: "Adapter Authoring"
description: "一つの public-service channel を evidence-bearing UMMAYA adapter として wrap する方法。"
llm_index: true
audience:
  - adapter_author
  - maintainer
  - public_sector_evaluator
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - docs/api/README.md
  - docs/plugins/security-review.md
---

adapter は UMMAYA の expansion unit です。一つの adapter は一つの public-service channel、mockable policy shape、または official handoff path を一つの tool entry として wrap し、schema、citation、state label、permission metadata を持ちます。

adapter authoring は backend work だけではありません。adapter は docs が何を honest に claim できるか、model が何を call できるか、user がどの permission を見るか、final answer がどの evidence を cite できるかを決めます。

## 正しい state を最初に選ぶ

code を書く前に channel を classify します。

| State | Use when | Documentation consequence |
|---|---|---|
| Live | official callable channel and credential path exist | docs may describe evidence-backed execution within scope |
| Mock | channel shape is known or policy-mandated, but live access is unavailable | docs must label simulation |
| Handoff | next step belongs to an opaque official service | docs should prepare the path and stop |
| Planned | target-state demand exists but shape/evidence is not ready | docs may describe roadmap, not current capability |

この decision は最初に行う必要があります。schema、tests、permission wording、user-facing claims をすべて変えるからです。

## Required Contents

有用な adapter は query engine と docs が agreement できる structure を持つ必要があります。

| Requirement | Why it matters |
|---|---|
| primitive | ties the adapter to `locate`, `find`, `check`, or `send` |
| input/output schema | prevents plausible but invalid tool calls |
| Live/Mock/Handoff state | controls user-facing authority language |
| permission tier | separates public lookup from protected action |
| public or policy citation | prevents UMMAYA-invented authority |
| fixture or artifact | makes Mock or Live behavior inspectable |
| search hints | lets retrieval find the adapter from citizen language |

adapter がこれら fields を欠く場合、docs は user workflow の evidence として promote してはいけません。

## User Documentation Requirement

user-facing coverage に影響する adapter は prose を持つ必要があります。その prose は adapter が support できること、support できないこと、適用される status label、安全な answer language を言うべきです。

例えば public weather adapter は Live weather lookup を support できます。separate protected path がない限り personal disaster benefit eligibility は support できません。docs はこれら claims を分ける必要があります。

## Promotion Requirement

Mock から Live への promotion には optimism ではなく evidence が必要です。official endpoint または channel validation、credential handling、schema validation、permission metadata、sanitized request/response artifacts、CI で live citizen infrastructure を call しない tests が必要です。

promotion 後、docs surfaces を regenerate し、affected pages を review します。

```bash
npm run docs:generate
npm run docs:check
```

generated adapter metadata が変わったら、user docs と LLM-readable docs も変わる必要があります。

## Failure Mode

common failure は tool を追加した後に broad marketing copy を書くことです。UMMAYA は逆に進むべきです。channel shape を prove し、boundary を define し、その evidence が support することだけ docs に claim させます。
