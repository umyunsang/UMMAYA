<!-- SPDX-License-Identifier: Apache-2.0 -->

# Spec 032 — Deferred Items Tracking

Five capability pushes that the IPC stdio-hardening spec (`specs/032-ipc-stdio-hardening/spec.md` § Deferred to Future Work) explicitly names as out-of-scope-for-now. This file keeps them visible so that a future `/speckit-taskstoissues` run (or manual triage) can promote them to real GitHub Task issues when the prerequisite phase arrives. Constitution §VI follow-up rule.

Every row below MUST stay linked to a GitHub tracking issue. If an issue is retired, replace the ID — never blank the cell.

## Deferred capability pushes

| # | Deferred item | Why deferred | Prerequisite phase / epic | Tracking issue | Re-open trigger |
|---|---------------|--------------|---------------------------|----------------|-----------------|
| 1 | 원격 TUI 전송 계층 (WebSocket / HTTP) | AGENTS.md stack pins TUI↔backend to same-host stdio. 원격 운영은 공무원 상담 수요가 생기면 재평가 (Phase 3). | Phase 3 remote ops | #1373 | 공무원 원격 상담 요건 확정 시, 또는 MCP Streamable HTTP transport 안정화 시 |
| 2 | Frame-level 서명 / 암호화 (e2e) | Local stdio 전제이므로 외부 위협 모델 없음. 필요 시 Spec 024 Merkle chain 확장으로 흡수. | Phase 3 sovereignty | #1374 | Spec 024 audit Merkle chain GA 또는 외부 네트워크 전송 도입 시 |
| 3 | 백엔드 다중 인스턴스 세션 shard | 현 단계는 단일 백엔드 모델. Swarm 수평 확장 시 `SessionRingBuffer` + `TransactionLRU` shard 키 재설계 필요. | Phase 2.5 swarm shard | #1375 | Spec 027 swarm GA 이후 동시 세션 > 100 측정 시 |
| 4 | WebMCP-style declarative capability advertisement | MCP transports 표준이 정립 중. KOSMOS는 우선 active primitive 고정 세트로 진행. | Phase 2.5 MCP host | #1376 | MCP host 포트 시점 또는 MCP transport spec이 GA reach 시 |
| 5 | OS-native stdio alternative (Windows named pipes) | KOSMOS 타겟 OS는 macOS + Linux. Windows portability 우선순위 낮음. | Phase 3 portability | #1377 | Windows citizen TUI 배포 요건 확정 시 |

## Rules for this document

- Every row must have a **Tracking issue** column populated with a real GitHub issue number (no placeholders).
- When a Phase activates a deferred row, move it to its Phase's Initiative/Epic and **delete the row** from this table.
- If a row is cancelled (not deferred), record the ADR that cancelled it in-place and move the row into a `## Cancelled` section below.
- Do NOT silently remove a row. Cancellations leave an audit trail.

## Cross-references

- Source of truth: `specs/032-ipc-stdio-hardening/spec.md` § Scope Boundaries & Deferred Items
- ADR: `docs/adr/ADR-006-cc-migration-vision-update.md` § Part D-2 Epic A
- Constitution §VI: deferred items stay tracked until closed or cancelled
- Memory: `feedback_deferred_sub_issues.md` — Epic sub-issue close 시 `[Deferred]` 프리픽스 항목은 본 문서 + tracking issue로만 추적
