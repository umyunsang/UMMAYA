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

UMMAYA v0.1.18 now publishes macOS release archives:

- `ummaya-<version>-macos-arm64.tar.gz`
- `ummaya-<version>-macos-x64.tar.gz`

These archives are built before release. Homebrew Cask installation no longer runs
`npm install` or `bun install`; it downloads one prebuilt archive and links the `ummaya`
wrapper. This addresses the direct maintainer comment on PR #265674.

The cask is macOS-only and installs one prebuilt archive. Official cask submission should use
the UMMAYA docs/download domain rather than the GitHub source repository URL:

- download base: `https://ummaya-docs.pages.dev/downloads/homebrew/v<version>/`
- livecheck JSON: `https://ummaya-docs.pages.dev/downloads/homebrew/latest.json`
- version index: `https://ummaya-docs.pages.dev/downloads/homebrew/versions.json`

This avoids coupling official cask auditability to a GitHub source repository URL while keeping
the downloadable artifact on a user-facing UMMAYA-owned release surface. Cloudflare Pages has
a 25 MiB per-file limit, so Pages hosts only the small manifests, SHA files, and `_redirects`
rules; the large tarballs are GitHub Release assets reached through first-party docs/download
URLs. It also needs
`depends_on :macos` so Linux cask jobs do not attempt to install a macOS archive.

The release and docs workflows both run `scripts/stage-homebrew-downloads.mjs`. Release deploys
add the new manifests, SHA files, and redirect rules; ordinary docs deploys first rehydrate the
existing `versions.json` index and referenced small files from the live site before redeploying.
This keeps already published Homebrew URLs stable across later documentation-only deployments.

## Official Submission Gates

### 1. Prebuilt artifact gate

Status: satisfied for the current tap and official cask candidate.

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

Status: automated audit path addressed by moving the cask download URL off GitHub.

`brew audit --cask --new --online` fails when the cask URL or homepage points at the GitHub
source repository:

```text
GitHub repository not notable enough (<30 forks, <30 watchers and <75 stars)
```

The Homebrew policy threshold is higher for self-submitted software:

- non-self-submitted GitHub project: at least one of 30 forks, 30 watchers, or 75 stars
- self-submitted GitHub project: at least one of 90 forks, 90 watchers, or 225 stars

At the time of the first audit, `umyunsang/UMMAYA` reported 4 stars, 0 forks, and 0 watchers
through the GitHub API. This cannot be fixed by a release script or cask syntax change when the
cask URL remains a GitHub repository URL.

The release pipeline therefore publishes the same prebuilt artifacts to the UMMAYA docs/download
domain and renders official casks against that stable public download surface. This removes the
automated GitHub-repository notability failure from the cask file. Maintainers can still apply
manual notability discretion during review.

### 4. Gatekeeper/runtime gate

Status: addressed in the v0.1.18 release artifact.

The archive bundles Bun 1.3.14 so users do not run `npm install` during cask installation.
Earlier tap-only casks removed `com.apple.quarantine` in `postflight` to make the bundled
runtime work from `Caskroom`, but official casks should not bypass Homebrew's quarantine model.
The v0.1.18 wrapper therefore keeps the cask DSL free of quarantine-stripping hooks and, when
running from Homebrew `Caskroom`, copies the bundled runtime into a SHA-256-addressed user cache
with `cp -X` before execution. The copied runtime SHA is checked before reuse, and the archive
itself is still verified by the cask SHA.

Official cask candidates must not include a `postflight` stanza that strips quarantine.

## Current Recommendation

Do not reopen Homebrew/homebrew-cask#265674 without changing the release surface first.

The minimum safe sequence is:

1. Keep the project tap cask on the prebuilt artifact path.
2. Publish prebuilt cask artifacts to the UMMAYA docs/download domain.
3. Render the cask from the docs/download URL, not the GitHub source repository URL.
4. Remove cask syntax/style issues (`verified:`, missing `depends_on :macos`, and quarantine
   removal hooks).
5. If maintainers request the formula-first route, cite that UMMAYA's cask artifact includes a
   bundled macOS runtime so installation is a prebuilt binary distribution rather than a
   source-build formula. If they still require `homebrew/core`, open the formula discussion and
   link it from the cask PR.
6. Use the v0.1.18+ wrapper so the official cask can run without a quarantine-removal
   `postflight`.
7. Re-run `brew audit --cask --new --online` or `brew audit --formula --new --online` in the
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
