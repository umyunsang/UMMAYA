# Contract — Verify Input Shape Translation (FR-008 / 008a / 008b / 009 / 010)

**Date**: 2026-04-30
**Owner**: Backend (`src/ummaya/tools/mvp_surface.py`) + canonical-map module (`src/ummaya/tools/verify_canonical_map.py`)

## I-V1 — LLM-emitted shape MUST be accepted

**Given** the LLM emits a `verify` function_call per `prompts/system_v1.md` v2 `<verify_chain_pattern>`:

```json
{
  "tool_id": "mock_verify_module_modid",
  "params": {
    "scope_list": ["find:hometax.simplified", "send:hometax.tax-return"],
    "purpose_ko": "종합소득세 신고",
    "purpose_en": "Comprehensive income tax filing"
  }
}
```

**Then** `_VerifyInputForLLM.model_validate(emit)` MUST succeed and the resulting model instance MUST have:
- `family_hint == "modid"` (translated)
- `session_context == { "scope_list": [...], "purpose_ko": "...", "purpose_en": "..." }` (packed)
- `tool_id == "mock_verify_module_modid"` (preserved)
- `params == {...}` (preserved)

## I-V2 — Legacy shape continues to work (backward compat)

**Given** a direct dispatcher caller emits the legacy shape:

```json
{
  "family_hint": "modid",
  "session_context": {"scope_list": [...]}
}
```

**Then** `_VerifyInputForLLM.model_validate(legacy)` MUST succeed unchanged. The pre-validator detects `family_hint` is set and returns the dict unchanged. `tool_id` defaults to `None`; `params` defaults to `None`.

## I-V3 — Unknown tool_id raises ValueError

**Given** an unknown `tool_id`:

```json
{"tool_id": "mock_verify_module_NONEXISTENT", "params": {}}
```

**Then** `_VerifyInputForLLM.model_validate(emit)` MUST raise `ValueError("unknown verify tool_id: 'mock_verify_module_NONEXISTENT'")`. The error MUST propagate to `_dispatch_primitive`, which catches it (existing `except Exception` at `stdio.py:1100`) and emits a `tool_result` envelope with `error` field set. The TUI renders the error envelope citizen-facing as "오류 / Error: 알 수 없는 인증 모듈입니다 (mock_verify_module_NONEXISTENT)".

## I-V4 — Canonical map sourced from markdown at boot

**Given** `prompts/system_v1.md` is on disk with the η-shipped `<verify_families>` block.

**Then** the first call to `ummaya.tools.verify_canonical_map.resolve_family(...)` MUST:
- Locate `prompts/system_v1.md` via `UMMAYA_PROMPTS_DIR` env (default `<repo_root>/prompts`).
- Read the `<verify_families>` ... `</verify_families>` block.
- Parse all `mock_verify_*` rows.
- Return a 10-entry frozen mapping.
- Raise `RuntimeError("verify_canonical_map: expected ≥10 entries, got N")` if fewer than 10 entries are parsed.

**Subsequent calls** MUST hit the `lru_cache` and return the cached mapping (no re-read).

## I-V5 — Idempotent resolution

**Given** `_VerifyInputForLLM.model_validate(...)` is called with a dict whose pre-validator has already run (i.e., already in legacy shape with `family_hint` set AND `tool_id`/`params` also set):

**Then** the pre-validator MUST detect this state (via `data.get("family_hint")` non-empty check) and return the dict unchanged — no double-translation. This guards against pre-validator re-entry in nested validation.

## I-V6 — TUI MUST NOT translate (FR-009)

**Given** the TUI's `VerifyPrimitive.call(input, context)` is invoked with the LLM-emitted shape.

**Then** the IPC `tool_call` frame's `arguments` field MUST equal the input verbatim — no `tool_id → family_hint` mapping at the TUI side. A regression test (`tui/src/tools/_shared/dispatchPrimitive.test.ts`) MUST assert `frame.arguments.tool_id === input.tool_id` (no mutation) for verify dispatches.

## I-V7 — Schema export round-trip

**Given** `mvp_surface.VERIFY_TOOL.input_schema.model_json_schema()` is invoked (the OpenAI-compat schema published to K-EXAONE).

**Then** the schema MUST list `tool_id` AND `params` as the citizen-canonical fields (the LLM sees them as primary). `family_hint` and `session_context` SHOULD be retained for backward compat but MAY have `description` flagged as `(legacy)` for human readers.

## I-V8 — Pre-validator runs in mode='before' (Pydantic v2 strict)

**Given** Pydantic v2.13+.

**Then** the validator MUST be declared as `@model_validator(mode="before")` — not `mode="after"`. Mode-before runs against the raw dict input before field validation; mode-after runs against the model instance and cannot rebuild missing fields. Constitution § III mandates strict typing with no `Any`; the pre-validator's signature is `(cls, data: dict[str, object]) -> dict[str, object]` — fully typed.
