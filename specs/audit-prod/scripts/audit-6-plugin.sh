#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# audit-prod § Audit 6 — Plugin DX (Tier 1-5) + /plugin slash commands
#
# Scope (Spec 1636 + Spec 1979):
#   Tier 1 — kosmos-plugin-template + `kosmos plugin init` TUI + uvx fallback
#   Tier 2 — 9 Korean-primary guides under docs/plugins/
#   Tier 3 — 4 example repos (seoul-subway / post-office Live + nts-homtax / nhis-check Mock)
#   Tier 4 — 50-item validation matrix + reusable workflow + plugin_submission template
#   Tier 5 — kosmos-plugin-store/index catalog + 8-phase installer + SLSA verifier
#   /plugin install/list/uninstall/pipa-text  +  /plugins (browser surface)
#   PIPA §26 trustee acknowledgment SHA-256 gate
#   tool_id namespace `plugin.<id>.<verb>` (ADR-007)
#
# Hard rule: no live SLSA download in CI smoke. KOSMOS_PLUGIN_SLSA_SKIP=true
# is set by the harness; the manifest's L3 path remains hard-refused.
#
# Helpers exported by scripts/tui-tmux-capture.sh:
#   wait_for_pane <regex> [deadline_seconds=30]
#   snapshot_pane <label>
#   send_text_pane <text>
#   send_enter_pane
#   send_keys_pane <key1> [key2...]
#   send_ctrlc_pane

set -uo pipefail

# ---------------------------------------------------------------------------
# Stage 0 — Boot + branding
# ---------------------------------------------------------------------------
wait_for_pane "KOSMOS|kosmos" 60 || true
snapshot_pane 0-boot

# ---------------------------------------------------------------------------
# Stage 1 — /plugin pipa-text → canonical PIPA §26 acknowledgment SHA-256
# ---------------------------------------------------------------------------
send_text_pane '/plugin pipa-text'
send_enter_pane
wait_for_pane "PIPA|trustee|acknowledgment|sha|SHA|수탁자|영수증|manifest" 20 || true
snapshot_pane 1-pipa-text
sleep 1

# ---------------------------------------------------------------------------
# Stage 2 — /plugin (no subcommand) → usage hint
# ---------------------------------------------------------------------------
send_text_pane '/plugin'
send_enter_pane
wait_for_pane "사용법|usage|install|uninstall|list|pipa" 15 || true
snapshot_pane 2-usage
sleep 1

# ---------------------------------------------------------------------------
# Stage 3 — /plugin list → IPC round-trip to plugin_op_dispatcher.handle_list
# ---------------------------------------------------------------------------
send_text_pane '/plugin list'
send_enter_pane
wait_for_pane "플러그인|plugin|목록|list|installed|설치|empty|비어|payload|complete" 30 || true
snapshot_pane 3-list
sleep 2
snapshot_pane 3b-list-after

# ---------------------------------------------------------------------------
# Stage 4 — /plugins → PluginBrowser surface (Spec 1635 / FR-031)
# ---------------------------------------------------------------------------
send_text_pane '/plugins'
send_enter_pane
wait_for_pane "browser|browse|플러그인|Plugin|store|⏺|○|installed|empty" 30 || true
snapshot_pane 4-plugins-browser
sleep 1
# Esc dismiss
send_keys_pane Escape
sleep 1
snapshot_pane 4b-plugins-after-esc

# ---------------------------------------------------------------------------
# Stage 5 — /plugin install <known-bad-name> → catalog miss path
#   Expected: "✗" + exit_code=1 + KOSMOS branding for failure summary.
# ---------------------------------------------------------------------------
send_text_pane '/plugin install nonexistent-plugin-zzzz'
send_enter_pane
wait_for_pane "✗|실패|fail|catalog|exit_code|타임아웃|timeout|오류|error|설치|install" 30 || true
snapshot_pane 5-install-catalog-miss
sleep 2

# ---------------------------------------------------------------------------
# Stage 6 — /plugin uninstall <not-installed> → not-installed path
# ---------------------------------------------------------------------------
send_text_pane '/plugin uninstall nonexistent-plugin-zzzz'
send_enter_pane
wait_for_pane "✗|실패|fail|not.*install|미설치|exit_code|제거|uninstall" 30 || true
snapshot_pane 6-uninstall-miss
sleep 2

# ---------------------------------------------------------------------------
# Stage 7 — /plugin install seoul_subway --dry-run
#   Uses cached bundle if present (~/.kosmos/cache/plugin-bundles/) but
#   may catalog-miss if KOSMOS_PLUGIN_CATALOG_URL is the live default.
#   Either way, a structured ✗/✓ summary must surface.
# ---------------------------------------------------------------------------
send_text_pane '/plugin install seoul_subway --dry-run'
send_enter_pane
wait_for_pane "Phase|✗|✓|실패|설치|catalog|complete|exit_code|영수증" 60 || true
snapshot_pane 7-install-dryrun
sleep 3
snapshot_pane 7b-install-dryrun-after

# ---------------------------------------------------------------------------
# Stage 8 — Final state
# ---------------------------------------------------------------------------
snapshot_pane 8-final
send_ctrlc_pane
sleep 0.5
send_ctrlc_pane
