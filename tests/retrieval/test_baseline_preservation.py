# SPDX-License-Identifier: Apache-2.0
"""Baseline preservation test — T025 (spec 026, US2 P1).

Programmatic invocation of ``kosmos.eval.retrieval._build_registry()`` and
``_evaluate()`` against the committed 30-query set with
``KOSMOS_RETRIEVAL_BACKEND`` unset (pure BM25 default path).

Asserts the SC-004 / Appendix A contract:
    - recall@5 == 1.0  (all 30 queries hit in top-5)
    - recall@1 == 0.9667 (29/30 queries hit at rank 1, rounded to 4 dp)

These assertions are the programmatic equivalent of the Appendix A evidence
table in spec 026; any regression in lookup.py / search.py / BM25Index that
shifts the ranking will be caught here.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

_QUERIES_PATH = Path(__file__).parent.parent.parent / "eval" / "retrieval_queries.yaml"

# Expected baseline values (Appendix A, spec 026):
#   recall@5 = 30/30 = 1.0
#   recall@1 = 29/30 — _evaluate() applies round(..., 4) giving 0.9667
_EXPECTED_RECALL5 = 1.0
_EXPECTED_RECALL1 = 0.9667  # round(29/30, 4)


@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
def test_recall_at_5_is_perfect(monkeypatch: pytest.MonkeyPatch) -> None:
    """recall@5 MUST equal 1.0 — all 30 queries hit in top-5.

    SC-004 / Appendix A evidence: BM25 default path matches the committed
    adapter hint baseline.
    """
    monkeypatch.delenv("KOSMOS_RETRIEVAL_BACKEND", raising=False)

    import yaml

    from kosmos.eval.retrieval import _build_registry, _evaluate

    registry, _ = _build_registry()
    with _QUERIES_PATH.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    queries = data["queries"]
    report = asyncio.run(_evaluate(queries, registry))

    assert report["recall_at_5"] == _EXPECTED_RECALL5, (
        f"recall@5 regressed: expected {_EXPECTED_RECALL5}, got {report['recall_at_5']}"
    )


@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
def test_recall_at_1_matches_baseline(monkeypatch: pytest.MonkeyPatch) -> None:
    """recall@1 MUST equal 0.9667 (29/30 rounded to 4 dp).

    This is the Appendix A evidence value from spec 026. Any change to
    BM25Index tokenisation, score formula, or adapter search_hint that
    shifts a rank-1 result will break this assertion.
    """
    monkeypatch.delenv("KOSMOS_RETRIEVAL_BACKEND", raising=False)

    import yaml

    from kosmos.eval.retrieval import _build_registry, _evaluate

    registry, _ = _build_registry()
    with _QUERIES_PATH.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    queries = data["queries"]
    report = asyncio.run(_evaluate(queries, registry))

    assert report["recall_at_1"] == _EXPECTED_RECALL1, (
        f"recall@1 regressed: expected {_EXPECTED_RECALL1}, got {report['recall_at_1']}"
    )


@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
def test_total_query_count(monkeypatch: pytest.MonkeyPatch) -> None:
    """Eval MUST run against exactly 30 committed queries."""
    monkeypatch.delenv("KOSMOS_RETRIEVAL_BACKEND", raising=False)

    import yaml

    from kosmos.eval.retrieval import _build_registry, _evaluate

    registry, _ = _build_registry()
    with _QUERIES_PATH.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    queries = data["queries"]
    report = asyncio.run(_evaluate(queries, registry))

    assert report["total_queries"] == 30


@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
def test_registry_has_all_four_seed_adapters(monkeypatch: pytest.MonkeyPatch) -> None:
    """All 4 seed adapters must be registered for a valid baseline run."""
    monkeypatch.delenv("KOSMOS_RETRIEVAL_BACKEND", raising=False)

    from kosmos.eval.retrieval import _build_registry

    registry, _ = _build_registry()
    registered = frozenset(t.id for t in registry.all_tools())
    expected = frozenset(
        {
            "koroad_accident_hazard_search",
            "kma_forecast_fetch",
            "hira_hospital_search",
            "nmc_emergency_search",
        }
    )
    missing = expected - registered
    assert not missing, f"Baseline test requires all 4 seed adapters; missing: {sorted(missing)}"
