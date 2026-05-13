# UMMAYA Final Packaging Readiness Audit

Date: 2026-05-07

Status: **P0 final-packaging gate passed**

This audit covers the reviewed final-packaging goal in
`specs/2773-rollback-debug-infra/codex-goal-final-packaging.md`. It does not
claim production affiliation or live authority for opaque citizen-write systems;
mock adapters remain evidence-graded mocks.

## Source Ledger

| Source | Authority | Decision Supported |
| --- | --- | --- |
| `.agents/skills/ummaya-reference-first/SKILL.md` | Skill gate | Reference-first workflow, curl-first live API validation, no fallback routing. |
| `docs/onboarding/codex-continuation.md` | UMMAYA Codex setup | Continuation requirements, OpenAI docs MCP check, Spec Kit skill location. |
| `docs/vision.md` | Canonical thesis | CC harness + FriendliAI/K-EXAONE + Korean public-service tool surface. |
| `docs/requirements/ummaya-migration-tree.md` | Requirement tree | P0-P6 scope and migration-readiness boundaries. |
| `.references/claude-code-sourcemap/restored-src/src/components/permissions/PermissionPrompt.tsx` | CC restored source | Permission prompt follows CC Select interaction. |
| `.references/claude-code-sourcemap/restored-src/src/hooks/toolPermission/handlers/interactiveHandler.ts` | CC restored source | Permission denial is terminal and must propagate. |
| `specs/2773-rollback-debug-infra/codex-goal-final-packaging.md` | Reviewed goal | Acceptance criteria and LLMOps/rendering-flow artifact requirements. |
| `specs/2773-rollback-debug-infra/nmc-curl-evidence.md` | Direct curl evidence | NMC coordinate vs region operation contract. |
| `specs/2773-rollback-debug-infra/mohw-curl-evidence.md` | Direct curl evidence | MOHW SSIS welfare parameters and quota behavior. |
| `specs/2773-rollback-debug-infra/nfa-curl-evidence.md` | Direct curl evidence | NFA 119 statistics endpoint and wire parameters. |
| `specs/2773-rollback-debug-infra/location-koroad-curl-evidence.md` | Direct curl evidence | Kakao location and KOROAD hazard lookup parameters. |

`codex mcp list` was previously run in this goal session and showed
`openaiDeveloperDocs ... enabled`.

## Final P0 Matrix

Command:

```text
uv run python scripts/tui-realuse-matrix.py \
  --capture-root specs/2773-rollback-debug-infra/captures/p0-full-final-16-2026-05-07 \
  --priority P0
```

The first full run produced one welfare audit false positive. The citizen flow
had completed `mohw_welfare_eligibility_search -> mock_verify_mydata ->
mock_welfare_application_submit_v1` and emitted receipt
`MOCK-WA-6d49a9edfe29`, but the old forbid regex matched the benign phrase
`사용자에게 직접 확인을 구하지 않고도`. After narrowing that audit-only regex,
the captures were re-audited without recapturing:

```text
uv run python scripts/tui-realuse-matrix.py \
  --capture-root specs/2773-rollback-debug-infra/captures/p0-full-final-16-2026-05-07 \
  --priority P0 \
  --audit-only
=> passed
```

Final summary:

```text
specs/2773-rollback-debug-infra/captures/p0-full-final-16-2026-05-07/matrix-summary.md
Overall: **pass**
```

All 20 P0 scenarios passed:

```text
LOC-ER-HADAN-001
LOC-WEATHER-DADAE-001
LOC-WEATHER-CURRENT-001
SAFETY-WEATHER-ALERT-001
HEALTH-HIRA-PEDIATRIC-001
SAFETY-NFA119-001
MOBILITY-ACCIDENT-HOTSPOT-001
WELFARE-ELIGIBILITY-001
WELFARE-APPLICATION-001
CIV-GOV24-MINWON-001
TAX-HOMETAX-SIMPLIFIED-001
TAX-HOMETAX-SUBMIT-001
PAY-TRAFFIC-FINE-001
IDENTITY-MOBILE-ID-001
IDENTITY-GANPYEON-001
MYDATA-ACTION-001
SUBSCRIBE-CBS-DISASTER-001
NEG-UNKNOWN-LOCATION-001
NEG-PERMISSION-DENY-SUBMIT-001
DISCOVERY-TOOL-SEARCH-001
```

