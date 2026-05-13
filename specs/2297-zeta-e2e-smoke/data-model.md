# Phase 1 Data Model — Epic ζ #2297

**Date**: 2026-04-30
**Branch**: `2297-zeta-e2e-smoke`

This document enumerates the entities, fields, validation rules, and state transitions introduced or extended by this Epic. All Python entities are Pydantic v2 models (Constitution § III). All TS entities are Zod schemas + TS interfaces.

## 1. Backend — `_VerifyInputForLLM` (extended)

**File**: `src/ummaya/tools/mvp_surface.py:243`

**Schema (after FR-008a/8b extension)**:

```python
class _VerifyInputForLLM(BaseModel):
    """LLM-visible verify input schema — accepts both citizen-shape and legacy-shape."""

    # Citizen-facing canonical fields (LLM-emitted shape per system_v1.md v2):
    tool_id: str | None = Field(
        default=None,
        description=(
            "Verify adapter tool_id. MUST match a row in the system prompt's "
            "<verify_families> table (e.g. 'mock_verify_module_modid'). "
            "Pre-validator translates this to family_hint."
        ),
    )
    params: dict[str, object] | None = Field(
        default=None,
        description=(
            "Adapter-specific input. Must include scope_list (list[str] of "
            "'<verb>:<adapter_family>.<action>' scopes), purpose_ko, "
            "purpose_en. Pre-validator packs this into session_context."
        ),
    )

    # Legacy fields (preserved for backward compatibility — direct dispatcher calls):
    family_hint: str = Field(default="", description="(legacy) family hint string")
    session_context: dict[str, object] = Field(
        default_factory=dict, description="(legacy) session evidence dict"
    )

    @model_validator(mode="before")
    @classmethod
    def translate_tool_id_shape(cls, data: dict[str, object]) -> dict[str, object]:
        """Translate citizen-shape {tool_id, params} → legacy-shape {family_hint, session_context}.

        Idempotent — if data already has family_hint set, the citizen-shape fields
        are ignored. Raises ValueError on unknown tool_id.
        """
        if not isinstance(data, dict):
            return data
        # Already in legacy shape — pass through
        if data.get("family_hint"):
            return data
        # Citizen shape — translate
        tool_id = data.get("tool_id")
        if tool_id:
            from ummaya.tools.verify_canonical_map import resolve_family
            family = resolve_family(str(tool_id))
            if family is None:
                raise ValueError(f"unknown verify tool_id: {tool_id!r}")
            data = dict(data)  # don't mutate caller's dict
            data["family_hint"] = family
            params = data.get("params") or {}
            if isinstance(params, dict):
                data["session_context"] = {**data.get("session_context", {}), **params}
        return data
```

**Validation rules**:
- `tool_id` (when present) MUST match the canonical map's 10 keys; unknown values raise `ValueError`.
- `params` (when present) MUST be a dict; non-dict raises Pydantic validation error.
- `family_hint` (after translation) MUST be non-empty; the dispatcher reads it.
- `session_context` (after translation) is `params` merged with any existing `session_context` (citizen-shape `params` wins on key conflict).

**State transitions**: stateless (single-pass validation).

## 2. Backend — `verify_canonical_map` module

**File**: `src/ummaya/tools/verify_canonical_map.py` (new)

**Public API**:

```python
def resolve_family(tool_id: str) -> str | None:
    """Return the family_hint for the given verify tool_id, or None if unknown.

    The mapping is loaded once from prompts/system_v1.md <verify_families>
    block at module first-import (lru_cache).
    """

def get_canonical_map() -> Mapping[str, str]:
    """Return the full {tool_id: family_hint} frozen mapping (read-only)."""
```

**Internal state**: module-level `_MAP: Mapping[str, str] | None = None` populated by an `@lru_cache(maxsize=1)` loader that:
1. Resolves `prompts/system_v1.md` path via existing `UMMAYA_PROMPTS_DIR` env var (falls back to `<repo_root>/prompts`).
2. Reads the file, finds the `<verify_families>` ... `</verify_families>` block via regex.
3. Parses each table row (regex `^\| .+ \| `mock_verify_*` ...`).
4. Builds a frozen dict; raises `RuntimeError` if <10 entries found (FR-008b assertion).

**Validation rules**:
- Unicode-safe parsing (Korean column headers).
- The 10 canonical `tool_id` values are: `mock_verify_gongdong_injeungseo`, `mock_verify_geumyung_injeungseo`, `mock_verify_ganpyeon_injeung`, `mock_verify_mobile_id`, `mock_verify_mydata`, `mock_verify_module_simple_auth`, `mock_verify_module_modid`, `mock_verify_module_kec`, `mock_verify_module_geumyung`, `mock_verify_module_any_id_sso`.
- The mapping family_hint values are: `gongdong_injeungseo`, `geumyung_injeungseo`, `ganpyeon_injeung`, `mobile_id`, `mydata`, `simple_auth_module`, `modid`, `kec`, `geumyung_module`, `any_id_sso`.

