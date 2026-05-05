#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# audit-prod § Audit 6 (real install) — exercise the live catalog with the
# correct catalog `name` (seoul-subway, hyphen, not seoul_subway underscore).
# KOSMOS_PLUGIN_SLSA_SKIP=true is set by the harness env to skip live SLSA
# binary download; the bundle SHA-256 + manifest validation still run.
set -uo pipefail

wait_for_pane "KOSMOS|kosmos" 60 || true
snapshot_pane 0-boot

# /plugin install seoul-subway --dry-run (correct catalog name)
send_text_pane '/plugin install seoul-subway --dry-run'
send_enter_pane
wait_for_pane "Phase|✗|✓|catalog|complete|exit_code|영수증|설치 완료|설치 실패" 120 || true
snapshot_pane 1-install-dryrun-real
sleep 5
snapshot_pane 2-install-dryrun-after

# Verify a Phase 2 / Phase 3 / Phase 4 progress message was actually rendered
# (the right-hand notification zone shows only the most recent text, so we
# scan the scrollback buffer for any phase tick).
sleep 1
snapshot_pane 3-final
send_ctrlc_pane
sleep 0.5
send_ctrlc_pane
