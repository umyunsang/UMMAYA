# Requirements Checklist: Retrieval Backend Evolution — BM25 → Dense Embeddings

**Purpose**: Validate that spec.md is internally consistent, honours the frozen contract, and surfaces every cross-Epic dependency before `/speckit-plan`.
**Created**: 2026-04-17
**Feature**: [spec.md](../spec.md)

## Frozen Contract Preservation

- [ ] CHK001 `LookupSearchInput` pydantic schema is named as frozen in spec Background §1 and FR-003.
- [ ] CHK002 `LookupSearchResult(kind, candidates, total_registry_size, effective_top_k, reason)` shape is named as frozen in spec and covered by SC-004.
- [ ] CHK003 `AdapterCandidate` field set is explicitly preserved under FR-003.
- [ ] CHK004 Adaptive `top_k` clamp `max(1, min(k, registry_size, 20))` is preserved under FR-005.
- [ ] CHK005 Deterministic tie-break (score DESC, tool_id ASC) is preserved under FR-004.
- [ ] CHK006 A schema-snapshot regression test is specified (Appendix B).
- [ ] CHK007 `BM25Index.rebuild`/`score` surface preservation is codified under FR-009.

## Baseline Saturation & Re-anchoring

- [ ] CHK008 Measured baseline (`recall_at_5 = 1.0`, `recall_at_1 = 0.9667`) is captured with method + timestamp.
- [ ] CHK009 Spec explicitly states why Epic's "+10%p" is unmeasurable on the 30-query set.
- [ ] CHK010 SC-001 is re-anchored to the extended corpus (#22) with `PENDING_#22` semantics via FR-013.
- [ ] CHK011 SC-002 adversarial-subset target and BM25 ceiling (< 0.50) are both specified.

## Requirements — Completeness

- [ ] CHK012 FR-001 makes the backend choice explicit and fail-closed on unknown values.
- [ ] CHK013 FR-002 distinguishes fail-open on retrieval from fail-closed on auth/invocation.
- [ ] CHK014 FR-007 prohibits new OTEL attributes in line with #501 boundary.
- [ ] CHK015 FR-008 forbids hardcoded synonym/keyword/salvage layers per `feedback_no_hardcoding.md`.
- [ ] CHK016 FR-010 forbids committed weight artefacts > 1 MB and disallows CI weight download.
- [ ] CHK017 FR-012 requires the adversarial subset file to ship in this PR.
- [ ] CHK018 NFR-License excludes ko-SBERT candidates unless upstream licence confirmed.
- [ ] CHK019 NFR-Reproducibility specifies determinism tolerance (≤ 1e-6).
- [ ] CHK020 NFR-BootBudget protects the `backend=bm25` cold-start path.

## Cross-Epic Dependencies

- [ ] CHK021 #507 byte-level contract commitment is named and evidenced.
- [ ] CHK022 #22 dependency is named; closed #579 is explicitly NOT cited.
- [ ] CHK023 #501 OTEL boundary is respected (log-only path via FR-007).
- [ ] CHK024 #467 manifest extension fields are proposed (not named finally).
- [ ] CHK025 #468 env-var registry is flagged; four proposed env vars listed.

## Clarifications Discipline

- [ ] CHK026 Exactly three `[NEEDS CLARIFICATION: ...]` markers are present (≤ 3 rule).
- [ ] CHK027 Each clarification carries a recommendation and rationale.

## Scope & Deferral Hygiene

- [ ] CHK028 Every "deferred" item in the Deferred table has either a tracking issue number or `NEEDS TRACKING`.
- [ ] CHK029 Out-of-scope section names cross-encoder re-ranking and GPU/CUDA explicitly.
- [ ] CHK030 Out-of-scope forbids changes to `GovAPITool` schema and any adapter body.

## Hard-Rule Audit

- [ ] CHK031 Spec confirms Apache-2.0-only model policy.
- [ ] CHK032 Spec forbids print() outside CLI.
- [ ] CHK033 Spec confirms no new dependency is added outside this spec-driven PR.
- [ ] CHK034 Spec confirms CPU-only, no CUDA/GPU code paths.
- [ ] CHK035 Spec confirms English source / Korean domain-data only.

## Testability

- [ ] CHK036 Each SC is mapped to a concrete test surface (file path or harness entry point).
- [ ] CHK037 Edge cases list covers empty registry, empty query, mixed-language query, and first-query tail latency.
- [ ] CHK038 FR-002 graceful-degradation path has a paired SC-005 and an acceptance scenario.

## Notes

- This checklist validates the SPEC, not the implementation. `/speckit-plan` produces its own checks on plan completeness.
- Items are numbered sequentially (CHK001–CHK038). Cross-reference numbers from `/speckit-analyze` findings if any item flips to `[x]` based on subsequent review.
