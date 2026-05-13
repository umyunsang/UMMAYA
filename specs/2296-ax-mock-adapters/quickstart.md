# Quickstart — Citizen End-to-End Tax-Filing Chain (US1)

**Spec**: [spec.md](./spec.md) US1
**Plan**: [plan.md](./plan.md)
**Date**: 2026-04-29

This document walks through the canonical Epic ε demonstration: a Korean citizen tells UMMAYA "내 종합소득세 신고해줘", and the LLM autonomously chains `verify(modid)` → `lookup(hometax_simplified)` → `submit(hometax_taxreturn)` → returns 접수번호. Every step uses Mock adapters with the six transparency fields fully populated.

---

## Prerequisites

- macOS or Linux developer machine
- UMMAYA worktree at `/Users/um-yunsang/UMMAYA-w-2296` checked out on branch `2296-ax-mock-adapters` (Epic ε post-merge)
- Python 3.12+ via `uv`
- Bun v1.2.x for the TUI
- `expect` for the Layer 2 PTY scenario
- `vhs` ≥ 0.11 for the Layer 4 visual scenario
- `UMMAYA_FRIENDLI_API_KEY` set in `.env` (the LLM must be reachable for the full chain; for offline runs, see § 6 alternative)

## 1. Install + boot the Mock backend

```bash
cd /Users/um-yunsang/UMMAYA-w-2296
uv sync
uv run python -m ummaya.ipc.demo.mock_backend &  # starts the Mock backend listening on stdio
# (Note: the backend is normally launched by the TUI via UMMAYA_BACKEND_CMD; this manual launch
#  is only useful for backend-side smoke. For the full chain, skip to § 2.)
```

Expected backend boot output (stderr — stdout is reserved for JSONL frames):

```text
INFO  ummaya.tools.register_all  Registered tool: resolve_location
INFO  ummaya.tools.register_all  Registered tool: lookup
INFO  ummaya.tools.register_all  Registered tool: koroad_accident_search
... (12 Live tools)
INFO  ummaya.tools.mock          Registered mock adapter: mock_verify_mobile_id (verify)
... (5 retrofitted existing verify mocks)
INFO  ummaya.tools.mock          Registered mock adapter: mock_verify_module_simple_auth (verify)
... (5 new verify mocks)
INFO  ummaya.tools.mock          Registered mock adapter: mock_submit_module_hometax_taxreturn (submit)
... (3 new submit mocks)
INFO  ummaya.tools.mock          Registered mock adapter: mock_lookup_module_hometax_simplified (lookup, GovAPITool)
... (2 new lookup mocks)
INFO  ummaya.ipc.demo.mock_backend  All 20 mock surfaces registered. Emitting AdapterManifestSyncFrame ...
INFO  ummaya.ipc.adapter_manifest_emitter  Manifest emitted: 16 main-registry entries + 18 sub-registry entries; SHA-256=8a7b6c5d...
INFO  ummaya.ipc.demo.mock_backend  Listening on stdio.
```

## 2. Launch the TUI against the Mock backend

```bash
cd /Users/um-yunsang/UMMAYA-w-2296
UMMAYA_BACKEND_CMD="uv run python -m ummaya.ipc.demo.mock_backend" \
  bun run tui
```

Expected first frames the TUI processes from the backend:

1. Handshake (existing Spec 287 frame)
2. **`AdapterManifestSyncFrame`** — populates the TS-side adapter cache (NEW — gates `validateInput` from the cold-boot race)
3. Heartbeat / idle

The TUI shows the UMMAYA branding boot screen → idle prompt.

## 3. The citizen turn

Type the citizen request:

```text
> 내 종합소득세 신고해줘
```

The LLM autonomously:

1. Recognises the request as a `submit` class against the `hometax` adapter family
2. Recognises the `hometax` family is OPAQUE without prior verify
3. Emits `verify(method='modid', scope_list=['find:hometax.simplified', 'send:hometax.tax-return'], purpose_ko='2024년 귀속 종합소득세 신고', purpose_en='Filing 2024 comprehensive income tax return')`

