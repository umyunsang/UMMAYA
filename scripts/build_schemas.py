# SPDX-License-Identifier: Apache-2.0
"""Build JSON Schema files for all registered KOSMOS tool adapters.

Covers the active registries:
  1. kosmos.tools.registry.ToolRegistry  — lookup-side tools (14 adapters)
  2. kosmos.primitives.submit._ADAPTER_REGISTRY  — submit adapters (2 mocks)
  3. kosmos.primitives.verify._VERIFY_ADAPTERS   — verify adapters (6 mocks)

Subscribe schemas are intentionally not generated. National notification
delivery is deferred until KOSMOS has an app/push runtime that can own delivery.

Usage:
    python scripts/build_schemas.py [--check] [--output-dir DIR] [--quiet]

Exit codes:
    0 — success (or --check with no drift)
    1 — drift detected with --check
    2 — registry import failed
    3 — output write failed (IO / permission)
    4 — schema generation failed for at least one model
"""

from __future__ import annotations

import argparse
import importlib
import json
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic import BaseModel

logger = logging.getLogger(__name__)


def _find_repo_root(start: Path) -> Path:
    """Ascend from *start* until a directory containing pyproject.toml is found."""
    current = start.resolve()
    while True:
        if (current / "pyproject.toml").exists():
            return current
        parent = current.parent
        if parent == current:
            raise FileNotFoundError(
                "Could not locate pyproject.toml — is this script inside the repo?"
            )
        current = parent


def _build_schema_payload(
    tool_id: str,
    input_model: type[BaseModel],
    output_model: type[BaseModel],
) -> dict[str, object]:
    """Produce the combined JSONSchema entity for one adapter.

    The input envelope occupies the top-level schema (type/properties/required).
    The output model is injected under ``$defs`` keyed by its class name.
    All ``$defs`` from both models are merged under the top-level ``$defs`` key.

    Args:
        tool_id: Stable snake_case adapter identifier.
        input_model: Pydantic v2 model class for request parameters.
        output_model: Pydantic v2 model class for response data.

    Returns:
        A dict ready for ``json.dumps``.
    """
    ref_template = "#/$defs/{model}"
    input_schema = input_model.model_json_schema(
        mode="validation", ref_template=ref_template
    )
    output_schema = output_model.model_json_schema(
        mode="validation", ref_template=ref_template
    )

    # Start from the input schema as the root; harvest its $defs.
    merged_defs: dict[str, object] = dict(input_schema.pop("$defs", {}))

    # Collect output schema $defs.
    output_defs = dict(output_schema.pop("$defs", {}))
    merged_defs.update(output_defs)

    # Nest the output model itself under $defs keyed by its class name.
    merged_defs[output_model.__name__] = output_schema

    payload: dict[str, object] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"https://kosmos.example/api/schemas/{tool_id}.json",
        "title": tool_id,
    }
    # Merge root-level input schema fields (type, properties, required, etc.)
    for key, value in input_schema.items():
        if key not in ("title",):
            payload[key] = value

    # Attach merged $defs (input nested models + output model).
    if merged_defs:
        payload["$defs"] = merged_defs

    return payload


def _render(payload: dict[str, object]) -> str:
    """Deterministically render payload to a JSON string with trailing newline."""
    return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def _resolve_model_ref(ref: str) -> type | None:
    """Resolve an ``input_model_ref`` string to its Pydantic model class.

    Two formats are supported:
    - ``module.path:ClassName``  (colon separator, e.g.
      ``kosmos.primitives.verify:VerifyInput``)
    - ``module.path.ClassName``  (dot separator, e.g.
      ``kosmos.tools.mock.data_go_kr.fines_pay.FinesPayParams``)

    Returns the class object, or ``None`` if the module/attribute cannot be found.
    """
    if ":" in ref:
        mod_path, cls_name = ref.rsplit(":", 1)
    else:
        mod_path, cls_name = ref.rsplit(".", 1)
    try:
        mod = importlib.import_module(mod_path)
        return getattr(mod, cls_name)
    except (ImportError, AttributeError) as exc:
        logger.warning("Cannot resolve model ref %r: %s", ref, exc)
        return None


