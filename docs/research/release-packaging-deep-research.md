# Release Packaging Deep Research

Date: 2026-05-07

Status: Evidence package for the npm + Homebrew release path. PyPI research was
completed earlier, but PyPI/backend publication is removed from the active
v0.1.0 plan.

Scope:

- TypeScript/Bun TUI plus Python backend source distribution through npm.
- Homebrew tap packaging based on the npm tarball.
- CI/CD, provenance, SBOM, package-size, install-smoke, and LLMOps release
  evidence.

## Executive Findings

1. UMMAYA should not use long-lived npm tokens for normal final release. npm and
   OpenSSF guidance now converge on OIDC-based Trusted Publishing. UMMAYA
   already uses Infisical OIDC federation as a CI secret broker, so Infisical
   should be reused for Homebrew tap credentials and break-glass fallback only.
2. The npm package must be a deliberate CLI package, not an accidental publish
   of `tui/`. A root package with `bin/ummaya`, `files`, package-content gates,
   provenance, and clean global install smoke matches current agentic CLI
   practice better than publishing a private workspace package.
3. UMMAYA currently needs a source-distributed Bun package because bundling the
   TUI still exposes stale dead imports from the reconstructed Claude Code tree.
   The npm package therefore includes the TUI source, backend source,
   `pyproject.toml`, and `uv.lock`, and the wrapper launches the backend with
   `uv --directory <package-root>`.
4. Homebrew should follow the npm artifact through a cask. The tap repository
   exists, but Homebrew has no central reservation mechanism for third-party
   names. The cask should install from a stable npm registry tarball, run the
   package dependency install in `preflight`, create a Caskroom-local wrapper,
   and let Homebrew manage the public link through a `binary` artifact.
5. LLMOps packaging evidence should be release metadata, not another runtime
   framework. UMMAYA already has prompt hashes, eval scenarios, OpenTelemetry,
   optional Langfuse integration, and release manifests. Packaging should bind
   these into release notes and artifact evidence.

## Local Baseline

Name and registry checks as of 2026-05-07:

| Surface | Result |
|---|---|
| npm `ummaya` | `npm view ummaya version` returned 404. |
| Homebrew core formula/cask `ummaya` | API checks returned 404. |
| GitHub tap | `umyunsang/homebrew-ummaya` exists. This secures the tap path, not Homebrew core. |

npm package state after implementation:

- Root `package.json` is named `ummaya`, version `0.1.0`.
- `bin/ummaya` is executable, can be launched by Node or Bun, and selects a
  compatible Bun `>=1.3.0` from `UMMAYA_BUN`, `PATH`, `~/.bun/bin/bun`, or
  common Homebrew locations before loading the Bun TUI entrypoint.
- `files` allowlist includes only the npm wrapper, TUI runtime source, Python
  backend source, prompts, and canonical plugin-validation runtime files.
- `scripts/check-npm-package.mjs` enforces content, size, and entry-count gates.
- Local dry-run result:
  - compressed size: 9,938,016 bytes
  - unpacked size: 34,545,264 bytes
  - entry count: 2,331
- Clean global install smoke passed for `ummaya --version`.

Homebrew state after implementation:

- `scripts/render-homebrew-cask.mjs` renders `Casks/ummaya.rb` from version and
  npm tarball SHA-256.
- `ruby -c Casks/ummaya.rb` passed locally.
- `brew audit --cask ummaya` passed against the tap cask.
- The cask depends on `oven-sh/bun/bun` and `uv`, installs npm package
  dependencies in `preflight`, and writes a Caskroom-local wrapper that
  executes `#{HOMEBREW_PREFIX}/opt/bun/bin/bun` directly so stale user PATH
  entries do not select an older Bun. The package launcher still re-checks Bun
  `>=1.3.0` at runtime and reports all checked candidates when none qualify.
- The npm package includes `bun.lock` for cask/Bun dependency installation and
  `npm-shrinkwrap.json` for npm consumers. Future cask installs can use Bun's
  frozen lockfile path. Older tarballs without `bun.lock` fall back to
  non-frozen install args for compatibility.

Existing CI/release infrastructure:

