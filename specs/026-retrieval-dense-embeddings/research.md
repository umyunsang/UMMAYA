# Phase 0 Research — Retrieval Backend Evolution (Feature 026)

**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-04-17

This document resolves every `NEEDS CLARIFICATION` marker from `spec.md`, maps every design decision to a concrete reference per Constitution Principle I, and validates the Deferred Items table against Principle VI.

---

## NEEDS CLARIFICATION resolutions

### CL-1 — Adversarial subset location

**Question (spec §Clarifications #1)**: Should `eval/retrieval_queries_adversarial.yaml` be authored inside this spec's PR, or should this spec block on #22 to produce it?

**Decision**: Author inside this PR.

**Rationale**: Adversarial queries exercise retrieval semantics (synonym / paraphrase robustness), not adapter breadth. Authoring here keeps SC-002 measurable at merge regardless of #22 timing and avoids a circular dependency (this spec's recall gate cannot block on #22's corpus expansion because #22 has no recall gate of its own). FR-012 codifies the deliverable.

**Alternatives considered**:
- *Push to #22*: rejected — couples retrieval-semantics evaluation to unrelated adapter-growth work, delays SC-002 evidence, and violates the principle that a spec should be mergeable against the measurements it authors.
- *Author in follow-on micro-spec*: rejected — leaves SC-002 unprovable at merge, defeats the purpose of re-anchoring Epic #585's success criteria in this PR.

### CL-2 — Default backend at merge

**Question (spec §Clarifications #2)**: Ship as `KOSMOS_RETRIEVAL_BACKEND=bm25` default with `hybrid` opt-in, or flip default to `hybrid` immediately?

**Decision**: Ship as `bm25` default; `hybrid` is opt-in for one release cycle.

**Rationale**:
- Protects SC-004 (byte-level contract preservation) — the default-path regression gate stays green without requiring an operator to flip a flag.
- Gives the ops team a proven revert path if dense/hybrid exhibits unforeseen failure modes in real traffic (memory pressure, first-query tail latency spikes under concurrency, weight-cache corruption).
- Matches Spec 022's committed gate semantics — operators expect `recall_at_5 == 1.0, recall_at_1 == 0.9667` on the 30-query set at merge.
- A follow-on micro-spec flips the default after one release cycle of telemetry (log-only per FR-007) proves dense/hybrid is stable.

**Alternatives considered**:
- *Flip to hybrid on merge*: rejected — conflates two landings (mechanism + policy change) in one PR, strips the revert path, and risks SC-004 regression if any environment's HF cache is cold and `cold_start=eager` is later chosen.
- *Ship dense-only default*: rejected — loses the BM25 lexical-match grounding for technical queries like `"KMA 단기예보 grid 좌표"` where BM25 outperforms pure dense embeddings in code-switched regimes (see Cormack SIGIR 2009 for why fused retrievers beat either alone).

### CL-3 — ko-SBERT licence status

**Question (spec §Clarifications #3)**: If `jhgan/ko-sroberta-multitask` and `snunlp/KR-SBERT-V40K-klueNLI-augSTS` licences remain unconfirmed, formally exclude them now?

**Decision**: Formally excluded from the shortlist.

**Rationale**:
- HF model cards for both resources do not state a licence at the time of writing (verified 2026-04-17).
- NFR-License is a hard rule: "Every shipped model weight + tokenizer artefact MUST be Apache-2.0-compatible."
- The four remaining candidates (E5-large/small, MiniLM-L12-v2, BGE-M3) have published, permissive licences (MIT or Apache-2.0) and cover the Korean performance envelope via MIRACL-ko.
- Future licence confirmation can be handled by a follow-on micro-spec; it does not need to block this PR.

**Alternatives considered**:
- *Include under assumption of permissive licence*: rejected — hard-rule violation; a future DMCA or licence-clarification upstream could force an emergency rollback.
- *Defer the decision to `/speckit-plan`*: superseded — this *is* `/speckit-plan`, and the licences remain unconfirmed.

---

## 1. Embedding model selection

**Decision**: Default to `intfloat/multilingual-e5-small` (MIT, 100M params, 384-dim); `intfloat/multilingual-e5-large` is the opt-in quality upgrade for operators with memory budget.

**Rationale**:
| Criterion | E5-small | E5-large | MiniLM-L12-v2 | BGE-M3 |
|---|---|---|---|---|
| Licence | MIT ✅ | MIT ✅ | Apache-2.0 ✅ | MIT ✅ |
| Params | 100 M | 600 M | 100 M | ~560 M |
| Dim | 384 | 1024 | 384 | 1024 |
| Korean evidence | MIRACL-ko MRR@10 = 55.4 | MIRACL-ko MRR@10 = 62.5 (best) | No published Korean benchmark | MIRACL-multi (strong) |
| CPU viability (M-series) | ✅ ~10 ms/query | Marginal, ~40 ms/query | ✅ ~10 ms/query | Marginal, ~35 ms/query |
| Memory (~encoder + 100 × 384) | ~500 MB | ~2.2 GB | ~500 MB | ~2.1 GB |
| Prefix requirement | `"query: "` / `"passage: "` | Same | None | None |
| Seq length | 512 | 512 | 512 | 8192 |

E5-small is the **default** because it maximises MIRACL-ko score (55.4 vs MiniLM with no Korean benchmark) within the NFR-MemoryBudget "< 2 GB smallest candidate" envelope and keeps p99 < 50 ms on reference CPU with headroom for RRF fusion overhead. E5-large is a first-class **opt-in** via `KOSMOS_RETRIEVAL_MODEL_ID=intfloat/multilingual-e5-large` for users who accept the 10 s eager-cold-start and 2.2 GB memory cost in exchange for +7 MRR@10.

MiniLM-L12-v2 remains a licence-safe **fallback** if E5's MIT licence becomes a future concern (not currently expected).

BGE-M3 is not shortlisted because its 8192 sequence length is not useful for `search_hint` strings (typically < 200 tokens) and its memory cost matches E5-large without Korean-specific evidence superior to E5-large's MIRACL-ko 62.5.

**References**:
- MIRACL-ko scores: `intfloat/multilingual-e5-small` and `-large` model cards (HuggingFace).
- Cormack et al., "Reciprocal Rank Fusion outperforms Condorcet and individual rank learning methods," SIGIR 2009 — establishes that retriever-quality gains come largely from fusion, making the smallest viable dense encoder a defensible default.
- `docs/vision.md § Reference materials` row 3 (Pydantic AI): schema-driven tool discovery pattern — encoder is a dependency-injected component behind a typed protocol.

**Alternatives rejected**:
- `jhgan/ko-sroberta-multitask`, `snunlp/KR-SBERT-V40K-klueNLI-augSTS` — licence unconfirmed (CL-3).

---

## 2. Fusion algorithm

**Decision**: Reciprocal Rank Fusion (RRF) with k = 60 as the single default.

**Rationale**:
- **Score-free**: RRF needs only per-retriever *ranks*, not raw scores, which eliminates the per-backend normalisation stage that Relative Score Fusion (RSF) and weighted linear require. This matters because `BM25Okapi.get_scores()` returns unbounded non-negative floats, whereas cosine similarity returns [-1, 1]; any normalisation would be an additional hyperparameter surface vulnerable to distribution shift.
- **Empirically robust**: Cormack/Clarke/Buettcher SIGIR 2009 shows RRF beats Condorcet and beats both source retrievers individually across a wide range of TREC corpora. k = 60 is the paper's recommended constant and the default in Weaviate, Elasticsearch 8.9+, and OpenSearch hybrid search.
- **Preserves deterministic tie-break**: RRF outputs a single fused score per document, consumed by the existing score-DESC / tool_id-ASC tie-break in `search.search_tools()` (FR-004).
- **Single hyperparameter (k)** is cleaner than RSF's α + normalisation choice; RSF's reported ~6 % uplift vs RRF (Weaviate 2024) comes with a normalisation-method dependency that a dependency-injected encoder cannot cleanly expose.

**Alternatives considered**:
- RSF — deferred to an ablation in follow-on work; can be added behind `KOSMOS_RETRIEVAL_FUSION=rsf` later without schema change.
- Weighted linear — exposes α as a hyperparameter without a principled default; rejected as primary.

**References**:
- Cormack, Clarke, Buettcher, "Reciprocal Rank Fusion outperforms Condorcet and individual rank learning methods," SIGIR 2009.
- Weaviate v1.24 release notes (2024): hybrid-search default.

---

## 3. Vector-index implementation

**Decision**: In-memory numpy cosine (normalised IP) linear scan.

**Rationale**:
- Current registry_size = 4; target post-#22 = 8; SC-003 synthetic envelope = 100. At N = 100, d = 384, a single query's O(Nd) matmul costs ~40 k FLOPs — sub-millisecond on numpy's BLAS-backed backend.
- Zero new dependency. FAISS (`faiss-cpu` wheel) and hnswlib would each add ~50 MB and a C++ build dependency for no measurable gain at this scale.
- Keeps the dense backend's memory layout trivially introspectable for debugging and snapshot testing.
- Migration path preserved: when registry_size grows past 1000, swap the index implementation behind `DenseBackend` without touching the `Retriever` protocol.

**Alternatives considered**:
- FAISS `IndexFlatIP`: identical recall, marginal perf gain at N ≤ 100, adds a C++ build dep. Deferred.
- hnswlib: sub-linear ANN at very large N; overkill at this scale. Deferred.

**References**:
- numpy BLAS benchmarks (standard): at d = 384, N = 100, single-query cosine ≈ 0.5 ms on M-series.
- `docs/vision.md § Reference materials` row 3 (Pydantic AI): schema-driven tool registry — the vector index is an internal implementation detail of `DenseBackend`, not a schema-level decision.

---

## 4. Cold-start strategy

**Decision**: Default `cold_start=lazy`. First `lookup(mode="search")` call triggers encoder load + corpus embed; subsequent calls are warm. Eager mode available via `KOSMOS_RETRIEVAL_COLD_START=eager` for environments that prefer flat steady-state latency.

**Rationale**:
- Matches the zero-boot-latency posture of `backend=bm25` (default) — operators running the `bm25` default or deploying behind a load balancer with a warm-up probe see no regression.
- First-query tail latency budget is 500 ms per the spec's Edge Cases table — within the 10 s eager-load ceiling but without the up-front cost.
- Cached-on-disk variant deferred — HF hub already caches weights at `~/.cache/huggingface/hub/`, so "cached on disk" is the default behaviour after first boot. The embedding matrix itself could be pickled per corpus-hash, but that is a follow-on optimisation (not needed at N ≤ 100).
- Eager is available because operator-grade deploys that want flat p99 from the first call can accept the 10 s boot cost.

**Alternatives considered**:
- Eager-default: rejected — regresses `backend=bm25` boot time (violates NFR-BootBudget) when an operator chooses `backend=hybrid`.
- Cached-embeddings-on-disk: deferred — complexity not justified at current scale; revisit if corpus embed becomes visible in first-query tail latency.

---

## 5. Graceful degradation trigger and telemetry

**Decision**: FR-002 fail-open on four specific trigger classes, routed through a single `degrade.py` helper that emits exactly one structured WARN per registry instance:

| Trigger | Detection site |
|---|---|
| Model weight download / load failure | `DenseBackend.__init__` or first `rebuild()` |
| Tokenizer initialisation failure | `DenseBackend.__init__` |
| Weight SHA-256 mismatch against manifest | `DenseBackend.__init__` before encoder construction |
| Out-of-memory on corpus embed | `DenseBackend.rebuild()` |

WARN record structure (stdlib `logging.warning` with `extra={...}`):
```
event=retrieval.degraded
requested_backend=dense|hybrid
effective_backend=bm25
reason=<one-line cause>
model_id=<requested model id or null>
```

**Rationale**: FR-007 forbids new OTEL span attributes until Epic #501 owns them. Log-only telemetry satisfies the "one structured WARN" contract and is observable via existing log pipelines. A single emission per registry instance (guarded by an internal flag) prevents log flooding on hot-path degradation.

**References**:
- `feedback_no_hardcoding.md` (private memory) — forbids salvage/rewrite layers; degradation is a clean fallback to BM25, not a synonym-stuffing retry.
- Claude Code's permission-denied WARN pattern (`docs/vision.md § Reference materials`, Claude Code sourcemap): log once, continue, never raise.

---

## 6. Environment variables (proposals for Epic #468)

**Decision**: Propose four new env vars; `#468` owns final naming.

| Proposed name | Values | Default | Purpose |
|---|---|---|---|
| `KOSMOS_RETRIEVAL_BACKEND` | `bm25` / `dense` / `hybrid` | `bm25` | Select retrieval implementation at registry construction (FR-001). |
| `KOSMOS_RETRIEVAL_MODEL_ID` | HF model id | `intfloat/multilingual-e5-small` | Override default dense encoder. |
| `KOSMOS_RETRIEVAL_FUSION` | `rrf` | `rrf` | Enum for future RSF/weighted-linear expansion. |
| `KOSMOS_RETRIEVAL_COLD_START` | `lazy` / `eager` | `lazy` | Warm-up strategy (FR-011). |

Additional: `KOSMOS_RETRIEVAL_FUSION_K` (int, default 60) becomes active only when RRF remains the sole fusion algorithm.

**Rationale**: Keeps naming consistent with existing `KOSMOS_LOOKUP_TOPK` style; each var has a safe default that preserves today's behaviour.

---

## 7. Deferred-items validation (Constitution Principle VI gate)

Scanned `spec.md` for all deferral language and verified each entry appears in the "Deferred to Future Work" table.

| Deferred item | Tracking issue | Principle VI status |
|---|---|---|
| Cross-encoder re-ranking | `NEEDS TRACKING` | ✅ Table entry present; `/speckit-taskstoissues` will back-fill. |
| New OTEL span attributes for retrieval | #501 | ✅ Active open issue; on-file dependency. |
| Final release-manifest field names | #467 | ✅ Active open issue. |
| Canonical env-var names | #468 | ✅ Active open issue. |
| Flipping default backend to `hybrid` | `NEEDS TRACKING` | ✅ Table entry present; follow-on micro-spec placeholder. |
| Aggressive rollout reconsideration | `NEEDS TRACKING` | ✅ Table entry present; placeholder. |
| Adapter growth beyond #22 | Phase 4 umbrella | ✅ Phase reference acceptable. |

Free-text scan — phrases searched: "separate epic", "future epic", "Phase 2+", "v2", "deferred to", "later release", "out of scope for v1". All matches are inside the Deferred table or the Out-of-Scope (Permanent) section. Zero orphaned deferrals.

`/speckit-taskstoissues` action required: create placeholder tracking issues for the three `NEEDS TRACKING` entries (cross-encoder re-ranking, default flip, aggressive rollout) and back-fill the issue numbers into the spec.

**Constitution Principle VI**: ✅ PASS.

---

## 8. Reference-source mapping (Constitution Principle I gate)

| Design decision | Primary reference | Secondary reference |
|---|---|---|
| `Retriever` protocol (typed swap surface) | Pydantic AI schema-driven tool registry (`docs/vision.md § Reference materials` row 3) | Claude Agent SDK tool definitions (row 1) |
| RRF fusion at k = 60 | Cormack/Clarke/Buettcher SIGIR 2009 | Weaviate v1.24 release notes |
| E5-small default encoder | `intfloat/multilingual-e5-small` model card (MIRACL-ko MRR@10 = 55.4) | E5-large model card (55.4 → 62.5 quality upgrade path) |
| In-memory numpy cosine index | numpy BLAS at N ≤ 100 (sub-millisecond per query) | Pydantic AI (index is an internal impl detail behind a typed protocol) |
| Lazy cold-start default | Claude Code sourcemap (`docs/vision.md § Reference materials` row 10): tool-loop zero-boot-cost posture | FR-011 + NFR-BootBudget |
| Fail-open WARN on retrieval | Claude Code permission-denied WARN pattern (log once, continue, never raise) | LangGraph `ToolNode(handle_tool_errors=True)` fail-closed lesson (row 16) — we fail *open* on retrieval path only (correctness degradation, not auth) |
| Schema-snapshot regression gate | Pydantic AI Pydantic v2 message assembly | Constitution Principle III |
| Adversarial paraphrase subset | MIRACL-ko methodology (paraphrase / zero-overlap query design) | Korean Public APIs index (`docs/vision.md § Reference materials` row 20) for `search_hint` vocabulary analysis |

**Constitution Principle I**: ✅ PASS.

---

## 9. Dependency impact

**Proposed new runtime dependency**: `sentence-transformers >= 3.0` (Apache-2.0). Transitively pulls `torch` (CPU wheel pinned), `transformers`, `tokenizers`, `numpy` (already present).

**Rationale for `sentence-transformers` over raw `transformers`**:
- Single `.encode()` call handles pooling, normalisation, and (when configured) the `"query: "` / `"passage: "` prefix for E5-family models.
- One dependency name instead of three; `torch` CPU wheel is selected via `pip install` markers.
- Apache-2.0 licence, matches KOSMOS licensing.
- Widely used in retrieval literature; mature enough that its encode-loop stability is not a research risk.

**`torch` CPU-wheel pinning**: `pyproject.toml` will declare `torch>=2.0,<3.0` with an explicit `--extra-index-url https://download.pytorch.org/whl/cpu` hint in `docs/design/retrieval.md` to prevent accidental GPU wheel pulls on CUDA-capable CI runners.

**CI disk budget**: `sentence-transformers` + `torch` CPU wheel ≈ 250 MB install. CI caches via `uv` lockfile, so marginal cost is one-time per lockfile refresh.

**Memory cost at import time (without model load)**: ~100 MB. Model load under `backend=bm25` default **does not occur** (lazy cold-start, and the backend factory never instantiates `DenseBackend` when `backend=bm25`) — NFR-BootBudget preserved.

**References**:
- `sentence-transformers` README (Apache-2.0 confirmation).
- KOSMOS AGENTS.md "No new dependency outside a spec-driven PR" — this IS the spec-driven PR.

---

## 10. Open questions carried to `/speckit-tasks`

All spec-level clarifications are resolved. One implementation-level question remains for `/speckit-tasks` to decide:

- **Q-IMPL-1**: The `tests/retrieval/test_dense_backend.py` mocked-encoder test — should it use `unittest.mock.MagicMock` on `SentenceTransformer` directly, or a purpose-built `FakeEncoder` class that implements the minimum subset of the interface? Recommendation: `FakeEncoder` — more maintainable, type-checkable, and mirrors the `Retriever` Protocol approach at the unit-test layer. Decision deferred to `/speckit-tasks` task breakdown.

---

## Summary for Phase 1

- Backend default: `bm25` (unchanged behaviour). Dense encoder default model: `intfloat/multilingual-e5-small`. Fusion: RRF k=60.
- Vector index: numpy cosine linear scan.
- Cold-start: lazy default.
- Degradation: single structured WARN, log-only telemetry.
- New dependency: `sentence-transformers >= 3.0`.
- Env-var names proposed to Epic #468; final names deferred.
- Three `NEEDS TRACKING` deferrals flagged for `/speckit-taskstoissues` resolution.
- All six Constitution principles PASS.

Phase 1 will codify these decisions into `data-model.md` (entity schemas), `contracts/` (Retriever protocol + frozen JSON-schema snapshots), and `quickstart.md` (operator walkthrough).
