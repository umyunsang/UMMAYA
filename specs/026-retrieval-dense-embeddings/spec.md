# Feature Specification: Retrieval Backend Evolution — BM25 → Dense Embeddings (+ Hybrid Fusion)

**Feature Branch**: `feat/585-retrieval-dense`
**Created**: 2026-04-17
**Status**: Draft
**Input**: Epic #585 — Retrieval Backend Evolution. Parent Epic #507 (CLOSED, byte-level contract owner). Depends on #22 (corpus extension), coordinates with #501 (OTEL spans), #467 (manifest), #468 (env-var registry).

---

## Background *(mandatory — anchors the re-pivot of Epic #585's Success Criteria)*

### 1. Current retrieval stack (verified in this worktree)

`lookup(mode="search")` resolves to `kosmos.tools.search.search()` → `ToolRegistry.bm25_index.score(query)` → `rank_bm25.BM25Okapi.get_scores()` with a kiwipiepy morpheme tokenizer (POS-filtered: NNG/NNP/VV/VA/SL; ASCII fallback to whitespace). Ranked `AdapterCandidate` objects flow back through `lookup.py` to the LLM as `LookupSearchResult(kind="search", candidates=…)`. Adaptive `top_k = max(1, min(k, registry_size, 20))` comes from `KOSMOS_LOOKUP_TOPK`.

### 2. Measured baseline — saturation problem

Running `kosmos.eval.retrieval._evaluate()` against the committed 30-query set in `eval/retrieval_queries.yaml` (4 seed adapters) produces:

| Metric | Value |
|---|---|
| `recall_at_5` | **1.0000** (30/30) |
| `recall_at_1` | **0.9667** (29/30) |
| KOROAD | 10/10/10 |
| KMA (kma_forecast_fetch) | 7/7 @ 5, 6/7 @ 1 |
| HIRA | 7/7 @ 5, 7/7 @ 1 |
| NMC | 6/6/6 |
| `registry_size` | 4 |
| `warnings` | [] |

Gate thresholds from `docs/design/mvp-tools.md §5.5.1`: pass ≥ 0.80, warn 0.60–0.80, fail < 0.60. **The baseline sits at the ceiling.**

### 3. Why Epic #585's "+10%p" SC must be re-anchored

The Epic body specifies "recall@5 ≥ 0.90 (+10%p vs BM25 baseline)". Against the 30-query set this is **unmeasurable** — recall@5 is already 1.0, and the only room left is recall@1 (0.9667, one miss to close). A spec that advances on the current set would produce A/B numbers whose differences are noise, not signal.

This spec therefore re-anchors Success Criteria to a **new eval methodology** that makes any dense-backed uplift measurable:

1. **Extended corpus** (via Epic #22): expected ≥ 8 adapters, ≥ 50 queries.
2. **Adversarial paraphrase subset** (authored inside this epic's PR): ≥ 20 queries with zero lexical overlap against `search_hint` tokens — the exact regime where BM25 is known to fail and dense embeddings are expected to win.

Both surfaces are required for SC-01 and SC-02 below.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Paraphrase-robust tool discovery (Priority: P1)

A citizen types "아이 열이 40도 넘어요 지금 응급실 가려면 어디가 가까워요?" Current BM25 tokenizer emits `[아이, 열, 응급실, 가려, 어디, 가까]` — misses on `nmc_emergency_search` if its `search_hint` uses only `[응급의료센터, 병상, 중증응급]`. Dense embedding collapses "응급실" ↔ "응급의료센터" and "열 40도" ↔ "중증" into near-neighbours in vector space. The LLM keeps its Claude-Code-style single call; only the retrieval backend changes.

**Why this priority**: This is the entire motivation of Epic #585. Without a paraphrase-robust retrieval layer, users are forced to mimic the tool's `search_hint` vocabulary — which is exactly the failure mode that Claude Code / K-AI-2026 discoverability principle 8/9 forbids.

**Independent Test**: Can be fully tested by running the adversarial paraphrase subset (`eval/retrieval_queries_adversarial.yaml`, authored in this PR) with `KOSMOS_RETRIEVAL_BACKEND=hybrid` vs `bm25` and asserting SC-02 thresholds. No live API calls.

**Acceptance Scenarios**:

1. **Given** `KOSMOS_RETRIEVAL_BACKEND=hybrid` and the adversarial 20-query subset, **When** `lookup(mode="search")` is invoked for each query, **Then** recall@5 ≥ 0.80.
2. **Given** `KOSMOS_RETRIEVAL_BACKEND=bm25` (default) and the same adversarial 20-query subset, **When** `lookup(mode="search")` is invoked, **Then** recall@5 < 0.50 (establishes the gap the hybrid backend must close).
3. **Given** any `KOSMOS_RETRIEVAL_BACKEND` value, **When** a query arrives, **Then** the returned `LookupSearchResult` JSON schema is byte-identical to the committed snapshot (regression gate).

---

### User Story 2 — Zero-change default path (backward compatibility) (Priority: P1)

Existing callers (the tool loop, E2E tests, `lookup(mode="search")` consumers) MUST see no behaviour change unless they explicitly opt into the new backend. `KOSMOS_RETRIEVAL_BACKEND` unset or `=bm25` produces identical rankings to today's code — same order, same scores, same `why_matched` strings.

**Why this priority**: Parent Epic #507 (CLOSED) owns the byte-level contract. Breaking the default path invalidates #507's acceptance evidence and the 30-query gate committed with Spec 022.

**Independent Test**: Can be fully tested by running `tests/eval/test_retrieval_gate.py` with `KOSMOS_RETRIEVAL_BACKEND` unset and asserting `recall_at_5 == 1.0`, `recall_at_1 == 0.9667`, plus a JSON-schema snapshot regression test over `LookupSearchInput` / `LookupSearchResult`.

**Acceptance Scenarios**:

1. **Given** `KOSMOS_RETRIEVAL_BACKEND` unset, **When** the 30-query gate runs, **Then** `recall_at_5 == 1.0` and `recall_at_1 == 0.9667` exactly (byte-for-byte baseline preservation).
2. **Given** the committed pydantic schemas for `LookupSearchInput` and `LookupSearchResult`, **When** `model_json_schema()` is exported and compared against a snapshot file, **Then** the diff is empty.
3. **Given** `KOSMOS_RETRIEVAL_BACKEND=dense` and a simulated model-load failure (patched import raises `RuntimeError`), **When** the registry boots, **Then** it degrades to BM25, emits exactly one structured WARN line, and continues to serve the 30-query gate at `recall_at_5 == 1.0`.

---

### User Story 3 — Extended-corpus A/B uplift (Priority: P2)

Once Epic #22 lands (≥ 4 new adapters, ≥ 20 new queries) the combined ≥ 50-query set becomes the authoritative regression surface. Hybrid retrieval must beat BM25 by ≥ +5%p on recall@1 over this surface while matching or exceeding recall@5.

**Why this priority**: The Epic's "+10%p" claim becomes verifiable only on the extended set. Until #22 lands, SC-01 will be marked PENDING in the CI artifact with a WARN, not a FAIL.

**Independent Test**: Can be fully tested by re-running `kosmos.eval.retrieval._evaluate()` on the combined corpus under `backend=bm25` and `backend=hybrid` and comparing the two JSON reports. The harness already emits a `per_adapter` breakdown and `registry_size` for audit.

**Acceptance Scenarios**:

1. **Given** #22 is merged and the combined ≥ 50-query set is present, **When** the eval runs under `backend=hybrid`, **Then** recall@5 ≥ 0.90.
2. **Given** the same corpus, **When** comparing hybrid vs bm25, **Then** hybrid's recall@1 is ≥ +5 percentage points over bm25's recall@1.
3. **Given** #22 has NOT landed, **When** SC-01 is evaluated, **Then** the harness MUST emit a `PENDING_#22` status (not a false pass) and CI MUST NOT mark SC-01 as green.

---

### User Story 4 — Operator-grade performance (Priority: P2)

A synthetic 100-adapter registry (padded by cloning seed adapters with suffixed ids) establishes the steady-state performance envelope. p99 per-query search latency MUST stay < 50 ms on the reference CPU to keep the tool-loop iteration budget within the Claude-Code-like target.

**Why this priority**: The point of hybrid retrieval is silent uplift — if latency regresses visibly, the change fails SC-03 even if recall is perfect. Operators need a hard number, not a vibe.

**Independent Test**: Can be fully tested via `tests/retrieval/test_latency.py` using `time.perf_counter_ns()` over 500 warm queries on a padded 100-adapter registry. No live API, no external service.

**Acceptance Scenarios**:

1. **Given** a 100-adapter padded registry and `backend=hybrid`, **When** 500 warm queries run sequentially, **Then** p99 wall-clock latency < 50 ms.
2. **Given** `backend=bm25` (default), **When** the same test runs, **Then** p99 latency is within ±10% of the pre-#585 baseline (no regression on the default path).

---

### Edge Cases

- **Empty registry**: `search()` already returns `[]`; dense backend MUST preserve this — no model load attempted until the first non-empty rebuild.
- **Empty query**: BM25 returns all-zero scores; dense backend MUST return the same all-zero list (no vector, no call) to keep tie-break deterministic.
- **Mixed Korean + English query** (e.g., "KMA 단기예보 grid 좌표"): tokenizer already handles this via the ASCII/Korean split path. Dense backend MUST accept the raw string unchanged — multilingual embedding models handle code-switch natively.
- **Model load failure at boot** (network, disk full, checksum mismatch): degrade to BM25, emit WARN once per registry instance, never raise.
- **First-query tail latency** (lazy load): if lazy warm-up is the chosen strategy, the first query MAY exceed 50 ms but MUST NOT exceed 500 ms or the SC fails.
- **Tie scores across backends** (two adapters with identical fused score): existing tie-break (score DESC, tool_id ASC) applies unchanged.
- **Weight-hash mismatch at boot** (cached weights don't match the manifest): refuse the dense backend, degrade to BM25, emit WARN — do not silently use stale weights.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001 (Pluggable backend)**: `ToolRegistry` MUST resolve its retrieval implementation from a `KOSMOS_RETRIEVAL_BACKEND` value in `{bm25, dense, hybrid}` at construction time. Unset → `bm25`. Unknown value → `ValueError` at boot (fail-closed on config).
- **FR-002 (Fail-open runtime degradation)**: When `backend ∈ {dense, hybrid}` and model load or tokenizer initialisation fails, the registry MUST degrade to pure BM25, emit exactly one structured WARN log line (keys: `event=retrieval.degraded`, `requested_backend`, `effective_backend=bm25`, `reason`), and continue to serve. Auth/invocation gates MUST remain fail-closed — only the retrieval ordering degrades.
- **FR-003 (Byte-level contract preservation)**: `LookupSearchInput` and `LookupSearchResult` JSON schemas MUST remain byte-identical to the committed snapshot. `AdapterCandidate` field set, types, and default values MUST remain byte-identical. A schema-snapshot regression test MUST gate CI.
- **FR-004 (Deterministic tie-break preserved)**: For every backend, the final ranking MUST tie-break on `score DESC, tool_id ASC`. Fusion layers MUST feed this invariant, not replace it.
- **FR-005 (Adaptive top_k preserved)**: The existing clamp `max(1, min(k, registry_size, 20))` and the `KOSMOS_LOOKUP_TOPK` default MUST remain the single place `top_k` is shaped. Dense/hybrid backends operate on the already-clamped value.
- **FR-006 (Reproducibility manifest)**: When `backend ∈ {dense, hybrid}`, the release manifest MUST carry the model weight SHA-256, the tokenizer version, and the embedding dimension. Final field names come from Epic #467; this spec proposes extension fields only.
- **FR-007 (No new OTEL span attributes)**: This spec MUST NOT introduce new OTEL semantic-convention attribute names. It MAY emit values on attributes already defined by Epic #501 (e.g., a backend tag, if one exists) — otherwise telemetry is log-only via stdlib logging.
- **FR-008 (No hardcoded synonym/keyword/salvage layer)**: No static synonym lists, query-rewrite heuristics, stopword curations outside of kiwipiepy's POS filter, or salvage loops. Residual miss recovery is the LLM's job, consistent with `feedback_no_hardcoding.md`.
- **FR-009 (BM25Index interface preserved)**: `BM25Index.rebuild(corpus)` and `BM25Index.score(query) → list[(tool_id, float)]` remain the only contact surface between `ToolRegistry` and the retrieval layer. New backends MUST satisfy an identical `Retriever` protocol so `registry.py` and `search.py` change by dependency injection only.
- **FR-010 (No model weights in the repo)**: Weight artefacts MUST be resolved via Hugging Face hub cache at install-time or first boot. The repo MUST NOT contain any `*.bin`, `*.safetensors`, or `*.onnx` file > 1 MB. CI MUST NOT download weights; tests use a mocked embedder or the `backend=bm25` default.
- **FR-011 (Cold-start strategy is configurable)**: Cold-start behaviour (eager at boot vs lazy on first search) MUST be selectable via env var (proposed: `KOSMOS_RETRIEVAL_COLD_START ∈ {eager, lazy}`; final name registered via Epic #468). Default: `lazy` — matches current zero-latency-at-boot behaviour for `backend=bm25`.
- **FR-012 (Adversarial eval subset authored in-PR)**: The PR MUST deliver `eval/retrieval_queries_adversarial.yaml` with ≥ 20 queries that have zero lexical overlap with any adapter's `search_hint` token set. The harness MUST accept this file as a secondary eval surface alongside the existing `eval/retrieval_queries.yaml`.
- **FR-013 (Extended-corpus A/B posture)**: If Epic #22 has landed at merge time, SC-01 MUST be evaluated against the combined corpus. If #22 has not landed, the harness MUST emit `PENDING_#22` (not a pass, not a fail) on SC-01 and document this in the CI artifact.

### Non-Functional Requirements

- **NFR-License**: Every shipped model weight + tokenizer artefact MUST be Apache-2.0-compatible. Candidates with unconfirmed licenses (`jhgan/ko-sroberta-multitask`, `snunlp/KR-SBERT-V40K-klueNLI-augSTS`) are **excluded from the final shortlist** unless the licence is formally confirmed upstream before `/speckit-plan`.
- **NFR-Reproducibility**: Given the same weight SHA-256 + tokenizer version + corpus + query, retrieval **ranking order** (the `(tool_id, rank)` sequence) MUST be deterministic and byte-identical across runs. Raw scalar scores MAY drift within ≤ 1e-6 due to floating-point noise, but MUST NOT reorder the ranking. Tie-break `(score DESC, tool_id ASC)` is the sole tiebreaker.
- **NFR-CPU**: CPU inference only. No CUDA/GPU code paths, no GPU-only libraries. `torch` MAY be added only via its CPU wheel.
- **NFR-NoNetAtRuntime**: After the first-boot warm-up, no network egress is permitted to fetch weights. CI MUST NOT download weights.
- **NFR-Fallback**: Pure BM25 MUST always be available as a runtime backend choice and as the automatic fallback for FR-002.
- **NFR-BootBudget**: With `backend=bm25` (default) the cold-start time MUST NOT regress. With `backend=dense|hybrid` and `cold_start=eager`, cold-start MAY add up to 10 seconds (model load + corpus embedding) — this is an ADR-worthy trade-off and MUST be disabled by default.
- **NFR-MemoryBudget**: With `backend=dense|hybrid` at steady state (registry_size = 100), resident memory of the retrieval layer MUST stay < 2 GB for the smallest candidate model and < 4 GB for the largest.

### Key Entities

- **Retriever (protocol)**: `rebuild(corpus: dict[str, str]) -> None` + `score(query: str) -> list[tuple[str, float]]`. Mirrors the existing `BM25Index` surface so the registry swaps by DI.
- **BM25Backend**: Current implementation, unchanged externally. May wrap `kosmos.tools.bm25_index.BM25Index` verbatim.
- **DenseBackend**: Holds a sentence-transformer-style encoder + a numpy or FAISS vector index. Implements `rebuild` (tokenize → embed → index) and `score` (embed query → cosine / IP → `[(tool_id, score)]`).
- **HybridBackend**: Composes one BM25Backend + one DenseBackend under a fusion algorithm (RRF default at k=60 per Cormack 2009, or RSF per Weaviate 2024). Returns a single fused ranking.
- **RetrievalManifest**: Structured record `{ backend, model_id, weight_sha256, tokenizer_version, embedding_dim, built_at }` surfaced into the Epic #467 release manifest.
- **AdversarialQuerySet**: `eval/retrieval_queries_adversarial.yaml` — ≥ 20 entries, each `{ query, expected_tool_id, lexical_overlap_score }` where `lexical_overlap_score == 0.0` against all adapter `search_hint` token sets.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001 (Extended-corpus recall uplift)**: On the Epic-#22-extended query set (≥ 50 queries over ≥ 8 adapters), `backend=hybrid` MUST achieve recall@5 ≥ 0.90 AND recall@1 ≥ (bm25_recall@1 + 0.05). If #22 has not landed at merge time, this SC is `PENDING_#22` and MUST NOT be marked green.
- **SC-002 (Adversarial paraphrase robustness)**: On `eval/retrieval_queries_adversarial.yaml` (≥ 20 queries, zero lexical overlap with `search_hint` tokens), `backend=hybrid` MUST achieve recall@5 ≥ 0.80 AND `backend=bm25` MUST remain < 0.50 — demonstrating the synonym-robustness hypothesis that motivated the epic.
- **SC-003 (Performance envelope)**: On a synthetic 100-adapter padded registry, `backend=hybrid` p99 per-query search latency MUST stay < 50 ms. `backend=bm25` p99 MUST stay within ±10% of the pre-#585 baseline on the same padded registry.
- **SC-004 (Contract preservation)**: With `KOSMOS_RETRIEVAL_BACKEND` unset (default `bm25`), 100% of the committed schema snapshot test and 100% of the existing `tests/eval/test_retrieval_gate.py` suite MUST pass. `recall_at_5 == 1.0`, `recall_at_1 == 0.9667` byte-for-byte on the committed 30-query set.
- **SC-005 (Graceful degradation)**: With `KOSMOS_RETRIEVAL_BACKEND=dense` and a forced model-load failure, the registry MUST serve zero 5xx, emit exactly one structured WARN line with `event=retrieval.degraded`, and continue to satisfy SC-004 thresholds via the BM25 fallback.

---

## Assumptions

- Epic #22 will produce ≥ 4 additional adapters and ≥ 20 additional curated queries in `eval/retrieval_queries.yaml` within the same release window. If not, SC-01 remains `PENDING_#22` (FR-013).
- Reference CPU for SC-003 is Apple M-series 8-core (primary) or Linux x86_64 8-core (fallback); both are available to CI runners that carry the `reference-cpu` label.
- Epic #501 will not rename existing OTEL attributes before this spec merges; if it does, the safer log-only telemetry path (FR-007) still holds.
- Epic #467's release-manifest format is additive (extension fields acceptable); final field names will be reconciled in a follow-on.
- Epic #468 accepts four new `KOSMOS_*` env vars (backend, model id, fusion, cold-start) without objection — names may be renamed by #468 but semantics as specified here MUST survive.
- Users of `lookup(mode="search")` rely only on the public `LookupSearchResult` shape, not on internal score magnitudes (scores are documented as opaque ranking signal, not probabilities).

---

## Candidate Design Space *(reference-backed, non-binding until `/speckit-plan`)*

### Embedding-model shortlist (Apache-2.0-compatible only)

| Model | License | Params | Dim | Korean evidence | Notes |
|---|---|---|---|---|---|
| `intfloat/multilingual-e5-large` | MIT | 600 M | 1024 | MIRACL-ko MRR@10 = 62.5 (vs BM25 21.7) | Requires `"query: "` / `"passage: "` prefixes; 24-layer XLM-R. |
| `intfloat/multilingual-e5-small` | MIT | 100 M | 384 | MIRACL-ko MRR@10 = 55.4 | 12-layer, CPU-viable default. |
| `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | Apache-2.0 | 100 M | 384 | 50-lang coverage; no Korean-specific MRR published. | Safest licence baseline. |
| `BAAI/bge-m3` | MIT | ~560 M | 1024 | Multi-functional (dense + sparse + ColBERT); MIRACL-evaluated. | Prefix-free, 8192 seq. |

Excluded (unless licence confirmation arrives before `/speckit-plan`):

- `jhgan/ko-sroberta-multitask` — HF card does not state a licence.
- `snunlp/KR-SBERT-V40K-klueNLI-augSTS` — HF card does not state a licence.

### Fusion algorithms

| Algorithm | Citation | Default params | Notes |
|---|---|---|---|
| Reciprocal Rank Fusion | Cormack, Clarke, Buettcher — SIGIR 2009 | k = 60 | Score-free, robust across retrievers; empirically beats Condorcet and individual retrievers. |
| Relative Score Fusion | Weaviate v1.24 (2024) release notes | normalized weighted sum | ~6 % recall uplift reported vs RRF; default in Weaviate 1.24. |
| Weighted linear | — | α · bm25_norm + (1−α) · dense_cos | Requires per-retriever score normalisation; a useful ablation baseline but not a primary candidate. |

### Vector-index implementations (CPU-only)

| Implementation | Pros | Cons |
|---|---|---|
| In-memory numpy cosine | No new deps, simplest, fine at registry_size ≤ 200. | Linear scan; O(Nd) per query. |
| FAISS `IndexFlatIP` | C++-backed, still exact; small wheel. | New runtime dep. |
| hnswlib | Sub-linear ANN at scale; pip wheel. | Graph build cost; overkill at current scale. |

### Cold-start strategies

| Strategy | Pros | Cons |
|---|---|---|
| Eager at boot | Flat latency after boot; simplest contract. | Blocks process start by ~5–10 s on the large model. |
| Lazy on first search | Zero boot-time cost; matches BM25 default. | First-query tail spike; must not exceed 500 ms. |
| Cached on disk (weight-hash keyed) | Best UX after second run. | New filesystem surface, invalidation logic. |

---

## Cross-Epic Dependencies

- **#507 (CLOSED, parent Epic)** — Owns the byte-level lookup contract. This spec guarantees zero diff on `LookupSearchInput`/`LookupSearchResult` JSON schema snapshots and on `recall_at_5 == 1.0, recall_at_1 == 0.9667` for the committed 30-query set. Evidence: schema-snapshot regression test + unchanged gate test.
- **#22 (OPEN, Phase 3 Adapters)** — Corpus extension. Adds ≥ 4 adapters (Gov24, MOLTM vehicle, NHIS, NEMA) and ≥ 20 queries to `eval/retrieval_queries.yaml`. SC-01 becomes measurable only after #22 lands; FR-013 requires `PENDING_#22` status in the interim. Absorbs the closed #579.
- **#501 (OPEN, OTEL spans)** — Owns `gen_ai.tool.execute`, `gen_ai.tool_loop.iteration`, `gen_ai.resolve_location`, `gen_ai.adapter.request` attribute sets. This spec emits telemetry via stdlib logging only (FR-007). Any new OTEL attribute names require an ADR under #501.
- **#467 (OPEN, release manifest)** — Weight SHA-256, tokenizer version, and embedding dim enter the manifest. This spec proposes the fields; #467 owns their final names.
- **#468 (OPEN, env-var registry)** — Four proposed env vars: `KOSMOS_RETRIEVAL_BACKEND`, `KOSMOS_RETRIEVAL_MODEL_ID`, `KOSMOS_RETRIEVAL_FUSION`, `KOSMOS_RETRIEVAL_COLD_START` (plus `KOSMOS_RETRIEVAL_FUSION_K` if RRF is selected). Names may be adjusted by #468; semantics are load-bearing here.

---

## Hard-Rule Audit *(AGENTS.md + private memory)*

| Hard rule | Applies here as |
|---|---|
| All source text in English | Spec + all new Python code. Korean appears only inside `search_hint` strings and adversarial query text. |
| No hardcoded synonym lists, keyword rewrites, salvage loops | FR-008 — codified. Residual misses go back through the LLM loop. |
| Every design decision cites `docs/vision.md § Reference materials` or an external source named in this spec | Candidate matrices above cite Cormack SIGIR 2009, Weaviate 2024, MIRACL-ko, HF licence metadata. `/speckit-plan` Phase 0 must re-confirm. |
| Pydantic v2; stdlib logging; no `print()` outside CLI | All new code conforms. WARN on degradation uses `logger.warning(...)` with structured kwargs. |
| No dependency added outside a spec-driven PR | This IS the spec-driven PR. Proposed new deps: one embedding-model library (`sentence-transformers` or HF `transformers` CPU stack), optionally `faiss-cpu` or `hnswlib`, plus `torch` CPU wheel transitively. Final selection in `/speckit-plan`. |
| No Go / Rust; TypeScript only for TUI | All additions are Python. |
| Apache-2.0-compatible model weights only | NFR-License — enforced at **design time** via the shortlist in `research.md` §Models; ko-sroberta / KR-SBERT excluded by default. No runtime licence validation is performed at load; operators who override `KOSMOS_RETRIEVAL_MODEL_ID` take responsibility for the chosen slug's licence. |
| CPU-only | NFR-CPU — enforced. |
| No model weights committed to repo (> 1 MB) | FR-010 — enforced; CI MUST NOT download weights. |
| Korean chat output, English source, no Claude co-author trailer | Session-scoped; not codified in spec. |

---

## Clarifications *(resolved 2026-04-17 prior to `/speckit-taskstoissues`)*

1. **Adversarial subset location — RESOLVED**: `eval/retrieval_queries_adversarial.yaml` is authored inside this spec's PR (not gated on Epic #22). Rationale: adversarial queries test retrieval **semantics** (synonym robustness), not adapter breadth; coupling them to adapter delivery would delay SC-002 evidence without payoff.
2. **Default backend at merge — RESOLVED**: Ship as `KOSMOS_RETRIEVAL_BACKEND=bm25` (default) with `hybrid` opt-in for one release cycle. A follow-on Epic (see §Deferred Items — "Default-backend rollout") owns the future flip to `hybrid` default after real-usage signal. Rationale: protects SC-004 (byte-level preservation) and gives ops a zero-cost revert path.
3. **ko-SBERT licence status — RESOLVED**: `jhgan/ko-sroberta-multitask` and `snunlp/KR-SBERT-V40K-klueNLI-augSTS` are formally **excluded** from the shortlist. They remain excluded until a licence declaration PR is filed upstream and the HF model card carries an explicit Apache-2.0-compatible SPDX identifier. Rationale: NFR-License is a hard rule; shortlist discipline prevents analysis-of-analysis at `/speckit-plan` time.

---

## Scope Boundaries & Deferred Items *(mandatory)*

### Out of Scope (Permanent)

- **Real-time corpus updates / streaming index rebuild** — not a registry use case at this scale; full rebuild stays < 5 ms on BM25 and is acceptable with a small embed cache on dense.
- **GPU / CUDA inference** — KOSMOS is CPU-only per AGENTS.md.
- **Model fine-tuning** — we consume off-the-shelf multilingual weights only.
- **TypeScript / TUI changes (Layer 7)** — retrieval lives entirely in the Python tool layer.
- **Changes to any adapter body or `GovAPITool` schema** — Spec 024/025 V1–V6 invariants are load-bearing.

### Deferred to Future Work

| Item | Reason for deferral | Target Epic / Phase | Tracking Issue |
|------|---------------------|---------------------|----------------|
| Cross-encoder re-ranking (e.g., BGE-reranker / mxbai-rerank) | Post-fusion re-ranking is a distinct architectural layer; measure hybrid first, decide re-ranker later. | Follow-on Epic (post-#585) | #772 |
| New OTEL span attributes for retrieval (e.g., `retrieval.backend`, `retrieval.latency_ms`, `retrieval.fusion`) | Attribute namespace owned by #501; this spec is log-only. | Epic #501 | #501 |
| Final release-manifest field names for weight SHA-256 / tokenizer version / embedding dim | Manifest format owned by #467. | Epic #467 | #467 |
| Canonical env-var names (final strings) | Env-var registry owned by #468. | Epic #468 | #468 |
| Default-backend rollout — flip `KOSMOS_RETRIEVAL_BACKEND` default from `bm25` to `hybrid` after one release cycle of real-usage signal (supersedes the earlier split "aggressive rollout" row; same concern, single follow-up). | Clarification #2 locks in conservative default for this spec; the flip itself is a separate release decision that needs an independent SC on real-traffic recall. | Follow-on Epic (post-#585) | #779 |
| Adapter growth beyond #22 (Phase 4 adapters) | Out of retrieval-layer scope. | Phase 4 | Phase 4 umbrella |

---

## Appendix A — Baseline Evidence (captured 2026-04-17)

```json
{
  "total_queries": 30,
  "recall_at_1": 0.9666666666666667,
  "recall_at_5": 1.0,
  "per_adapter": {
    "koroad_accident_hazard_search": {"total_queries": 10, "hits_at_1": 10, "hits_at_5": 10},
    "kma_forecast_fetch":            {"total_queries": 7,  "hits_at_1": 6,  "hits_at_5": 7},
    "hira_hospital_search":          {"total_queries": 7,  "hits_at_1": 7,  "hits_at_5": 7},
    "nmc_emergency_search":          {"total_queries": 6,  "hits_at_1": 6,  "hits_at_5": 6}
  },
  "registry_size": 4,
  "warnings": [],
  "timestamp": "2026-04-17T12:49:57.725918+00:00"
}
```

Method: direct invocation of `kosmos.eval.retrieval._build_registry()` + `_evaluate()` on the committed 4-seed-adapter registry and `eval/retrieval_queries.yaml`. No live API calls. The saturated `recall_at_5 = 1.0` is the specific justification for the SC re-anchoring above.

---

## Appendix B — Frozen-Contract Regression Mechanism

1. Export `LookupSearchInput.model_json_schema()` and `LookupSearchResult.model_json_schema()` to `tests/retrieval/__snapshots__/lookup_schema.json`.
2. Commit the snapshot.
3. A pytest-level snapshot-comparison test (`tests/retrieval/test_schema_snapshot.py`) fails on any diff.
4. `AdapterCandidate.model_json_schema()` snapshot is committed and compared the same way.
5. The 30-query gate (`tests/eval/test_retrieval_gate.py`) is run under `KOSMOS_RETRIEVAL_BACKEND=bm25` as SC-004 evidence.
6. CI blocks merge on any of steps 3, 4, or 5 failing.