## 3. TUI — `pendingCallRegistry`

**File**: `tui/src/tools/_shared/pendingCallRegistry.ts` (new)

**Schema**:

```typescript
export interface PendingCall {
  callId: string                               // UUIDv7 from TUI dispatcher
  primitive: 'lookup' | 'verify' | 'submit' | 'subscribe'
  resolve: (frame: ToolResultFrame) => void
  reject: (err: Error) => void
  timeoutHandle: ReturnType<typeof setTimeout>
  startMs: number
}

export class PendingCallRegistry {
  register(call: Omit<PendingCall, 'startMs'>): void
  resolve(callId: string, frame: ToolResultFrame): boolean  // returns true if found
  reject(callId: string, err: Error): boolean
  has(callId: string): boolean
  size(): number
  clear(): void                                 // session teardown
}
```

**Lifecycle**:
- `register` — called by `dispatchPrimitive.ts` immediately before sending the IPC `tool_call` frame.
- `resolve` — called by `llmClient.ts:tool_result` arm when an inbound `tool_result` frame arrives. Idempotent (no-op on duplicate).
- `reject` — called on timeout (FR-006).
- `clear` — called on session teardown (no leaks).

**Validation rules**:
- `callId` MUST be unique within a session lifetime.
- Resolve before reject is fine (race-tolerant — first-resolution wins, second is silent no-op).
- The registry is session-scoped (fresh instance per chat REPL); not persistent.

## 4. TUI — `dispatchPrimitive` shared helper

**File**: `tui/src/tools/_shared/dispatchPrimitive.ts` (new)

**Schema**:

```typescript
export interface DispatchPrimitiveOpts {
  primitive: 'lookup' | 'verify' | 'submit' | 'subscribe'
  args: Record<string, unknown>          // forwarded verbatim into tool_call frame
  context: ToolUseContext                // from CC SDK Tool.call signature
  registry: PendingCallRegistry          // session-scoped, injected
  bridge: IPCBridge                      // from bridgeSingleton
  timeoutMs?: number                     // default 30_000 (FR-006); UMMAYA_TUI_PRIMITIVE_TIMEOUT_MS override
}

export async function dispatchPrimitive<O>(
  opts: DispatchPrimitiveOpts,
): Promise<ToolResult<O>>
```

**Behavior**:
1. Generate fresh `callId = makeUUIDv7()`.
2. Construct `ToolCallFrame { call_id: callId, name: opts.primitive, arguments: opts.args, ... }` — sessionId/correlationId pulled from `opts.context.toolUseId` and ambient session.
3. Register pending call via `opts.registry.register(...)` with timeoutHandle = `setTimeout(reject, timeoutMs)`.
4. Send frame via `opts.bridge.send(frame)`.
5. Return a `Promise<ToolResult<O>>` that the registry resolves on `tool_result` arrival.
6. On success: parse `frame.envelope` per the primitive's expected schema, return `{ data: { ok: true, result: envelope } }`.
7. On error envelope (`envelope.error` set): return `{ data: { ok: false, error: envelope.error } }`.
8. On timeout: emit OTEL span attribute `ummaya.tui.primitive.timeout=true`, return `{ data: { ok: false, error: '응답 시간이 초과되었습니다' } }`.

**Validation rules**:
- The `ToolResultFrame` envelope is opaque to the dispatcher (just a passthrough); each primitive's `call()` body interprets the result type.
- Timeout MUST be > 0; default 30s. CI may override via env.

## 5. TUI — frame stream `tool_result` route in `llmClient.ts`

**File**: `tui/src/ipc/llmClient.ts:405` (extended after the existing `tool_call` arm)

**Schema (TS pseudocode)**:

```typescript
// ---- ToolResultFrame ----------------------------------------------
else if (frame.kind === 'tool_result') {
  const trFrame = frame as ToolResultFrame
  const resolved = pendingCallRegistry.resolve(trFrame.call_id, trFrame)
  if (!resolved) {
    process.stderr.write(
      `[UMMAYA LLMClient WARN] tool_result with no pending call_id=${trFrame.call_id}\n`,
    )
  }
  // Do not yield a SDK event — the SDK loop continues to await message_stop
}
```