Per-scenario LLMOps/render evidence exists under each scenario directory:

```text
backend.log        chat_request, reasoning preview, LLM usage, permission/ledger/tool events
frames/timeline.tsv frame sequence hashes and timestamps
frames/frame_*.txt  de-duplicated terminal frame snapshots
snap-*.txt          boot/input/permission/post-tool/expanded-detail checkpoints
final.raw.txt       raw terminal capture
final.txt           final plain-text screen
audit.json          abnormal-flow verdicts
audit.md            human-readable verdict
```

Counts in the final matrix root:

```text
20 backend.log files
20 frames/timeline.tsv files
20 final.raw.txt files
20 final.txt files
20 audit.json files, all `overall=pass`
```

## Targeted Recovery Evidence

Focused reruns used for root-cause proof:

```text
specs/2773-rollback-debug-infra/captures/p0-targeted-final-fixes-2026-05-07/
=> LOC-ER-HADAN-001 pass, IDENTITY-MOBILE-ID-001 pass
```

```text
specs/2773-rollback-debug-infra/captures/p0-targeted-urlheader-2026-05-07/
=> LOC-ER-HADAN-001 pass; no U+FFFD in verbose external-API header
```

```text
specs/2773-rollback-debug-infra/captures/p0-targeted-welfare-scope-2026-05-07/
=> WELFARE-APPLICATION-001 pass; visible verify scope collapsed to
   ["send:mydata.welfare_application"]
```

```text
specs/2773-rollback-debug-infra/captures/p0-targeted-hometax-submit-scope-timeout-2026-05-07/
=> TAX-HOMETAX-SUBMIT-001 pass; verify -> lookup -> submit with receipt
   hometax-2026-05-07-RX-6F8F3A38
```

Failed or invalid attempts retained as root-cause evidence:

```text
p0-full-final-12   LOC-ER U+FFFD and Mobile ID initial verify mismatch
p0-full-final-13   killed after reproducing verbose URL header corruption
p0-full-final-14   welfare verify scope polluted by stale Hometax lookup scope
p0-full-final-15   Hometax submit harness timeout while valid follow-up LLM call was still streaming
p0-targeted-hometax-submit-timeout invalid/aborted after exposing dotted Hometax lookup scope alias
```

## TUI Visual Evidence

The TUI change in `tui/src/tools/_shared/verboseRender.ts` is covered by the
real PTY matrix plus a vhs visual replay of the final passing Hadan emergency
capture:

```text
specs/2773-rollback-debug-infra/vhs/loc-er-hadan-urlheader.tape
specs/2773-rollback-debug-infra/vhs/loc-er-hadan-urlheader.gif
specs/2773-rollback-debug-infra/vhs/loc-er-hadan-urlheader.txt
specs/2773-rollback-debug-infra/vhs/loc-er-hadan-urlheader.ascii
specs/2773-rollback-debug-infra/vhs/loc-er-hadan-urlheader-01-boot.png
specs/2773-rollback-debug-infra/vhs/loc-er-hadan-urlheader-02-input.png
specs/2773-rollback-debug-infra/vhs/loc-er-hadan-urlheader-03-post-tool-flow.png
```

`vhs 0.11.0` accepted `Output ... .ascii` but did not materialize the file, so
`loc-er-hadan-urlheader.ascii` is a byte-identical copy of the vhs text render:

```text
sha256 txt/ascii: 9d43e13674e9fd69d062edf16030c902b86c56917c10e1ecef698fee66e643b6
```

No vhs artifact exceeds 1 MB.

## Implementation Deltas Covered

- Verify scope normalization now canonicalizes adapter aliases and prunes stale
  cross-domain lookup scopes before permission gating.
