#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Spec 2521 — extract ONLY scene-change frames (visual transitions) from a
# vhs-produced .gif/.mp4. Drastically reduces token cost when the LLM agent
# inspects keyframes — a 30-second screen recording at 5fps produces ~150
# frames but typically only 10-20 of them are visually distinct.
#
# Uses ffmpeg's `select='gt(scene,X)'` filter with default threshold 0.05
# (very sensitive — catches even a single new tool-use line). Lower X for
# more sensitivity, higher X for fewer keyframes.
#
# Usage:
#   scripts/tui-scene-extract.sh <input.gif|input.mp4> [output-dir] [scene-threshold]

set -euo pipefail

INPUT="${1:?usage: $0 <input.gif|input.mp4> [output-dir] [scene-threshold]}"
OUTDIR="${2:-${INPUT}.scenes}"
THRESHOLD="${3:-0.001}"

[[ -f "$INPUT" ]] || { echo "::error::input not found: $INPUT" >&2; exit 1; }
mkdir -p "$OUTDIR"
rm -f "$OUTDIR"/scene_*.png

# `showinfo` writes per-frame stats to stderr so we can recover the
# pts_time of each kept scene. The `select` filter keeps only frames whose
# scene-change score exceeds THRESHOLD.
# `eq(n,0)` always keeps the very first frame (otherwise ffmpeg's scene
# detector skips it because there's nothing to compare against), then
# `gt(scene,X)` keeps subsequent visually-distinct frames.
ffmpeg -y -loglevel info \
  -i "$INPUT" \
  -vf "select='eq(n\,0)+gt(scene\,${THRESHOLD})',showinfo" \
  -vsync vfr \
  "$OUTDIR/scene_%03d.png" 2> "$OUTDIR/.ffmpeg.log"

COUNT=$(ls "$OUTDIR"/scene_*.png 2>/dev/null | wc -l | tr -d ' ')
echo "Extracted $COUNT scene-change frames (threshold ${THRESHOLD}) to $OUTDIR/"

# Pull the timing of each kept frame from the showinfo stderr log.
if [[ -s "$OUTDIR/.ffmpeg.log" ]]; then
  echo
  echo "Timeline (kept frames):"
  grep -E "pts_time:" "$OUTDIR/.ffmpeg.log" \
    | awk -F"pts_time:" '{print $2}' \
    | awk '{print "  +" $1 "s"}' \
    | head -50 || true
fi
