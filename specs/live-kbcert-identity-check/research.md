# Research: Live KB Identity Check Adapter

## Official Source Findings

### KB identity flow

**Decision**: Implement the two API server-side flow documented by KB: identity request followed by identity result lookup.

**Rationale**: KB describes a service flow where the institution server calls the identity request API, receives `certTxId` and `callUrl`, the user completes KB app/standard-window authentication, and the institution server calls the result API. The guide identifies request fields `companyCd`, `reqTxId`, and `requestType`, and result lookup fields `reqTxId`, `certTxId`, `companyCd`, and `requestType`.

**Primary source**: `https://cert.kbstar.com/quics?page=C112279`

**Alternatives considered**:

- Browser/device automation of the standard window: rejected as outside adapter scope because KB owns the app/window ceremony.
- BaroCert-style provider wrapper: rejected because KB has distinct endpoint/header semantics.

### KB common API information

**Decision**: Use `https://stg-openapi.kbstar.com:8443/` and `https://openapi.kbstar.com:8443/` as allowed base URLs, with `Content-Type: application/json; charset=UTF-8`.

**Rationale**: KB common information lists HTTPS/TLS 1.2+, POST, JSON content type, and staging/production domains.

**Primary source**: `https://cert.kbstar.com/quics?page=C112276`

**Alternatives considered**:

- Hardcoding staging only: rejected because production URL is official and must be configurable.
- Letting arbitrary base URLs through silently: rejected; tests validate URL normalization, while live env can still point to KB-provided staging/production.

### KB test procedure

**Decision**: Live tests require KB partner credentials and must remain opt-in.

**Rationale**: KB's test page states `apiKey` is issued after contract completion, `hsKey` is generated using `apiKey`, and firewall/test app setup happens after contract completion. Default CI cannot assume those credentials or network allowlisting.

**Primary source**: `https://cert.kbstar.com/quics?page=C112283`

**Alternatives considered**:

- Running credentialed smoke in CI: rejected by project government API compliance and KB partner setup requirements.

## UMMAYA Integration Findings

### Verify family shape

**Decision**: Add `kb_identity` as a new verify family and `KbIdentityContext` as a new AuthContext variant.

**Rationale**: The primitive dispatcher keys adapters by family, not by tool id. Registering KB under `ganpyeon_injeung` would overwrite the existing mock adapter and violate the cross-worktree boundary. A new family is additive and keeps BaroCert/MobileID untouched.

**Alternatives considered**:

- Return `GanpyeonInjeungContext(provider="bank")`: rejected because dispatch still needs a unique family to avoid replacing existing adapter registration.
- Return a plain dict: rejected because the verify dispatcher accepts only typed AuthContext variants or `VerifyMismatchError`.

### Discovery shape

**Decision**: Add `live_verify_kb_identity` to `discovery_bridge._VERIFY_FAMILIES` and `verify_canonical_map` derivation through metadata.

**Rationale**: The core `check` surface translates citizen-shape `tool_id` to a verify family through the canonical map. Discovery metadata is already the source of truth for check tool ids.

**Alternatives considered**:

- Direct `family_hint="kb_identity"` only: rejected because current LLM-facing and IPC paths prefer `tool_id`.

### Gateway eligibility

**Decision**: Keep KB check direct-only and non-proxyable.

**Rationale**: `live_proxy.py` only treats `find` and `locate` live adapters as gateway-proxyable. KB is a citizen identity check and must not be routed through the public-data live gateway without a separate policy spec.

**Alternatives considered**:

- Extend the gateway for `check`: rejected as outside this feature and likely to need a separate security spec.

## Deferred Items Validation

Spec declares no deferred work. Excluded KB app/window automation, identity decryption/storage, and other provider changes are adapter scope exclusions rather than tracked follow-up work.
