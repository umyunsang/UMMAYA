#!/usr/bin/env bash
# Smoke 시나리오 — 부팅 후 5초 대기 + /quit 만. 인프라 자체 검증.
wait_for "KOSMOS|✻" "branding"
wait_seconds 3
snapshot "settled"
send_keys "/quit"
send_enter
wait_seconds 1
