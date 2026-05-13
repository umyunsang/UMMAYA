#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
#
# Rebuild the README demo with t-rec only. No VHS, asciinema, agg, or alternate
# recorder is allowed for this artifact.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COLS="${UMMAYA_DEMO_COLS:-120}"
ROWS="${UMMAYA_DEMO_ROWS:-34}"
FPS="${UMMAYA_DEMO_FPS:-10}"
RAW_DIR="${ROOT_DIR}/package-evidence/readme-demo"
SESSION_SCRIPT="${ROOT_DIR}/docs/demo/record-readme-demo-session.sh"
FINAL_GIF="${ROOT_DIR}/assets/ummaya-demo.gif"
FINAL_TEXT="${ROOT_DIR}/assets/ummaya-demo.txt"

usage() {
  cat <<'USAGE'
Usage: docs/demo/record-readme-demo.sh

Records the live README demo with t-rec only. This must run from a macOS GUI
terminal that t-rec can identify and that has Screen Recording permission.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

require_cmd() {
  local cmd="${1:?}"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "missing required command: $cmd" >&2
    exit 127
  fi
}

optimize_gif() {
  local input="${1:?}"
  local output="${2:?}"

  if command -v gifsicle >/dev/null 2>&1; then
    gifsicle --lossy=45 -k 96 -O3 "$input" -o "$output"
  else
    cp "$input" "$output"
  fi
}

prepare() {
  mkdir -p "$RAW_DIR" "$(dirname "$FINAL_GIF")"
  rm -f "$RAW_DIR"/ummaya-demo-* "$RAW_DIR"/t-rec.*
  rm -f "$ROOT_DIR/assets/ummaya-demo.cast"
}

require_cmd t-rec
require_cmd expect
require_cmd bun
require_cmd uv

base="$RAW_DIR/t-rec"

prepare

trec_args=(
  --quiet
  --decor none
  --natural
  --fps "$FPS"
  --start-pause 800ms
  --end-pause 4s
  --idle-pause 3s
  --output "$base"
  --video
)
if [[ -n "${UMMAYA_TREC_WIN_ID:-}" ]]; then
  trec_args+=(--win-id "$UMMAYA_TREC_WIN_ID")
fi
trec_args+=("$SESSION_SCRIPT")

UMMAYA_DEMO_COLS="$COLS" \
UMMAYA_DEMO_ROWS="$ROWS" \
UMMAYA_DEMO_TEXT_OUT="$FINAL_TEXT" \
  t-rec "${trec_args[@]}"

[[ -f "$base.gif" ]]
optimize_gif "$base.gif" "$FINAL_GIF"
if [[ -f "$base.mp4" ]]; then
  cp "$base.mp4" "$ROOT_DIR/assets/ummaya-demo.mp4"
fi

printf 'README demo generated:\n'
printf '  GIF : %s\n' "$FINAL_GIF"
printf '  TXT : %s\n' "$FINAL_TEXT"
if [[ -f "$ROOT_DIR/assets/ummaya-demo.mp4" ]]; then
  printf '  MP4 : %s\n' "$ROOT_DIR/assets/ummaya-demo.mp4"
fi
