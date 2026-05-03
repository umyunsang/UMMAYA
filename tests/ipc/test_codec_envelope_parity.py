# SPDX-License-Identifier: Apache-2.0
"""Field-level parity check between codec.ts envelope zod and Pydantic _BaseFrame.

Spec 2642 / Epic F · S7 / US3.

Background
----------
``tui/src/ipc/frames.generated.ts`` is auto-generated from
``src/kosmos/ipc/frame_schema.py`` (covered by the existing
``test_schema_python_ts_diff.py`` JSON-Schema parity gate).

``tui/src/ipc/codec.ts`` is **hand-written** and provides runtime
zod validation belt-and-braces atop the generated TS types. The
hand-written zod must match the Pydantic envelope field-for-field —
otherwise the TS side will silently accept a frame the Python backend
would reject (or vice-versa).

This test parses the codec.ts ``BaseFrame = z.object({...})`` block
and asserts each field's nullability + min-length constraint matches
``_BaseFrame.model_fields``.

A negative-fixture (``tests/ipc/fixtures/codec_drift_negative.ts``)
proves the gate fails when an intentional drift is injected (the
companion ``test_drift_negative_fixture_triggers_failure`` test).

Drift fixture is opt-in only via ``KOSMOS_IPC_PARITY_DRIFT_FIXTURE=1``;
``conftest.py`` enforces the env var defaults to OFF in CI.
"""

from __future__ import annotations

import os
import pathlib
import re
from dataclasses import dataclass

import pytest

from kosmos.ipc.frame_schema import _BaseFrame

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
_REAL_CODEC_PATH = _REPO_ROOT / "tui" / "src" / "ipc" / "codec.ts"
_DRIFT_FIXTURE_PATH = _REPO_ROOT / "tests" / "ipc" / "fixtures" / "codec_drift_negative.ts"
_DRIFT_ENV_VAR = "KOSMOS_IPC_PARITY_DRIFT_FIXTURE"


# ---------------------------------------------------------------------------
# Spec — what each envelope field MUST look like on both sides
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FieldSpec:
    """Normalised parity contract for one envelope field."""

    required: bool
    nullable: bool
    min_length: int | None  # None means "no min_length constraint"
    type_kind: str  # "string" / "int" / "literal" / "enum" / "object"

    def __str__(self) -> str:  # pragma: no cover — diagnostic only
        parts = [self.type_kind]
        if self.min_length is not None:
            parts.append(f"min({self.min_length})")
        if self.nullable:
            parts.append("nullable")
        if not self.required:
            parts.append("optional")
        return ".".join(parts)


# ---------------------------------------------------------------------------
# Pydantic side — derive the spec from _BaseFrame
# ---------------------------------------------------------------------------


def _derive_pydantic_envelope_spec() -> dict[str, FieldSpec]:
    """Walk _BaseFrame.model_fields and produce the parity contract.

    The contract is derived authoritatively from the Pydantic model so
    that the test does not duplicate the canonical envelope definition.
    """
    fields = _BaseFrame.model_fields
    out: dict[str, FieldSpec] = {}

    for name, info in fields.items():
        annotation = info.annotation
        annot_str = str(annotation) if annotation is not None else ""

        # Determine type_kind heuristically from the annotation string.
        if "Literal" in annot_str:
            type_kind = "literal"
        elif "FrameTrailer" in annot_str:
            type_kind = "object"
        elif "int" in annot_str.lower() or "NonNegativeInt" in annot_str:
            type_kind = "int"
        elif "str" in annot_str.lower():
            type_kind = "string"
        else:  # pragma: no cover — defensive fallback
            type_kind = "unknown"

        # Nullability.
        nullable = "None" in annot_str or "| None" in annot_str

        # Required-ness: default == PydanticUndefined → required.
        required = info.is_required()

        # min_length from Field metadata.
        min_length: int | None = None
        for meta in info.metadata:
            min_len_attr = getattr(meta, "min_length", None)
            if min_len_attr is not None:
                min_length = int(min_len_attr)
                break

        out[name] = FieldSpec(
            required=required,
            nullable=nullable,
            min_length=min_length,
            type_kind=type_kind,
        )

    return out


# ---------------------------------------------------------------------------
# codec.ts side — extract the envelope spec via narrow regex
# ---------------------------------------------------------------------------

# Match the BaseFrame zod object body. Two anchors:
#   const BaseFrame = z.object({
#     ...
#   })
_BASE_FRAME_BLOCK_RE = re.compile(
    r"const\s+BaseFrame\s*=\s*z\.object\(\{(?P<body>.*?)\n\}\)",
    re.DOTALL,
)

# Match a single field line. Three shapes we accept:
#   foo: z.string(),
#   foo: z.string().min(1),
#   foo: z.string().min(1).nullable().optional(),
#   foo: z.literal('1.0'),
#   foo: z.number().int().min(0),
#   foo: z.enum([...]),
#   foo: z.object({...}).nullable().optional(),
#
# We split the body into top-level statements (commented lines stripped) and
# parse each one.
_COMMENT_RE = re.compile(r"//.*$", re.MULTILINE)


