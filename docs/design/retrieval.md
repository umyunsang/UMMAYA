# Design Doc: Retrieval Backend Evolution (Epic #585)

**Branch**: `feat/585-retrieval-dense` | **Date**: 2026-04-17
**Spec**: `specs/026-retrieval-dense-embeddings/spec.md`
**Research**: `specs/026-retrieval-dense-embeddings/research.md` (single source of truth for every decision below)

---

## 1. Overview

Epic #585 adds a pluggable dense-embedding retrieval layer to KOSMOS so that citizen queries expressed in paraphrase or synonym form reach the correct government-API tool — even when the query shares no lexical tokens with the adapter's `search_hint`. The change is a dependency-injection swap inside `ToolRegistry`: the concrete `BM25Index` is replaced by a `Retriever` protocol that three interchangeable backends implement. Parent Epic #507 (CLOSED) owns the byte-level contract; FR-003 guarantees that `LookupSearchInput`, `LookupSearchResult`, and `AdapterCandidate` JSON schemas are byte-identical before and after this change. Callers of `lookup(mode="search")` see no behavioural change unless `KOSMOS_RETRIEVAL_BACKEND` is explicitly set to `dense` or `hybrid`.

---

## 2. Baseline and the `+10%p` Anchoring Problem

The committed 30-query evaluation set (`eval/retrieval_queries.yaml`, 4 seed adapters) is **saturated**:

| Metric | Value |
|---|---|
| `recall_at_5` | **1.0000** (30 / 30) |
| `recall_at_1` | **0.9667** (28 / 30) |
| `registry_size` | 4 |

Source: Appendix A of `specs/026-retrieval-dense-embeddings/spec.md` (captured 2026-04-17 via direct invocation of `kosmos.eval.retrieval._evaluate()`).

The Epic body originally specified "recall@5 ≥ 0.90 (+10%p vs BM25 baseline)". Against this set the target is **unmeasurable** — `recall_at_5` is already 1.0, leaving only two recall@1 misses and no headroom for a signal-vs-noise comparison between BM25 and a hybrid backend.

SC-01 was therefore re-anchored to two surfaces:

