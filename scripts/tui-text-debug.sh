#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Spec 2521 — TUI Layer 5: LLM-readable per-frame cell-grid capture.
#
# Pipeline (asciinema v3 cast → pyte VT-100 replay → text frames):
#   1. asciinema rec drives an `expect` scenario inside a real PTY,
#      recording every output byte with sub-millisecond timestamps.
#   2. cast_to_frames.py replays the cast through pyte (real VT-100 +
#      xterm subset, CJK wide-char aware) and dumps one plain-text
#      cell-grid snapshot per *distinct* state.
#   3. timeline.txt indexes every frame by (idx, t, sha1, label).
#
# Why not tmux capture-pane: polling-based; an 80 ms spinner tick or
# transient repaint flash can fall between samples and become invisible
# to the LLM agent — exactly the failure mode behind memory
# `feedback_pty_log_full_inspection`.
#
# Why text frames not PNG: the agent Read tool ingests text natively and
# can grep across thousands of frames; PNG keyframes require multimodal
# vision and miss byte-level diffs.
#
# Usage:
#   scripts/tui-text-debug.sh <output-dir> <expect-scenario>
#     output-dir       : directory to drop {frame_*.txt, timeline.txt,
#                        summary.txt, raw.cast}
#     expect-scenario  : path to expect script driving the TUI session
#
# Companion: scripts/cast_to_frames.py (offline replay; can also be run
# manually against any committed *.cast).

set -euo pipefail

OUTDIR="${1:?usage: $0 <output-dir> <expect-scenario>}"
SCENARIO="${2:?usage: $0 <output-dir> <expect-scenario>}"
COLS="${KOSMOS_DEBUG_COLS:-200}"
ROWS="${KOSMOS_DEBUG_ROWS:-50}"

REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"

# Resolve to absolute paths before any cd.
SCENARIO="$(cd "$(dirname "$SCENARIO")" 2>/dev/null && pwd)/$(basename "$SCENARIO")"
mkdir -p "$OUTDIR"
OUTDIR="$(cd "$OUTDIR" && pwd)"

if [[ ! -f "$SCENARIO" ]]; then
  echo "::error::expect scenario not found: $SCENARIO" >&2
  exit 1
fi
if ! command -v asciinema >/dev/null 2>&1; then
  echo "::error::asciinema not on PATH (brew install asciinema)" >&2
  exit 1
fi

CAST="$OUTDIR/raw.cast"
rm -f "$CAST" "$OUTDIR"/frame_*.txt "$OUTDIR"/timeline.txt "$OUTDIR"/summary.txt

# asciinema 3.x defaults to v3 cast; --quiet suppresses banner spam in
# CI logs but keeps the cast file complete. --cols/--rows forces a
# deterministic terminal size so frame diffs are byte-stable across
# runs (avoids the "user has 200x60, agent rerun has 80x24" trap).
cd "$REPO_ROOT/tui"
asciinema rec \
  --quiet \
  --window-size "${COLS}x${ROWS}" \
  --idle-time-limit 5 \
  --command "expect '$SCENARIO'" \
  "$CAST"

# Replay → per-frame text snapshots.
cd "$REPO_ROOT"
uv run python scripts/cast_to_frames.py "$CAST" "$OUTDIR"

echo
echo "Frames captured at: $OUTDIR/"
echo "  Read $OUTDIR/summary.txt for the timeline + final frame."
echo "  Read $OUTDIR/timeline.txt to pick frame indices to inspect."
echo "  Read $OUTDIR/frame_NNNN_*.txt for individual cell-grid snapshots."
