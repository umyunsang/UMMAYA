# KOSAX Release Checklist

Use this checklist for a tagged KOSAX npm + Homebrew release. Do not publish
from a local machine.

## Before Tagging

- Confirm the release branch is clean except for intended release changes.
- Confirm `package.json`, `tui/package.json`, and the planned tag use the same
  version.
- Confirm `pyproject.toml` remains `name = "kosax"`; PyPI/backend publish is
  outside this release.
- Confirm `README.md`, `docs/packaging.md`, and this checklist match npm and
  Homebrew as the active package surfaces.
- Confirm npm Trusted Publishing is configured for:
  - package: `kosax`
  - owner: `umyunsang`
  - repository: `KOSAX`
  - workflow: `publish-npm.yml`
  - environment: `npm`
- Confirm the GitHub `npm` environment has reviewer approval enabled.
- Confirm Infisical project `kosax`, project slug `kosax-3f-zs`, and machine
  identity `github-actions-kosax` are present for non-registry release secrets.
- Confirm Infisical `/release/KOSAX_HOMEBREW_TAP_TOKEN` can write only to
  `umyunsang/homebrew-kosax`.
- Rotate any npm or PyPI token value that appeared in chat, logs, or local
  shell history before enabling any fallback path.

## Local Dry Run

```bash
npm run package:check
npm pack --json
npm install --global --prefix /tmp/kosax-npm-prefix-test ./umyunsang-umyunsang-kosax-0.1.0.tgz
/tmp/kosax-npm-prefix-test/bin/kosax --version
```

Record the npm tarball SHA-256:

```bash
shasum -a 256 umyunsang-kosax-0.1.0.tgz
```

Render the formula for syntax review:

```bash
node scripts/render-homebrew-formula.mjs 0.1.0 <sha256> Formula/kosax.rb
ruby -c Formula/kosax.rb
```

## Tag And Publish

```bash
git tag -s v0.1.0 -m "v0.1.0"
git push origin v0.1.0
```

Wait for `.github/workflows/publish-npm.yml`:

- `build` passes.
- `attest` passes for the npm tarball.
- `publish` waits for the `npm` environment approval.
- npm upload completes through Trusted Publishing without `NODE_AUTH_TOKEN`.

Run `.github/workflows/publish-homebrew.yml` manually with `version=0.1.0`, then
wait for it:

- npm tarball download succeeds.
- SHA-256 is computed from the registry tarball.
- `Formula/kosax.rb` is committed to `umyunsang/homebrew-kosax`.

## Post-Release Smoke

```bash
npm view @umyunsang/kosax version
npm install -g @umyunsang/kosax
kosax --version
```

```bash
brew tap oven-sh/bun
brew tap umyunsang/kosax
brew install kosax
kosax --version
brew test umyunsang/kosax/kosax
```

Verify the release evidence:

- npm package page shows the expected version and provenance.
- npm tarball hash matches workflow evidence.
- GitHub artifact attestation exists for the npm tarball.
- Homebrew formula SHA-256 matches the npm registry tarball.
- SBOM workflow artifacts exist for the release commit.
- Release manifest exists under `docs/release-manifests/` after the tag
  workflow finishes.
- Release notes link package hashes, SBOM artifacts, attestations, prompt
  manifest hash, eval scenario checksum, and TUI verification artifacts if
  `tui/src/**` changed.
