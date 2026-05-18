# Research: Live BaroCert Identity Check

## Decision 1: Use Toss `userIdentity` as the v1 live priority

**Decision**: Implement the v1 live path around Toss 본인확인, using the official
Python method sequence `requestUserIdentity`, `getUserIdentityStatus`, and
`verifyUserIdentity`.

**Rationale**: The feature request names Toss `userIdentity` as the first live
priority. The official BaroCert Toss Python reference exposes the same three
methods and documents required fields, status values, and returned result fields.

**Alternatives considered**:
- Kakao/Naver first: rejected because the user explicitly prioritizes Toss.
- A provider-neutral live path first: rejected because it risks a shallow
  abstraction before one live provider has concrete evidence.

## Decision 2: Keep raw identity evidence out of UMMAYA models

**Decision**: Parse provider result payloads into a sanitized verification
summary that records only evidence-presence booleans, provider, receipt
reference, status, and timestamps. Do not retain CI, DI, phone, birthday, name,
signedData, or encrypted identity attributes.

**Rationale**: BaroCert result models include identity-bearing fields such as CI,
DI, receiver attributes, and signedData. This Epic's acceptance criteria require
that UMMAYA returns `AuthContext` or external session references, not raw identity
payloads.

**Alternatives considered**:
- Store encrypted result fields for later comparison: rejected because encrypted
  identity payload retention violates this feature's privacy boundary.
- Return signedData to downstream submit adapters: rejected because there is no
  documented UMMAYA delegation-token exchange for this provider in v1.

## Decision 3: Explicit live tool id maps to the existing family

**Decision**: Register `live_verify_ganpyeon_injeung` as a check tool id whose
canonical family is `ganpyeon_injeung`. Preserve `mock_verify_ganpyeon_injeung`
mapping and behavior.

**Rationale**: Existing dispatcher and auth context models use family as the
identity mechanism discriminator, not runtime mode. The live and mock BaroCert
surfaces are two tool ids for the same identity family.

**Alternatives considered**:
- Add a new `ganpyeon_injeung_live` family: rejected because it would extend the
  auth union with runtime mode rather than identity semantics.
- Replace the mock adapter: rejected by FR-002.

## Decision 4: Optional SDK runtime, no default live dependency path

**Decision**: The adapter may use the official BaroCert Python SDK at live
runtime when installed, but default imports and fixture tests do not require it.

**Rationale**: The official guide instructs Python users to install `barocert`,
`pycryptodome`, and `cffi`, while UMMAYA default CI must remain fixture-only.
Optional runtime loading lets the live test fail closed when a human has not
prepared the SDK and credentials, without adding network behavior to default
tests.

**Alternatives considered**:
- Add a mandatory runtime dependency immediately: rejected for v1 because the
  adapter can be tested and reviewed through fixtures before live credentials
  are available.
- Reimplement Linkhub token and BaroCert HTTP calls directly with `httpx`:
  rejected because official docs expose an SDK contract and token/IP policy that
  should not be reverse-engineered in UMMAYA.

## Decision 5: Deferred items are tracked before implementation

**Decision**: Kakao live execution, Naver live execution, and provider-side raw
identity comparison are deferred and must receive tracking issues before
implementation starts.

**Rationale**: Constitution Principle VI forbids untracked ghost work. These
items are mentioned in the feature description but intentionally outside v1.

**Deferred validation summary**: 3 deferred items in spec.md, all marked
`NEEDS TRACKING` pending `/speckit-taskstoissues`.

## Official Sources Consulted

- `https://developers.barocert.com/reference/toss/python/userIdentity/api`
- `https://developers.barocert.com/reference/kakao/asp/identity/api`
- `https://developers.barocert.com/reference/naver/asp/identity/api`
- `https://developers.barocert.com/guide/toss/identity/python/getting-started/sdk-configuration`
- `https://developers.barocert.com/guide/toss/identity/python/getting-started/tutorial`
