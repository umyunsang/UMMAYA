# Testing Guide

KOSMOS testing conventions and expectations. `AGENTS.md` summarizes the rules; this file is the long form.

## Stack

- **Runner**: `pytest` with `pytest-asyncio`
- **Fixtures**: recorded JSON under `tests/fixtures/`
- **Assertions**: plain `assert` — no unittest.TestCase subclasses
- **Mocks**: `pytest-mock` for in-process patches, `respx` for httpx, never mock Pydantic models

## Layout

```
tests/
├── conftest.py                  # shared fixtures
├── fixtures/
│   └── <provider>/<tool_id>.json
├── tools/
│   └── <provider>/test_<tool_id>.py
├── query_engine/
├── permissions/
└── agents/
```

Every source module under `src/kosmos/<area>/<module>.py` gets a parallel `tests/<area>/test_<module>.py`.

## Running tests

```bash
uv run pytest                    # default — fast, fixture-only
uv run pytest -m live            # include live API calls (local only)
uv run pytest tests/tools        # scope to one area
uv run pytest -k koroad          # filter by keyword
uv run pytest --cov=src/kosmos   # with coverage
```

Run `uv run pytest` before every commit. Once CI is configured, CI must be green before merging a PR.

## Live-call discipline

Integration tests that would hit live `data.go.kr` APIs are marked:

```python
import pytest

@pytest.mark.live
async def test_koroad_adapter_real_endpoint():
    ...
```

Rules:
- `@pytest.mark.live` tests are **skipped by default** via `pyproject.toml` config
- CI never runs them
- Developers run them locally when validating a new adapter or debugging a fixture mismatch
- If a live test fails, fix the adapter and re-record the fixture — do not delete the test

## Fixture recording

1. Set the API key: `export KOSMOS_DATA_GO_KR_KEY=...`
2. Run the recording script: `scripts/record_fixture.py <tool_id>`
3. Review the captured JSON for personal data, redact anything sensitive
4. Commit under `tests/fixtures/<provider>/<tool_id>.json`

Never commit a fixture containing real citizen PII. Synthetic values only.

## Test categories

**Unit tests** — pure functions, schema validation, tool input/output parsing. Must run in milliseconds and have no I/O.

**Adapter tests** — replay a recorded fixture through the adapter and assert the parsed output shape. Use `respx` to stub httpx.

**Integration tests** — exercise the query engine with a full tool loop against fixture-backed adapters. These are slower but still deterministic.

**Live tests** — marked `@pytest.mark.live`, opt-in only.

## Coverage expectations

- New tool adapters: one happy-path + one error-path test minimum
- New query engine features: unit tests for the state machine transitions
- Bug fixes: a regression test reproducing the bug, added in the same PR as the fix
- Refactors: the existing test suite must still pass; no loosening of assertions without justification

## What not to test

- Third-party library internals (httpx, pydantic, openai)
- The FriendliAI endpoint itself
- Trivial getters and one-line wrappers
- Private methods — test via the public interface

## Async tests

Use `pytest-asyncio` in auto mode:

```python
import pytest

@pytest.mark.asyncio
async def test_query_engine_loop():
    ...
```

