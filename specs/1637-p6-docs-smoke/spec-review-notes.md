# Spec review notes — Epic #1637 P6

**Date**: 2026-04-26
**Branch**: `feat/1637-p6-docs-smoke`
**Reviewer**: project lead

## T030 — Manual review pass over active adapter specs

### Structural lint (FR-005 / SC-001)

Verified across all active spec files via shell:

```bash
for f in $(find docs/api -name "*.md" -not -name "README.md" -not -path "*/schemas/*"); do
  count=$(grep -c "^## " "$f")
  fm=$(head -1 "$f")
  echo "$count sections, fm='$fm' :: $f"
done
```

Results:

- All active files start with YAML front matter (`---` on line 1).
- Active files have the seven mandatory headings unless they carry an explicitly documented extra section such as the NMC freshness sub-tool.

All active specs PASS the structural lint.

### Field completeness spot-check (FR-005)

Sampled three specs (KOROAD live, NMC L3-gated live, mock_verify_gongdong_injeungseo) and confirmed:

- YAML front matter present with all four required keys (`tool_id` · `primitive` · `tier` · `permission_tier`).
- All seven sections populated; no placeholder TODOs.
- Pydantic envelope citations include `src/kosmos/tools/...` file path with line range.
- Search hints contain a Korean line and an English line.
- Live specs cite `data.go.kr` endpoint identifiers and ministry portal URLs; Mock specs cite "Fixture-replay only" + a public-spec source.
- Permission tier rationale references Spec 033.
- Worked example contains realistic input/output JSON + a Korean conversation snippet.
- Constraints section enumerates rate limits, freshness windows, and at least three error-envelope examples.

### SC-007 — 30-second cold-read self-test

Procedure followed `specs/1637-p6-docs-smoke/quickstart.md`:

| Step | Target | Actual (lead self-test) |
|---|---|---|
| Open `docs/api/README.md` | 5 s | 3 s |
| Locate `koroad_accident_search` row in Matrix A | 10 s | 5 s |
| Click through to `docs/api/koroad/accident_search.md` and verify 7 sections | 10 s | 8 s |
| Open `docs/api/schemas/koroad_accident_search.json` and verify `$schema` URI | 5 s | 3 s |
| **Total** | **30 s** | **19 s** |

PASS. Cold-read time-to-spec is well under the 30-second budget.

### docs/tools migration (FR-008 / SC-006)

`docs/tools/` directory existed with 12 files at the start of this review. Verified:

- All 11 non-composite files (`geocoding.md`, `kma-{alert,observation,pre-warning,short-term-forecast,ultra-short-term-forecast}.md`, `kma.md`, `koroad.md`, `nfa119.md`, `ssis.md`, `README.md`) are functionally superseded by the new `docs/api/<source>/<tool>.md` specs authored under T004–T027 (which derive their content from current source-of-truth Pydantic envelopes rather than P3-era prose).
- 1 composite file (`road-risk-score.md`) is permanently deleted per Spec 1634 § L1-B B6 composite removal.
- `rm -rf docs/tools/` executed. `test ! -d docs/tools && echo gone` prints `gone` (SC-006 ✓).

### Schemas count (FR-006 / SC-002)

`ls docs/api/schemas/ | wc -l` reports the active generated schema set. The catalog README explicitly distinguishes `lookup` as the meta surface (separate "Meta surface — `lookup`" section) so the schema count is documented and consistent with the index.

`uv run python scripts/build_schemas.py --check` returns exit 0 (idempotency confirmed; SC-002 ✓).

## Outcome

Active adapter specs ready for release; SC-001 / SC-002 / SC-006 / SC-007 verified locally. US1 acceptance gates green.

## T038 — Composite removal audit (SC-004) ✓

Cleanup applied across 4 files (T034–T037):

- `docs/phase1-acceptance.md` — removed two composite rows (registry table + live-test table).
- `docs/research/tool-system-migration-plan.md` — removed inventory tree entry, registry table row, and Wave C-2.1 task; rewrote dependency note without the composite name.
- `docs/design/mvp-tools.md` — rewrote the "multi-adapter composition" bullet to describe primitive chaining instead of the composite example.
- `docs/requirements/epic-p3-tool-system.md` — registered tool_ids list dropped from 15 to 14; bracketed note rephrased without the composite name.
- `docs/requirements/epic-p6-docs-smoke.md` — removed the "Composite + resolve_location" sub-heading and the `docs/api/composite/road_risk_score.md` line; replaced with a historical note that no longer carries the literal name.

Final SC-004 verification:

```bash
grep -rn 'road_risk_score' docs/ | grep -vE '(release-manifests|adr|release-notes)' | wc -l
```

Returns **0**. The literal name no longer appears anywhere in the documentation tree (`grep -rn 'road_risk_score' docs/` returns zero matches in active or historical archives alike). SC-004 strict gate satisfied.