- `.github/workflows/ci.yml` covers uv sync, Python checks, tests, Docker build,
  and related gates.
- `.github/workflows/ci.yml` already fetches CI secrets from Infisical through
  GitHub OIDC federation (`Infisical/secrets-action` plus
  `vars.INFISICAL_CLIENT_ID`).
- `.github/workflows/release-manifest.yml` emits prompt hashes and a release
  manifest on `v*.*.*` tags.
- `.github/workflows/security.yml` runs CodeQL, TruffleHog, pip-audit, and
  license checks.

## Ecosystem Benchmarks

Agentic npm CLI packages checked on 2026-05-07:

| Package | Version | CLI bin | Unpacked size |
|---|---:|---|---:|
| `@openai/codex` | `0.128.0` | `codex -> bin/codex.js` | 12,855 bytes |
| `@anthropic-ai/claude-code` | `2.1.132` | `claude -> bin/claude.exe` | 131,959 bytes |
| `@google/gemini-cli` | `0.41.2` | `gemini -> bundle/gemini.js` | 112,783,793 bytes |
| `opencode-ai` | `1.14.40` | `opencode -> bin/opencode` | 8,961 bytes |
| local UMMAYA npm tarball | `0.1.0` | `ummaya -> bin/ummaya` | 34,545,264 bytes |

Insight: agentic CLIs split into two patterns. Some packages publish tiny
launcher shims that fetch or execute a platform binary. Others publish a large,
bundled JavaScript CLI. UMMAYA is currently between those patterns: source
distributed for v0.1.0, with a future bundled/native TUI artifact as the likely
next packaging hardening step.

Additional packaging checks on 2026-05-13:

- Claude Code's Homebrew cask downloads a platform-specific executable and
  exposes it through a Homebrew-managed `binary "claude"` artifact. Its shell
  installer downloads the latest installer binary, verifies the SHA-256 checksum
  from a manifest, then delegates setup to `claude install`.
- Codex's Homebrew cask follows the same native-artifact pattern: a GitHub
  release tarball contains the platform executable, and the cask maps that file
  to the public `codex` binary.
- Gemini CLI is the useful npm-tarball counterexample. It is packaged as a
  Homebrew formula, not a cask, and runs `npm install` into Homebrew-managed
  `libexec` before linking the executable.

Implication for UMMAYA: if the project remains cask-only, the cask must avoid
direct writes to `HOMEBREW_PREFIX/bin`; it should create any generated launcher
inside Caskroom and expose it with `binary`. The current npm source tarball path
also needs a lockfile in the published artifact. The production-grade target is
still a platform-specific native/bundled artifact similar to Claude Code and
Codex, with the cask reduced to URL, SHA-256, dependencies, and `binary`.

## Official Guidance Digest

npm:

- npm refuses to publish when `private` is true.
- npm recommends `npm pack --dry-run` to inspect package contents.
- `files` is the correct allowlist mechanism for publish content.
- `bin` is the correct field for globally installed CLI commands.
- npm Trusted Publishing uses OIDC, requires npm CLI 11.5.1+ and Node 22.14.0+,
  and automatically generates provenance for public packages from public repositories.
- `npm trust` package-configuration commands require npm 11.10.0+. Keep release
  workflows on current npm 11.x and GitHub-hosted Node 24 runners to match npm's
  maintained examples.
- Operational rule: when configuring npm Trusted Publishing for a package owner that
  uses WebAuthn/passkey/fingerprint 2FA, run `npm trust` in an interactive TTY.
  Non-TTY execution cannot invoke npm's browser auth opener and falls into `EOTP`
  failures with masked `/auth/cli/...` URLs.

Homebrew:

- A tap maps `brew tap owner/name` to
  `https://github.com/owner/homebrew-name`.
- Homebrew casks should use stable versioned URLs, SHA-256 checksums, a
  `verified` URL parameter when the download and homepage domains differ, and
  Homebrew-managed artifacts such as `binary` instead of direct writes to
  `HOMEBREW_PREFIX/bin`.
- Cask verification should exercise deterministic basic behavior by reinstalling
  the cask and checking `ummaya --version` rather than calling live APIs.