The TUI surfaces the permission prompt (CC-style `<PermissionRequest>`):

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 권한 요청 — verify (모바일 신분증)                                        │
│                                                                          │
│ 목적: 2024년 귀속 종합소득세 신고                                          │
│ 요청 범위:                                                               │
│   - 홈택스 간소화 자료 조회                                                │
│   - 홈택스 종합소득세 신고서 제출                                           │
│ 인용: 행정안전부 모바일 신분증 정책                                         │
│       https://www.mois.go.kr/.../mobile-id-policy.do                     │
│                                                                          │
│ [Y 한 번만]  [A 세션 동안 자동]  [N 거부]                                   │
└─────────────────────────────────────────────────────────────────────────┘
```

The citizen presses `Y`. The verify adapter:

- Simulates the modid biometric ceremony (3-second simulated wait — actually instant in Mock for smoke speed)
- Constructs a `DelegationToken` with `scope="find:hometax.simplified,send:hometax.tax-return"`, `expires_at=now+24h`, `issuer_did="did:web:mobileid.go.kr"`
- Appends a `delegation_issued` event to `~/.ummaya/memdir/user/consent/<today>.jsonl`
- Returns the token in a `DelegationContext` to the LLM

The LLM stores the token in tool-call context and emits:

```text
lookup(mode='fetch', tool_id='mock_lookup_module_hometax_simplified', params={year: 2024}, delegation=<context>)
```

The lookup adapter validates the token (scope match: `find:hometax.simplified` ∈ token's comma-list ✓), returns synthetic 간소화 자료 with the six transparency fields, and appends a `delegation_used` event with `outcome="success"`.

The LLM analyses the data and emits:

```text
submit(tool_id='mock_submit_module_hometax_taxreturn', params={...신고내용...}, delegation=<context>)
```

The submit adapter validates the token (scope match: `send:hometax.tax-return` ∈ token's comma-list ✓), produces a synthetic 접수번호 (e.g., `hometax-2026-04-29-RX-7K2J9`), and appends a `delegation_used` event with `outcome="success"` and the 접수번호.

The TUI renders the LLM's final response:

```text
신고가 완료되었습니다.
접수번호: hometax-2026-04-29-RX-7K2J9
```

## 4. Verify the audit ledger

```bash
tail -3 ~/.ummaya/memdir/user/consent/$(date +%Y-%m-%d).jsonl | jq -c .
```

Expected output (3 lines, all sharing the same `delegation_token` value):

```jsonl
{"kind":"delegation_issued","ts":"...","session_id":"...","delegation_token":"del_xyz...","scope":"find:hometax.simplified,send:hometax.tax-return","expires_at":"...","issuer_did":"did:web:mobileid.go.kr","verify_tool_id":"mock_verify_module_modid","_mode":"mock"}
{"kind":"delegation_used","ts":"...","session_id":"...","delegation_token":"del_xyz...","consumer_tool_id":"mock_lookup_module_hometax_simplified","receipt_id":null,"outcome":"success"}
{"kind":"delegation_used","ts":"...","session_id":"...","delegation_token":"del_xyz...","consumer_tool_id":"mock_submit_module_hometax_taxreturn","receipt_id":"hometax-2026-04-29-RX-7K2J9","outcome":"success"}
```

This satisfies SC-001 (under 30 s wall-clock) + SC-002 (3 ledger entries, matching token).

## 5. Layer 2 + Layer 4 smoke (PR-mandatory per AGENTS.md vhs Layer 4 mandate)

### 5.1 Layer 2 — PTY text-log scenario (FR-021)

```bash
cd /Users/um-yunsang/UMMAYA-w-2296
expect specs/2296-ax-mock-adapters/scripts/smoke-citizen-taxreturn.expect \
  | tee specs/2296-ax-mock-adapters/smoke-citizen-taxreturn-pty.txt
```

The `.expect` script:

1. spawns `bun run tui` with `UMMAYA_BACKEND_CMD` set to the Mock backend
2. waits for UMMAYA branding to appear
3. sends `내 종합소득세 신고해줘\r`
4. waits for permission prompt
5. sends `Y\r`
6. waits up to 30s for `접수번호` to appear in the output
7. asserts non-zero match
8. sends `\003\003` (double Ctrl-C) to exit cleanly

The captured `.txt` is committed to the PR for LLM grep-review (auto-memory `feedback_pr_pre_merge_interactive_test`).

### 5.2 Layer 4 — vhs visual + Screenshot keyframes (FR-022)

```bash
cd /Users/um-yunsang/UMMAYA-w-2296
vhs specs/2296-ax-mock-adapters/scripts/smoke-citizen-taxreturn.tape
```

The `.tape` file emits:

- `Output specs/2296-ax-mock-adapters/smoke-citizen-taxreturn.gif` (animated, sharable)
- `Screenshot specs/2296-ax-mock-adapters/smoke-keyframe-1-boot.png` — boot + UMMAYA branding visible
- `Screenshot specs/2296-ax-mock-adapters/smoke-keyframe-2-input.png` — citizen query typed in
- `Screenshot specs/2296-ax-mock-adapters/smoke-keyframe-3-action.png` — 접수번호 surfaced

Lead Opus uses Read tool on each PNG to verify visual content before push (per AGENTS.md vhs mandate).

## 6. Offline / no-LLM smoke

If `UMMAYA_FRIENDLI_API_KEY` is unavailable, replace step 3's "natural language to LLM" path with a scripted tool-call sequence using the backend RPC harness:

```bash
uv run python -m ummaya.ipc.demo.scripted_chain \
  --scenario specs/2296-ax-mock-adapters/scenarios/citizen-taxreturn.json
