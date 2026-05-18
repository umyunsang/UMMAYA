# Implementation Plan: Live KB Identity Check Adapter

**Branch**: `feat/live-kbcert-identity-check` | **Date**: 2026-05-18 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/live-kbcert-identity-check/spec.md`
**Epic**: #2888

## Summary

Add a KB국민인증서 live `check` adapter that wraps the KB identity request and result lookup flow. The adapter exposes `live_verify_kb_identity`, stores no raw identity attributes, and returns an AuthContext-compatible result whose only external reference is an opaque combination of `reqTxId` and `certTxId`. Default tests use sanitized fixtures only; credentialed KB calls are isolated behind `@pytest.mark.live`.

## Technical Context

**Language/Version**: Python 3.12+
**Primary Dependencies**: httpx, pydantic v2, pytest, pytest-asyncio
**Storage**: N/A for adapter state; sanitized fixtures under `tests/fixtures/kbcert/`
**Testing**: pytest, `@pytest.mark.live` for credentialed KB calls, default `-m "not live"` fixture replay
**Target Platform**: macOS/Linux CLI and backend runtime
**Project Type**: CLI/backend adapter in UMMAYA Tool System Layer 2
**Performance Goals**: One request call and one result lookup per identity ceremony; no caching of identity results
**Constraints**: No live KB calls in CI; all credentials via `UMMAYA_KBCERT_*`; no CI/DI/name/birthday/gender/nationality in outputs, logs, or snapshots; fail closed on upstream or schema errors
**Scale/Scope**: One live check adapter, one KB-specific client module, focused unit/registry/live tests, one adapter doc

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Reference-Driven Development | PASS | KB official guide pages are the source for flow, request/result fields, headers, domains, and content type. `docs/vision.md` confirms active primitives are `find` / `locate` / `send` / `check`, and this feature binds only to `check`. |
| II. Fail-Closed Security | PASS | Adapter drops identity attributes, rejects incomplete or failed KB responses, and uses no hardcoded credentials. |
| III. Pydantic v2 Strict Typing | PASS | New input/output/client payloads are Pydantic v2 models; no `Any` in public I/O schemas. |
| IV. Government API Compliance | PASS | Live tests are opt-in via `@pytest.mark.live`; fixtures are sanitized; credentials use `UMMAYA_` environment names. |
| V. Policy Alignment | PASS | Identity verification supports consent-based public-service execution while keeping personal identifiers out of UMMAYA persistence. |
| VI. Deferred Work Accountability | PASS | Spec declares zero deferred items and scopes out KB device/window automation as excluded from this adapter. |

## Project Structure

### Documentation (this feature)

```text
specs/live-kbcert-identity-check/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── kb-identity-check.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/ummaya/primitives/verify.py                  # additive kb_identity context
src/ummaya/tools/registry.py                     # additive KB published tier literal
src/ummaya/tools/models.py                       # additive GovAPITool tier literal if needed
src/ummaya/tools/live/__init__.py                # import side-effect package
src/ummaya/tools/live/kb_identity_client.py      # KB request/result HTTP client
src/ummaya/tools/live/verify_kb_identity.py      # live check adapter registration/invoke
src/ummaya/tools/discovery_bridge.py             # live check discovery metadata
src/ummaya/tools/verify_canonical_map.py         # live tool id mapping compatibility
src/ummaya/tools/mvp_surface.py                  # check primitive description update
src/ummaya/tools/register_all.py                 # import live check package before bridging
docs/api/verify/live-kb-identity.md              # adapter usage and evidence requirements
tests/fixtures/kbcert/                           # sanitized KB request/result fixtures
tests/unit/tools/live/test_kb_identity_client.py # client and redaction unit tests
tests/unit/tools/live/test_verify_kb_identity.py # adapter and registry unit tests
tests/live/test_live_kb_identity.py              # opt-in credentialed smoke tests
```

**Structure Decision**: KB receives its own `src/ummaya/tools/live/` client and adapter to avoid touching BaroCert or MobileID implementation files. `verify.py` changes are additive only: a new `kb_identity` family and typed context. Central discovery changes are limited to metadata needed for `live_verify_kb_identity` to be selectable through the existing `check(tool_id=..., params=...)` path.

## Complexity Tracking

> No constitution violations. No complexity tracking required.

---

## Phase 0: Research

See [research.md](./research.md).

### Key Decisions

1. **New `kb_identity` family instead of overloading `ganpyeon_injeung`**: The KB flow has separate headers, endpoint names, transaction semantics, and result fields. Reusing BaroCert/Ganpyeon would either overwrite the mock family adapter or hide KB-specific failure modes.
2. **Opaque external reference only**: `external_session_ref` uses `kbcert:reqTxId=<redacted-or-synthetic>;certTxId=<redacted-or-synthetic>` style metadata. Identity result fields are recognized only to record `identity_evidence_present=True` internally during parsing; they are not copied into AuthContext.
3. **Direct local adapter only**: The live adapter gateway currently permits `find` and `locate` live adapters only. KB is a `check` identity ceremony and must not be proxyable through the existing public-data gateway path.
4. **Environment contract**: `UMMAYA_KBCERT_BASE_URL`, `UMMAYA_KBCERT_API_KEY`, `UMMAYA_KBCERT_HS_KEY`, and `UMMAYA_KBCERT_COMPANY_CD` are required for live tests. Optional `UMMAYA_KBCERT_REQUEST_TYPE` defaults to `NONE`.
5. **Credentialed evidence policy**: Documentation includes official curl templates and requires sanitized direct-curl evidence before live-readiness claims, but fixture replay remains the default acceptance path.

### Deferred Items Validation

The spec has no `NEEDS TRACKING` entries. Excluded items are scoped as permanent exclusions for this adapter and do not create deferred feature work.

---

## Phase 1: Design

See [data-model.md](./data-model.md), [contracts/kb-identity-check.md](./contracts/kb-identity-check.md), and [quickstart.md](./quickstart.md).

### Design Decisions

#### D1: Client boundary

`kb_identity_client.py` owns:

- base URL normalization
- `apiKey` / `hsKey` header construction
- request body construction for `/kbsign/api/sign_request2`
- result body construction for `/kbsign/api/sign_result`
- response status normalization
- fail-closed exceptions with sanitized messages

It never logs or returns KB identity fields.

#### D2: Adapter boundary

`verify_kb_identity.py` owns:

- session context parsing from `check(tool_id="live_verify_kb_identity", params={...})`
- environment configuration
- request-only and result-lookup modes
- conversion to `KbIdentityContext`
- registration via `register_verify_adapter("kb_identity", invoke)`

#### D3: Redaction contract

The sanitizer drops these keys recursively from response bodies before any error or receipt construction: `CI`, `DI`, `userNm`, `birthday`, `receiverHP`, `receiverName`, `receiverBirthday`, `gender`, `krnFrgnDstcd`, `phone`, `name`, `birthdate`, and lowercase variants. Tests use sentinel values and assert absence from returned model dumps and log records.

#### D4: Failure contract

The adapter returns `VerifyMismatchError` for check-layer failures instead of raising raw transport or parsing errors through the primitive dispatcher. The observed family is `kb_identity_error`, and messages are sanitized.

#### D5: Registry/discovery contract

`live_verify_kb_identity` is non-core, `primitive="check"`, `adapter_mode="live"`, `auth_type="api_key"`, `source_mode=OOS`, and `cache_ttl_seconds=0`. It is discoverable via Korean/English KB identity keywords but only invoked through the core `check` primitive.

### Post-Design Constitution Re-Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Reference-Driven Development | PASS | Official KB docs and `docs/vision.md` are cited in research and docs. |
| II. Fail-Closed Security | PASS | All parser/transport failures become sanitized check errors; identity fields are dropped recursively. |
| III. Pydantic v2 Strict Typing | PASS | Public input/output and internal response models are Pydantic v2. |
| IV. Government API Compliance | PASS | Live tests require env credentials and marker opt-in; fixture replay is default. |
| V. Policy Alignment | PASS | The adapter supports identity verification without storing personal identifiers. |
| VI. Deferred Work Accountability | PASS | Zero deferred items. |
