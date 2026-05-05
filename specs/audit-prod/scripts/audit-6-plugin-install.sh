#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# audit-prod § Audit 6 (install variant) — exercise /plugin install/uninstall
# BEFORE /plugins so the stuck-overlay (P0 #1) does not swallow input.
set -uo pipefail

wait_for_pane "KOSMOS|kosmos" 60 || true
snapshot_pane 0-boot

# /plugin install <bad-name> → catalog miss
send_text_pane '/plugin install nonexistent-plugin-zzzz'
send_enter_pane
wait_for_pane "✗|실패|catalog|exit_code|타임아웃|complete|설치" 60 || true
snapshot_pane 1-install-bad
sleep 2
snapshot_pane 2-install-bad-after

# /plugin uninstall <not-installed>
send_text_pane '/plugin uninstall nonexistent-plugin-zzzz'
send_enter_pane
wait_for_pane "✗|실패|미설치|not.*install|complete|uninstall|exit_code" 30 || true
snapshot_pane 3-uninstall-miss
sleep 2
snapshot_pane 4-uninstall-miss-after

# /plugin install seoul_subway --dry-run
send_text_pane '/plugin install seoul_subway --dry-run'
send_enter_pane
wait_for_pane "Phase|✗|✓|catalog|complete|exit_code|영수증" 90 || true
snapshot_pane 5-install-dryrun
sleep 5
snapshot_pane 6-install-dryrun-after

snapshot_pane 7-final
send_ctrlc_pane
sleep 0.5
send_ctrlc_pane