- Identity-only Mobile ID requests force the first verify tool choice only until
  verification succeeds.
- Hometax submit canonicalizes `find:mock.lookup_module_hometax_simplified`
  and `find:mock_lookup_module_hometax_simplified` to
  `find:hometax.simplified`.
- Hometax submit matrix timeout was raised to 300 seconds for the valid
  verify/lookup/submit sequence under K-EXAONE reasoning latency.
- Welfare application audit forbid regex now rejects actual user-handoff prose
  without flagging the benign "no direct confirmation required" transcript.
- `scripts/tui-realuse-matrix.py` gained `--audit-only` so audit rule fixes can
  be reapplied to immutable captures.
- Verbose outbound API headers now show bounded URL summaries while preserving
  the full original `outbound_traces.url` inside the JSON envelope.
- NMC ER operating-hour note is shorter and explicitly separates 24-hour ER
  semantics from outpatient hours.

## Local Gates

Already passed during the recovery loop:

```text
uv run ruff check src/ummaya/ipc/stdio.py src/ummaya/tools/nmc/emergency_search.py tests/ipc/test_stdio_chain_followup_gate.py tests/tools/nmc/test_field_semantics_enrichment.py
uv run pytest tests/ipc/test_stdio_chain_followup_gate.py tests/tools/nmc/test_field_semantics_enrichment.py -q
bun test tui/src/tools/_shared/verboseRender.test.ts
cd tui && bun run typecheck
uv run ruff check scripts/tui-realuse-matrix.py tests/scripts/test_tui_realuse_matrix.py
uv run pytest tests/scripts/test_tui_realuse_matrix.py -q
uv run python -m json.tool specs/2773-rollback-debug-infra/scenario-matrix.json
vhs validate specs/2773-rollback-debug-infra/vhs/loc-er-hadan-urlheader.tape
vhs specs/2773-rollback-debug-infra/vhs/loc-er-hadan-urlheader.tape
```

Final broad gates after the last code/test/doc updates:

```text
uv run ruff check src tests scripts
=> passed

uv run pytest -m "not live"
=> 4048 passed, 11 skipped, 51 deselected, 3 xfailed

cd tui && bun run typecheck
=> passed

cd tui && bun test
=> 1256 pass, 11 skip, 3 todo, 0 fail

git diff --check
=> passed
```

## Hygiene Checks

Final capture hygiene:

```text
find specs/2773-rollback-debug-infra/captures/p0-full-final-16-2026-05-07 -type f -size +1M
=> no files

rg --pcre2 -n "KakaoAK|serviceKey=(?!\\*\\*\\*)|authorization\\\"\\s*:\\s*\\\"(?!\\*\\*\\*)|Bearer " \
  specs/2773-rollback-debug-infra/captures/p0-full-final-16-2026-05-07
=> no matches

rg -n "Overall: \\*\\*fail\\*\\*|�|verify_tool_choice_mismatch|auth_required|Failed to detach|Traceback|Unknown tool|submit_already_succeeded|ValidationError|Field required|LookupFetchInput|String should match|scenario ERROR|timeout" \
  specs/2773-rollback-debug-infra/captures/p0-full-final-16-2026-05-07
=> no matches
```

VHS hygiene:

```text
find specs/2773-rollback-debug-infra/vhs -type f -size +1M
=> no files

rg -n "�|serviceKey=|Authorization:|Bearer |KakaoAK" specs/2773-rollback-debug-infra/vhs
=> no matches
```

## Completion Verdict

The reviewed P0 final-packaging gate is green: the five primitive abstraction
holds across the 20-scenario real-use matrix; recoverable validation/tool-choice
issues remain inside the loop; permission-gated mock submit/verify flows
propagate decisions and receipts; live lookup adapters cite curl-proven endpoint
contracts; expanded transcripts expose parameters, outbound traces, receipts,
and correlation context; frame artifacts and audit verdicts reconstruct each
tested turn from input to final render.

No blocking residual issue remains for the reviewed P0 packaging-readiness goal.
