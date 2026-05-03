# Regression fixture — intentional-divergence test

> Purpose: prove that `.github/workflows/cc-byte-identical-guard.yml` (Epic
> #2639) actually fails the build when a SHA-256 mismatch is introduced
> against the CC 2.1.88 baseline without a corresponding whitelist entry.
>
> Spec: `specs/2639-s3-ui-guard/spec.md` FR-005 / SC-008.
> Audit: `specs/cc-migration-audit/scope-S3-components-screens.md § 9 D2`.

## Reproducible scenario (local)

The guard is invokable locally without spawning a CI job:

```bash
cd /path/to/KOSMOS

# 1. Baseline: confirm current main passes the guard.
python3 scripts/cc_byte_identical_guard.py \
    --baseline specs/2639-s3-ui-guard/fixtures/cc-baseline-shas.txt \
    --whitelist tui/src/.cc-byte-identical-whitelist.yaml \
    --slice-root tui/src
# expected: "PASS · scanned 454 files · 330 byte-identical · 60 whitelisted · 64 KOSMOS-only · 0 failed"

# 2. Inject an intentional divergence into a byte-identical file.
#    `tui/src/components/App.tsx` is byte-identical with CC and not in the
#    whitelist, so any change must trigger a fail.
echo "// regression-fixture: intentional divergence" >> tui/src/components/App.tsx

# 3. Re-run the guard.
python3 scripts/cc_byte_identical_guard.py \
    --baseline specs/2639-s3-ui-guard/fixtures/cc-baseline-shas.txt \
    --whitelist tui/src/.cc-byte-identical-whitelist.yaml \
    --slice-root tui/src
# expected:
#   ::error file=tui/src/components/App.tsx::SHA-256 mismatch and not in whitelist (got <hex>, expected CC <hex>). Add an entry to tui/src/.cc-byte-identical-whitelist.yaml with cause + spec_ref, or revert to byte-identical.
#   ::error::cc-byte-identical-guard FAILED · 1 divergent file(s) without whitelist entry. Total scanned: 454.
# exit code: 1

# 4. Revert the change.
git checkout tui/src/components/App.tsx

# 5. Confirm guard returns to PASS.
python3 scripts/cc_byte_identical_guard.py \
    --baseline specs/2639-s3-ui-guard/fixtures/cc-baseline-shas.txt \
    --whitelist tui/src/.cc-byte-identical-whitelist.yaml \
    --slice-root tui/src
# expected: PASS
```

## Reproducible scenario (PR-driven, CI)

1. Open a PR branch `test/cc-guard-regression-XXXX`.
2. Commit a single `// noop` line to `tui/src/components/App.tsx`.
3. Push — observe `CC Byte-Identical Guard (S3 slice) / guard` job FAIL with the same error annotation.
4. Add a whitelist entry for `App.tsx` with cause + spec_ref → guard PASSes.
5. Discard the test PR (no merge).

## Expected failure messages

For each unjustified divergent file, exactly one `::error file=...::` annotation appears:

```
::error file=tui/src/components/App.tsx::SHA-256 mismatch and not in whitelist (got 4f3a..., expected CC 9d12...). Add an entry to tui/src/.cc-byte-identical-whitelist.yaml with cause + spec_ref, or revert to byte-identical.
```

Followed by a job-level summary:

```
::error::cc-byte-identical-guard FAILED · 1 divergent file(s) without whitelist entry. Total scanned: 454.
```

## Pinned-SHA divergence (optional, future use)

The whitelist also supports `expected_sha256` for entries that need their
divergence content pinned (e.g. mascot files where any further mutation
should be reviewed). When set, a SHA mismatch from the pin produces:

```
::error file=tui/src/components/LogoV2/Clawd.tsx::SHA-256 differs from whitelist pin (got <hex>, pinned <hex>). Update expected_sha256 if the divergence intentionally changed.
```

## Edge cases covered

| Case | Expected behaviour |
|---|---|
| KOSMOS-only file (e.g. `components/onboarding/Onboarding.tsx`) | PASS — counted as `kosmos_only`. |
| CC-only file (e.g. `Feedback.tsx`) | Not present in slice → no enumeration, never failing. NEVER-PORT registry covers these (see `tui/src/components/.never-port.md`). |
| Whitelist YAML malformed | exit 2 with `::error file=...whitelist.yaml::` annotation. |
| Baseline fixture missing | exit 2 with `::error::baseline file not found:`. |
| Whitelist `expected_sha256` mismatch | exit 1 with pinned-SHA error annotation. |
| No divergence at all | PASS summary line printed to stdout. |

## Maintenance

The CC baseline SHA list is regenerated only when CC is intentionally
updated (e.g. CC 2.1.88 → next release). Procedure documented in
`specs/2639-s3-ui-guard/plan.md § 1.2`. ADR-004 (Spec 287) cycle covers
the bump.