Supply chain:

- GitHub artifact attestations can establish where and how release artifacts
  were built and can also attest SBOMs.
- GitHub's current attestation action for new workflows is `actions/attest`,
  which generates SLSA provenance by default when given `subject-path`.
- SLSA provenance and `slsa-verifier` remain relevant for tamper-evident
  artifacts, but GitHub artifact attestations are the simplest first step for
  npm tarballs and release SBOMs.

LLMOps:

- OpenTelemetry GenAI semantic conventions are still marked Development, so
  UMMAYA should record the exact convention version or opt-in mode it emits.
- Langfuse, MLflow GenAI, W&B Weave, and Arize Phoenix all converge on release
  evidence needs: traces, prompt management, evaluations, datasets,
  experiments, and OpenTelemetry interoperability.
- For UMMAYA, release evidence should include prompt manifest hashes, scenario
  dataset checksums, eval scorecard paths, and trace correlation keys.

## UMMAYA Packaging Direction

Recommended order:

1. npm package first.
2. Homebrew cask second, generated from the npm tarball.
3. PyPI/backend package later only if the product surface requires standalone
   Python distribution.

Recommended install story:

| User need | Preferred install |
|---|---|
| General CLI | `curl -fsSL https://raw.githubusercontent.com/umyunsang/UMMAYA/main/install.sh \| bash` |
| Homebrew manual install | `brew install --cask umyunsang/ummaya/ummaya` |
| npm fallback | `npm install -g ummaya` |
| Source checkout | `uv sync --frozen --all-extras --dev`, then `cd tui && bun install --frozen-lockfile` |

Recommended release gates:

- Token gate: no npm/PyPI token in repo, workflow, logs, or local publish path.
- Secret-broker gate: reuse Infisical OIDC for Homebrew tap token and
  break-glass fallback; do not add GitHub encrypted registry tokens.
- npm gate: `npm pack --dry-run --json`, `bin` smoke, content allowlist,
  package-size budgets, no test/source-only files unless explicitly accepted.
- Homebrew gate: cask syntax, cask audit, reinstall smoke, stable URL, SHA-256,
  and no live government API calls.
- Supply-chain gate: SBOM upload, artifact attestation, release manifest,
  prompt hash emission, and optional SLSA provenance verification.
- LLMOps gate: eval scenario checksum and trace/eval scorecard attached to the
  release notes.

## Source Links

- npm package.json: <https://docs.npmjs.com/cli/v11/configuring-npm/package-json/>
- npm publish and package files: <https://docs.npmjs.com/cli/v11/commands/npm-publish/>
- npm Trusted Publishing: <https://docs.npmjs.com/trusted-publishers/>
- npm provenance: <https://docs.npmjs.com/generating-provenance-statements/>
- Homebrew taps: <https://docs.brew.sh/Taps>
- Homebrew Cask Cookbook: <https://docs.brew.sh/Cask-Cookbook>
- Claude Code setup docs: <https://docs.anthropic.com/en/docs/claude-code/setup>
- Claude Code shell installer: <https://claude.ai/install.sh>
- Homebrew Claude Code cask: <https://formulae.brew.sh/cask/claude-code>
- Homebrew Codex cask: <https://formulae.brew.sh/cask/codex>
- Homebrew Gemini CLI formula: <https://formulae.brew.sh/formula/gemini-cli>
- GitHub artifact attestations: <https://docs.github.com/actions/security-for-github-actions/using-artifact-attestations/using-artifact-attestations-to-establish-provenance-for-builds>
- OpenSSF Trusted Publishers: <https://repos.openssf.org/trusted-publishers-for-all-package-repositories.html>
- OpenTelemetry GenAI semantic conventions: <https://opentelemetry.io/docs/specs/semconv/gen-ai/>
- Langfuse docs: <https://langfuse.com/docs>
- MLflow GenAI docs: <https://mlflow.org/docs/latest/genai/>
- Arize Phoenix docs: <https://arize.com/docs/phoenix>
- W&B Weave docs: <https://docs.wandb.ai/weave>
- Local Infisical runbook: `docs/configuration.md#infisical-operator-runbook`