1. **Extended corpus** (PENDING_#22): ≥ 8 adapters and ≥ 50 queries delivered by Epic #22. Until #22 lands, SC-01 emits `PENDING_#22` in CI — never a false pass.
2. **Adversarial paraphrase subset** (authored in this PR as `eval/retrieval_queries_adversarial.yaml`): ≥ 20 queries with zero lexical overlap against all adapter `search_hint` token sets — the exact regime where BM25 fails and dense embeddings are expected to win.

---

## 3. The `Retriever` Protocol

### Component map

```
ToolRegistry
    |
    |-- build_retriever_from_env()          # reads KOSMOS_RETRIEVAL_* env vars
    |       |
    |       |-- KOSMOS_RETRIEVAL_BACKEND=bm25   --> BM25Backend
    |       |-- KOSMOS_RETRIEVAL_BACKEND=dense  --> DenseBackend  (or BM25Backend on load failure)
    |       `-- KOSMOS_RETRIEVAL_BACKEND=hybrid --> HybridBackend (or BM25Backend on load failure)
    |
    `--> Retriever (Protocol)
             rebuild(corpus: dict[str, str]) -> None
             score(query: str) -> list[tuple[str, float]]

HybridBackend
    |-- BM25Backend   (lexical, rank_bm25.BM25Okapi + kiwipiepy)
    `-- DenseBackend  (semantic, sentence-transformers + numpy cosine)
         |
         RRF fusion (k=60) via hybrid.py::HybridBackend.score()

Degradation path:
    DenseBackend / HybridBackend load failure
         |
         DegradationRecord.emit_if_needed()   # one-shot WARN latch
         |
         BM25Backend (automatic fallback)
```

### Factory

`build_retriever_from_env()` in `src/kosmos/tools/retrieval/backend.py` reads three mandatory env vars:

- `KOSMOS_RETRIEVAL_BACKEND` (default `bm25`; unknown value → `ValueError` at boot, fail-closed per FR-001)
- `KOSMOS_RETRIEVAL_MODEL_ID` (default `intfloat/multilingual-e5-small`)
- `KOSMOS_RETRIEVAL_FUSION` (default `rrf`; only `rrf` supported; unknown → `ValueError`)
- `KOSMOS_RETRIEVAL_FUSION_K` (default `60`; non-integer → `ValueError`)
- `KOSMOS_RETRIEVAL_COLD_START` (default `lazy`; `eager` triggers pre-load at boot)

### Degradation latch

`DegradationRecord` in `src/kosmos/tools/retrieval/degrade.py` is a one-shot boolean latch scoped to one `ToolRegistry` instance. The first call to `emit_if_needed()` writes a structured `logging.WARNING` with keys `event=retrieval.degraded`, `requested_backend`, `effective_backend=bm25`, and `reason`. Subsequent calls are no-ops. This satisfies FR-002 (exactly one WARN) and FR-007 (no new OTEL attribute names — stdlib logging only).

---

## 4. Phase 0 Research Consolidation

> All decisions in this section are documented with full alternative analysis in `specs/026-retrieval-dense-embeddings/research.md`.

### 4.1 Model Shortlist

Apache-2.0-compatible candidates only (NFR-License hard rule):

| Model | License | Params | Dim | Korean evidence | Ship role |
|---|---|---|---|---|---|
| `intfloat/multilingual-e5-small` | MIT | 100 M | 384 | MIRACL-ko MRR@10 = 55.4 (HF model card) | **Default** |
| `intfloat/multilingual-e5-large` | MIT | 600 M | 1024 | MIRACL-ko MRR@10 = 62.5 (HF model card) | Opt-in via `KOSMOS_RETRIEVAL_MODEL_ID` |
| `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | Apache-2.0 | 100 M | 384 | No published Korean-specific MRR | Licence-safe fallback |
| `BAAI/bge-m3` | MIT | ~560 M | 1024 | MIRACL-multi evaluated | Not shortlisted (see rationale below) |

**Ship choice**: `intfloat/multilingual-e5-small` — the highest MIRACL-ko score among models that fit the NFR-MemoryBudget "< 2 GB for the smallest candidate" envelope and stay comfortably under the SC-03 p99 50 ms ceiling on reference CPU at N = 100 (~10 ms/query, M-series estimate from research.md §1).

**Apache-2.0 compatibility rule**: Every shipped model weight and tokenizer artefact must carry an Apache-2.0-compatible SPDX licence. `jhgan/ko-sroberta-multitask` and `snunlp/KR-SBERT-V40K-klueNLI-augSTS` are **formally excluded** — their HF model cards do not state a licence (verified 2026-04-17). They remain excluded until an explicit Apache-2.0-compatible SPDX identifier is published upstream. BGE-M3 is not shortlisted because its 8192-token seq length is unused for `search_hint` strings (< 200 tokens), and its memory profile matches E5-large without superior Korean-specific evidence.

### 4.2 Fusion Decision

**Algorithm**: Reciprocal Rank Fusion (RRF), k = 60.

**Citation**: Cormack, Clarke, Büttcher, "Reciprocal Rank Fusion outperforms Condorcet and Individual Rank Learning Methods," SIGIR 2009. k = 60 is the paper's recommended constant and the default in Weaviate, Elasticsearch 8.9+, and OpenSearch hybrid search.

**Formula** (implemented in `src/kosmos/tools/retrieval/hybrid.py`):

```
fused(d) = 1/(k + rank_bm25(d)) + 1/(k + rank_dense(d))
```

Missing-from-list rank = N + 1 (N = retriever output size), ensuring every union member has a strictly positive fused score.

**Why RRF over alternatives**:

- **Score-free**: RRF needs only per-retriever ranks, not raw scores. `BM25Okapi.get_scores()` returns unbounded non-negative floats; cosine similarity returns [-1, 1]. Any cross-retriever normalisation would introduce a hyperparameter surface vulnerable to distribution shift.
- **Robust**: Cormack SIGIR 2009 shows RRF beats Condorcet and beats both source retrievers individually across a wide range of TREC corpora.
- **Single hyperparameter**: k is cleaner than Relative Score Fusion's α + normalisation choice. Weaviate v1.24 (2024) reports ~6% recall uplift with RSF vs RRF, but that figure comes with a normalisation-method dependency that a dependency-injected encoder cannot cleanly expose. RSF remains available as a future `KOSMOS_RETRIEVAL_FUSION=rsf` extension without schema change.
- **Preserves tie-break**: RRF outputs a single fused score per document, consumed by the existing `score DESC, tool_id ASC` tie-break in `kosmos.tools.search` (FR-004).

### 4.3 Index Decision

**Choice**: In-memory numpy cosine linear scan (`DenseBackend` holds an `(N, d)` float32 matrix).

**Rationale**: Current registry_size = 4; target post-#22 = 8; SC-03 synthetic envelope = 100. At N = 100, d = 384, a single query's O(Nd) matmul costs ~40 k FLOPs — sub-millisecond on numpy's BLAS-backed backend (estimated ~0.5 ms, M-series, research.md §3). FAISS (`faiss-cpu`) and hnswlib each add ~50 MB and a C++ build dependency for no measurable gain at this scale. The migration path is preserved: when registry_size grows past 1000, swap the index implementation inside `DenseBackend` without touching the `Retriever` protocol.

### 4.4 Cold-Start Decision

**Default**: `lazy` — encoder load and corpus embed are triggered on the first `lookup(mode="search")` call. This matches the zero-boot-latency posture of the `bm25` default and preserves NFR-BootBudget.

**Eager opt-in**: `KOSMOS_RETRIEVAL_COLD_START=eager` triggers `DenseBackend.rebuild({})` immediately after construction so steady-state p99 is flat from the first query. The eager path may add up to 10 s at boot (ADR-worthy trade-off) and is disabled by default.

**First-query tail latency budget**: 500 ms (spec Edge Cases). HF hub caches weights locally after the first boot; subsequent restarts see warm cache.

---

## 5. Success-Criteria Framework

| SC | Threshold | Enforcement location |
|---|---|---|
| SC-01 (Extended-corpus recall uplift) | `backend=hybrid` recall@5 ≥ 0.90 AND recall@1 ≥ bm25_recall@1 + 0.05 on ≥ 50-query set | `src/kosmos/eval/retrieval.py::run_extended_gate` / `tests/retrieval/test_extended_corpus_harness.py` — **PENDING_#22** until Epic #22 lands |
| SC-02 (Adversarial paraphrase robustness) | `backend=hybrid` recall@5 ≥ 0.80; `backend=bm25` recall@5 < 0.50 on adversarial 20-query subset | `tests/retrieval/test_adversarial_recall.py` |
| SC-03 (Performance envelope) | `backend=hybrid` p99 < 50 ms; `backend=bm25` p99 within ±10% of pre-#585 baseline on 100-adapter synthetic registry | `tests/retrieval/test_latency.py` |
| SC-04 (Contract preservation) | `recall_at_5 == 1.0`, `recall_at_1 == 0.9667` (byte-for-byte) on 30-query set; zero schema snapshot diff | `tests/retrieval/test_schema_snapshot.py`, `tests/retrieval/test_baseline_preservation.py` |
| SC-05 (Graceful degradation) | Zero 5xx; exactly one structured WARN with `event=retrieval.degraded`; SC-04 thresholds maintained via BM25 fallback | `tests/retrieval/test_fail_open.py` |

---

## 6. Operator Handbook

### Environment variables

| Variable | Allowed values | Default | Effect |
|---|---|---|---|
| `KOSMOS_RETRIEVAL_BACKEND` | `bm25` / `dense` / `hybrid` | `bm25` | Selects retrieval implementation at registry construction. Unknown value → `ValueError` at boot (fail-closed, FR-001). |
| `KOSMOS_RETRIEVAL_MODEL_ID` | Any HF model id string | `intfloat/multilingual-e5-small` | Overrides the dense encoder. Active only when `backend` is `dense` or `hybrid`. |
| `KOSMOS_RETRIEVAL_FUSION` | `rrf` | `rrf` | Fusion algorithm enum. Only `rrf` is implemented; any other value → `ValueError` at boot. |
| `KOSMOS_RETRIEVAL_FUSION_K` | Positive integer | `60` | RRF constant k (Cormack 2009 default). Non-integer or k < 1 → `ValueError` at boot. |
| `KOSMOS_RETRIEVAL_COLD_START` | `lazy` / `eager` | `lazy` | `lazy`: encoder loads on first search call. `eager`: encoder loads at registry construction (adds up to 10 s boot time; NFR-BootBudget caveat). |

### Typical operator commands

```bash
# Default (BM25 only — no model download, no behaviour change):
uv run python -m kosmos.tools.registry

# Opt into hybrid retrieval with lazy warm-up:
KOSMOS_RETRIEVAL_BACKEND=hybrid uv run python -m kosmos.tools.registry

# Opt into hybrid with eager warm-up and the large model:
KOSMOS_RETRIEVAL_BACKEND=hybrid \
KOSMOS_RETRIEVAL_MODEL_ID=intfloat/multilingual-e5-large \
KOSMOS_RETRIEVAL_COLD_START=eager \
  uv run python -m kosmos.tools.registry
```

### torch CPU wheel

CI MUST NOT download model weights. When installing for local development, pin the CPU wheel to prevent accidental CUDA pulls on CUDA-capable hosts:

```bash
pip install torch --extra-index-url https://download.pytorch.org/whl/cpu
pip install sentence-transformers>=3.0
```

### Degradation observation

On a dense/hybrid load failure, search exactly one log line at WARNING level with the following structured keys:

```
event=retrieval.degraded
requested_backend=dense|hybrid
effective_backend=bm25
reason=<one-line cause>
```

Subsequent queries are served by pure BM25 at full SC-04 throughput. No 5xx is emitted to callers (FR-002).

---

## 7. Cross-Epic Dependencies

- **#22 (OPEN — corpus extension)**: Adds ≥ 4 adapters (Gov24, MOLTM vehicle, NHIS, NEMA) and ≥ 20 queries to `eval/retrieval_queries.yaml`. SC-01 becomes measurable only after #22 lands; FR-013 requires `PENDING_#22` in the CI artifact until then. Epic #585 is mergeable independently.
- **#467 (OPEN — release manifest)**: Weight SHA-256, tokenizer version, and embedding dimension enter the release manifest as `RetrievalManifest` extension fields. Epic #585 proposes the field names; #467 owns their final canonical strings.
- **#468 (OPEN — env-var registry)**: The five `KOSMOS_RETRIEVAL_*` env vars proposed here are registered via Epic #468. Names may be adjusted by #468; the semantics specified in Section 6 are load-bearing.
- **#501 (OPEN — OTEL spans)**: Owns all `gen_ai.*` span attribute names. Epic #585 does NOT introduce new OTEL attribute names (FR-007). Retrieval telemetry is stdlib `logging.warning` only. Any future `retrieval.backend` / `retrieval.latency_ms` attributes require an ADR filed under #501.

---

## Appendix A — Frozen-Contract Regression Mechanism

1. `LookupSearchInput.model_json_schema()`, `LookupSearchResult.model_json_schema()`, and `AdapterCandidate.model_json_schema()` are exported to `tests/retrieval/__snapshots__/*.schema.json` and committed.
2. `tests/retrieval/test_schema_snapshot.py` compares live schema output against the snapshot; any diff fails CI.
3. `tests/eval/test_retrieval_gate.py` runs under `KOSMOS_RETRIEVAL_BACKEND=bm25` (unset → default) and asserts `recall_at_5 == 1.0` and `recall_at_1 == 0.9667` byte-for-byte.
4. CI blocks merge on any failure of steps 2 or 3.

Schema SHA-256 values committed at plan time (from `specs/026-retrieval-dense-embeddings/plan.md §Phase 1 Artifact Manifest`):

| Schema | SHA-256 |
|---|---|
| `LookupSearchInput` | `422ed50f3a26c6627d8177222600e0a42afeb8348a6c3f228009bc58d4fa788b` |
| `LookupSearchResult` | `c2a50c0d9a2b088e391c2f21557a0613871ff40a6e8157262a0cf56569745ed1` |
| `AdapterCandidate` | `ea5187bdfa981288b83b337f6ae4ee9de7ff14d07c630b1bab2a22c47b3ca12b` |

---

## Appendix B — Key Source Files

| File | Role |
|---|---|
| `src/kosmos/tools/retrieval/backend.py` | `Retriever` protocol definition + `build_retriever_from_env()` factory |
| `src/kosmos/tools/retrieval/bm25_backend.py` | `BM25Backend` — wraps `BM25Index` byte-identically |
| `src/kosmos/tools/retrieval/dense_backend.py` | `DenseBackend` — sentence-transformers encoder + numpy cosine index |
| `src/kosmos/tools/retrieval/hybrid.py` | `HybridBackend` — RRF (k=60) over BM25 + Dense |
| `src/kosmos/tools/retrieval/degrade.py` | `DegradationRecord` — one-shot WARN latch (FR-002) |
| `src/kosmos/tools/retrieval/manifest.py` | `RetrievalManifest` — Pydantic v2 model for #467 extension fields |
| `src/kosmos/eval/retrieval.py` | Eval harness extended to accept backend param and adversarial query file |
| `eval/retrieval_queries.yaml` | Committed 30-query baseline set (frozen, SC-04 evidence) |
| `eval/retrieval_queries_adversarial.yaml` | ≥ 20 zero-lexical-overlap queries (SC-02 evidence, authored in this PR) |
| `tests/retrieval/` | Full test suite: protocol conformance, fail-open, schema snapshot, latency |
