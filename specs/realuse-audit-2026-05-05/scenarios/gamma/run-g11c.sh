#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Wave-4 G11c — run Shift+Tab mode cycle Bun PTY verification.
# Usage: bash specs/realuse-audit-2026-05-05/scenarios/gamma/run-g11c.sh [out-dir]

set -euo pipefail

REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
OUT_DIR="${1:-${REPO_ROOT}/specs/realuse-audit-2026-05-05/wave4/gamma/g11c}"
SCENARIO="${REPO_ROOT}/specs/realuse-audit-2026-05-05/scenarios/gamma/g11c-shift-tab-mode-cycle.ts"

mkdir -p "${OUT_DIR}"

echo "[run-g11c] output dir: ${OUT_DIR}"
echo "[run-g11c] scenario:   ${SCENARIO}"
echo "[run-g11c] sending raw BackTab=\\x1b[Z via Bun PTY (bypasses tmux escape-time)"

# Ensure onboarding is pre-completed so we land straight in the REPL
ONBOARDING_DIR="${HOME}/.kosmos/memdir/user/onboarding"
mkdir -p "${ONBOARDING_DIR}"
if [[ ! -f "${ONBOARDING_DIR}/state.json" ]]; then
  echo '{"current_step_index":5,"steps":{"preflight":true,"theme":true,"pipa-consent":true,"ministry-scope":true,"terminal-setup":true}}' \
    > "${ONBOARDING_DIR}/state.json"
  echo "[run-g11c] onboarding pre-completed"
fi

bun "${REPO_ROOT}/scripts/bun-pty-capture.ts" "${OUT_DIR}" "${SCENARIO}"

echo "[run-g11c] captures saved to ${OUT_DIR}"
echo "[run-g11c] check snap-001-after-first-shift-tab.txt for mode indicator change"