def _strip_comments(text: str) -> str:
    return _COMMENT_RE.sub("", text)


_FIELD_LINE_RE = re.compile(
    r"^(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*(?P<chain>.+)$",
    re.DOTALL,
)


def _split_into_top_level_statements(text: str) -> list[str]:
    """Split text on top-level commas (depth 0), respecting () and {} nesting."""
    statements: list[str] = []
    depth_paren = 0
    depth_brace = 0
    current: list[str] = []
    for ch in text:
        if ch == "(":
            depth_paren += 1
        elif ch == ")":
            depth_paren -= 1
        elif ch == "{":
            depth_brace += 1
        elif ch == "}":
            depth_brace -= 1
        at_top_level_comma = ch == "," and depth_paren == 0 and depth_brace == 0
        if at_top_level_comma:
            statements.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


def _split_top_level_field_lines(body: str) -> list[tuple[str, str]]:
    """Return list of (field_name, zod_chain) at the top level of BaseFrame.

    Strips comments, splits on top-level commas, then matches each
    statement against ``<name>: <chain>``.
    """
    text = _strip_comments(body)
    fields: list[tuple[str, str]] = []
    for stmt in _split_into_top_level_statements(text):
        if not stmt:
            continue
        m = _FIELD_LINE_RE.match(stmt)
        if m is None:
            continue
        fields.append((m.group("name"), m.group("chain").strip()))
    return fields


def _parse_zod_chain(chain: str) -> FieldSpec:
    """Extract the FieldSpec from a single zod chain expression."""
    chain_compact = re.sub(r"\s+", "", chain)

    # type_kind
    if chain_compact.startswith("z.literal"):
        type_kind = "literal"
    elif chain_compact.startswith("z.string"):
        type_kind = "string"
    elif chain_compact.startswith("z.number"):
        type_kind = "int" if ".int(" in chain_compact else "number"
    elif chain_compact.startswith("z.enum"):
        type_kind = "enum"
    elif chain_compact.startswith("z.object"):
        type_kind = "object"
    elif chain_compact.startswith("z.boolean"):
        type_kind = "boolean"
    else:  # pragma: no cover — defensive
        type_kind = "unknown"

    # min_length from `.min(N)` (string only — for numbers .min is range, distinct concept).
    min_length: int | None = None
    if type_kind in {"string"}:
        m = re.search(r"\.min\((\d+)\)", chain_compact)
        if m:
            min_length = int(m.group(1))

    nullable = ".nullable(" in chain_compact
    optional = ".optional(" in chain_compact
    required = not optional

    return FieldSpec(
        required=required,
        nullable=nullable,
        min_length=min_length,
        type_kind=type_kind,
    )


def _derive_codec_envelope_spec(codec_text: str) -> dict[str, FieldSpec]:
    """Parse codec.ts text → envelope FieldSpec dict."""
    m = _BASE_FRAME_BLOCK_RE.search(codec_text)
    if m is None:
        raise AssertionError(
            "Could not locate `const BaseFrame = z.object({...})` block in codec.ts. "
            "Did the envelope definition move or rename?"
        )
    body = m.group("body")
    field_lines = _split_top_level_field_lines(body)
    return {name: _parse_zod_chain(chain) for name, chain in field_lines}


# ---------------------------------------------------------------------------
# Public driver
# ---------------------------------------------------------------------------

# Pydantic envelope field name → codec.ts envelope field name.
# (Currently 1:1 for every field. Added explicitly to make any future
# rename discoverable in this single map rather than via subtle test failures.)
_PYDANTIC_TO_CODEC_FIELD_MAP: dict[str, str] = {
    "session_id": "session_id",
    "correlation_id": "correlation_id",
    "ts": "ts",
    "version": "version",
    "role": "role",
    "frame_seq": "frame_seq",
    "transaction_id": "transaction_id",
    "trailer": "trailer",
}

# Pydantic type_kind → set of acceptable codec.ts type_kinds.
# (Pydantic Literal["1.0"] === codec z.literal('1.0'); Pydantic
# Literal-of-roles is enum on codec side.)
_TYPE_KIND_EQUIV: dict[str, frozenset[str]] = {
    "literal": frozenset({"literal", "enum"}),
    "string": frozenset({"string"}),
    "int": frozenset({"int", "number"}),
    "object": frozenset({"object"}),
    "unknown": frozenset(),
}