Configure in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
markers = ["live: hits real data.go.kr APIs, skipped by default"]
```

## Test data language

Test values may include Korean strings when they represent real domain data a citizen would send (e.g., `"홍길동"`, `"부산광역시"`). Test names, docstrings, and assertion messages stay English per the source code language rule.

## CI OTEL suppression

CI sets `OTEL_SDK_DISABLED=true` at the job level (`jobs.test.env`) so no OTLP exporter, `BatchSpanProcessor`, or network activity is ever initialised during test runs (FR-009, SC-003).

## TUI verification methodology

Pytest covers the Python backend; the TUI (Ink + Bun) and the stdio IPC bridge sit *outside* that perimeter. "작동 확인" / "검증" / "smoke" requests MUST exercise the actual interactive path — code grep alone is not verification (memory `feedback_runtime_verification`).

This section is the canonical reference cited from `AGENTS.md § TUI verification`. It distils the upstream community guidance (Charm `vhs` 0.11.0, `asciinema` 3.x with `asciicast` v3 format, POSIX `expect(1)` / `script(1)`, `ink-testing-library` v4, Microsoft `node-pty`) into a four-layer ladder where each layer answers a different question and isolates a different failure mode.

### The four-layer ladder

Run **all four layers** for any change that touches the chat-request emit path, the TUI render layer, or the LLM orchestration loop. The cost is a few minutes; the alternative is shipping a regression that pytest cannot see.

| Layer | What it answers | Tool | Output | LLM-readable? |
|-------|----------------|------|--------|---------------|
| 1a. Python unit / fixture | "Does each backend module's contract hold?" | `pytest` + `pytest-asyncio` + `respx` | text | ✓ grep |
| 1b. **TUI Ink snapshot** | "Does each Ink component render the expected `frames` array on prop / state transitions?" — fastest TUI-side regression net (no terminal spawn, ms-fast) | `bun test` with `ink-testing-library` v4 — `render()` → `lastFrame()` / `frames[]` | text snapshots | ✓ grep |
| 2. **stdio JSONL probe** | "Does the backend invoke tools when given a citizen prompt?" — bypasses the TUI render entirely | `subprocess.Popen(['uv','run','kosmos','--ipc','stdio'])` + line-based JSONL frames | `*.jsonl` | ✓ grep |
| 3. **Text-log smoke** | "Does the full TUI session render the expected text?" | `expect(1)` / `script(1)` / `asciinema rec` (asciicast v3) | `*.txt` / `*.cast` (JSON-Lines) | ✓ grep |
| 4. **vhs visual + PNG keyframes** | "Does the rendered UI render the expected pixels at each scenario stage?" | `vhs file.tape` (Charm vhs ≥ 0.11.0) with `Output ...gif` + 3+ `Screenshot ...png` directives | `*.gif` (animated) + `*.png` (keyframes) | ✓ multimodal vision (Claude / Codex Read tool on each PNG) |
| 5. **Per-frame cell-grid text capture** | "What did the user *actually* see at every distinct frame, in order?" — only layer that catches transient repaint flashes (~80 ms) | `scripts/tui-text-debug.sh` = `asciinema rec --output-format asciicast-v3` → `scripts/cast_to_frames.py` (pyte VT-100 emulator) | `frame_NNNN_t<sec>_<sha>.txt` (one per distinct cell-grid state) + `timeline.txt` + `raw.cast` | ✓ grep + Read |

All five layers are **gating** for TUI-changing PRs (2026-04-29 — Layer 4 promoted from supplementary; 2026-05-01 — Layer 1b split out so the rule names `ink-testing-library` explicitly + Layer 5 added because PNG keyframes alone can't catch transient flashes that fall between sample timestamps, see `feedback_pty_log_full_inspection`). Layers 1–3 + 5 are LLM-grep-friendly text; Layer 4 is LLM-vision-friendly via the keyframe PNGs.

### Layer 1b — Ink snapshot tests with `ink-testing-library`

Use `ink-testing-library` v4 (`tui/package.json` `^4.0.0`) for **component-level** assertions on Ink output. It is the cheapest layer that exercises the React reconciler and the Ink ANSI writer, and it does NOT require a real terminal — the harness drives `stdin.write()` / `rerender()` and exposes `frames[]` (every render) and `lastFrame()` (the most recent ANSI string).

```typescript
import { render } from 'ink-testing-library'

