# TUI Real-Use Audit

Overall: **pass**

## capture_completeness: pass
Capture contains final state and intermediate artifacts.

- `frames=124`
- `snapshots=4`

## utf8_replacement_character: pass
No UTF-8 replacement characters were found in captured text.

## backend_log_health: pass
backend.log contains no audited traceback or OpenTelemetry context errors.

## agentic_chain_order: pass
Expected tool chain was visible in order inside one chronological capture.

- `chain@49:frames/frame_0049_798547bfb482.txt`

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
Required regex matched: 천안동남소방서|충청남도소방본부|202112|NORMAL SERVICE|구급활동
