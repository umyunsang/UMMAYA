# Real-Use Audit Report

- Root: `/Users/um-yunsang/KOSMOS/specs/realuse-audit-2026-05-05/fixes/target-state-full-after-research-grounded-routing-and-final-flow-fixes/TAX-001`
- Status: `pass`
- Files scanned: `610`
- Distinct sampled frames: `586`
- Tool calls observed: `4`

## Tool Calls

- `verify` final-scrollback.txt:9 `mock_verify_module_modid` — ⎿ 검증 결과: 인증 완료
- `lookup` final-scrollback.txt:12 `mock_lookup_module_hometax_simplified` — ⎿ record — 1건
- `submit` final-scrollback.txt:17 `mock_submit_module_hometax_taxreturn` — ⎿ 🧪 모의 제출 접수 | 처리: 신고 제출 | 접수 번호: hometax-2026-05-06-RX-6D75E4B9 | 상태: 신고완료
- `submit` final-scrollback.txt:27 `mock_submit_module_hometax_taxreturn` — ⎿ 🧪 모의 제출 접수 | 처리: register_refund_account | 접수 번호: hometax-2026-05-06-RFND-2A2A4A45 | 상태: 환급계좌등록완료
