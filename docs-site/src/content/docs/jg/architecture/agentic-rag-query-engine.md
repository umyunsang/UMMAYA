---
title: "Agentic RAG And Query Engine"
description: "検索、推論、tool calling、permission、stop reason が一つの UMMAYA turn で協調する仕組みです。"
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

UMMAYA uses retrieval for actions, not only for prose. Query engine は利用者 request を受け取り、adapter candidates を取得し、K-EXAONE に primitive を選ばせ、呼び出しを検証し、permission を確認し、Live/Mock behavior を実行するか Handoff を生成します。Final answer はその evidence から合成されます。

<figure class="architecture-diagram">
  <img src="/architecture/c4/structurizr-03-query-engine-core.svg" alt="最小 C4 component diagram：Context, Retrieve, Primitives, Validate, Gate, Dispatch, Stop." />
  <figcaption>Query engine view：context、retrieval、primitive choice、validation、permission、dispatch、stop は別々の control steps です。</figcaption>
</figure>

## One turn in detail

```text
1. 利用者が public-service outcome を尋ねる。
2. Context assembly が session state、prior results、policy mode、runtime facts をまとめる。
3. Adapter retrieval が domain、hint、primitive support、tier、schema、citation metadata で候補を rank する。
4. Prompt には relevant adapter set と primitive contracts だけが入る。
5. K-EXAONE が answer、ask question、call primitive のどれかを選ぶ。
6. Query engine が tool call envelope を検証する。
7. Permission classification が safe、consent-gated、blocked、Mock、Handoff を決める。
8. Adapter が live run、mock replay、handoff material のいずれかを返す。
9. Tool results が model conversation に戻される。
10. Final answer が evidence、boundary、next action を示す。
```

UMMAYA は先に答えを書き、後から source を飾るべきではありません。十分な context を集め、tool を選び、validation と permission gate を通した後、returned result から答えるか、workflow が止まった理由を説明します。

<figure class="architecture-diagram">
  <img src="/architecture/c4/structurizr-04-public-lookup-flow.svg" alt="最小 C4 dynamic diagram：Citizen asks, UI routes, Query Engine selects, Adapters call Public APIs, and UI answers." />
  <figcaption>Public lookup view：`find` は Live public channel から adapter evidence が戻った後にだけ答えられます。</figcaption>
</figure>

<figure class="architecture-diagram">
  <img src="/architecture/c4/structurizr-05-protected-handoff-flow.svg" alt="最小 C4 dynamic diagram：Citizen asks, UI routes, Query Engine checks permission, Adapters reach Official Channels, and UI stops or hands off." />
  <figcaption>Protected action view：`check` と `send` は permission を通過するか、完了を装わず Handoff で停止する必要があります。</figcaption>
</figure>

## Why this is agentic RAG

Traditional RAG は文書を検索し、model が回答します。UMMAYA は tool candidates を検索し、model が安全な action を選びます。Document snippet は service が存在することを示せますが、tool candidate は schema、Live/Mock/Handoff status、credential requirement、citation、fixture、permission metadata を持てます。

| Retrieval signal | Why it matters |
|---|---|
| Korean/English `search_hint` | 利用者は自然な韓国語で尋ね、adapter は安定した metadata を必要とする |
| Primitive support | Engine は候補が `locate`、`find`、`check`、`send` のどれを支えるか知る必要がある |
| Live/Mock/Handoff state | execution authority の過大表現を防ぐ |
| Schema shape | model は plausible intent ではなく valid arguments を出す必要がある |
| Policy citation | protected action には UMMAYA が作った権限ではなく外部 boundary が必要 |
| Prior results | 後続 step が location、agency、receipt context を再利用できる |

## Query engine responsibilities

| Responsibility | Engine checks | Failure if skipped |
|---|---|---|
| Context assembly | session、prior results、current request、policy mode | model が作業を繰り返す、または法的順序を失う |
| Candidate narrowing | relevant adapters and primitive contracts | prompt だけ大きくなり decision quality が上がらない |
| Tool-call validation | envelope、schema、required fields、type constraints | invalid request が adapter に到達する |
| Permission gate | public lookup、protected action、Handoff | 権限がないのに authorized のように聞こえる |
| Result projection | compact evidence back into conversation | final text が tool result から離れる |
| Stop decision | complete、ask user、retry、Mock、Handoff、error | loop が空転する、または fake completion になる |

## Stop reasons

UMMAYA treats visible failure as part of the architecture: no adapter found, invalid arguments, permission denied, credential missing, protected channel unavailable, adapter error, max iterations or budget reached, official Handoff required.

## Boundary

UMMAYA は身分確認、証明書発行、支払い、提出、税申告、公式記録変更を偽装しません。live 公式チャネル、credential、consent、証拠がない場合、正しい結果は Mock または Handoff です。Request から adapter selection、primitive call、permission decision、tool result、final text まで追跡できない answer は ungrounded と扱うべきです。
