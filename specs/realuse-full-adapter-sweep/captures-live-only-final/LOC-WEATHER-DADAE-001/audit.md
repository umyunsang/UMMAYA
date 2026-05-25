# TUI Real-Use Audit

Overall: **pass**

## capture_completeness: pass
Capture contains final state and intermediate artifacts.

- `frames=188`
- `snapshots=4`

## utf8_replacement_character: pass
No UTF-8 replacement characters were found in captured text.

## backend_log_health: pass
backend.log contains no audited traceback or OpenTelemetry context errors.

## agentic_chain_order: pass
Expected tool chain was visible in chronological captures.

- `locate@104:frames/frame_0104_b7b42f85330d.txt`
- `kma_forecast_fetch|kma_current_observation|kma_short_term_forecast@174:frames/frame_0174_0d01cc073ec2.txt`

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
Required regex matched: kma_forecast_fetch|kma_current_observation|kma_short_term_forecast

## require_regex: pass
Required regex matched: KMA격자좌표|현재날씨|기온|T1H|t1h

## forbid_regex: pass
Forbidden regex absent: 도구 결과 기준으로 처리 상태를 정리합니다\s*- 조회 .*invalid_params

## forbid_regex: pass
Forbidden regex absent: Missing .*lat|Missing .*lon
