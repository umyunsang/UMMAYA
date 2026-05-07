# KOSAX Packaging

KOSAX releases are built by CI from tagged commits. Local machines may run dry
builds and install-smoke checks, but must not upload distributions to package
registries.

## Package Surfaces

| Surface | Status | Install target |
|---------|--------|----------------|
| npm | First release surface | `@umyunsang/kosax` package with `kosax` bin wrapper |
| Homebrew | First release follow-up | `umyunsang/homebrew-kosax` formula generated from the npm tarball |
| PyPI | Removed from this release | No backend/PyPI publish in the current plan |

The npm package is the canonical artifact for v0.1.0. It includes the Bun TUI
wrapper plus the Python backend source, `pyproject.toml`, `uv.lock`, prompts,
and canonical plugin-validation files needed by the local stdio bridge. The
wrapper sets `KOSAX_BACKEND_CMD_JSON` so paths with spaces survive the TUI to
backend handoff.

Homebrew follows npm. The formula points at the immutable npm tarball URL and
uses the tarball SHA-256 generated after `npm publish`.

## User Credentials

Public CLI users provide only a FriendliAI API key through `/login`.
Operational provider keys for data.go.kr, Kakao, Juso, SGIS, and similar
services are operator-managed credentials. They may exist in server-side or
self-hosted live-adapter environments, but must never be embedded in npm
packages, Homebrew formulae, frontend assets, or documentation examples.

## Local Dry Run

Run these commands before opening a release PR:

```bash
npm run package:check
npm pack --json
npm install --global --prefix /tmp/kosax-npm-prefix-test ./umyunsang-umyunsang-kosax-0.1.0.tgz
/tmp/kosax-npm-prefix-test/bin/kosax --version
```

The package-content gate enforces these defaults:

- packed size <= 15 MB
- unpacked size <= 70 MB
- entry count <= 2700
- required TUI/backend runtime files are present
- no `.env`, `secrets`, `.github`, `.specify`, `.references`, root `specs`,
  `node_modules`, test snapshots, or generated distribution paths

The smoke commands must not call live Korean government, identity, payment,
certificate, utility, or public-data APIs.

## CI Workflows

`.github/workflows/package-npm.yml` is the PR/manual dry-run workflow. It runs
the package-content gate, builds the npm tarball, installs it into a clean
temporary global prefix, and runs `kosax --version`.

`.github/workflows/publish-npm.yml` is tag-gated:

1. `build` creates and verifies the npm tarball.
2. `attest` emits GitHub artifact attestations for the tarball.
3. `publish` runs only on version tag pushes and requires the `npm` GitHub
   environment before uploading to npm.

The publish job uses npm Trusted Publishing through GitHub Actions OIDC. It
intentionally omits `NODE_AUTH_TOKEN`.

`.github/workflows/publish-homebrew.yml` runs manually after successful npm
publish with a version input. It downloads the npm tarball, computes SHA-256,
renders `Formula/kosax.rb`, and pushes it to `umyunsang/homebrew-kosax` using a
Homebrew tap token fetched from Infisical OIDC under `/release`.

## Trusted Publishing Setup

Configure npm Trusted Publishing for:

| Field | Value |
|-------|-------|
| npm package | `@umyunsang/kosax` |
| Owner | `umyunsang` |
| Repository | `KOSAX` |
| Workflow | `publish-npm.yml` |
| Environment | `npm` |

The `npm` GitHub environment should require reviewer approval. npm Trusted
Publishing requires GitHub-hosted runners, `id-token: write`, npm CLI 11.5.1+
and Node 22.14.0+.

Configure Infisical for Homebrew:

| Field | Value |
|-------|-------|
| Project slug | `kosax-3f-zs` |
| Environment | `prod` |
| Secret path | `/release` |
| Secret name | `KOSAX_HOMEBREW_TAP_TOKEN` |

That token must have write access only to `umyunsang/homebrew-kosax`.

## Secret Policy

Normal npm publishing must use registry-native Trusted Publishing/OIDC.
Long-lived registry tokens are break-glass fallbacks only.

Infisical remains the release secret broker for non-registry secrets, including
the Homebrew tap token. Do not duplicate Infisical values into GitHub encrypted
secrets.

Any npm or PyPI token that appeared in chat, logs, shell history, or test
artifacts must be treated as exposed and rotated before fallback use.

## Homebrew Gates

The formula is rendered by:

```bash
node scripts/render-homebrew-formula.mjs 0.1.0 <npm-tarball-sha256> Formula/kosax.rb
ruby -c Formula/kosax.rb
```

After the tap update:

```bash
brew tap oven-sh/bun
brew tap umyunsang/kosax
brew audit --formula umyunsang/kosax/kosax
brew install umyunsang/kosax/kosax
brew test umyunsang/kosax/kosax
```

KOSAX currently depends on the `oven-sh/bun` tap because Bun is not available
as a Homebrew core formula on this local Homebrew 5.1.9 installation.

## Rollback And Unpublish Policy

If a release artifact is defective but not dangerous, publish a patch release
and document the defect in the release notes.

Do not delete release tags or rewrite published release history. If a token or
release credential is exposed, revoke it first, then publish a postmortem note
with the affected versions and replacement release.

## References

- npm Trusted Publishing: <https://docs.npmjs.com/trusted-publishers/>
- npm publish and package files: <https://docs.npmjs.com/cli/v11/commands/npm-publish/>
- npm package.json `bin` and `files`: <https://docs.npmjs.com/cli/v11/configuring-npm/package-json/>
- Homebrew Formula Cookbook: <https://docs.brew.sh/Formula-Cookbook>
- Homebrew Node formula guidance: <https://docs.brew.sh/Node-for-Formula-Authors>
- GitHub artifact attestations: <https://github.com/actions/attest>
