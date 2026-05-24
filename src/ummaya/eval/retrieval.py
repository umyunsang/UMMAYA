# SPDX-License-Identifier: Apache-2.0
"""BM25 retrieval quality evaluation harness — T039.

CLI entry point::

    python -m ummaya.eval.retrieval eval/retrieval_queries.yaml

Loads the seed adapter registry, runs each query through lookup(mode="search"),
computes recall@1 and recall@5, and writes a JSON report to
.eval-artifacts/retrieval.json.

Exit codes:
    0 — pass  (recall@5 >= 0.80)
    1 — warn  (0.60 <= recall@5 < 0.80)
    2 — fail  (recall@5 < 0.60)

Extended gate exit codes (run_extended_gate / --backend flag):
    0 — pass  (recall@5 >= 0.80, sc_01_status is not PENDING_#22)
    1 — warn  (0.60 <= recall@5 < 0.80)
    2 — PENDING_#22  (registry_size < 8 or no Phase-3 adapters detected)
    2 — fail  (recall@5 < 0.60, when sc_01 is not PENDING)

NOTE: As of Stage 2a, only ``koroad_accident_hazard_search`` is registered.
The other 3 seed adapters (kma_forecast_fetch, hira_hospital_search,
nmc_emergency_search) land in Stage 3.  When fewer than 4 adapters are
registered, recall@5 will be artificially high for queries targeting KOROAD
and zero for the others — the JSON report emits a WARN in that case.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import sys
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Report schema (Pydantic-free to avoid import overhead in a CLI entrypoint)
# ---------------------------------------------------------------------------

# The minimum number of distinct seed adapters we expect.
_EXPECTED_ADAPTER_COUNT = 4

# The adapter IDs that should be registered for a complete eval run.
_SEED_ADAPTER_IDS: frozenset[str] = frozenset(
    {
        "koroad_accident_hazard_search",
        "kma_forecast_fetch",
        "hira_hospital_search",
        "nmc_emergency_search",
    }
)

# Minimum registry size required for a meaningful A/B eval (SC-001, FR-013).
# Until Epic #22 lands (≥ 4 new adapters), the combined registry will be < 8.
_SC01_MIN_REGISTRY_SIZE = 8

# The four seed-adapter prefixes.  When every registered tool_id starts with
# one of these, no Phase-3 adapters are present and SC-01 is PENDING_#22.
_SEED_PREFIXES: tuple[str, ...] = ("koroad_", "kma_", "hira_", "nmc_")


@contextlib.contextmanager
def _backend_env_overlay(backend: str) -> Iterator[None]:
    """Context manager that overlays UMMAYA_RETRIEVAL_BACKEND for the duration.

    Restores the previous value (or removes the key entirely if it was absent)
    when the block exits.  This ensures that callers that set the env var via
    this function do not pollute the process environment after the harness run.

    Args:
        backend: One of ``bm25``, ``dense``, ``hybrid``.

    Yields:
        None
    """
    key = "UMMAYA_RETRIEVAL_BACKEND"
    previous = os.environ.get(key)
    os.environ[key] = backend
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous


@contextlib.contextmanager
def _eager_cold_start_overlay() -> Iterator[None]:
    """Force ``UMMAYA_RETRIEVAL_COLD_START=eager`` for the duration of a block.

    The eval harness always issues queries immediately after build, so there
    is no boot-cost benefit to the production lazy default (FR-011 /
    NFR-BootBudget). Eager cold-start lets ``ToolRegistry.register()`` observe
    dense-load failures synchronously and fire the single structured WARN via
    ``DegradationRecord`` at build time — the contract
    ``tests/retrieval/test_fail_open.py`` locks in.

    Production ``ToolRegistry`` instances constructed outside this harness
    continue to honour the lazy default.
    """
    key = "UMMAYA_RETRIEVAL_COLD_START"
    previous = os.environ.get(key)
    os.environ[key] = "eager"
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous


def _compute_sc01_status(registry: object) -> tuple[str, str]:
    """Determine SC-01 status for the current registry.

    Returns:
        (status, reason) where status is ``"PENDING_#22"`` or ``"EVALUATED"``.

    The PENDING_#22 status is emitted when:
    1. ``registry_size < _SC01_MIN_REGISTRY_SIZE`` — not enough adapters for
       a meaningful A/B comparison between BM25 and hybrid backends, OR
    2. Every registered tool_id starts with one of the four seed-adapter
       prefixes — meaning no Phase-3 adapters from Epic #22 are present.

    When either condition holds, SC-01 MUST NOT be marked green (FR-013).
    """
    registry_size = len(registry)  # type: ignore[arg-type]

    if registry_size < _SC01_MIN_REGISTRY_SIZE:
        return (
            "PENDING_#22",
            f"registry_size < 8 (require >= 8 adapters from #22 for meaningful A/B); "
            f"current registry_size={registry_size}",
        )

    tool_ids: list[str] = [t.id for t in registry.all_tools()]  # type: ignore[attr-defined]
    if tool_ids and all(
        any(tid.startswith(prefix) for prefix in _SEED_PREFIXES) for tid in tool_ids
    ):
        return (
            "PENDING_#22",
            "no Phase-3 adapter ids detected — awaiting #22",
        )

    return ("EVALUATED", "")


def _load_queries(yaml_path: Path) -> list[dict[str, Any]]:
    """Load and validate the queries YAML file.

    Args:
        yaml_path: Path to the retrieval_queries.yaml file.

    Returns:
        List of query dicts, each with 'id', 'query', 'expected_tool_id'.

    Raises:
        SystemExit: If the file is missing or malformed.
    """
    if not yaml_path.exists():
        logger.error("Queries file not found: %s", yaml_path)
        sys.exit(2)

    with yaml_path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    if not isinstance(data, dict) or "queries" not in data:
        logger.error("Invalid YAML structure in %s — expected top-level 'queries' key", yaml_path)
        sys.exit(2)

    queries: list[dict[str, Any]] = data["queries"]
    for entry in queries:
        if "query" not in entry or "expected_tool_id" not in entry:
            logger.error("Query entry missing required fields: %r", entry)
            sys.exit(2)

    return queries


def _build_registry() -> tuple[object, object]:
    """Build and populate the tool registry with the 4 seed adapters.

    Registers each seed adapter individually so the eval harness is resilient
    to partial registration (e.g., if one adapter module has import errors).
    This avoids calling ``register_all_tools()`` which may fail if geocoding
    or composite modules are not yet implemented.

    The 4 seed adapters are:
        - koroad_accident_hazard_search  (always available)
        - kma_forecast_fetch             (Stage 3)
        - hira_hospital_search           (Stage 3)
        - nmc_emergency_search           (Stage 2a stub)

    Returns:
        (registry, executor) tuple ready for search.
    """
    from ummaya.tools.executor import ToolExecutor
    from ummaya.tools.registry import ToolRegistry

    # Force eager cold-start for the eval harness: every register() call below
    # triggers ``Retriever.rebuild(corpus)``, and the fail-open contract in
    # ``tests/retrieval/test_fail_open.py`` requires dense-load failures to
    # surface synchronously at build time (single WARN via ``DegradationRecord``).
    # Production ToolRegistry instances outside this harness retain the
    # production lazy default (FR-011 / NFR-BootBudget).
    with _eager_cold_start_overlay():
        registry = ToolRegistry()
        executor = ToolExecutor(registry)

        # Attempt to register each seed adapter; log warnings on failure.
        _try_register_adapter(
            "ummaya.tools.koroad.accident_hazard_search",
            "register",
            registry,
            executor,
            requires_executor=True,
        )
        _try_register_adapter(
            "ummaya.tools.kma.forecast_fetch",
            "register",
            registry,
            executor,
            requires_executor=True,
        )
        _try_register_adapter(
            "ummaya.tools.hira.hospital_search",
            "register",
            registry,
            executor,
            requires_executor=True,
        )
        _try_register_adapter(
            "ummaya.tools.nmc.emergency_search",
            "register",
            registry,
            executor,
            requires_executor=True,
        )

    return registry, executor


def _try_register_adapter(
    module_path: str,
    fn_name: str,
    registry: object,
    executor: object,
    requires_executor: bool,
) -> None:
    """Attempt to import and call a register function, logging on failure.

    Args:
        module_path: Dotted module path to import.
        fn_name: Name of the registration function in the module.
        registry: ToolRegistry instance.
        executor: ToolExecutor instance.
        requires_executor: If True, call register(registry, executor),
                           else call register(registry).
    """
    import importlib

    try:
        module = importlib.import_module(module_path)
        fn = getattr(module, fn_name)
        if requires_executor:
            fn(registry, executor)
        else:
            fn(registry)
        logger.info("Registered adapter from %s", module_path)
    except Exception as exc:
        logger.warning("Failed to register adapter from %s: %s", module_path, exc)


async def _run_query(
    query: str,
    registry: object,
    top_k: int = 5,
) -> list[str]:
    """Run a single BM25 search query and return ordered tool_id list.

    Args:
        query: Natural-language query string.
        registry: Populated ToolRegistry.
        top_k: Maximum number of results to fetch.

    Returns:
        Ordered list of tool_id strings (rank 1 first).
    """
    from ummaya.tools.lookup import lookup
    from ummaya.tools.models import LookupSearchInput

    inp = LookupSearchInput(mode="search", query=query, top_k=top_k)
    result = await lookup(inp, registry=registry)

    # lookup returns LookupSearchResult on search mode
    if hasattr(result, "candidates"):
        return [c.tool_id for c in result.candidates]
    return []


def _compute_recall(
    ranked: list[str],
    expected: str,
    at_k: int,
) -> int:
    """Return 1 if expected appears in the top-at_k of ranked, else 0."""
    return 1 if expected in ranked[:at_k] else 0


def _build_warnings(
    registry: object,
    missing_adapters: list[str],
) -> list[str]:
    """Build the warnings list for the JSON report.

    Args:
        registry: The populated ToolRegistry.
        missing_adapters: Seed adapter IDs that were not found in the registry.

    Returns:
        List of warning strings.
    """
    warnings: list[str] = []
    registry_size = len(registry)  # type: ignore[arg-type]

    if registry_size < _EXPECTED_ADAPTER_COUNT:
        warnings.append(
            f"Registry has {registry_size} adapter(s); expected {_EXPECTED_ADAPTER_COUNT}. "
            "recall@5 is artificially inflated for registered adapters and zero for "
            f"missing adapters: {missing_adapters}. "
            "Stage 3 will register the remaining adapters."
        )

    return warnings


async def _evaluate(
    queries: list[dict[str, Any]],
    registry: object,
) -> dict[str, Any]:
    """Run the full eval loop and return the report dict.

    Args:
        queries: Loaded query entries from the YAML file.
        registry: Populated ToolRegistry.

    Returns:
        Report dict matching the documented JSON schema.
    """
    total = len(queries)
    hits_at_1 = 0
    hits_at_5 = 0

    # Per-adapter tracking: {tool_id: {"total": int, "hits_at_1": int, "hits_at_5": int}}
    per_adapter: dict[str, dict[str, int]] = {}

    for entry in queries:
        query_str: str = entry["query"]
        expected_tool_id: str = entry["expected_tool_id"]

        ranked = await _run_query(query_str, registry, top_k=5)

        hit1 = _compute_recall(ranked, expected_tool_id, at_k=1)
        hit5 = _compute_recall(ranked, expected_tool_id, at_k=5)

        hits_at_1 += hit1
        hits_at_5 += hit5

        if expected_tool_id not in per_adapter:
            per_adapter[expected_tool_id] = {"total": 0, "hits_at_1": 0, "hits_at_5": 0}
        per_adapter[expected_tool_id]["total"] += 1
        per_adapter[expected_tool_id]["hits_at_1"] += hit1
        per_adapter[expected_tool_id]["hits_at_5"] += hit5

        query_id = entry.get("id", "?")
        logger.debug(
            "Query %s (%r): expected=%s ranked=%s hit@1=%d hit@5=%d",
            query_id,
            query_str[:40],
            expected_tool_id,
            ranked[:5],
            hit1,
            hit5,
        )

    recall_at_1 = hits_at_1 / total if total > 0 else 0.0
    recall_at_5 = hits_at_5 / total if total > 0 else 0.0

    # Check which seed adapters are missing from the registry
    registered_ids: set[str] = {t.id for t in registry.all_tools()}  # type: ignore[attr-defined]
    missing_adapters = sorted(_SEED_ADAPTER_IDS - registered_ids)

    # Compute per-adapter recall metrics
    per_adapter_report: dict[str, dict[str, object]] = {}
    for tool_id, counts in per_adapter.items():
        t = counts["total"]
        per_adapter_report[tool_id] = {
            "total_queries": t,
            "hits_at_1": counts["hits_at_1"],
            "hits_at_5": counts["hits_at_5"],
            "recall_at_1": counts["hits_at_1"] / t if t > 0 else 0.0,
            "recall_at_5": counts["hits_at_5"] / t if t > 0 else 0.0,
        }

    return {
        "total_queries": total,
        "recall_at_1": round(recall_at_1, 4),
        "recall_at_5": round(recall_at_5, 4),
        "per_adapter": per_adapter_report,
        "registry_size": len(registry),  # type: ignore[arg-type]
        "warnings": _build_warnings(registry, missing_adapters),
        "timestamp": datetime.now(UTC).isoformat(),
    }


def _write_report(report: dict[str, Any], output_path: Path) -> None:
    """Write the JSON report to output_path, creating parent dirs as needed."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
    logger.info("Report written to %s", output_path)