const { stdout, rerender, stdin, unmount } = render(<MyTUI />)
expect(stdout.lastFrame()).toContain('KOSMOS')
stdin.write('/help\r')
expect(stdout.frames.at(-1)).toMatch(/Help/)
unmount()
```

When to reach for this layer:
- Permission modal layout regressions (which line emits, which color, which Ink Box border style) — these are invisible to PTY text logs because ANSI escapes get stripped or normalised.
- Slash-command autocomplete `frames[]` progression on every keystroke.
- Theme contrast / wide-glyph alignment that is _too cheap_ to justify spinning up vhs.

When NOT to reach for it:
- Anything involving the real backend stdio bridge (Layer 2 owns that).
- Pixel-level regressions across themes / fonts (Layer 4 owns that — Ink does not render to a real terminal cell grid).
- Multi-turn agentic loops with tool calls (Layer 3 PTY captures the full interleave deterministically).

Existing references: `tui/tests/ink/renderer-double-buffer.test.tsx`, `tui/tests/keybindings/tier1-wiring.test.ts`.

### Layer 2 — stdio JSONL probe

The most deterministic verification. Bypasses the TUI render layer entirely; proves the LLM tool-calling chain works.

```bash
# Spawn the backend, send one chat_request, read JSONL frames back.
specs/<spec>/scripts/smoke-stdio.py
# → emits smoke-stdio-<scenario>.jsonl per scenario
# → grep -c '"kind":"tool_call"' smoke-stdio-*.jsonl
```

Frame schema is `kosmos.ipc.frame_schema.ChatRequestFrame` (extra fields rejected — `version: "1.0"` not `1`). Required fields: `version`, `kind`, `role`, `session_id`, `correlation_id`, `frame_seq`, `ts`, `messages`. The backend's first reply is a `session_event{event:"exit"}` only when stdin closes — there is no boot-ready signal; just send the request immediately after spawn.

When this layer fails the bug is in the prompt / registry / agentic loop (server side). When it passes but Layer 3 fails, the bug is in the TUI render or the IPC bridge (TS side).

### Layer 3 — Text-log smoke

Captures the full pty session including ANSI escape codes. Three interchangeable tools, ranked by reliability under LLM driving:

1. **`expect`** — POSIX-standard, scripted, tightest control. Use for citizen smoke runs:

   ```bash
   expect <<'EOF' > specs/<spec>/smoke.txt 2>&1
   set timeout 90
   spawn -noecho bun --cwd tui run tui
   sleep 6
   send -- "강남역 어디?\r"
   sleep 60
   send -- "\x03"
   expect eof
   EOF
   ```

   Caveat: `expect`'s `log_file` directive silently drops output when the script is driven via heredoc; wrap the call in `script(1)` for reliable capture.

2. **`script(1)`** — POSIX terminal session capture. Wraps any command (including expect):

   ```bash
   script -q smoke.txt expect -f /tmp/scenario.exp
   ```

   On macOS the syntax is `script -q file cmd args`; on Linux `script -q -c "cmd args" file`.

3. **`asciinema`** — JSON-Lines (`.cast`) format. Best when timestamp-aware analysis is needed:

   ```bash
   asciinema rec --command "bun run tui" --idle-time-limit 2 smoke.cast
   ```

When this layer fails but Layer 2 passes, the regression is in the TUI render path (Ink components, raw-mode keystroke handling, frame transport).

### Layer 4 — vhs visual + PNG keyframes

`vhs` (Charm, ≥ 0.11) records `.gif` / `.mp4` / `.webm` for animated visual proof AND captures static PNG keyframes at named scenario stages via the `Screenshot` directive. The PNG keyframes are the **LLM-reviewable** artefact: Lead Opus uses the Read tool (Claude / Codex multimodal vision) to inspect each keyframe before push. The bare `.gif` is for humans and animated proof — the agent Read tool only renders its first frame, which during boot is typically a blank prompt.

**Canonical 3-keyframe rule** (extend per scenario complexity):

| Keyframe | Stage | What it proves |
|---|---|---|
| `smoke-keyframe-1-boot.png` | After `bun run tui` settles | KOSMOS branding, boot-guard line (`tool_registry: N entries verified ...`), prompt rendered |
| `smoke-keyframe-2-input.png` | After citizen Korean input + Enter | Input was accepted (text echoed in REPL prompt area, ANSI not garbled) |
| `smoke-keyframe-3-action.png` | After scenario action settles (permission prompt, tool call, agentic-loop indicator) | The change being landed actually fires — primitive call, permission render, error envelope, etc. |

Add more keyframes when the scenario branches (e.g. permission `y` vs `n`, `/help` overlay, `/agents --detail`). 3 is the floor, not the ceiling.

**Reference tape** (run from worktree root):

```text
# specs/<spec>/scripts/smoke.tape
Output specs/<spec>/smoke.gif
Set Width 1200
Set Height 800
Set FontSize 14
Set TypingSpeed 50ms

