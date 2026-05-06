# Retriever Protocol Contract

**Owner**: Spec 026 (Retrieval Backend Evolution)
**Stability**: Internal contract — may evolve with spec 026; external consumers (`lookup`, `search`) MUST NOT depend on it directly.
**Module**: `src/kosmos/tools/retrieval/backend.py` (NEW)

## Purpose

`Retriever` is the internal abstraction that allows `ToolRegistry` to accept any of three ranking strategies — BM25 (default), Dense (opt-in), Hybrid (opt-in) — through a single dependency-injection seam without altering the frozen external contract owned by Spec 507 (`LookupSearchInput`, `LookupSearchResult`, `AdapterCandidate`, `GovAPITool`).

## Protocol Definition

```python
from typing import Protocol, runtime_checkable


@runtime_checkable
class Retriever(Protocol):
    """Pluggable ranking backend consumed by ``ToolRegistry``.

    Implementations MUST be pure CPU, MUST NOT hardcode synonym / keyword
    expansions (``feedback_no_hardcoding.md``), and MUST preserve the
    deterministic tie-break (score DESC, tool_id ASC) at the score layer.
    """

    def rebuild(self, corpus: dict[str, str]) -> None:
        """Replace the entire index with a new corpus.

        Args:
            corpus: Mapping of ``tool_id`` → concatenated ``search_hint`` text.
                    Empty dict is legal and resets the index to empty.

        Returns:
            None. Implementations MUST be idempotent across repeated calls
            with the same corpus.

        Raises:
            Never. On internal failure, implementations MUST latch into a
            degraded state and surface failure via the next ``score()`` call
            or (for DenseBackend / HybridBackend) via ``DegradationRecord``.
        """

    def score(self, query: str) -> list[tuple[str, float]]:
        """Rank the corpus against a free-text query.

        Args:
            query: Free-text user query (Korean or English). Caller
                   guarantees length ≥ 1 (``LookupSearchInput.query`` is
                   ``Field(min_length=1, max_length=200)``).

        Returns:
            List of ``(tool_id, score)`` pairs with ``score >= 0.0``.
            Ordering MUST be score DESC, tool_id ASC for ties. Empty list
            is legal when the corpus is empty or the query produces zero
            scores.
        """
```

## Invariants

| # | Invariant | Enforcement |
|---|-----------|-------------|
| R1 | `score()` returns scores in `[0.0, +∞)` only (no NaN, no negatives). | Unit test `tests/retrieval/test_backend_contract.py::test_score_range`. |
| R2 | `score()` result is deterministic across repeated calls on an unchanged corpus. | Regression test with SHA-256 fixture of the ranking. |
| R3 | Deterministic tie-break (score DESC, tool_id ASC) is applied **at the Retriever boundary**, not shifted onto the registry. | Unit test feeds a corpus with guaranteed ties and asserts ordering. |
| R4 | `rebuild({})` must succeed and leave the backend in a legal empty state; a subsequent `score("anything")` returns `[]`. | Unit test. |
| R5 | `rebuild()` is the only mutation entry point. No implicit re-indexing on `score()`. | Code review; no registry code path triggers reindex from a search. |
| R6 | No backend may raise on `score()` for well-formed queries (≥1 char). Degradation paths log + return ranked or empty; they do not raise. | API-level integration test via `kosmos.eval.retrieval._evaluate`. |

## Implementations (in-scope for spec 026)

### `BM25Backend` (default — `KOSMOS_RETRIEVAL_BACKEND=bm25`)

- Wraps the existing `BM25Index` (no internal change).
- Preserves baseline recall@5 = 1.0, recall@1 = 0.9667 on the 30-query set.
- Boot latency unchanged (Principle II — default path cannot regress).

### `DenseBackend` (opt-in — `KOSMOS_RETRIEVAL_BACKEND=dense`)

- Lazy-loads `sentence-transformers` model referenced by `KOSMOS_RETRIEVAL_MODEL_ID` (default: `intfloat/multilingual-e5-small`).
- Applies `"query: "` / `"passage: "` prefixes for e5-family models.
- Stores embeddings as an in-memory `numpy.ndarray` matrix (`float32`, L2-normalized rows).
- `score()` computes cosine similarity via a single matmul (≤ 200 tools fits comfortably in < 5 ms on reference CPU).
- On load failure → invokes `DegradationRecord.latch("model_load_failed", ...)` and falls back to BM25 (surfaced via `HybridBackend` when in hybrid mode, or directly via `ToolRegistry.bm25_index` fallback when in dense mode).

### `HybridBackend` (opt-in — `KOSMOS_RETRIEVAL_BACKEND=hybrid`)

- Composes one `BM25Backend` and one `DenseBackend`.
- Fusion: Reciprocal Rank Fusion with `k = KOSMOS_RETRIEVAL_FUSION_K` (default 60, Cormack et al. SIGIR 2009).
- Formula: `RRF_score(d) = Σ_retriever 1 / (k + rank_retriever(d))`.
- On Dense subsystem degradation → `HybridBackend` transparently returns BM25-only ranking with a WARN log line (fail-open on retrieval path; Principle II is preserved because auth/invocation remain fail-closed).

## Registry Integration

`ToolRegistry.__init__` swaps `self.bm25_index: BM25Index` for:

```python
self._retriever: Retriever = build_retriever_from_env(
    backend=os.getenv("KOSMOS_RETRIEVAL_BACKEND", "bm25"),
    model_id=os.getenv("KOSMOS_RETRIEVAL_MODEL_ID"),
    fusion_k=int(os.getenv("KOSMOS_RETRIEVAL_FUSION_K", "60")),
)
# Back-compat alias (used by existing tests that reference `.bm25_index`).
# Points to a BM25Backend view regardless of the selected retriever, so
# legacy direct access keeps working and the Spec 507 byte-level contract
# on `LookupSearchResult` holds even when downstream code asks the
# registry for BM25 specifically.
self.bm25_index = self._retriever.bm25_view()  # see manifest for view semantics
```

**External callers (`kosmos.tools.search.search`, `kosmos.tools.lookup.lookup`) see no signature change.**

## Non-Goals (spec 026)

- Streaming index rebuild (deferred to Phase 4 umbrella — `NEEDS TRACKING (Phase 4 umbrella)`).
- Query expansion, synonym injection, salvage loops (forbidden by `feedback_no_hardcoding.md`; LLM self-correction handles residual misses).
- FAISS / hnswlib ANN backends (deferred — activates when registry_size exceeds ~200; tracked by Phase 4 umbrella).
- Cross-encoder re-ranking (explicit out-of-scope — follow-on Epic).
- New OTEL span attributes (owned by #501; this spec ships log-only telemetry).

## Regression Gate

A schema-snapshot regression test (`tests/retrieval/test_schema_snapshot.py`) MUST:

1. Hash `LookupSearchInput.model_json_schema()`, `LookupSearchResult.model_json_schema()`, `AdapterCandidate.model_json_schema()` as of merge of spec 022 (MVP main tool) and spec 025 (V6 auth).
2. Fail CI if any of the three hashes changes on this branch.

This is the **byte-level invariance evidence** #507 asks for (Appendix B of spec.md).
