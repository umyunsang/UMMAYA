#!/usr/bin/env bash
# S3: 출산 보조금 신청 — lookup(mohw) + verify(simple_auth) + submit(welfare_application) + permission ⓷ + receipt + export
set -euo pipefail
wait_for_pane "KOSMOS|❯" 30
snapshot_pane 00-boot

# Step 1: search MOHW welfare
send_text_pane "출산 보조금 알아보고 싶어"; sleep 1; send_enter_pane; sleep 90
snapshot_pane 01-mohw-lookup

# Step 2: verify (simple_auth mock)
send_text_pane "간편인증으로 본인확인 해줘"; sleep 1; send_enter_pane; sleep 60
snapshot_pane 02-verify-simple-auth

# Step 3: submit welfare application (Layer 3 — orange/red permission expected)
send_text_pane "첫만남이용권 신청 제출해줘"; sleep 1; send_enter_pane; sleep 90
snapshot_pane 03-submit-welfare-app
# Permission gauntlet — accept once
send_text_pane "y"; sleep 1; send_enter_pane; sleep 30
snapshot_pane 04-permission-accepted

# Step 4: /consent list
send_text_pane "/consent list"; sleep 1; send_enter_pane; sleep 5
snapshot_pane 05-consent-list

# Step 5: /export (PDF)
send_text_pane "/export"; sleep 1; send_enter_pane; sleep 10
snapshot_pane 06-export-pdf
