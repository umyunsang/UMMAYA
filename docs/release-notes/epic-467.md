# Epic #467 — CI/CD & Prompt Registry

Spec: `specs/026-cicd-prompt-registry/`. Branch: `feat/467-cicd-prompt-registry`.

## Delivered artefacts

1. **`docker/Dockerfile`** — Multi-stage uv build on `python:3.12-slim`; builder runs `uv sync --frozen` with `UV_LINK_MODE=copy` + `UV_COMPILE_BYTECODE=1`; runtime drops to non-root `USER 1000`; final image target ≤ 2 GB. CI `docker-build` job enforces both gates.
2. **`.devcontainer/devcontainer.json`** — `mcr.microsoft.com/devcontainers/python:3.12` + `ghcr.io/astral-sh/uv:latest` feature; `postCreateCommand: uv sync --frozen --all-extras --dev`; forwards ports 4000 (LiteLLM) and 4318 (OTEL collector); opens with Python + Ruff + Mypy VS Code extensions.
3. **Prompt Registry v1** — `prompts/system_v1.md`, `prompts/session_guidance_v1.md`, `prompts/compact_v1.md` with matching `prompts/manifest.yaml` (SHA-256-integrity entries). `PromptLoader` (`src/ummaya/context/prompt_loader.py`) loads the manifest at boot, fails closed on missing / tampered / orphan files, and caches immutable strings. `SystemPromptAssembler` and `session_compact` now consume the loader — byte-identical output preserved (golden fixtures in `tests/context/fixtures/`).
4. **`ummaya.prompt.hash` OTEL span attribute** — Emitted by the Context Assembly layer on every LLM call under the UMMAYA extension namespace (reserved by Spec 021). Carries the 64-hex SHA-256 of the system prompt bytes actually sent. Consumed by Epic #501 for supply-chain observability.
5. **Prompt-change verification** — originally shipped as a split prompt eval workflow; superseded on 2026-05-26 by Evidence Fabric v2, which runs on `prompts/**` and emits `.evidence/run.json`.
6. **Release-manifest workflow** — `.github/workflows/release-manifest.yml` fires on `push.tags: v*.*.*`. Resolves `commit_sha`, `uv_lock_hash`, `docker_digest`, `prompt_hashes`, `friendli_model_id`, and `litellm_proxy_version`, then commits `docs/release-manifests/<sha>.yaml` back to `main` via a machine-authored commit referencing the tag.

## Cross-Epic contracts

- **Epic #501** — `ummaya.prompt.hash` attribute is now on the wire. No semantic change to existing GenAI spans; new attribute lives in the UMMAYA namespace and does not collide with OpenTelemetry GenAI v1.40 conventions.
- **Epic #468** — The following env keys are proposed for the central env registry (still tentative until #468 merges): `UMMAYA_PROMPT_REGISTRY_LANGFUSE` (bool, default `false`), `UMMAYA_LANGFUSE_HOST`, `UMMAYA_LANGFUSE_PUBLIC_KEY`, `UMMAYA_LANGFUSE_SECRET_KEY`, `GHCR_TOKEN` (via GitHub Actions OIDC).
- **Epic #465** — `release-manifest.yaml` includes the `litellm_proxy_version` field as a placeholder (`"unknown"`) until #465 publishes the LiteLLM Proxy image digest. No blocker; the field is already schema-validated and the value can be filled in downstream.

## Constitutional compliance

- **I. Reference-Driven Design** — Five external + four internal reference mappings in `specs/026-cicd-prompt-registry/research.md`.
- **II. Fail-Closed Security** — `PromptLoader` raises on missing file (R1), hash mismatch (R2), and orphan file (R3); tests in `tests/context/test_prompt_loader_fail_closed.py`.
- **III. Pydantic v2 Strict Typing** — `PromptManifestEntry`, `PromptManifest`, `ReleaseManifest` all `frozen=True` + `extra="forbid"`; no `typing.Any`.
- **IV. Gov API Compliance** — prompt/evidence checks are fixture-only; no live `data.go.kr` traffic from CI.
- **V. Policy Alignment** — Langfuse kept as `[project.optional-dependencies] langfuse` extras; `jsonschema` stays in dev extras; no new core runtime dependency.
- **VI. Deferred-Work Accountability** — Six deferred items in `spec.md § Scope Boundaries` each tracked against a future Epic (see spec table).

## Success Criteria

All seven success criteria (SC-001..SC-007) green — see the Epic #467 PR description for the `uv run pytest -q` evidence line.