def run_codec_envelope_parity_check(codec_path: pathlib.Path | None = None) -> None:
    """Compare the codec.ts envelope to Pydantic _BaseFrame field-for-field.

    Raises AssertionError on the first divergence with a descriptive
    message pointing at the affected field. The CI failure message must
    name the field so the fix is obvious.
    """
    if codec_path is None:
        if os.environ.get(_DRIFT_ENV_VAR) == "1":
            codec_path = _DRIFT_FIXTURE_PATH
        else:
            codec_path = _REAL_CODEC_PATH

    if not codec_path.exists():
        raise AssertionError(f"codec source not found: {codec_path}")

    codec_text = codec_path.read_text(encoding="utf-8")
    codec_spec = _derive_codec_envelope_spec(codec_text)
    pydantic_spec = _derive_pydantic_envelope_spec()

    # Field-set parity.
    expected_codec_fields = set(_PYDANTIC_TO_CODEC_FIELD_MAP.values())
    actual_codec_fields = set(codec_spec.keys())
    missing = expected_codec_fields - actual_codec_fields
    extra = actual_codec_fields - expected_codec_fields
    assert not missing, (
        f"codec.ts BaseFrame missing fields: {sorted(missing)}. "
        f"Pydantic _BaseFrame defines them as required envelope keys."
    )
    assert not extra, (
        f"codec.ts BaseFrame has extra fields not in Pydantic _BaseFrame: "
        f"{sorted(extra)}. Either delete them from codec.ts or add them to "
        f"_BaseFrame in src/kosmos/ipc/frame_schema.py."
    )

    # Per-field constraint parity.
    for py_name, codec_name in _PYDANTIC_TO_CODEC_FIELD_MAP.items():
        py_spec = pydantic_spec[py_name]
        cd_spec = codec_spec[codec_name]

        # type_kind compatibility
        accepted = _TYPE_KIND_EQUIV.get(py_spec.type_kind, frozenset())
        assert cd_spec.type_kind in accepted, (
            f"codec.ts:{codec_name} type_kind={cd_spec.type_kind!r} does not "
            f"match Pydantic _BaseFrame.{py_name} type_kind={py_spec.type_kind!r} "
            f"(accepted: {sorted(accepted)})."
        )

        # nullability
        assert cd_spec.nullable == py_spec.nullable, (
            f"codec.ts:{codec_name} nullable={cd_spec.nullable} does not match "
            f"Pydantic _BaseFrame.{py_name} nullable={py_spec.nullable}."
        )

        # required-ness — wire-compatibility rule:
        # - codec.ts:required=True, Pydantic:required=True            → compatible
        # - codec.ts:required=False, Pydantic:required=False          → compatible
        # - codec.ts:required=True,  Pydantic:required=False (defaulted) → compatible
        #     because Python `model_dump()` always materialises the field
        #     so the wire-frame TS validates includes the value.
        # - codec.ts:required=False, Pydantic:required=True           → INCOMPATIBLE
        #     (TS would accept a frame with the field omitted, Python rejects).
        required_compat = cd_spec.required == py_spec.required or (
            cd_spec.required and not py_spec.required
        )
        assert required_compat, (
            f"codec.ts:{codec_name} required={cd_spec.required} does not match "
            f"Pydantic _BaseFrame.{py_name} required={py_spec.required}. "
            f"This direction (codec optional, Pydantic required) is wire-incompatible: "
            f"the TUI side would accept a frame the backend rejects."
        )

        # min_length (string fields only)
        if py_spec.type_kind == "string":
            assert cd_spec.min_length == py_spec.min_length, (
                f"codec.ts:{codec_name} min_length={cd_spec.min_length} does not match "
                f"Pydantic _BaseFrame.{py_name} min_length={py_spec.min_length}. "
                f"Run `cd tui && bun run gen:ipc` is NOT enough — codec.ts is "
                f"hand-written; edit it directly and re-run this test."
            )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_codec_envelope_parity_passes_on_real_codec() -> None:
    """The committed `tui/src/ipc/codec.ts` envelope matches `_BaseFrame`."""
    run_codec_envelope_parity_check(_REAL_CODEC_PATH)


def test_drift_negative_fixture_triggers_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Negative fixture proves the gate is fail-loud on injected drift.

    The fixture re-declares ``correlation_id`` as optional/nullable.
    We expect the parity check to AssertionError on the
    ``correlation_id`` field's required-ness or min_length divergence.
    """
    monkeypatch.setenv(_DRIFT_ENV_VAR, "1")
    with pytest.raises(AssertionError, match=r"correlation_id"):
        run_codec_envelope_parity_check()


def test_drift_fixture_file_exists_and_is_test_only() -> None:
    """The drift fixture must exist and carry a forbid-runtime-import header."""
    assert _DRIFT_FIXTURE_PATH.exists(), f"Drift fixture not found at {_DRIFT_FIXTURE_PATH}."
    text = _DRIFT_FIXTURE_PATH.read_text(encoding="utf-8")
    assert "DO NOT IMPORT" in text or "DO NOT import" in text, (
        "Drift fixture must carry a 'DO NOT IMPORT' header to prevent runtime use."
    )