**Validation rules**:
- The frame's `correlation_id` MUST match the chat_request's; if not, the bridge would have routed it elsewhere — defensive log only.
- Unknown `call_id` (no pending registration) is logged at WARN and dropped (forward compat).
- The SDK event stream is NOT extended — `tool_result` is consumed silently from the SDK's perspective; the registry resolution is what matters.

## 6. Smoke fixture — citizen chain prompt

**File**: `tests/fixtures/citizen_chains/<family>.json` (new, 10 files)

**Schema**:

```json
{
  "family_hint": "modid",
  "tool_id": "mock_verify_module_modid",
  "citizen_prompt": "종합소득세 신고해줘",
  "expected_first_tool_call": {
    "name": "verify",
    "arguments": {
      "tool_id": "mock_verify_module_modid",
      "params": {
        "scope_list": ["find:hometax.simplified", "send:hometax.tax-return"],
        "purpose_ko": "종합소득세 신고",
        "purpose_en": "Comprehensive income tax filing"
      }
    }
  },
  "expected_chain_completes_with_receipt": true,
  "expected_mock_invocations": [
    "mock_verify_module_modid",
    "mock_lookup_module_hometax_simplified",
    "mock_submit_module_hometax_taxreturn"
  ]
}
```

**Validation rules**:
- `family_hint` MUST be one of the 10 canonical values.
- `tool_id` MUST be the canonical-map key for `family_hint`.
- `expected_chain_completes_with_receipt` is `true` for `modid` / `simple_auth_module` / `kec` / etc. (chain-class verify) and `false` for `any_id_sso` (IdentityAssertion only — no submit).
- `expected_mock_invocations` is an ordered list; the integration test asserts order.

**State transitions**: fixtures are static; no mutation.

## 7. Smoke artefacts

**Files**:
- `specs/2297-zeta-e2e-smoke/scripts/smoke-citizen-taxreturn.expect` — `expect`-based PTY driver.
- `specs/2297-zeta-e2e-smoke/scripts/smoke-citizen-taxreturn.tape` — vhs script.
- `specs/2297-zeta-e2e-smoke/smoke-citizen-taxreturn-pty.txt` — captured PTY log.
- `specs/2297-zeta-e2e-smoke/scripts/smoke-keyframe-{1-boot,2-dispatch,3-receipt}.png` — keyframes.
- `specs/2297-zeta-e2e-smoke/scripts/smoke-citizen-taxreturn.gif` — animated capture.

**Validation rules**:
- `.expect` script MUST set timeout=90s, send the citizen prompt, await receipt, exit cleanly.
- `.tape` MUST emit `Output …gif` AND ≥3 `Screenshot` directives.
- Keyframe-3 PNG MUST contain the receipt-id text `접수번호: hometax-2026-MM-DD-RX-XXXXX` legible to multimodal Read.

## 8. Policy mapping doc

**File**: `docs/research/policy-mapping.md` (new)

**Structure**:

```markdown
# UMMAYA Adapter ↔ International AX-Gateway Mapping

[Bilingual title]

## Thesis (한국어 primary, English secondary)
[1-2 paragraphs linking AGENTS.md § CORE THESIS to the four international analogs]

## Mapping table

| UMMAYA adapter family | Singapore APEX | Estonia X-Road | EU EUDI Wallet | Japan マイナポータル API |
|---|---|---|---|---|
| modid (mobile_id_module)         | Singpass NDI                | eID (mID)              | EUDI PID            | マイナンバーカード認証 |
| kec (corporate certificate)      | CorpPass                    | Riigiportaal eID corp  | LEI / EUDI corporate| 法人共通認証基盤        |
| ... (≥10 rows total)             | ...                         | ...                    | ...                 | ...                    |

## Citations (footnotes)
[1] APEX — https://www.developer.tech.gov.sg/products/categories/digital-identity/apex/overview ...
```

**Validation rules**: ≥10 rows. Each foreign-spec column has at least one non-null mapping. All citation URLs return 2xx/3xx.

## 9. OPAQUE scenario docs

**Files** (5):
- `docs/scenarios/hometax-tax-filing.md`
- `docs/scenarios/gov24-minwon-submit.md`
- `docs/scenarios/mobile-id-issuance.md`
- `docs/scenarios/kec-yessign-signing.md`
- `docs/scenarios/mydata-live.md`

**Structure** (per FR-018):
1. Korean-primary title.
2. "Why no adapter" paragraph (1-2 sentences).
3. Numbered citizen narrative (≥5 steps: citizen action → TUI message → hand-off URL → return path → confirmation).
4. `## Hand-off URL` footer with the canonical agency UI URL.

**Validation rules**: lint-only (existing `markdownlint`); no runtime tests.