def _exit_code(recall_at_5: float) -> int:
    """Compute exit code from recall@5 value.

    Returns:
        0 — pass  (>= 0.80)
        1 — warn  ([0.60, 0.80))
        2 — fail  (< 0.60)
    """
    if recall_at_5 >= 0.80:
        return 0
    if recall_at_5 >= 0.60:
        return 1
    return 2


# Sentinel that distinguishes "caller omitted report_path" from
# "caller explicitly passed report_path=None (no file write)".
_REPORT_PATH_DEFAULT = object()


def run_extended_gate(
    *,
    backend: str | None = None,
    queries_path: Path | None = None,
    report_path: object = _REPORT_PATH_DEFAULT,
    registry: object | None = None,
) -> dict[str, Any]:
    """Run the extended retrieval gate with backend selection and SC-01 status.

    This function extends the baseline ``_evaluate()`` harness with:
    - Pluggable backend selection via ``UMMAYA_RETRIEVAL_BACKEND`` env overlay.
    - ``sc_01_status`` / ``sc_01_reason`` fields added to the report dict.
    - ``sc_02_status`` placeholder (evaluated when adversarial file exists).

    The existing baseline schema fields (``total_queries``, ``recall_at_1``,
    ``recall_at_5``, ``per_adapter``, ``registry_size``, ``warnings``,
    ``timestamp``) are preserved byte-identical so ``test_retrieval_gate.py``
    contract continues to pass.

    SC-01 PENDING_#22 conditions (FR-013, T032):
    - ``registry_size < 8`` — not enough adapters from Epic #22.
    - All tool_ids start with a seed prefix — no Phase-3 adapters detected.

    Args:
        backend: Retrieval backend to activate (``bm25``, ``dense``, ``hybrid``).
            When ``None`` (default), the ambient ``UMMAYA_RETRIEVAL_BACKEND``
            env var — or ``bm25`` if unset — is honoured. Only meaningful when
            ``registry`` is also ``None``; an injected registry already has a
            retriever bound at construction time and the env overlay is a no-op.
        queries_path: Path to the queries YAML file.  Defaults to the committed
            ``eval/retrieval_queries.yaml`` in the repo root.
        report_path: Path to write the JSON report, or ``None`` to skip writing.
            When omitted entirely, defaults to
            ``.eval-artifacts/retrieval_extended.json``.
        registry: Pre-built registry to use (for testing).  When ``None``,
            builds the 4-seed registry via ``_build_registry()`` under the
            backend env overlay so the retriever is initialised correctly.

    Returns:
        Report dict containing all baseline fields PLUS new SC-status fields.
        The caller is responsible for interpreting ``sc_01_status`` and
        deciding whether to ``sys.exit(2)`` at the CLI layer.
    """
    if queries_path is None:
        queries_path = (
            Path(__file__).parent.parent.parent.parent / "eval" / "retrieval_queries.yaml"
        )

    # Resolve the effective report path:
    # - sentinel (omitted by caller) → use default file path
    # - None (explicitly passed) → no file write
    # - Path instance → write to that path
    # A runtime isinstance check replaces the prior ``# type: ignore`` so
    # bad caller types (e.g. str) fail loudly here rather than deep in
    # the JSON writer.
    if report_path is _REPORT_PATH_DEFAULT:
        effective_report_path: Path | None = Path(".eval-artifacts/retrieval_extended.json")
    elif report_path is None:
        effective_report_path = None
    elif isinstance(report_path, Path):
        effective_report_path = report_path
    else:
        raise TypeError(
            f"report_path must be pathlib.Path, None, or omitted (got {type(report_path).__name__})"
        )

    # The env overlay only influences ``ToolRegistry.__init__`` (which reads
    # ``UMMAYA_RETRIEVAL_BACKEND`` to bind a retriever). Scope it narrowly so
    # it is not leaked across the scoring phase, and skip it entirely when the
    # caller has injected a pre-built registry whose retriever is already set,
    # or when ``backend`` is ``None`` (honour ambient env var, defaulting to
    # ``bm25`` inside ``build_retriever_from_env``).
    if registry is None and backend is not None:
        with _backend_env_overlay(backend):
            built_registry, _ = _build_registry()
    elif registry is None:
        built_registry, _ = _build_registry()
    else:
        built_registry = registry

    queries = _load_queries(queries_path)
    report: dict[str, Any] = asyncio.run(_evaluate(queries, built_registry))

    # Compute SC-01 status outside the env overlay — depends on registry
    # composition, not on the backend in use.
    sc01_status, sc01_reason = _compute_sc01_status(built_registry)
    report["sc_01_status"] = sc01_status
    report["sc_01_reason"] = sc01_reason

    # SC-02 placeholder — evaluated against adversarial file in a follow-on task.
    report["sc_02_status"] = "PENDING_ADVERSARIAL_EVAL"

    if effective_report_path is not None:
        _write_report(report, effective_report_path)

    return report