# Backend mock so the TUI boots without a live FriendliAI key
Env KOSMOS_BACKEND_CMD "sleep 60"

Type "cd tui && bun run tui"
Enter
Sleep 6s
Screenshot specs/<spec>/smoke-keyframe-1-boot.png

Type "강남역 어디야?"
Enter
Sleep 4s
Screenshot specs/<spec>/smoke-keyframe-2-input.png

Sleep 6s
Screenshot specs/<spec>/smoke-keyframe-3-action.png

Ctrl+C
Sleep 500ms
Ctrl+C
```

```bash
vhs specs/<spec>/scripts/smoke.tape
```

Lead Opus then runs `Read` on each `*.png` and asserts the visible elements match the spec's acceptance criteria. **DO NOT** use ffmpeg post-extraction to pull middle frames — `Screenshot` is more deterministic (frame timing controlled by the tape) and a single tool, no shell-out.

**vhs 0.11.0 (March 2026) capabilities** to use when the scenario needs them — none of these supersede the canonical 3-keyframe rule, they extend it:

- `ScrollUp <n>` / `ScrollDown <n>` — exercise the REPL's scrollback (e.g. assert that compaction-marker glyphs survive scrollback, or that long tool_result envelopes do not get truncated visually).
- `Ctrl+Left` / `Ctrl+Up` / `Ctrl+Right` / `Ctrl+Down` chord support — required for KOSMOS keybinding tier-1 smoke (Spec 287 / 1979 keybinding wiring) where word-jump and history-navigation chords need a tape capture.

#### Frame-timing methodology — `Wait` over `Sleep` (Spec 2521 — added 2026-05-01)

**Hard rule**: when capturing a transient UI state (spinner phase, thinking glyph, in-flight tool_use indicator, streaming text mid-render), use `vhs` `Wait+Screen /<regex>/` or `Wait+Line /<regex>/` instead of fixed `Sleep N` before the `Screenshot` call. `Sleep` captures whatever happens to be on screen at that wall-clock moment; `Wait` blocks until the regex matches the actual screen content (default 15-second timeout, `@<interval>` overrides polling rate). This eliminates the entire class of "captured-too-early / captured-too-late / captured-during-spinner-flicker" false negatives that LLM agent verification cannot self-recover from.

**Pattern** (canonical for any "I expect glyph X to appear":

```text
# Citizen sends prompt → ∴ Thinking should render before tool_call
Type "오늘 부산 날씨 어때?"
Enter
Wait+Screen /∴ Thinking/                       # blocks ≤ 15 s; fail-fast if glyph never appears
Screenshot specs/<spec>/smoke-keyframe-thinking-visible.png

