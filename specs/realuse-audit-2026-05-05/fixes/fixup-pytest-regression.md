# fixup-pytest-regression — 5-test system prompt regression analysis

Spec: `specs/realuse-audit-2026-05-05`  
Commit: `fix(2773-fixup): refresh system prompt regression tests for integrated PIPA + PTY/SKY/VEC structure`  
Date: 2026-05-05

---

## Root Cause (common to all 5 tests)

The G1+G5 integration added a `<pipa_safety>` XML block between `</core_rules>` and `<tool_usage>` in `prompts/system_v1.md`.  The `<pipa_safety>` block contains two internal `\n\n` blank-line separators, splitting into three additional paragraphs when the assembler runs `text.split("\n\n")`.

`SystemPromptAssembler.__init__` stored sections by integer index into the split list:

| Index | Old expected tag | New actual content |
|-------|-----------------|-------------------|
| 2     | `<tool_usage>`  | `<pipa_safety>` block start |
| 3     | `<turn_order>`  | `<pipa_safety>` block middle |
| 4     | `<output_style>`| `<pipa_safety>` block end |

`<tool_usage>` moved to index 5, `<turn_order>` to index 6, `<output_style>` to index 7.

---

## Per-test root cause and fix

### Test 1 — `test_session_guidance.py::test_guidance_block_appended_after_existing_sections`

**Assertion**: `prompt.find("Use available tools") != -1`  
**Root cause**: `_tool_use_policy_section()` returned `<pipa_safety>` block (index 2) instead of `<tool_usage>` (index 5). `"Use available tools"` is in `<tool_usage>` (line 103 of system_v1.md) → not found → assertion `-1 != -1` fails.  
**Fix type**: Assembler + test helper  
**Fix**:
- `system_prompt.py`: switched from `split("\n\n")[index]` to `_extract_section(text, tag)` using `re.search` on `<tag>...</tag>` blocks.
- `test_session_guidance.py` `_prefix_without_guidance()`: added `assembler._pipa_safety_section()` call between `_language_policy_section()` and `_tool_use_policy_section()` to match the new section ordering.

---

### Test 2 — `test_system_prompt.py::test_omits_personal_data_reminder_when_disabled`

**Assertion**: `"PIPA" not in result` when `personal_data_warning=False`  
**Root cause**: `<pipa_safety>` is a mandatory safety directive that must always be emitted regardless of `personal_data_warning`. It contains `PIPA §22` multiple times. The existing assertion `"PIPA" not in result` is now impossible to satisfy.  
**Fix type**: Test assertion update (sentinel change)  
**Fix** (`test_system_prompt.py` lines 49–57):
- Replaced `assert "personal data" not in result.lower()` + `assert "PIPA" not in result` + `assert "개인정보" not in result` with:
  - `assert "Handle personal data with care" not in result` — unique opening of `<output_style>` block, absent in `<pipa_safety>`
  - `assert "시민의 개인정보는 PIPA 에 따라 처리합니다" not in result` — the `<output_style>`-specific PIPA line

---

### Test 3 — `test_system_prompt_refactor_equivalence.py::test_assemble_matches_pre_refactor_golden`

**Assertion**: `assembled_bytes == golden.replace(b"address_to_region", b"resolve_location")`  
**Root cause**: The golden file (`tests/context/fixtures/system_prompt_pre_refactor.txt`) was 22,475 bytes, calibrated to the pre-integration system_v1.md that lacked `<pipa_safety>` + `<turn_order>` + `<output_style>` PTY/SKY/VEC + NO_DATA + mock-disclaimer content. Assembled output was now 9,042 bytes (wrong sections) vs 22,467 expected bytes. After the assembler fix, assembled output is 27,615 bytes.  
**Fix type**: Golden file regeneration  
**Fix**: Regenerated `tests/context/fixtures/system_prompt_pre_refactor.txt` (27,623 bytes) as `assembled_bytes.replace(b"resolve_location", b"address_to_region")` so that `golden.replace(address_to_region, resolve_location) == assembled_bytes` holds exactly.

---

### Test 4 — `test_system_prompt_trust_hierarchy.py::test_trust_hierarchy_between_sections_3_and_4`

**Assertion**: `prompt.index(TOOL_USE_SENTINEL)` where `TOOL_USE_SENTINEL = "Use available tools when the citizen's request requires live data lookup"`  
**Root cause**: Same as Test 1 — `<tool_usage>` was at wrong index, so the sentinel wasn't in the assembled prompt → `ValueError: substring not found`.  
**Fix type**: Assembler fix (same as Test 1)  
**Fix**: After the XML-tag-based assembler fix, `<tool_usage>` is correctly emitted. `TOOL_USE_SENTINEL` is at position 11184, `TRUST_HIERARCHY_SENTINEL` at 11273, `PERSONAL_DATA_SENTINEL` at 15856. Ordering assertion `tool < trust < personal` passes.

---

### Test 5 — `test_system_prompt_trust_hierarchy.py::test_session_guidance_is_strictly_last`

**Assertion**: `prompt.index(PERSONAL_DATA_SENTINEL)` where `PERSONAL_DATA_SENTINEL = "Handle personal data with care."`  
**Root cause**: `<output_style>` was at wrong index (assembler returned middle of `<pipa_safety>` for `_personal_data_reminder_section()`). `"Handle personal data with care."` not found → `ValueError`.  
**Fix type**: Assembler fix (same as Test 1)  
**Fix**: XML-tag-based extraction correctly maps `_personal_data_reminder_section()` → `<output_style>` block. `PERSONAL_DATA_SENTINEL` is at position 15856, `SESSION_GUIDANCE_SENTINEL` at 17608. Ordering assertions pass.

---

## Secondary regression found and fixed

### `test_engine_multiturn.py` — 2 tests with `context_window=6000`

After the assembler fix, the assembled system prompt grew from ~9,042 chars to ~18,597 chars (estimated ~6,049 tokens). Two engine tests used `context_window=6000`, causing the hard-limit guard (100% of context_window) to reject every turn.

| Test | Old value | New value | Rationale |
|------|-----------|-----------|-----------|
| `test_preprocessing_triggered_with_small_context_window` | 6000 | 16000 | threshold=0.6 → fires at 9600; system prompt 6049 + turn pairs cross threshold |
| `test_preprocessing_compresses_stale_tool_results` | 6000 | 16000 | threshold=0.05 → fires at 800; preprocessing still fires on turn messages |

`tests/integration/test_agentic_loop.py::test_multi_tool_turn_is_coerced_to_one_visible_dispatch` was already failing on `995b88bb` before our changes — confirmed pre-existing, out of scope.

---

## Files changed

| File | Change type |
|------|-------------|
| `src/kosmos/context/system_prompt.py` | XML-tag section extraction + `_pipa_safety_section()` method |
| `tests/context/test_session_guidance.py` | `_prefix_without_guidance()` — added `_pipa_safety_section()` |
| `tests/context/test_system_prompt.py` | `test_omits_personal_data_reminder_when_disabled` — new sentinels |
| `tests/context/fixtures/system_prompt_pre_refactor.txt` | Golden regenerated (27,623 bytes) |
| `tests/engine/test_engine_multiturn.py` | Two `context_window` bumps (6000 → 16000) |
