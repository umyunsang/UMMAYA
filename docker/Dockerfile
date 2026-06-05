# UMMAYA — multi-stage runtime image
#
# Base image licences:
#   python:3.12-slim  — Python Software Foundation (PSF) Licence
#                       (Apache-2.0-compatible; see https://docs.python.org/3/license.html)
#   uv                — MIT Licence (https://github.com/astral-sh/uv/blob/main/LICENSE-MIT)
#
# Runtime security: container executes as non-root uid 1000 (group 1000).
# No secrets, API keys, or credentials are baked into any image layer.

# ---------------------------------------------------------------------------
# Stage 1 — builder
# Installs all Python dependencies into an isolated venv via uv.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

# Copy the pinned uv binary from the official release image.
# Pin to an explicit semver tag — never use :latest.
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv

# uv environment flags:
#   UV_LINK_MODE=copy       — copy files across FS layers (avoids hard-link failures)
#   UV_COMPILE_BYTECODE=1   — pre-compile .py → .pyc (faster cold-start at runtime)
#   UV_PROJECT_ENVIRONMENT  — isolate the venv to a predictable path
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Layer 1: sync dependencies only (pyproject + lockfile), without the project src.
# README.md must be present because pyproject.toml declares `readme = "README.md"`;
# hatchling reads it during metadata build even under --no-install-project.
# This layer is cache-stable as long as pyproject.toml, uv.lock, and README.md are unchanged.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-install-project --no-dev

# Layer 2: install the project itself now that its source is present.
# prompts/ + docs/plugins/security-review.md + tests/fixtures/plugin_validation/
# checklist_manifest.yaml are required here because pyproject.toml
# [tool.hatch.build.targets.wheel.force-include] bundles them into the wheel as
# ummaya/prompts/, ummaya/_canonical/security-review.md, and
# ummaya/_canonical/checklist_manifest.yaml respectively — hatchling resolves
# force-include paths at build time and fails with FileNotFoundError if any are
# absent from the build context. Spec 1636 P5 added the latter two so plugin
# canonical PIPA hashing + 50-item validation work in production wheels.
COPY src/ ./src/
COPY prompts/ ./prompts/
COPY docs/plugins/security-review.md ./docs/plugins/security-review.md
COPY specs/2802-public-doc-harness/contracts/ ./specs/2802-public-doc-harness/contracts/
COPY tests/fixtures/plugin_validation/ ./tests/fixtures/plugin_validation/
RUN uv sync --frozen --no-dev

# ---------------------------------------------------------------------------
# Stage 2 — runtime
# Receives only the resolved venv + application source; no build toolchain.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

# Create a dedicated non-root user (uid/gid 1000).
RUN groupadd -g 1000 app \
    && useradd -u 1000 -g 1000 -d /app -s /sbin/nologin app

WORKDIR /app

# Copy the pre-built virtual environment from the builder stage.
COPY --from=builder /app/.venv /app/.venv

# Copy application source and prompt files.
COPY src/ /app/src/
COPY prompts/ /app/prompts/
COPY specs/2802-public-doc-harness/contracts/ /app/specs/2802-public-doc-harness/contracts/

# Activate the venv and expose the project package on PYTHONPATH.
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONPATH=/app/src

# Run as non-root uid 1000 (enforced at OCI layer, not just shell).
USER 1000

# Minimal entrypoint — application CLI entry is wired by callers.
ENTRYPOINT ["python"]