```

The scripted-chain harness reads a JSON file describing the verify → lookup → submit calls (with a placeholder for the LLM-determined scope_list and purpose strings) and exercises the same Mock adapters with the same audit ledger output. Useful for CI runs that don't hit the LLM.

## 7. Verify the IPC manifest sync (US2)

```bash
# In a separate terminal while the TUI is running:
uv run python -c "
from ummaya.ipc.demo.mock_backend import latest_manifest_emit_log
print(latest_manifest_emit_log())
"
```

Expected: a JSON dump of the most recent `AdapterManifestSyncFrame.entries` showing all 34 entries (16 main-registry + 10 verify + 5 submit + 3 subscribe). The `manifest_hash` field can be cross-checked against the value the TUI logs to its dev console (Bun stderr).

## 8. Verify the Codex P1 fix (US2 acceptance scenario #1)

In the TUI prompt, type:

```text
> 응급실 자리 알려줘 — 서울시 종로구
```

The LLM emits (via the existing geocoding + lookup chain):

```text
lookup(mode='fetch', tool_id='nmc_emergency_search', params={lat: 37.5..., lon: 126.9..., radius_km: 5})
```

This call previously failed at `validateInput` with `AdapterNotFound: 'nmc_emergency_search'` because the TS-side `context.options.tools` only contained the 14 internal tools. After Epic ε:

1. Tier 1 resolution succeeds against the synced manifest (`nmc_emergency_search` is a backend Live adapter)
2. Citation slot populates with `https://www.e-gen.or.kr/nemc/main.do` (NMC published policy URL)
3. Permission prompt surfaces with the agency-published citation
4. After citizen approval, the call dispatches to the backend's `nmc_emergency_search` adapter
5. The TUI renders the result

This satisfies SC-006 (`nmc_emergency_search` reaches `call()` end-to-end).

## 9. Test summary

| Test scenario | Spec coverage | Command |
|---|---|---|
| Unit: `DelegationToken` + scope/expiry/session | FR-007/009/010/011 | `uv run pytest tests/unit/primitives/test_delegation_*.py` |
| Unit: 5 new verify mocks (happy + error each) | FR-001 | `uv run pytest tests/unit/primitives/test_verify_module_*.py` |
| Unit: 3 new submit mocks (happy + error each) | FR-002 | `uv run pytest tests/unit/primitives/test_submit_module_*.py` |
| Unit: 2 new lookup mocks | FR-003 | `uv run pytest tests/unit/tools/test_lookup_module_*.py` |
| Unit: registry-wide transparency scan | FR-005/006, SC-005 | `uv run pytest tests/unit/tools/test_mock_transparency_scan.py` |
| Unit: IPC frame round-trip + 21-arm union | FR-015 | `uv run pytest tests/unit/ipc/test_adapter_manifest_sync_frame.py` |
| Integration: US1 chain | SC-001/002/007 | `uv run pytest tests/integration/test_e2e_citizen_taxreturn_chain.py` |
| Integration: US2 NMC adapter resolution | SC-006 | `uv run pytest tests/integration/test_codex_p1_adapter_resolution.py` |
| TS: manifest cache + cold-boot race | FR-016/019 | `cd tui && bun test adapterManifest.test.ts` |
| TS: primitive validateInput two-tier | FR-017/018/020 | `cd tui && bun test primitive/lookup-validation-fallback.test.ts` |
| TS: citation populated from manifest | FR-018 | `cd tui && bun test primitive/submit-citation-from-manifest.test.ts` |
| Layer 2 PTY scenario | FR-021 | `expect specs/2296-ax-mock-adapters/scripts/smoke-citizen-taxreturn.expect` |
| Layer 4 vhs + 3 keyframe PNGs | FR-022, SC-009 | `vhs specs/2296-ax-mock-adapters/scripts/smoke-citizen-taxreturn.tape` |
| Hard-rule: zero new deps | FR-023, SC-008 | `git diff main -- pyproject.toml tui/package.json \| grep -E '^\+\s'` (expect empty) |

All 13 test surfaces gate the merge.
