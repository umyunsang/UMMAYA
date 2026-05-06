# Real-Use Audit Report

- Root: `/Users/um-yunsang/KOSMOS/specs/realuse-audit-2026-05-05/fixes/target-state-full-after-research-grounded-routing-and-final-flow-fixes/TAX-002`
- Status: `pass`
- Files scanned: `57`
- Distinct sampled frames: `33`
- Tool calls observed: `5`

## Tool Calls

- `verify` final-scrollback.txt:9 `mock_verify_module_modid` — ⎿ 검증 결과: 인증 완료
- `lookup` final-scrollback.txt:12 `mock_lookup_module_hometax_simplified` — ⎿ record — 1건
- `submit` final-scrollback.txt:17 `mock_submit_module_hometax_taxreturn` — ⎿ 🧪 모의 제출 접수 | 처리: 신고 제출 | 접수 번호: hometax-2026-05-06-RX-BC4ECB51 | 상태: 신고완료
- `submit` final-scrollback.txt:27 `mock_submit_module_hometax_taxreturn` — ⎿ 🧪 모의 제출 접수 | 처리: 납부기한 알림 생성 | 접수 번호: hometax-2026-05-06-PAYREM-204B2C4E | 상태: 납부기한알림생성
- `subscribe` final-scrollback.txt:37 `mock_rest_pull_tick_v1` — ⎿ 구독 완료: 핸들 ID 없음 (error) | 실시간 스트림은 대화창에서 별도 ⎿ 인용으로 전달됩니다.
