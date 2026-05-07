# KOSAX Release Packaging Plan

Date: 2026-05-07

Status: npm and Homebrew package-surface implementation in progress. PyPI and
backend package publication are removed from this release plan.

Research basis: `docs/research/release-packaging-deep-research.md`

## Release Decision

Proceed with npm first, then Homebrew.

The npm package name is `@umyunsang/kosax` and the installed command is `kosax`. The npm
tarball is the canonical v0.1.0 artifact: it carries the Bun TUI wrapper, TUI
source needed for runtime execution, and the Python backend source used by the
stdio bridge. The Python project remains `kosax` for local `uv` execution only;
no `kosax-cli` PyPI release is part of this plan.

Homebrew follows npm by rendering a formula from the immutable npm registry
tarball URL and SHA-256. The formula is pushed to `umyunsang/homebrew-kosax`.

The pasted npm and PyPI tokens are exposed chat material. Treat any matching
Infisical values as compromised and rotate them before any token fallback is
enabled.

## Resolved Package Surfaces

| Surface | Decision |
|---|---|
| npm | Active first surface: root `package.json`, `bin/kosax`, `files` allowlist, OIDC Trusted Publishing, provenance, clean global install smoke. |
| Homebrew | Active follow-up surface: generated formula from npm tarball SHA, pushed to `umyunsang/homebrew-kosax` through Infisical-held tap token. |
| PyPI | Removed/deferred. No backend wheel/sdist publish in v0.1.0. |
| Secrets | npm uses Trusted Publishing. Homebrew tap token comes from Infisical OIDC. Long-lived registry tokens are break-glass only. |
| User keys | Public CLI users enter FriendliAI only through `/login`; provider keys are operator-managed. |

## Phase 0: Secret Broker And Token Hygiene

Owner: user plus release lead.

Tasks:

- Reuse the existing Infisical project and machine-identity pattern documented
  in `docs/configuration.md#infisical-operator-runbook`.
- Configure npm Trusted Publishing for `@umyunsang/kosax` with workflow
  `publish-npm.yml` and environment `npm`.
- Configure GitHub environment reviewer approval for `npm` and `homebrew`.
- Store `KOSAX_HOMEBREW_TAP_TOKEN` under Infisical `/release` in `prod`.
- Revoke and rotate any exposed npm/PyPI token if it matches an Infisical value.

Exit criteria:

- Normal npm publish does not reference `NODE_AUTH_TOKEN`.
- Homebrew tap update fetches its token through Infisical OIDC.
- Token fallback paths remain disabled unless explicitly approved.

## Phase 1: npm Package Surface

Owner: release lead.

Implemented files:

- `package.json`
- `bin/kosax`
- `scripts/check-npm-package.mjs`
- `.github/workflows/package-npm.yml`
- `.github/workflows/publish-npm.yml`

Key decisions:

- `bin/kosax` is a Bun wrapper.
- The wrapper requires Bun `>=1.3.0`.
- The wrapper sets `KOSAX_BACKEND_CMD_JSON` to run:
  `uv --directory <package-root> run kosax --ipc stdio`.
- `tui/src/ipc/bridge.ts` now prefers `KOSAX_BACKEND_CMD_JSON` over the legacy
  space-split `KOSAX_BACKEND_CMD`, preserving install paths with spaces.
- npm `files` is an allowlist; tests, snapshots, `.env`, `.github`,
  `.references`, `.specify`, root `specs`, `node_modules`, and generated
  distributions are blocked by the package gate.

Verification:

```bash
npm run package:check
npm pack --json
npm install --global --prefix /tmp/kosax-npm-prefix-test ./umyunsang-umyunsang-kosax-0.1.0.tgz
/tmp/kosax-npm-prefix-test/bin/kosax --version
```

Current local result:

- packed size: 9,938,016 bytes
- unpacked size: 34,545,264 bytes
- entry count: 2,331
- clean global `kosax --version`: passed

Exit criteria:

- Package dry-run and clean global install smoke pass in CI.
- npm publish is tag-gated and environment-gated.
- npm Trusted Publishing is configured before the first tag push.

## Phase 2: Homebrew Formula Surface

Owner: release lead.

Implemented files:

- `scripts/render-homebrew-formula.mjs`
- `.github/workflows/publish-homebrew.yml`

Formula strategy:

- Source URL: `https://registry.npmjs.org/@umyunsang/kosax/-/kosax-<version>.tgz`
- SHA-256: computed from the npm registry tarball after publish.
- Runtime dependencies: `uv` and Bun.
- Bun dependency: `oven-sh/bun/bun`, because local Homebrew 5.1.9 has no core
  `bun` formula.
- Install layout: tarball contents under `libexec`, symlink
  `libexec/bin/kosax` into `bin/kosax`.
- Test: `kosax --version`, avoiding live API calls and user credentials.

Verification before tap push:

```bash
node scripts/render-homebrew-formula.mjs 0.1.0 <sha256> Formula/kosax.rb
ruby -c Formula/kosax.rb
```

Verification after tap push:

```bash
brew tap oven-sh/bun
brew tap umyunsang/kosax
brew audit --formula umyunsang/kosax/kosax
brew install umyunsang/kosax/kosax
brew test umyunsang/kosax/kosax
```

Exit criteria:

- Tap formula references the npm registry tarball and matching SHA-256.
- Formula install/test pass without live public API calls.

## Phase 3: Documentation

Owner: docs/release lead.

Implemented files:

- `README.md`
- `docs/packaging.md`
- `docs/release-checklist.md`
- `docs/release-notes/package-release-template.md`

Tasks:

- Remove PyPI install instructions from the active release path.
- Document npm install first, Homebrew install second.
- Document FriendliAI `/login` as the only public user key input.
- Document provider credentials as operator-managed and never embedded in
  release artifacts.
- Link official npm Trusted Publishing and Homebrew formula guidance.

Exit criteria:

- A new user can install from npm or Homebrew.
- A maintainer can run a dry release from the checklist.

## Phase 4: Publish And Post-Release Smoke

Owner: release lead.

Tasks:

- Create signed tag.
- Let `publish-npm.yml` build, attest, and publish after environment approval.
- Run `publish-homebrew.yml` manually after npm publish to update the tap.
- Verify npm:

```bash
npm view @umyunsang/kosax version
npm install -g @umyunsang/kosax
kosax --version
```

- Verify Homebrew:

```bash
brew tap oven-sh/bun
brew tap umyunsang/kosax
brew install kosax
kosax --version
brew test umyunsang/kosax/kosax
```

- Check GitHub release assets and attestations.
- Check SBOM and release manifest are attached.
- Open a post-release issue with smoke results and residual gaps.

## Do Not Do

- Do not publish from a local machine.
- Do not use pasted tokens.
- Do not create `requirements.txt`, `setup.py`, or `Pipfile`.
- Do not publish PyPI/backend packages in v0.1.0.
- Do not call live Korean government, identity, payment, certificate, utility,
  or public-data APIs from packaging CI.