def _collect_primitive_adapters() -> list[tuple[str, type, type]]:
    """Collect (tool_id, input_model_class, output_model_class) from active
    primitive registries: submit and verify.

    The caller must have already imported ``kosmos.tools.mock`` (which triggers
    all adapter self-registration side-effects) before calling this function.

    For verify adapters the tool_id is sourced from the per-module
    ``ADAPTER_REGISTRATION.tool_id`` rather than the family key used internally
    by ``_VERIFY_ADAPTERS``.  If a verify adapter module cannot be located the
    family string is used as a fallback tool_id.

    Returns:
        List of 3-tuples sorted alphabetically by tool_id.
    """
    from pydantic import BaseModel  # noqa: PLC0415

    results: dict[str, tuple[type, type]] = {}

    # ------------------------------------------------------------------
    # 1. Submit adapters — _ADAPTER_REGISTRY: dict[tool_id, (reg, fn)]
    # ------------------------------------------------------------------
    submit_mod = importlib.import_module("kosmos.primitives.submit")
    submit_output_cls = submit_mod.SubmitOutput
    submit_registry: dict[str, tuple] = getattr(submit_mod, "_ADAPTER_REGISTRY", {})

    for tool_id, (reg, _fn) in submit_registry.items():
        input_ref: str | None = getattr(reg, "input_model_ref", None)
        if not input_ref:
            logger.warning("submit adapter %r has no input_model_ref — skipping", tool_id)
            continue
        input_cls = _resolve_model_ref(input_ref)
        if input_cls is None or not (
            isinstance(input_cls, type) and issubclass(input_cls, BaseModel)
        ):
            logger.warning(
                "submit adapter %r: input_model_ref=%r did not resolve to a "
                "BaseModel subclass — skipping",
                tool_id,
                input_ref,
            )
            continue
        results[tool_id] = (input_cls, submit_output_cls)

    # ------------------------------------------------------------------
    # 2. Verify adapters — _VERIFY_ADAPTERS: dict[family, callable]
    #    Per-family tool_id comes from the ADAPTER_REGISTRATION on each mock module.
    #    All six share VerifyInput / VerifyOutput.
    # ------------------------------------------------------------------
    verify_mod = importlib.import_module("kosmos.primitives.verify")
    verify_input_cls = verify_mod.VerifyInput
    verify_output_cls = verify_mod.VerifyOutput
    verify_registry: dict[str, object] = getattr(verify_mod, "_VERIFY_ADAPTERS", {})

    # Canonical mapping: family key → mock module path
    verify_family_module: dict[str, str] = {
        "digital_onepass": "kosmos.tools.mock.verify_digital_onepass",
        "ganpyeon_injeung": "kosmos.tools.mock.verify_ganpyeon_injeung",
        "geumyung_injeungseo": "kosmos.tools.mock.verify_geumyung_injeungseo",
        "gongdong_injeungseo": "kosmos.tools.mock.verify_gongdong_injeungseo",
        "mobile_id": "kosmos.tools.mock.verify_mobile_id",
        "mydata": "kosmos.tools.mock.verify_mydata",
    }

    for family in verify_registry:
        # Prefer tool_id from the ADAPTER_REGISTRATION on the mock module.
        tool_id = family  # fallback
        mod_path = verify_family_module.get(family)
        if mod_path:
            try:
                vmod = importlib.import_module(mod_path)
                areg = getattr(vmod, "ADAPTER_REGISTRATION", None)
                if areg is not None:
                    tool_id = areg.tool_id
            except ImportError:
                pass
        results[tool_id] = (verify_input_cls, verify_output_cls)

    # ------------------------------------------------------------------
    # Return sorted by tool_id for deterministic output
    return [(tid, inp, out) for tid, (inp, out) in sorted(results.items())]


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="build_schemas",
        description="Generate JSON Schema files for all registered KOSMOS tool adapters.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        default=False,
        help="Validate on-disk schemas match current output. Exit 1 on drift.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        metavar="DIR",
        help="Output directory (default: docs/api/schemas/ under repo root).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        default=False,
        help="Suppress per-file progress; print only the final summary.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:  # noqa: C901
    """Entry point. Returns an exit code."""
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    args = _parse_args(argv)

    # ------------------------------------------------------------------
    # 1. Resolve repository root.
    # ------------------------------------------------------------------
    script_path = Path(__file__).resolve()
    try:
        repo_root = _find_repo_root(script_path.parent)
    except FileNotFoundError:
        return 2

    # Insert repo root into sys.path so the kosmos package is importable
    # even when the script is invoked without `uv run` / activated venv.
    src_path = repo_root / "src"
    if src_path.exists() and str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

    # ------------------------------------------------------------------
    # 2. Import and populate the registry.
    # ------------------------------------------------------------------
    try:
        from kosmos.tools.executor import ToolExecutor  # type: ignore[import]
        from kosmos.tools.register_all import register_all_tools  # type: ignore[import]
        from kosmos.tools.registry import ToolRegistry  # type: ignore[import]
    except Exception:  # pragma: no cover
        logger.exception("Registry import failed")
        return 2

    try:
        registry = ToolRegistry()
        executor = ToolExecutor(registry)
        register_all_tools(registry, executor)
    except SystemExit:
        # register_all_tools raises SystemExit(78) on routing validation failure.
        return 2
    except Exception:
        logger.exception("Registry population failed")
        return 2

    # ------------------------------------------------------------------
    # 3. Determine output directory.
    # ------------------------------------------------------------------
    if args.output_dir is not None:
        output_dir = Path(args.output_dir)
    else:
        output_dir = repo_root / "docs" / "api" / "schemas"

    if not args.check:
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            return 3

    # ------------------------------------------------------------------
    # 4. Collect all adapters: ToolRegistry + active primitive registries.
    # ------------------------------------------------------------------

    # Trigger mock adapter self-registration side effects (submit/verify).
    try:
        import kosmos.tools.mock  # noqa: F401, PLC0415
    except Exception:  # pragma: no cover
        logger.exception("Mock registry import failed")
        return 2

    # Build sorted (tool_id, input_model, output_model) list from ToolRegistry.
    tool_registry_entries: list[tuple[str, type, type]] = [
        (t.id, t.input_schema, t.output_schema)
        for t in sorted(registry.all_tools(), key=lambda t: t.id)
    ]

    # Collect primitive adapter entries.
    try:
        primitive_entries = _collect_primitive_adapters()
    except Exception:
        logger.exception("Primitive registry collection failed")
        return 2

    # Merge: ToolRegistry entries take precedence; primitive entries keyed by
    # tool_id are appended only when not already present (no deduplication needed
    # since the registries are disjoint, but guard for safety).
    tool_id_seen: set[str] = {tid for tid, _, _ in tool_registry_entries}
    all_entries: list[tuple[str, type, type]] = list(tool_registry_entries)
    for tid, inp, out in primitive_entries:
        if tid not in tool_id_seen:
            all_entries.append((tid, inp, out))
            tool_id_seen.add(tid)
        else:
            logger.warning(
                "tool_id %r appears in both ToolRegistry and a primitive registry — "
                "ToolRegistry entry wins",
                tid,
            )

    # Final deterministic sort across all registries.
    all_entries.sort(key=lambda e: e[0])

    wrote: list[str] = []
    unchanged: list[str] = []
    drifted: list[str] = []
    schema_errors: list[str] = []

    for tool_id, input_model, output_model in all_entries:
        # Generate schema payload.
        try:
            payload = _build_schema_payload(tool_id, input_model, output_model)
        except Exception:
            logger.exception("Schema generation failed for tool_id=%s", tool_id)
            schema_errors.append(tool_id)
            continue

        rendered = _render(payload)
        out_file = output_dir / f"{tool_id}.json"

        if args.check:
            # Compare against on-disk content.
            if out_file.exists():
                existing = out_file.read_text(encoding="utf-8")
                if existing == rendered:
                    if not args.quiet:
                        pass
                    unchanged.append(tool_id)
                else:
                    if not args.quiet:
                        pass
                    drifted.append(tool_id)
            else:
                if not args.quiet:
                    pass
                drifted.append(tool_id)
        else:
            # Write only if content changed (preserve mtime when unchanged).
            if out_file.exists() and out_file.read_text(encoding="utf-8") == rendered:
                if not args.quiet:
                    pass
                unchanged.append(tool_id)
            else:
                try:
                    out_file.write_text(rendered, encoding="utf-8")
                except OSError:
                    return 3
                if not args.quiet:
                    pass
                wrote.append(tool_id)

    # ------------------------------------------------------------------
    # 5. Print summary and return exit code.
    # ------------------------------------------------------------------
    if schema_errors:
        return 4

    if args.check:
        if drifted:
            return 1
        else:
            return 0
    else:
        return 0


if __name__ == "__main__":
    sys.exit(main())