# Now wait for the FIRST tool_call row, then capture
Wait+Screen /● lookup\(/
Screenshot specs/<spec>/smoke-keyframe-first-tool-call.png

# Wait for the agentic-loop completion marker, then capture
Wait+Screen /Crunched for/
Screenshot specs/<spec>/smoke-keyframe-final-result.png
```

**`Wait` failure behaviour**: vhs exits non-zero when the timeout fires. The PR-side smoke artefacts then *do not exist* (Screenshot never ran) and CI / Lead-review catches the missing PNG immediately. This is strictly safer than `Sleep`-based capture which always produces SOME PNG, even if it's the wrong moment.

**When to keep `Sleep`**:
- Boot-settle phase before the first interactive step (no UI marker to wait for; 6-8s is universal across hosts).
- Final exit phase (Ctrl+C dispatch — no glyph to wait for, just a brief grace window).
- When the test specifically asserts "this glyph is NOT visible at time T".

**Multi-layer redundancy** for LLM-friendly verification (Spec 2521 directive 2026-05-01: TUI verification methodology must let LLM agents catch any missed state transitions):

1. **vhs `Wait` + Screenshot** — the Layer 4 visual capture, deterministic timing.
2. **asciinema cast** (`*.cast` JSON-Lines) — companion timeline; LLM can grep `cast.frames` for the target glyph at any time index without re-running the scenario.
3. **PTY text-log** (already mandatory at Layer 3) — ANSI-strip + grep for the target glyph; this catches the byte-level event even if the visual frame is unstable.
4. **ink-testing-library Layer 1b unit test** — proves the component itself renders the glyph correctly when given the expected props; isolates "wiring missing" from "rendering broken".

**The four together are the rule**: every LLM-driven TUI verification of a transient state MUST instrument all four layers. Single-layer verification is brittle and will miss state transitions.

The tape, the gif, and every keyframe go into the spec directory and the PR description references them. The text-log version of the same scenario (Layer 3) lives next to them for LLM grep audit.

**Why this layer is mandatory** (and not, as previously stated, "supplementary"): pure text logs cannot detect ANSI-cell-level rendering regressions (purple-on-purple branding text invisible against the wrong theme; Korean wide-glyph alignment breaking the prompt; the UFO mascot rendering as `?`-blocks). The Epic γ #2294 PR #2394 review surfaced the gap — `feedback_pr_pre_merge_interactive_test` was satisfied by the text log, but no agent had visually confirmed the citizen UI actually composed correctly. Layer 4 with `Screenshot` PNGs closes that loop without sacrificing the LLM-review property.

### Layer 5 — Per-frame cell-grid text capture (asciinema → pyte)

The most LLM-friendly layer. Records every byte the PTY emits with sub-millisecond timestamps via `asciinema rec` (asciicast-v3 format), then replays the cast through `pyte` — a real VT-100 + xterm subset emulator with full CJK wide-char support. The replay collapses consecutive identical cell-grid states and writes one plain-text snapshot per *distinct* state, indexed by absolute timestamp + sha1.

**Why this layer exists**: PNG keyframes (Layer 4) capture state at sample timestamps T₁, T₂, T₃. Any transient state that exists *between* samples — an 80 ms wrong-state flash during partial-redraw, an internal-search `lookup(search:…)` UI that should have been hidden but flashed for one frame, a Korean wide-glyph misalignment that self-corrects on the next reconcile — is invisible. Layer 5 records EVERY byte the PTY ever emitted, so the replay is byte-deterministic and frame-complete by construction.

**Why pyte over `tmux capture-pane`**: capture-pane is polling-based; an 80 ms spinner tick can fall between samples and become invisible. asciinema records every byte event with timestamps; pyte's `Stream.feed()` applies them all deterministically, so a re-run of the same cast produces byte-identical frames.

**Recipe**:

```bash
# Drives the scenario, records the PTY, writes per-frame text snapshots.
scripts/tui-text-debug.sh specs/<spec>/frames/ specs/<spec>/scripts/smoke.expect
#   → specs/<spec>/frames/raw.cast              # asciicast v3, replayable
#   → specs/<spec>/frames/frame_NNNN_tX.YYY_SHA.txt  # per distinct state
#   → specs/<spec>/frames/timeline.txt          # idx<TAB>t<TAB>sha1<TAB>label
#   → specs/<spec>/frames/summary.txt           # final frame + counts

# The expect script is exactly the same one used at Layer 3 — there is
# no double-authoring cost. Only the recording wrapper differs.
```

**Offline replay** (re-derive frames from a committed cast without re-running the scenario):

```bash
uv run python scripts/cast_to_frames.py specs/<spec>/frames/raw.cast /tmp/frames-rerun/
# Byte-identical to the original frames if the cast is unchanged.
```

**Reading the output**: `timeline.txt` is the index — pick the frame indices of interest, then `Read` the corresponding `frame_NNNN_*.txt`. Standard greps:

```bash
# When did the first tool-call ui appear?
grep -lF "● lookup" specs/<spec>/frames/frame_*.txt | head -1

# When was the user input first echoed?
grep -lF "오늘 서울 날씨" specs/<spec>/frames/frame_*.txt | head -1

# Did the internal-search UI ever leak (should be hidden)?
grep -l "lookup(search:" specs/<spec>/frames/frame_*.txt
# (returns ZERO frames → hide is working; any hit is a bug)
```

### Five mandatory probe points

Every TUI bugfix PR must verify all five before claiming "fixed":

1. **Input ingress** — log `KEYSTROKE ts=… txn=… key=… mode=…` at the keypress handler. Confirms what the user typed.
2. **IPC frame boundary** — every `chat_request` / `assistant_chunk` / `tool_call` envelope MUST carry `correlation_id` (Spec 032 invariant). Confirms backend received what frontend sent.
3. **Tool dispatch boundary** — log `TOOL ts=… txn=… tool_id=… status={dispatched|completed|errored}`. Confirms agentic loop completed each round.
4. **Render commit** — every Ink reconcile commits a frame; the resulting `frame_NNNN_*.txt` IS this probe. Confirms what was actually painted.
5. **Snapshot trigger** — Layer 5 capture must run for every TUI-touching PR; absence of `specs/<feature>/frames/` (or `raw.cast`) is a CI bypass violation.

### Seven anti-patterns LLM agents fall into (forbidden)

Each maps to a memory entry the agent has been corrected on. Catching yourself doing any of these → STOP, return to systematic debugging:

1. **Final-state fallacy** — reading only `lastFrame()` / end-of-PTY-log, declaring fix done, missing the 80 ms flash. (`feedback_pty_log_full_inspection`). **Countermeasure**: enumerate EVERY frame in the Layer 5 `frames/` directory.
2. **Grep-as-proof** — `grep -c "tool_call" smoke.txt = 0` ≠ "no tool call emitted". The literal may be wrong, the log may have ANSI leak, the grep may be in the wrong file. (`feedback_pty_log_full_inspection`). **Countermeasure**: full read after grep, never grep alone.
3. **Snapshot blindness** — green `bun test` ≠ green TUI. Component snapshots can't prove REPL.tsx dynamic-import path even compiled. **Countermeasure**: Layers 2-5 are non-negotiable.
4. **Tool-substitution for methodology** — adding more tools (vhs, asciinema) without anchoring them to a probe point. **Countermeasure**: every captured artefact must answer one of the 5 probe points above.
5. **Skim-and-summarize** — reading first 200 lines of a 10k-line PTY log, hallucinating the middle. **Countermeasure**: cast→pyte de-dups consecutive identical states; agent reads the deduped frame set in full.
6. **Trusting one's own expect run** — same machine, warm cache; a flash humans see on cold start may not reproduce. **Countermeasure**: vary `KOSMOS_*` startup env between runs, diff frame sets.
7. **Fix-the-symptom spiral** — three+ failed fixes without questioning architecture. (`superpowers:systematic-debugging` Phase 4.5). **Countermeasure**: STOP at fix #3, capture frames, post timeline.txt to user before attempting fix #4.

### Architectural limit — paragraph-batch streaming on K-EXAONE + Bun + Ink

Spec 2521 (2026-05-01, expanded after byte-copy relax 2026-05-01) — verified via *seven* mitigation attempts that Layer 5 frame-by-frame capture cannot dilate further. Each attempt was instrumented with the captured-cast inspection tool the user mandated; the outcome is the same paragraph-batch ANSI write across all combinations.

1. **Backend SSE chunk pacing** (`kosmos.llm.client._pace_text_chunk`, `KOSMOS_LLM_STREAM_PACE_MS`). K-EXAONE on FriendliAI Serverless emits SSE deltas. Splitting them server-side into 8-char sub-chunks with 80–150 ms sleep extends the *gap between paragraphs* but Ink's React reconciler folds the setStates back into a single commit at paint time. (`/tmp/tdb-md-fix/raw.cast` frame_0294, `/tmp/tdb-final/raw.cast` frame_0572.)
2. **Frontend deps.ts char-by-char yield** (`_typewriter()`). Trace verifies `_typewriter` entered 221 times per turn but PTY still emits a single 605-byte ANSI write at t=26.327 of `/tmp/tdb-typewriter/raw.cast`.
3. **Frontend wrapper component `KosmosTypewriterStreamingMarkdown`** with `useState(displayedLen)` + mount-time `setInterval`. visibleLen advances 1→2→…→8 (trace verified) while target grows to ≥190; PTY emits a 657-byte write at t=7.005 of `/tmp/tdb-tw-interval/raw.cast`. Single Ink redraw fold containing the entire paragraph.
4. **`StreamingMarkdown` direct modification** with the same `useState/useInterval` reveal hoisted into the byte-copied component. visibleLen progression visible in `frame_0170…0176` (`● 안 → 안녕 → 안녕하…`) but second-paragraph still paints atomically as a 602-byte chunk at t=12.058 (`/tmp/tdb-final2/raw.cast`).
5. **Ink throttle relax** (`tui/src/ink/constants.ts`: `FRAME_INTERVAL_MS = 16 → 4`). Token-level streaming achieved for the *first* paragraph (74-byte chunk at t=7.048 of `/tmp/tdb-throttle/raw.cast` containing only `● 안녕하세요! 😊`); subsequent paragraphs still paint as single ~600-byte writes. Confirms Ink throttle was a contributing factor but not the dominant one.
6. **`bridge.ts` per-frame `setImmediate` yield** between `assistant_chunk` frames so React's automatic batching can't fold a Bun-pipe-chunk's worth of setStates into one commit. `frame_0067` of `/tmp/tdb-yield/raw.cast` still paints the 143-char paragraph in a 210-byte ANSI write at t=10.551 (Δ=223 ms gap from previous chunk; the chunk arrives as a single `data:` line carrying the whole paragraph).
7. **`KOSMOS_K_EXAONE_THINKING=false`** to force K-EXAONE's content channel instead of `reasoning_content`. Inter-paragraph cadence improved (5 s gap between two answer paragraphs in `/tmp/tdb-thinking-off/raw.cast`) but each paragraph still arrives as a single 117-/617-byte SSE chunk. **This identifies the dominant root cause**: K-EXAONE on FriendliAI Serverless emits paragraph-granularity SSE deltas, not Anthropic-style per-token deltas. No frontend or pacing layer can dilate a single SSE delta — the chunk is paragraph-shaped on the wire.

**Honest UX claim**: KOSMOS gets the citizen visible streaming **between paragraphs** (5 s cadence on `enable_thinking=False`, longer on `True` because the reasoning channel buffers first); paragraph-internal token-by-token reveal **is not achievable** at the LLM-provider tier we run on. CC against Anthropic doesn't see the same fold because Anthropic's token-stream API delivers ~5-30-byte deltas at 50-100 ms intervals — comfortably outside Ink's throttle and aligned with React's commit cadence.

**Mitigations the citizen can opt into**:
- `KOSMOS_LLM_STREAM_PACE_MS=80` — backend pacing on, paragraph-cadence streaming made more deliberate.
- `KOSMOS_K_EXAONE_THINKING=false` — first-token latency drops to <10 s and the answer arrives on the content channel, but the agentic loop loses the model's CoT signal (multi-step tool chaining degrades).
- The `FRAME_INTERVAL_MS=4` byte-copy relax in `ink/constants.ts` is kept regardless because it makes spinner cycling feel responsive without measurable CPU cost.

**Future work** (logged for post-2521 spec): a) negotiate a token-stream surface from FriendliAI for K-EXAONE; b) bypass Bun-pipe-batching by switching the IPC bridge to a length-prefixed framed protocol with reader-side flushes per frame; c) emit a synthetic per-codepoint stream from the backend's _stream_response under an explicit `KOSMOS_LLM_FAKE_TOKEN_STREAM=1` flag (UX-only, no provider change). Each option is a separate spec — not in 2521 scope.

### Cross-layer debugging heuristics

- **Tool-calling regression** — Layer 2 (stdio) is the gate. If `tool_call` count is 0, the prompt or registry is the bug.
- **TUI render regression** — Layer 3 (text log) reveals it: missing assistant text, garbled ANSI, frozen cursor.
- **Transient flash regression** — Layer 5 only. Read every frame, look for one-off content that disappears on the next frame. (`feedback_pty_log_full_inspection`)
- **Latency or streaming regression** — Layer 3 `.cast` timestamps + Layer 5 `timeline.txt` `t_seconds` column surface chunk delays.
- **Prompt / context bleed** — Layer 3 grep on the captured transcript: e.g. `grep -E '/Users/|gitStatus|claudeMd' smoke.txt` should return zero for citizen runs.
- **Visual / pixel-level regression** — Layer 4 `Screenshot` PNGs, agent-vision-reviewed via Read. Catches: theme contrast (purple-on-purple branding), Korean wide-glyph misalignment, mascot rendering as `?`-blocks, banner truncation, REPL prompt jumping.
- **Wrong tool-call UI exposure** (e.g. internal-search leaking) — Layer 5 only. `grep -l "lookup(search:" frames/*.txt` should return zero hits if the hide is working.

### Forward-looking — agent-driven autonomous smoke (not yet gating)

Terminal-Bench / Terminus 2 (Harbor framework, 2026) and Krafton's Terminus-KIRA define an emerging pattern: the LLM agent itself drives the terminal via tmux ("send command → read buffer → think → repeat"), and the smoke artefact is the agent's tmux pane buffer. KOSMOS does not adopt this today — our backend ships as a single Bun.spawn child of the TUI, not a tmux-multiplexed environment, and our scenarios are deterministic enough that scripted `expect(1)` is preferable to autonomous LLM driving. We track this approach as a candidate for **multi-agent visual smoke** (the day a Lead Opus needs to watch four parallel Sonnet teammates each running their own TUI scenario), but it is not part of the gating ladder.

If you choose to pilot it on a future Epic, capture the pane buffer to a `*.tmux-buffer.txt` file alongside the existing Layer 3 / Layer 4 artefacts so the LLM-grep + LLM-vision invariants are preserved.

### Reference implementations

- **Epic γ #2294** (`specs/2294-5-primitive-align/scripts/`) — the canonical Layer 2 + 4 template post-2026-04-29 promotion:
  - `smoke-emergency-lookup.expect` — Layer 2 (expect-driven, mock-backend, captures the agentic-loop entry path).
  - `smoke-emergency-lookup.tape` — Layer 4 (vhs visual; emit `smoke-emergency-lookup.gif` + 3 `Screenshot` keyframes).
- **Epic #2152** (`specs/2152-system-prompt-redesign/scripts/`) — pre-2026-04-29 era; uses Layer 2 + the old "Layer 4 is supplementary" pattern:
  - `smoke-stdio.py` — Layer 2 (Python-driven stdio JSONL probe; deterministic SC-1 audit).
  - `smoke-one.sh` / `smoke-five.sh` — Layer 3 (expect-driven citizen scenarios under `script(1)`).
  - `smoke.tape` — Layer 4 in the old shape (gif only). Future PRs touching this Epic SHOULD migrate it to the keyframe pattern.

Use the Epic γ #2294 templates as the canonical starting point for any future TUI-affecting Epic.
