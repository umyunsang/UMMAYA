#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Spec 2521 — frame-by-frame TUI debugging infra.
#
# Extracts every redraw frame from a vhs-produced .gif/.mp4 into per-frame
# PNGs so the LLM agent can Read each frame and catch transient painting
# bugs that single Screenshot timestamps miss (e.g. wrong-flow flash, dead
# component mounts, spinner desync, scroll race conditions).
#
# Usage:
#   scripts/tui-frame-extract.sh <input.gif|input.mp4> [output-dir] [fps]
#     input.gif|input.mp4 : vhs Output target (also accepts any animated GIF)
#     output-dir          : default = <input>.frames/
#     fps                 : sample rate (default 5 = one frame every 200ms)
#
# Companion: scripts/tui-frame-grep.sh runs OCR-grep across the extracted
# frames; scripts/tui-frame-summary.sh prints the timeline of unique frames.

set -euo pipefail

INPUT="${1:?usage: $0 <input.gif|input.mp4> [output-dir] [fps]}"
OUTDIR="${2:-${INPUT}.frames}"
FPS="${3:-5}"

if [[ ! -f "$INPUT" ]]; then
  echo "::error::input not found: $INPUT" >&2
  exit 1
fi

mkdir -p "$OUTDIR"
rm -f "$OUTDIR"/frame_*.png

# -vsync vfr keeps the original frame timing instead of dropping/duplicating
# frames to match a constant rate. Combined with `select='gte(scene,0.0)'` (off
# by default) and a fixed fps filter, we get every distinct frame the gif
# carries plus interpolation if the gif fps is < requested fps.
ffmpeg -y -loglevel error \
  -i "$INPUT" \
  -vf "fps=${FPS}" \
  -vsync vfr \
  "$OUTDIR/frame_%04d.png"

COUNT=$(ls "$OUTDIR"/frame_*.png 2>/dev/null | wc -l | tr -d ' ')
echo "Extracted $COUNT frames at ${FPS}fps to $OUTDIR/"
echo
echo "Next steps:"
echo "  ls $OUTDIR/                       # list all frames"
echo "  open $OUTDIR/frame_0010.png       # spot-check a frame"
echo "  scripts/tui-frame-grep.sh $OUTDIR <pattern>  # OCR-grep across frames"
