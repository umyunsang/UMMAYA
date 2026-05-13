# Quickstart — Citizen-Perspective Verification Recipe

> Epic [#2077](https://github.com/umyunsang/UMMAYA/issues/2077) · 2026-04-27
> How to verify each migration step end-to-end as a real citizen would experience it. Based on `feedback_runtime_verification` and `feedback_cc_source_migration_pattern` memories — every claim of "step done" requires a PTY trace and a VHS GIF capture.

## Pre-flight

```bash
cd ~/UMMAYA

# Verify branch
git branch --show-current  # → 2077-kexaone-tool-wiring

# Verify .env has FriendliAI token
grep UMMAYA_FRIENDLI_TOKEN .env  # → UMMAYA_FRIENDLI_TOKEN=fri_...

# Static checks (these gate every step boundary)
cd tui && bun run typecheck && bun test \
  tests/adr-precheck.test.ts \
  tests/entrypoints \
  tests/hooks \
  tests/i18n \
  tests/ink \
  tests/ipc \
  tests/memdir \
  tests/permissions \
  tests/primitive \
  tests/store \
  tests/theme \
  tests/unit
# expected baseline: 928 pass / 0 fail / 0 errors

cd .. && uv run pytest tests/llm tests/ipc tests/tools
# expected baseline: see existing CI green count
```

## Per-step verification

Each step in `handoff-prompt.md § 5` requires both static gates AND the citizen-perspective check below before being marked done.

### Step 1 — CC reference cp + index README

**Static**:
```bash
ls src/ummaya/llm/_cc_reference/
# expected:
#   api.ts client.ts claude.ts emptyUsage.ts errors.ts
#   messages.ts permissions.ts prompts.ts query.ts
#   README.md tools.ts toolExecution.ts toolOrchestration.ts
#   toolResultStorage.ts
wc -l src/ummaya/llm/_cc_reference/*.ts
# expected total: ~13,720 lines (handoff §4 sum)
```

Each file's first line MUST be a Constitution §I research-use header:
```
// SPDX-License-Identifier: Apache-2.0 (Anthropic upstream) — research-use mirror
// Source: .references/claude-code-sourcemap/restored-src/src/<path> (CC 2.1.88)
```

### Step 2 — TUI tool serialization

**Static**:
```bash
cd tui && bun run typecheck && bun test tests/tools/serialization.test.ts
# expected: serialization spec passes (≥7 tests per contract)
```

**Citizen-perspective (PTY)**:
```bash
# trace frame.tools field on outbound chat_request
UMMAYA_IPC_TRACE=1 bun run tui 2>&1 | tee /tmp/ummaya-step2.log &
TUI_PID=$!
sleep 8
# inject one prompt
echo "강남구 24시간 응급실 알려주세요" | nc -U /tmp/ummaya-tui.sock 2>/dev/null || true
sleep 3
kill $TUI_PID 2>/dev/null

# verify
grep -c '"tools":\[' /tmp/ummaya-step2.log
# expected: ≥ 1 (frame includes non-empty tools list)
grep -o '"name":"lookup"' /tmp/ummaya-step2.log | wc -l
# expected: ≥ 1
```

### Step 3 — system prompt inject

**Static**:
```bash
uv run pytest tests/llm/test_system_prompt_builder.py -v
# expected: ≥7 tests (per system-prompt-builder.md contract)
```

**Citizen-perspective (PTY)**:

Run a one-shot conversation against the live FriendliAI endpoint, capture the LLM's response, count occurrences of "Read" / "Glob" / "Bash" tool-call attempts:

```bash
# /tmp/run_pty_step3.py — see template below
python3 /tmp/run_pty_step3.py "강남구 24시간 응급실 알려주세요" > /tmp/step3-output.txt
# verify
grep -c '<tool_call>{"name":"\(Read\|Glob\|Bash\|NotebookEdit\)"' /tmp/step3-output.txt
# expected: 0 (no CC-tool hallucinations)
grep -c '<tool_call>{"name":"\(lookup\|resolve_location\|submit\|subscribe\|verify\)"' /tmp/step3-output.txt
# expected: ≥ 1 (model invokes a UMMAYA primitive)
```

### Step 4 — backend registry fallback

**Static**:
```bash
uv run pytest tests/ipc/test_stdio.py::test_chat_request_with_empty_tools_uses_registry_fallback -v
```

**Citizen-perspective (PTY)**:

Patch the TUI to send `frame.tools = []` (skip Step 2 emission), then verify backend still functions:

```bash
UMMAYA_TUI_FORCE_EMPTY_TOOLS=1 python3 /tmp/run_pty_step3.py "강남구 응급실"
# check: same SC-001 hallucination check passes (because backend fallback inject ran)
```

### Step 5 — tool_use stream-event projection

**Static**:
```bash
cd tui && bun test tests/ipc/handlers.test.ts
# expected: tool_call → 2 stream events (content_block_start + content_block_stop) test passes
```

**Citizen-perspective (VHS)**:

```vhs
# /tmp/probe-step5.tape
Output "/tmp/probe-step5.gif"
Set Shell "bash"
Set FontSize 14
Set Width 1100
Set Height 700
Set Padding 16
Hide
Type "cd ~/UMMAYA/tui"; Enter; Sleep 200ms
Type "set -a; source ../.env; set +a"; Enter; Sleep 200ms
Type "export UMMAYA_FORCE_INTERACTIVE=1 OTEL_SDK_DISABLED=true"; Enter; Sleep 200ms
Type "clear"; Enter; Sleep 200ms
Show
Type "bun run tui"; Enter; Sleep 12s
Type "강남구 근처 24시간 응급실을 알려주세요."
Sleep 1s; Enter
Sleep 60s
Screenshot "/tmp/step5-final.png"
```

```bash
vhs /tmp/probe-step5.tape
# Extract frames
ffmpeg -i /tmp/probe-step5.gif -vf "fps=10" /tmp/step5-frames/frame_%03d.png 2>&1 | tail -3
# Visual inspection (open in image viewer):
#   1) Spinner appears
#   2) Thinking channel paints (from fdfd3e9)
#   3) tool_use box appears with "🔧 lookup" + JSON args (NOT a SystemMessage progress line)
#   4) Tool execution waits
```

The presence of a tool_use box (separate UI component, not a progress line) is the binary signal that Step 5 succeeded.

### Step 6 — tool_result content block + multi-turn closure

**Static**:
```bash
cd tui && bun test tests/ipc/handlers.test.ts
# new test: tool_result → user-role message with tool_result content block
uv run pytest tests/integration/test_agentic_loop.py
# new test: multi-turn loop completes with both blocks in transcript
```

**Citizen-perspective (VHS)** — same probe-step5.tape, expanded inspection:

```bash
# additional frame inspection:
#   5) tool_result envelope summary appears beneath tool_use box (paired)
#   6) Final natural-language assistant message paints below
#   7) Total time from Enter to final paint < 30s (SC-002)
```

### Step 7 — PermissionGauntletModal wire

**Static**:
```bash
cd tui && bun test tests/store/sessionStore.test.ts tests/integration/permission-modal.test.ts
# expected: pending permission slot lifecycle tests pass
```

**Citizen-perspective (VHS)**:

```vhs
# /tmp/probe-step7.tape — uses a submit-primitive triggering prompt
Output "/tmp/probe-step7.gif"
Set Shell "bash"
Set FontSize 14
Set Width 1100
Set Height 700
Set Padding 16
Hide
Type "cd ~/UMMAYA/tui"; Enter; Sleep 200ms
Type "set -a; source ../.env; set +a"; Enter; Sleep 200ms
Type "export UMMAYA_FORCE_INTERACTIVE=1 OTEL_SDK_DISABLED=true"; Enter; Sleep 200ms
Type "clear"; Enter; Sleep 200ms
Show
Type "bun run tui"; Enter; Sleep 12s
Type "출생신고 서류를 정부24에 제출하고 싶어요."
Sleep 1s; Enter
Sleep 30s
Screenshot "/tmp/step7-modal.png"   # modal should be visible here
Type "y"  # grant
Sleep 30s
Screenshot "/tmp/step7-final.png"   # tool result + final answer
```

```bash
vhs /tmp/probe-step7.tape
# Visual inspection:
#   1) Spinner + thinking
#   2) Tool_use box for submit
#   3) PERMISSION MODAL appears (full-width, visible bordered panel) within ~1s
#   4) Modal shows description_ko, risk_level=high, receipt_id
#   5) After "y" press: modal dismisses, tool_result appears, final answer renders
```

If the modal does NOT appear, Step 7 has regressed — PTY trace MUST show `permission_request` frame arrival to confirm the issue is the projection layer, not the backend.

## Final epic-level rehearsal

After all 7 steps complete:

```bash
# Full bun test
cd tui && bun test 2>&1 | tail -5
# expected: 928+ pass / 0 fail (regression budget = 0 over baseline)

# Full pytest
cd .. && uv run pytest tests/ 2>&1 | tail -5
# expected: existing pass count + new tests / 0 fail

# Run the full citizen rehearsal
vhs /tmp/probe-step5.tape  # response paint
vhs /tmp/probe-step7.tape  # consent flow

# 50-prompt regression (SC-001 hallucination = 0)
python3 /tmp/sc001-regression.py  # see template below
```

## Test harnesses (templates)

### `/tmp/run_pty_step3.py`

```python
#!/usr/bin/env python3
"""PTY harness for citizen-perspective tool-wiring verification.

Spawns `bun run tui` under a 200x80 PTY, sends one prompt, waits for the agentic
loop to complete (deadline 240s), prints stdout buffer to stdout.

Usage: python3 /tmp/run_pty_step3.py "<prompt>"
"""
import os
import pty
import select
import subprocess
import sys
import time

PROMPT = sys.argv[1] if len(sys.argv) > 1 else "강남구 24시간 응급실 알려주세요"
DEADLINE = time.time() + 240
ROWS, COLS = 80, 200

# (Implementation detail: spawn TUI, write PROMPT after 12s warmup, drain
# pty until deadline or "Press q to exit" pattern, exit. Matches
# /tmp/run_pty_tool.py from prior session.)
```

### `/tmp/sc001-regression.py`

```python
#!/usr/bin/env python3
"""SC-001 regression: 50 citizen prompts, count K-EXAONE CC-tool hallucinations.

Pass criterion: zero <tool_call>{"name":"<CC tool>"} occurrences across all 50.
"""
import re
import subprocess

PROMPTS = [
    "강남구 24시간 응급실 알려주세요",
    "오늘 서울 날씨가 어때?",
    "서대문구 보건소 위치",
    # ... (45 more)
]
HALLUCINATED = re.compile(r'<tool_call>\{"name":"(Read|Glob|Bash|Write|Edit|Grep|NotebookEdit|Task)"')

results = []
for prompt in PROMPTS:
    out = subprocess.check_output(["python3", "/tmp/run_pty_step3.py", prompt], timeout=300).decode()
    hits = HALLUCINATED.findall(out)
    results.append((prompt, len(hits)))

print(f"{sum(1 for _, n in results if n == 0)}/{len(results)} prompts hallucination-free")
assert all(n == 0 for _, n in results), f"hallucinations: {[r for r in results if r[1] > 0]}"
```

## VHS Tape catalogue

| Tape | Purpose | When to run |
|---|---|---|
| `/tmp/probe-step5.tape` | Tool_use box paint after tool_call frame | Step 5 boundary |
| `/tmp/probe-step5.tape` (expanded inspection) | Multi-turn closure with tool_result | Step 6 boundary |
| `/tmp/probe-step7.tape` | Permission modal interactive grant | Step 7 boundary |
| `/tmp/probe-final-rehearsal.tape` | Full epic citizen flow | Pre-PR merge |

## Exit criteria for the epic

- [ ] All 7 steps' static gates green
- [ ] All 7 steps' citizen-perspective verifications captured (PTY logs + VHS GIFs)
- [ ] SC-001 regression: 0 hallucinations across 50 prompts
- [ ] SC-002: median end-to-end ≤ 30s on 20-attempt rehearsal
- [ ] SC-003: median modal latency ≤ 1s on 5-attempt rehearsal
- [ ] SC-006: `git diff main pyproject.toml tui/package.json` shows zero new dependency lines
- [ ] PR description includes summary of citizen-perspective evidence (GIF links + log excerpts)
