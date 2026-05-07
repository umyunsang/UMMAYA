# KOSAX Package Release Notes Template

Version: `vX.Y.Z`
Date: `YYYY-MM-DD`
Commit: `<sha>`

## Package Artifacts

| Artifact | SHA-256 | Link |
|----------|---------|------|
| npm tarball | `<sha256>` | `https://registry.npmjs.org/@umyunsang/kosax/-/kosax-X.Y.Z.tgz` |
| Homebrew formula | `<formula-commit-sha>` | `https://github.com/umyunsang/homebrew-kosax/blob/main/Formula/kosax.rb` |

## Release Evidence

- npm Trusted Publishing workflow: `<run-url>`
- Homebrew tap workflow: `<run-url>`
- GitHub artifact attestation: `<attestation-url>`
- SBOM artifacts: `<workflow-artifact-url>`
- Release manifest: `docs/release-manifests/<commit-sha>.yaml`
- Prompt manifest hash: `<sha256>`
- Eval scenario checksum: `<sha256>`
- TUI verification artifacts: `<paths-or-TUI-no-change>`

## Smoke Results

```text
npm install -g @umyunsang/kosax
kosax --version
brew tap oven-sh/bun
brew tap umyunsang/kosax
brew install kosax
kosax --version
```

## Notes

- PyPI/backend package publishing is not included in this release.
