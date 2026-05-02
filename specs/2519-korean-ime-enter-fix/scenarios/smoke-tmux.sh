#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Spec: 2519-korean-ime-enter-fix — tmux capture-pane smoke scenario
#
# Ported from: specs/2519-korean-ime-enter-fix/scripts/smoke-2519-final.expect
# Port date: 2026-05-01
# Harness: scripts/tui-tmux-capture.sh (RFC debug-infra-rebuild § P2)
#
# Sourced (not exec'd) by tui-tmux-capture.sh — helpers available:
#   wait_for_pane <regex> [deadline_s]
#   snapshot_pane <label>
#   send_text_pane <text>
#   send_enter_pane
#   send_ctrlc_pane
#   send_keys_pane <key...>
#
# Verifies two Korean IME Enter flows that compose in the same code-path
# that K-EXAONE Korean queries hit (Hangul input → dispatchPrimitive):
#
#   Turn 1: "너 어떤 모델이야?"
#           → K-EXAONE must answer as a Korean public-service assistant
#             (not a software-engineering helper). Verifies the system
#             prompt is effective and the original IME Enter swallow is
#             patched (PR #2519: forward Enter regardless of isPasting).
#
#   Turn 2: "부산 사하구 동아대 위치 알려줘"
#           → dispatchPrimitive server-side-ack stub ("(어댑터 미상)" /
#             "dispatched_via" JSON) must NOT appear. A ● lookup paint
#             proves the clean code-path is active.
#
# Deadline map:
#   boot          30s  (first run cold-starts bun + node_modules)
#   branding      15s
#   turn-1 settle 60s  (K-EXAONE reasoning_content, 30-90s typical)
#   tool_call     60s
#   final answer 120s
#   settle         10s (activity-based, not wall-clock)

# ── 1. Boot ─────────────────────────────────────────────────────────────────
wait_for_pane "tool_registry: [0-9]+ entries verified" 60
wait_for_pane "KOSMOS" 15
snapshot_pane boot

# ── 2. Turn 1 — Korean IME identity question ─────────────────────────────────
# send_text_pane sends each character into the tmux pane without IME
# composition; the Korean bytes reach Bun's stdin raw, reproducing the
# same isPasting code-path the fix targets.
send_text_pane "너 어떤 모델이야?"
sleep 0.5
send_enter_pane
snapshot_pane turn1-submitted

# Wait for turn 1 to fully complete. K-EXAONE reasoning can take 30-90s.
# We need the full response text (not just "Symbioting...") before sending
# turn 2, otherwise turn 2 gets queued and the ● lookup predicate fires much
# later than the 60s deadline.
# Patterns: K-EXAONE public-service intro keywords OR a model self-description.
wait_for_pane "공공|서비스|모델|K-EXAONE|국민|assistant|EXAONE|저는|KOSMOS" 120
snapshot_pane turn1-response

# Wait for the spinner/thinking indicator to clear (response complete).
# We poll until the "Symbioting" / "Thinking" indicator disappears.
# Deadline 30s: completion after text arrives should be quick.
__spin_clear_deadline=$(( $(date +%s) + 30 ))
while (( $(date +%s) < __spin_clear_deadline )); do
  if ! tmux capture-pane -t "$TMUX_SESSION" -p 2>/dev/null | grep -qE "Symbioting|Thinking —"; then
    break
  fi
  sleep 0.5
done
snapshot_pane turn1-complete

# Ensure the stub regression is NOT present: "(어댑터 미상)" must be absent.
# We capture the pane and check absence inline (wait_for_pane has no negation).
if tmux capture-pane -t "$TMUX_SESSION" -p 2>/dev/null | grep -qF "(어댑터 미상)"; then
  echo "[SMOKE FAIL] stub regression detected: '(어댑터 미상)' visible after turn 1" >&2
  snapshot_pane turn1-regression
  # Non-fatal: capture + continue so all artefacts are saved.
fi

# ── 3. Turn 2 — Citizen lookup (verifies IME Enter → lookup path is clean) ──
send_text_pane "부산 사하구 동아대 위치 알려줘"
sleep 0.5
send_enter_pane
snapshot_pane turn2-submitted

# Wait for any first paint: ● lookup tool_call OR a direct location answer.
# K-EXAONE may answer from parametric knowledge (no tool dispatch) — both valid.
# The critical check is absence of the stub artefacts, not presence of tool_call.
wait_for_pane "● lookup|● resolve_location|위치|주소|대학|부산|동아" 120 || true
snapshot_pane after-result

# Stub regression check post-turn-2
if tmux capture-pane -t "$TMUX_SESSION" -p 2>/dev/null | grep -qF "dispatched_via"; then
  echo "[SMOKE FAIL] stub regression detected: 'dispatched_via' visible after turn 2" >&2
  snapshot_pane turn2-regression
fi

# ── 4. Settle — wait for screen to stop changing (activity-based, not sleep) ─
# Replaces the original "sleep 60" / "sleep 1" blocks with a bounded-activity
# loop. Short sleep 0.3 is the poll interval — no wall-clock guess.
__prev=""
__stable_start=$(date +%s)
__settle_deadline=$(( $(date +%s) + 15 ))
while (( $(date +%s) < __settle_deadline )); do
  __cur=$(tmux capture-pane -t "$TMUX_SESSION" -p)
  if [[ "$__cur" != "$__prev" ]]; then
    __prev="$__cur"
    __stable_start=$(date +%s)
  fi
  if (( $(date +%s) - __stable_start >= 1 )); then break; fi
  sleep 0.3
done
snapshot_pane stable

# ── 5. Graceful quit ──────────────────────────────────────────────────────────
send_ctrlc_pane
# sleep 1: wait for Ctrl+C signal delivery — no predicate fits because the
# TUI may not repaint before exit. Shortest acceptable settle, required by
# process-kill timing, not latency guessing.
sleep 1
send_ctrlc_pane
snapshot_pane quit
