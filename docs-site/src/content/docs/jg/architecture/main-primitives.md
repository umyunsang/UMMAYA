---
title: "Main Primitives"
description: "UMMAYA が model に小さな action vocabulary だけを見せる理由です。"
llm_index: true
audience:
  - citizen_user
  - considering_user
  - public_sector_evaluator
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - docs/vision.md
  - docs/requirements/ummaya-migration-tree.md
  - docs/api/README.md
  - eval/scenarios/national_ax_citizen_requests_v1.yaml
---

`locate`, `find`, `check`, and `send` keep the model-facing surface small while adapters carry domain detail, citations, schemas, and permission rules. Primitive layer は、利用者の文と分散した国家インフラの間にある compression point です。利用者は API 名で話す必要がなく、model もすべての agency operation を prompt に持つ必要がありません。

<figure class="architecture-diagram">
  <img src="/architecture/c4/structurizr-03-query-engine-core.svg" alt="最小 C4 component diagram：Context, Retrieve, Primitives, Validate, Gate, Dispatch, Stop." />
  <figcaption>Primitive view：retrieval が範囲を狭め、primitive が動詞を選び、validation と gate が action を制限します。</figcaption>
</figure>

## Primitive summary

| Primitive | Meaning | User wording | Boundary |
|---|---|---|---|
| `locate` | 場所、住所、座標、行政区域を解決 | 近く、この住所、この地域 | 入力や provider が risk を変えない限り概ね public |
| `find` | 選択された adapter で公開情報を fetch | 探して、見せて、公式情報で | fetch-only、adapter retrieval が先に行われる |
| `check` | 条件確認または protected workflow | 対象か、条件を満たすか | classification と consent が必要な場合あり |
| `send` | 許可された channel で準備または提出 | 申請、提出、支払い、依頼 | live official channel、credential、consent、evidence が必要 |

## Primitive が小さい理由

国家インフラの domain は広すぎるため、すべての agency verb を model prompt に置けません。Root verb を増やすと一見豊かに見えますが、agency-specific authority、credential、policy、receipt requirement を隠してしまいます。UMMAYA はそれらを adapter に置き、各 domain が自分の evidence と permission boundary を持てるようにします。

```text
利用者の表現
  -> intent/context assembly
  -> adapter retrieval
  -> primitive choice
  -> schema validation
  -> permission classification
  -> Live, Mock, or Handoff result
```

Primitive は adapter ではありません。`find` は internet search ではなく、選択された adapter による公開情報 fetch です。`send` は利用者が求めたすべての提出を実行することではなく、official channel、credential、consent、evidence が成立するときだけ準備または実行することです。

## Domain knowledge belongs in adapters

| Layer | Belongs there | Must not leak there |
|---|---|---|
| Primitive | stable action shape と input/output envelope | agency-specific policy や credential logic |
| Adapter | endpoint、schema、citation、fixture、Live/Mock/Handoff status | evidence のない hidden recovery path |
| Permission pipeline | consent gate と protected-action classification | UMMAYA が作った authority |
| Final answer | grounded result、boundary、next action | tool result に支えられない claim |

## Boundary

Arguments が invalid なら primitive call は validation で失敗すべきです。Adapter が Mock なら answer は Mock と言うべきです。Official channel がない場合、`send` は fake completion ではなく Handoff material になります。
