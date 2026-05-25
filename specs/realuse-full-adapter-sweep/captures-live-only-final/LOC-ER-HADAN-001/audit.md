# TUI Real-Use Audit

Overall: **pass**

## capture_completeness: pass
Capture contains final state and intermediate artifacts.

- `frames=158`
- `snapshots=4`

## utf8_replacement_character: pass
No UTF-8 replacement characters were found in captured text.

## backend_log_health: pass
backend.log contains no audited traceback or OpenTelemetry context errors.

## agentic_chain_order: pass
Expected tool chain was visible in chronological captures.

- `locate@65:frames/frame_0065_eb987f7c2c3e.txt`
- `nmc_emergency_search@151:frames/frame_0151_e8167bedbb1b.txt`

## submit_ledger_evidence: pass
No submit adapter ledger evidence is required for this scenario.

## recoverable_error_loop: pass
No recoverable invalid-parameter error was visible.

## visible_abnormal_flow: pass
No audited avoidable tool-selection recovery artifact was visible.

## cc_error_rendering: pass
No tool error was visible in this capture.

## expanded_tool_trace: pass
Tool trace details were visible.

## submit_rejected_status: pass
No rejected submit status was visible.

## raw_protocol_leak: pass
No raw IPC frame leak was detected in captured text.

## require_regex: pass
Required regex matched: 큐병원|응급실운영신고기관

## forbid_regex: pass
Forbidden regex absent: 도구 결과 기준으로 처리 상태를 정리합니다\s*- 조회 .*invalid_params

## forbid_regex: pass
Forbidden regex absent: collection\s*—\s*0건
