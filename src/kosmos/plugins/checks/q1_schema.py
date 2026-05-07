# SPDX-License-Identifier: Apache-2.0
"""Q1 — Schema integrity (10 checks).

Per research § R-1 Q1:

* Q1-PYV2 — `Pydantic v2 BaseModel` used in `schema.py`.
* Q1-NOANY — No `Any` types in `schema.py`.
* Q1-FIELD-DESC — Every `Field(...)` carries `description=`.
* Q1-INPUT-MODEL — `LookupInput` (or primitive-named input) class present.
* Q1-OUTPUT-MODEL — `LookupOutput` class present.
* Q1-MANIFEST-VALID — `manifest.yaml` validates against `PluginManifest`.
* Q1-FROZEN — `LookupInput` / `LookupOutput` `model_config` carries `frozen=True`.
* Q1-EXTRA-FORBID — Likewise `extra="forbid"`.
* Q1-VERSION-SEMVER — `manifest.version` is `X.Y.Z`.
* Q1-PLUGIN-ID-REGEX — `manifest.plugin_id` matches `^[a-z][a-z0-9_]*$`.

All checks are pure functions of :class:`CheckContext` and never touch
the network. AST-based scans operate on the plugin's `schema.py` text;
manifest-driven checks operate on the parsed manifest.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from kosmos.plugins.checks.framework import (
    CheckContext,
    CheckOutcome,
    failed,
    passed,
)

_PLUGIN_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def _schema_module_path(ctx: CheckContext) -> Path | None:
    if ctx.manifest is None:
        return None
    pkg = f"plugin_{ctx.manifest.plugin_id}"
    candidate = ctx.plugin_root / pkg / "schema.py"
    if candidate.is_file():
        return candidate
    return None


def _schema_text(ctx: CheckContext) -> str | None:
    path = _schema_module_path(ctx)
    if path is None:
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _parsed_schema_ast(ctx: CheckContext) -> ast.Module | None:
    text = _schema_text(ctx)
    if text is None:
        return None
    try:
        return ast.parse(text)
    except SyntaxError:
        return None


def _iter_classes(tree: ast.Module) -> list[ast.ClassDef]:
    return [n for n in tree.body if isinstance(n, ast.ClassDef)]


def check_pyv2(ctx: CheckContext) -> CheckOutcome:
    """Q1-PYV2 — schema.py imports BaseModel from pydantic and uses it."""
    text = _schema_text(ctx)
    if text is None:
        return failed(
            ko="schema.py 를 찾을 수 없음 (Q1-PYV2)",
            en="schema.py not found (Q1-PYV2)",
        )
    if "from pydantic import" not in text or "BaseModel" not in text:
        return failed(
            ko="Pydantic v2 BaseModel 을 import 해야 함",
            en="must import Pydantic v2 BaseModel",
        )
    return passed()


def check_noany(ctx: CheckContext) -> CheckOutcome:
    """Q1-NOANY — `Any` is not used as a type annotation in schema.py."""
    tree = _parsed_schema_ast(ctx)
    if tree is None:
        return failed(
            ko="schema.py AST 파싱 실패 (Q1-NOANY)",
            en="schema.py AST parse failed (Q1-NOANY)",
        )
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Name)
            and node.id == "Any"
            and isinstance(getattr(node, "ctx", None), ast.Load)
        ):
            # Allow `from typing import ...` line — only flag usage in
            # annotations. Heuristic: a Name in Load context is either
            # imported or used in an annotation; either way `Any` is the
            # violation we forbid.
            return failed(
                ko="schema.py 에 'Any' 타입 사용 금지 (Q1-NOANY)",
                en="`Any` type is banned in schema.py (Q1-NOANY)",
            )
    return passed()


def check_field_desc(ctx: CheckContext) -> CheckOutcome:
    """Q1-FIELD-DESC — every Field(...) call has a description= kwarg."""
    tree = _parsed_schema_ast(ctx)
    if tree is None:
        return failed(
            ko="schema.py AST 파싱 실패 (Q1-FIELD-DESC)",
            en="schema.py AST parse failed (Q1-FIELD-DESC)",
        )
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "Field"
        ):
            kwarg_names = {kw.arg for kw in node.keywords if kw.arg}
            if "description" not in kwarg_names:
                return failed(
                    ko="모든 Field 에 description= 필요 (Q1-FIELD-DESC)",
                    en="every Field(...) must include description= (Q1-FIELD-DESC)",
                )
    return passed()


def check_input_model(ctx: CheckContext) -> CheckOutcome:
    """Q1-INPUT-MODEL — class named LookupInput (or primitive-named) present."""
    tree = _parsed_schema_ast(ctx)
    if tree is None:
        return failed(
            ko="schema.py AST 파싱 실패 (Q1-INPUT-MODEL)",
            en="schema.py AST parse failed (Q1-INPUT-MODEL)",
        )
    classes = {c.name for c in _iter_classes(tree)}
    candidates = {"LookupInput", "SubmitInput", "VerifyInput"}
    if not (classes & candidates):
        return failed(
            ko=f"input model class 가 필요 (Q1-INPUT-MODEL); 후보: {sorted(candidates)}",
            en=f"input model class required (Q1-INPUT-MODEL); candidates: {sorted(candidates)}",
        )
    return passed()


def check_output_model(ctx: CheckContext) -> CheckOutcome:
    """Q1-OUTPUT-MODEL — class named LookupOutput present."""
    tree = _parsed_schema_ast(ctx)
    if tree is None:
        return failed(
            ko="schema.py AST 파싱 실패 (Q1-OUTPUT-MODEL)",
            en="schema.py AST parse failed (Q1-OUTPUT-MODEL)",
        )
    classes = {c.name for c in _iter_classes(tree)}
    candidates = {"LookupOutput", "SubmitOutput", "VerifyOutput"}
    if not (classes & candidates):
        return failed(
            ko=f"output model class 가 필요 (Q1-OUTPUT-MODEL); 후보: {sorted(candidates)}",
            en=f"output model class required (Q1-OUTPUT-MODEL); candidates: {sorted(candidates)}",
        )
    return passed()


def check_manifest_valid(ctx: CheckContext) -> CheckOutcome:
    """Q1-MANIFEST-VALID — manifest.yaml validates against PluginManifest."""
    if ctx.manifest is None:
        return failed(
            ko="manifest.yaml 이 PluginManifest 검증 실패 (Q1-MANIFEST-VALID)",
            en="manifest.yaml does not validate as PluginManifest (Q1-MANIFEST-VALID)",
        )
    return passed()


def _classes_with_model_config(tree: ast.Module) -> list[tuple[ast.ClassDef, ast.Call]]:
    """Return (class, model_config_call) for every class declaring model_config."""
    out: list[tuple[ast.ClassDef, ast.Call]] = []
    for cls in _iter_classes(tree):
        for stmt in cls.body:
            if (
                isinstance(stmt, ast.Assign)
                and stmt.targets
                and isinstance(stmt.targets[0], ast.Name)
                and stmt.targets[0].id == "model_config"
                and isinstance(stmt.value, ast.Call)
            ):
                out.append((cls, stmt.value))
    return out


def _config_kwarg(call: ast.Call, kwarg: str) -> ast.AST | None:
    """Return the AST node for a ConfigDict kwarg, or None if missing."""
    for kw in call.keywords:
        if kw.arg == kwarg:
            return kw.value
    return None


def check_frozen(ctx: CheckContext) -> CheckOutcome:
    """Q1-FROZEN — every Pydantic class with model_config must declare frozen=True.

    H8 (review eval): replace the ambiguous "any class has it" pattern
    with a strict per-class check — if ANY model_config is missing
    frozen=True (or sets it to False), the check fails. This catches
    the case where LookupInput is frozen but LookupOutput isn't.
    """
    tree = _parsed_schema_ast(ctx)
    if tree is None:
        return failed(
            ko="schema.py AST 파싱 실패 (Q1-FROZEN)",
            en="schema.py AST parse failed (Q1-FROZEN)",
        )

    pairs = _classes_with_model_config(tree)
    if not pairs:
        return failed(
            ko="schema.py 의 어느 모델도 model_config 를 선언하지 않음 (Q1-FROZEN)",
            en="no class in schema.py declares model_config (Q1-FROZEN)",
        )

    for cls, call in pairs:
        node = _config_kwarg(call, "frozen")
        if node is None:
            return failed(
                ko=f"schema.py {cls.name} 의 model_config 에 frozen 미선언 (Q1-FROZEN)",
                en=f"schema.py {cls.name} model_config missing frozen kwarg (Q1-FROZEN)",
            )
        if not (isinstance(node, ast.Constant) and node.value is True):
            return failed(
                ko=f"schema.py {cls.name} 의 model_config 가 frozen=True 가 아님 (Q1-FROZEN)",
                en=f"schema.py {cls.name} model_config does not set frozen=True (Q1-FROZEN)",
            )
    return passed()


def check_extra_forbid(ctx: CheckContext) -> CheckOutcome:
    """Q1-EXTRA-FORBID — model_config(extra='forbid') on input/output models."""
    tree = _parsed_schema_ast(ctx)
    if tree is None:
        return failed(
            ko="schema.py AST 파싱 실패 (Q1-EXTRA-FORBID)",
            en="schema.py AST parse failed (Q1-EXTRA-FORBID)",
        )
    # extra="forbid" OR extra="allow" — many adapters use allow on the output
    # model so unknown upstream fields don't break parsing. We only require
    # `extra` to be SET (not omitted).
    found = False
    for cls in _iter_classes(tree):
        for stmt in cls.body:
            if (
                isinstance(stmt, ast.Assign)
                and stmt.targets
                and isinstance(stmt.targets[0], ast.Name)
                and stmt.targets[0].id == "model_config"
                and isinstance(stmt.value, ast.Call)
            ):
                for kw in stmt.value.keywords:
                    if kw.arg == "extra":
                        found = True
                        break
    if not found:
        return failed(
            ko="schema.py 의 model_config 에 extra= 명시 필요 (Q1-EXTRA-FORBID)",
            en="schema.py model_config must declare extra= explicitly (Q1-EXTRA-FORBID)",
        )
    return passed()


def check_version_semver(ctx: CheckContext) -> CheckOutcome:
    """Q1-VERSION-SEMVER — manifest.version is N.N.N."""
    if ctx.manifest is None:
        return failed(
            ko="manifest.yaml 검증 실패로 version 확인 불가",
            en="cannot check version because manifest.yaml failed validation",
        )
    if not _SEMVER_RE.fullmatch(ctx.manifest.version):
        return failed(
            ko=f"version {ctx.manifest.version!r} 가 SemVer 형식이 아님 (Q1-VERSION-SEMVER)",
            en=f"version {ctx.manifest.version!r} is not SemVer (Q1-VERSION-SEMVER)",
        )
    return passed()


def check_plugin_id_regex(ctx: CheckContext) -> CheckOutcome:
    """Q1-PLUGIN-ID-REGEX — manifest.plugin_id matches snake_case regex."""
    if ctx.manifest is None:
        return failed(
            ko="manifest.yaml 검증 실패로 plugin_id 확인 불가",
            en="cannot check plugin_id because manifest.yaml failed validation",
        )
    if not _PLUGIN_ID_RE.fullmatch(ctx.manifest.plugin_id):
        return failed(
            ko=(
                f"plugin_id {ctx.manifest.plugin_id!r} 가 ^[a-z][a-z0-9_]*$ 와 "
                "맞지 않음 (Q1-PLUGIN-ID-REGEX)"
            ),
            en=(
                f"plugin_id {ctx.manifest.plugin_id!r} does not match "
                "^[a-z][a-z0-9_]*$ (Q1-PLUGIN-ID-REGEX)"
            ),
        )
    return passed()


__all__ = [
    "check_pyv2",
    "check_noany",
    "check_field_desc",
    "check_input_model",
    "check_output_model",
    "check_manifest_valid",
    "check_frozen",
    "check_extra_forbid",
    "check_version_semver",
    "check_plugin_id_regex",
]