def main(argv: list[str] | None = None) -> None:
    """CLI entry point for retrieval evaluation.

    Usage (baseline, backward-compatible)::

        python -m ummaya.eval.retrieval eval/retrieval_queries.yaml

    Usage (extended gate with backend selection)::

        python -m ummaya.eval.retrieval \\
            --backend hybrid \\
            --queries eval/retrieval_queries.yaml \\
            --report .eval-artifacts/retrieval_extended.json

    When ``--backend`` is supplied, the extended gate runs via
    ``run_extended_gate()`` and the exit code follows the extended scheme:
        0 — pass   (recall@5 >= 0.80, sc_01 is not PENDING_#22)
        1 — warn   (0.60 <= recall@5 < 0.80)
        2 — PENDING_#22  (registry too small / no Phase-3 adapters)
        2 — fail   (recall@5 < 0.60)

    Without ``--backend``, the legacy positional-arg path runs.

    Args:
        argv: Argument list (default: sys.argv[1:]).
    """
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    raw_args = argv if argv is not None else sys.argv[1:]

    # Detect extended mode: any arg that starts with "--" triggers argparse.
    # The legacy positional mode (first arg is a yaml path, no flags) still
    # works so existing scripts / tests are not broken.
    if raw_args and raw_args[0].startswith("--"):
        parser = argparse.ArgumentParser(
            prog="ummaya.eval.retrieval",
            description="Retrieval quality evaluation harness (extended gate).",
        )
        parser.add_argument(
            "--backend",
            choices=["bm25", "dense", "hybrid"],
            default=None,
            help=(
                "Retrieval backend to activate. "
                "Defaults to honouring UMMAYA_RETRIEVAL_BACKEND "
                "(or bm25 when that env var is unset)."
            ),
        )
        parser.add_argument(
            "--queries",
            type=Path,
            default=None,
            help="Path to retrieval_queries.yaml (default: eval/retrieval_queries.yaml).",
        )
        parser.add_argument(
            "--report",
            type=Path,
            default=None,
            help=(
                "Path to write the JSON report (default: .eval-artifacts/retrieval_extended.json)."
            ),
        )
        parsed = parser.parse_args(raw_args)

        effective_backend = parsed.backend or os.environ.get("UMMAYA_RETRIEVAL_BACKEND", "bm25")
        logger.info("Running extended gate with backend=%s", effective_backend)
        # Only forward ``report_path`` when the operator actually passed
        # ``--report``. If we always forwarded ``parsed.report`` (which is
        # ``None`` when omitted), ``run_extended_gate`` would interpret that
        # as "skip writing" and silently drop the default artifact at
        # ``.eval-artifacts/retrieval_extended.json``.
        #
        # Likewise for ``--backend``: when the operator omits it, we forward
        # ``None`` so ``run_extended_gate`` honours the ambient
        # ``UMMAYA_RETRIEVAL_BACKEND`` env var rather than force-overlaying a
        # CLI default that would silently override an operator's export.
        gate_kwargs: dict[str, Any] = {
            "backend": parsed.backend,
            "queries_path": parsed.queries,
        }
        if parsed.report is not None:
            gate_kwargs["report_path"] = parsed.report
        report = run_extended_gate(**gate_kwargs)

        recall5 = report["recall_at_5"]
        recall1 = report["recall_at_1"]
        sc01 = report.get("sc_01_status", "EVALUATED")

        if report.get("warnings"):
            for w in report["warnings"]:
                logger.warning("WARN: %s", w)

        if sc01 == "PENDING_#22":
            reason = report.get("sc_01_reason", "")
            logger.warning("SC-01 PENDING_#22: %s", reason)
            print(  # noqa: T201
                f"[PENDING_#22] recall@5={recall5:.2%} recall@1={recall1:.2%} "
                f"total={report['total_queries']} registry={report['registry_size']} "
                f"sc_01={sc01}"
            )
            sys.exit(2)

        code = _exit_code(float(recall5))
        status = {0: "PASS", 1: "WARN", 2: "FAIL"}[code]
        print(  # noqa: T201
            f"[{status}] recall@5={recall5:.2%} recall@1={recall1:.2%} "
            f"total={report['total_queries']} registry={report['registry_size']} "
            f"sc_01={sc01}"
        )
        sys.exit(code)

    # Legacy positional mode — byte-identical to the pre-T031 behaviour.
    if not raw_args:
        logger.error("Usage: python -m ummaya.eval.retrieval <queries.yaml>")
        sys.exit(2)

    queries_path = Path(raw_args[0])
    output_path = Path(".eval-artifacts/retrieval.json")

    logger.info("Loading queries from %s", queries_path)
    queries = _load_queries(queries_path)
    logger.info("Loaded %d queries", len(queries))

    logger.info("Building tool registry...")
    registry, _ = _build_registry()
    logger.info("Registry size: %d adapters", len(registry))  # type: ignore[arg-type]

    logger.info("Running BM25 retrieval evaluation...")
    report = asyncio.run(_evaluate(queries, registry))

    _write_report(report, output_path)

    recall5 = report["recall_at_5"]
    recall1 = report["recall_at_1"]

    if report["warnings"]:
        for w in report["warnings"]:
            logger.warning("WARN: %s", w)

    code = _exit_code(float(recall5))
    status = {0: "PASS", 1: "WARN", 2: "FAIL"}[code]

    # Single-line stdout summary (only print() allowed per spec)
    print(  # noqa: T201
        f"[{status}] recall@5={recall5:.2%} recall@1={recall1:.2%} "
        f"total={report['total_queries']} registry={report['registry_size']}"
    )

    sys.exit(code)


if __name__ == "__main__":
    main()
