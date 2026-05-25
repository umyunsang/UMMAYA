# TUI Real-Use Audit

Overall: **pass**

## capture_completeness: pass
Capture contains final state and intermediate artifacts.

- `frames=156`
- `snapshots=4`

## utf8_replacement_character: pass
No UTF-8 replacement characters were found in captured text.

## backend_log_health: pass
backend.log contains no audited traceback or OpenTelemetry context errors.

## agentic_chain_order: pass
Expected tool chain was visible in chronological captures.

- `locate@57:frames/frame_0057_82d00d0d42b2.txt`
- `kma_forecast_fetch|kma_current_observation@142:frames/frame_0142_5f69185d7cf9.txt`

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

## forbid_regex: pass
Forbidden regex absent: 강남역.*결과

## forbid_regex: pass
Forbidden regex absent: 강남구.*날씨
