# Homebrew Official Readiness

This note records the current gate for submitting UMMAYA to official Homebrew repositories.
It is intentionally separate from the user-facing install docs because official acceptance is
not controlled by UMMAYA release automation alone.

## Sources Checked

- Homebrew Cask maintainer feedback on Homebrew/homebrew-cask#265674:
  "We only install prebuilt binaries in `homebrew-cask`."
- Homebrew Cask README and AGENTS guidance from a fresh `Homebrew/homebrew-cask` checkout.
- Homebrew Cask Cookbook, especially `url`, `binary`, `livecheck`, and `*flight` stanzas.
- Homebrew Acceptable Casks and Acceptable Formulae policy pages.
- Homebrew/brew audit implementation in `utils/shared_audits.rb`.
- Current official cask patterns for CLI binaries: `codex`, `claude-code`, `kotlin-native`,
  `cursor-cli`, `hummingbird`, `1password-cli`, and related binary-only casks.

## Current State

UMMAYA v0.1.16 now publishes macOS release archives:

- `ummaya-<version>-macos-arm64.tar.gz`
- `ummaya-<version>-macos-x64.tar.gz`

These archives are built before release. Homebrew Cask installation no longer runs
`npm install` or `bun install`; it downloads one prebuilt archive and links the `ummaya`
wrapper. This addresses the direct maintainer comment on PR #265674.

The cask is macOS-only and uses a GitHub Release URL whose domain matches the homepage.
Therefore the generated cask must not include `verified:`. It also needs `depends_on :macos`
so Linux cask jobs do not attempt to install a macOS archive.

## Official Submission Gates

### 1. Prebuilt artifact gate

Status: satisfied for the current tap cask.

The original rejected cask used the npm registry tarball and a `preflight` block that ran
`npm install`. Official casks install prebuilt software artifacts, so that shape was not
acceptable. The current release asset shape matches accepted binary casks such as `codex`,
`claude-code`, `kotlin-native`, and `cursor-cli`.

### 2. Cask policy gate for open-source CLI-only software

Status: not satisfied for immediate official cask resubmission.

Homebrew's Acceptable Casks policy says open-source CLI-only software that only uses the
`binary` artifact should be submitted to `homebrew/core` first as a formula that builds from
source. If that formula is rejected, a later cask PR should link to the core discussion.

UMMAYA is currently open-source and CLI-only. A direct cask resubmission can therefore still be
closed even though the prebuilt artifact issue is fixed.

### 3. Notability and self-submission gate

Status: not satisfied.

`brew audit --cask --new --online` currently fails UMMAYA with:

```text
GitHub repository not notable enough (<30 forks, <30 watchers and <75 stars)
```

The Homebrew policy threshold is higher for self-submitted software:

- non-self-submitted GitHub project: at least one of 30 forks, 30 watchers, or 75 stars
- self-submitted GitHub project: at least one of 90 forks, 90 watchers, or 225 stars

At the time of this audit, `umyunsang/UMMAYA` reported 4 stars, 0 forks, and 0 watchers through
the GitHub API. This cannot be fixed by a release script or cask syntax change.

### 4. Gatekeeper/runtime gate

Status: not satisfied for a conservative official cask submission.

The current archive bundles Bun 1.3.14 so users do not run `npm install` during cask
installation. The bundled Bun binary is Developer ID signed but not accepted by Gatekeeper when
Homebrew quarantine is present:

```text
spctl: rejected
source=Unnotarized Developer ID
```

The tap cask removes `com.apple.quarantine` in `postflight` to make the installed runtime work.
That is acceptable for the project tap only as an operational workaround. For official
homebrew-cask, this is a review risk because accepted CLI casks generally install binaries that
run under Homebrew quarantine without a quarantine-removal workaround.

## Current Recommendation

Do not reopen Homebrew/homebrew-cask#265674 yet.

The minimum safe sequence is:

1. Keep the project tap cask on the prebuilt artifact path.
2. Remove cask syntax/style issues (`verified:` and missing `depends_on :macos`).
3. Decide the official route:
   - `homebrew/core` formula first if UMMAYA can build from source against Homebrew-managed
     dependencies and pass supported macOS/Linux CI; or
   - official cask later only after notability improves or after a rejected core formula
     discussion can be cited.
4. Remove the official cask runtime risk by shipping a runtime that works under Homebrew
   quarantine, or by changing the packaging model so the cask does not need to remove
   quarantine attributes.
5. Re-run `brew audit --cask --new --online` or `brew audit --formula --new --online` in the
   target official repository before opening another official PR.

The current project tap remains the correct public install path:

```bash
brew install --cask umyunsang/ummaya/ummaya
```

The shorter command:

```bash
brew install --cask ummaya
```

should not be documented as available until an official Homebrew PR is actually merged.
