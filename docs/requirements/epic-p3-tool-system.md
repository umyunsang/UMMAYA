# Epic P3 · Tool system wiring · Python stdio MCP + active primitives

## Objective

Wire Python adapters (`src/kosmos/tools/`) as the LLM tool surface via stdio MCP. Expose active primitives (`lookup`/`resolve_location`/`submit`/`verify`) + auxiliary tools. Remove all CC dev tools from the runtime path.

## Context from codebase audit

**Python side — already built:**
- 14 registered tool_ids: `resolve_location`, `lookup`, `koroad_accident_search`, `koroad_accident_hazard_search`, `kma_weather_alert_status`, `kma_current_observation`, `kma_short_term_forecast`, `kma_ultra_short_term_forecast`, `kma_pre_warning`, `nmc_emergency_search`, `kma_forecast_fetch`, `hira_hospital_search`, `nfa_emergency_info_service`, `mohw_welfare_eligibility_search` (an earlier composite adapter was removed in Epic #1634 per migration tree § L1-B B6)
- `GovAPITool` model already has `primitive` field — but only 4 adapters set it (`accident_hazard_search`, `kma_forecast_fetch`, `hira_hospital_search`, `nmc_emergency_search` → `"lookup"`). 11 adapters have `primitive=None`
- Mock adapters cover active `verify` and `submit` surfaces. Subscribe is deferred until KOSMOS has an app/push-notification runtime.
- `GovAPITool` does NOT have `permission_tier`, `ministry`, `mode` (live/mock) fields — see clarification below

**TUI side:**
- `tui/src/ipc/bridge.ts` fully implemented (stdio JSONL). No `tui/src/ipc/mcp.ts` yet.
- No `tui/src/tools/primitive/` directory yet.

## Acceptance criteria

- [ ] 0 references to CC dev tools (`BashTool`, `FileEditTool`, `FileReadTool`, `FileWriteTool`, `GlobTool`, `GrepTool`, `NotebookEditTool`, `PowerShellTool`, `LSPTool`, `EnterWorktreeTool`, `ExitWorktreeTool`, `EnterPlanModeTool`, `ExitPlanModeTool`) in runtime tool registration
- [ ] 4 primitive wrappers implemented in `tui/src/tools/primitive/`
- [ ] `primitive` field populated on all 15 registered adapters
- [ ] `src/kosmos/ipc/mcp_server.py` stub wraps existing `stdio.py`
- [ ] `tui/src/ipc/mcp.ts` thin client reuses `bridge.ts`
- [ ] CI test `tests/tools/test_routing_consistency.py` passes

## File-level scope

### Delete (CC dev tools)
- `tui/src/tools/{BashTool,FileEditTool,FileReadTool,FileWriteTool,GlobTool,GrepTool,NotebookEditTool,PowerShellTool,LSPTool,EnterWorktreeTool,ExitWorktreeTool,EnterPlanModeTool,ExitPlanModeTool,REPLTool,ConfigTool}/`

### Keep and rewire (CC auxiliary)
- `tui/src/tools/WebFetchTool/` · `WebSearchTool/` — keep as-is
- `tui/src/tools/AgentTool/` → Task primitive; strip built-in agents (`claudeCodeGuideAgent.ts` · `exploreAgent.ts` · `planAgent.ts` · `verificationAgent.ts`)
- `tui/src/tools/BriefTool/` — keep (citizen document upload)
- `tui/src/tools/MCPTool/` — keep (external MCP passthrough)

### Evaluate per P4/P5
- `tui/src/tools/{TodoWriteTool,ToolSearchTool,AskUserQuestionTool,SleepTool,MonitorTool,WorkflowTool,ScheduleCronTool,Task{Create,Get,List,Stop,Update}Tool,Team{Create,Delete}Tool}/`

### New — active primitive wrappers
- `tui/src/tools/primitive/{lookup,submit,verify}.ts`
- `resolve_location` is a built-in meta-tool. `subscribe` is deferred until KOSMOS has an app/push-notification runtime.

### New — auxiliary tools
- `tui/src/tools/{Translate,Calculator,DateParser,ExportPDF}/`

### Python-side changes
- `register_all.py` — populate `primitive` on 11 adapters (`resolve_location`/`lookup`=`lookup`, others per metadata)
- `routing_index.py` new — `build_routing_index()` validate `primitive != None` at boot

### MCP bridge
- `tui/src/ipc/mcp.ts` · stdio MCP client reusing `bridge.ts`
- `src/kosmos/ipc/mcp_server.py` · MCP server stub wrapping `stdio.py`

## Key findings requiring clarification before implementation

1. `permission_tier` on `GovAPITool` — **existing `auth_level` (AAL1/2/3) covers this**. Decide: redundant `permission_tier: Literal[1,2,3]` vs derive from `auth_level`
2. `ministry` — `provider` string field already carries it. Decide: rename or add typed alias
3. `mode: live|mock` — does not exist. `AdapterRegistration.source_mode` is a different axis. Add `adapter_mode: Literal["live","mock"]` to `GovAPITool`

## Out of scope

Plugin adapters (P5) · docs/api (P6) · UI tool_use rendering (P4)

## Dependencies

Epic P0 + Epic P1+P2

## Related decisions

`docs/requirements/kosmos-migration-tree.md § L1-B + § L1-C + § P3`
