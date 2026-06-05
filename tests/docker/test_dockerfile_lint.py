"""Dockerfile lint tests (T021, Epic #467).

Parse ``docker/Dockerfile`` as plain text and assert structural and security
invariants without invoking the Docker daemon.  All six sub-cases (a–f) from
tasks.md are each expressed as an independent test function.

Expected status: RED — ``docker/Dockerfile`` does not yet exist (created at
T035), so every test in this module will raise ``FileNotFoundError`` until
the file is written.
"""

import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Shared fixture: resolve Dockerfile path once at module level
# ---------------------------------------------------------------------------

_DOCKERFILE_PATH = Path(__file__).resolve().parents[2] / "docker" / "Dockerfile"
_DOCKERIGNORE_PATH = Path(__file__).resolve().parents[2] / ".dockerignore"
_PUBLIC_DOC_CONTRACT_DIR = "specs/2802-public-doc-harness/contracts/"
_PUBLIC_DOC_CONTRACT = "specs/2802-public-doc-harness/contracts/document-tools.schema.json"


def _read_dockerfile() -> str:
    """Return the full text of docker/Dockerfile.

    Raises FileNotFoundError (RED) until T035 creates the file.
    """
    return _DOCKERFILE_PATH.read_text(encoding="utf-8")


def _read_dockerignore() -> str:
    """Return the full text of .dockerignore."""
    return _DOCKERIGNORE_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# (a) Multi-stage build: builder + runtime stages
# ---------------------------------------------------------------------------


def test_dockerfile_has_builder_and_runtime_stages() -> None:
    """Asserts two FROM … AS … stages with the exact names 'builder' and 'runtime'.

    The builder stage installs dependencies under uv; the runtime stage copies
    only the compiled venv, keeping the final image lean.
    """
    text = _read_dockerfile()

    from_as_pattern = re.compile(r"^\s*FROM\s+\S+\s+AS\s+(\w+)", re.IGNORECASE | re.MULTILINE)
    stage_names = [m.group(1).lower() for m in from_as_pattern.finditer(text)]

    assert "builder" in stage_names, (
        f"Dockerfile must contain a 'FROM … AS builder' stage; found stages: {stage_names}"
    )
    assert "runtime" in stage_names, (
        f"Dockerfile must contain a distinct 'FROM … AS runtime' stage; found stages: {stage_names}"
    )
    assert stage_names.index("builder") != stage_names.index("runtime"), (
        "'builder' and 'runtime' must be distinct FROM stages"
    )


# ---------------------------------------------------------------------------
# (b) Dependency installation via uv sync --frozen
# ---------------------------------------------------------------------------


def test_dockerfile_uses_uv_sync_frozen() -> None:
    """Asserts ``uv sync --frozen`` is present (reproducible, lock-file-bound install).

    ``--frozen`` prevents uv from updating uv.lock during the build, guaranteeing
    the image matches the committed lock file exactly.
    """
    text = _read_dockerfile()

    pattern = re.compile(r"\buv\s+sync\s+--frozen\b")
    assert pattern.search(text) is not None, (
        "Dockerfile must invoke 'uv sync --frozen' for reproducible installs"
    )


# ---------------------------------------------------------------------------
# (c) Non-root runtime user
# ---------------------------------------------------------------------------


def test_dockerfile_sets_non_root_user() -> None:
    """Asserts ``USER 1000`` is present, enforcing non-root execution at runtime.

    Running as UID 1000 prevents privilege-escalation attacks and is required
    by the UMMAYA container hardening policy (spec 026-cicd-prompt-registry).
    """
    text = _read_dockerfile()

    pattern = re.compile(r"^\s*USER\s+1000\s*$", re.MULTILINE)
    assert pattern.search(text) is not None, (
        "Dockerfile must set 'USER 1000' to enforce non-root runtime execution"
    )


# ---------------------------------------------------------------------------
# (d) uv environment flags
# ---------------------------------------------------------------------------


def test_dockerfile_sets_uv_env_flags() -> None:
    """Asserts both ``UV_LINK_MODE=copy`` and ``UV_COMPILE_BYTECODE=1`` are set.

    ``UV_LINK_MODE=copy`` avoids hard-link failures across filesystem layers.
    ``UV_COMPILE_BYTECODE=1`` pre-compiles .py → .pyc, reducing cold-start
    latency by skipping on-the-fly compilation at container boot.
    """
    text = _read_dockerfile()

    link_mode_pattern = re.compile(r"\bUV_LINK_MODE\s*=\s*copy\b")
    assert link_mode_pattern.search(text) is not None, "Dockerfile must set ENV UV_LINK_MODE=copy"

    bytecode_pattern = re.compile(r"\bUV_COMPILE_BYTECODE\s*=\s*1\b")
    assert bytecode_pattern.search(text) is not None, (
        "Dockerfile must set ENV UV_COMPILE_BYTECODE=1"
    )


# ---------------------------------------------------------------------------
# (e) Licence header
# ---------------------------------------------------------------------------


def test_dockerfile_header_mentions_psf_license() -> None:
    """Asserts a comment near the top of the file mentions 'PSF' (Python Software Foundation).

    python:3.12-slim is distributed under the PSF License.  Documenting base-image
    licences in the Dockerfile header satisfies SBOM traceability requirements
    (spec 024-tool-security-v1 FR-019).  The check is case-insensitive and scans
    only the first 30 lines to ensure the note appears in the header block.
    """
    text = _read_dockerfile()

    header_lines = text.splitlines()[:30]
    header_block = "\n".join(header_lines)

    psf_pattern = re.compile(r"PSF", re.IGNORECASE)
    assert psf_pattern.search(header_block) is not None, (
        "Dockerfile header (first 30 lines) must mention 'PSF' to document the "
        "python:3.12-slim base-image licence"
    )


# ---------------------------------------------------------------------------
# (f) Pinned uv version — no :latest tag
# ---------------------------------------------------------------------------


def test_dockerfile_pins_uv_version() -> None:
    """Asserts the uv installer image is pinned to a semver tag, not ':latest'.

    Using ``ghcr.io/astral-sh/uv:latest`` would make builds non-reproducible.
    The pinned form must match ``ghcr.io/astral-sh/uv:<MAJOR>.<MINOR>.<PATCH>``.
    """
    text = _read_dockerfile()

    latest_pattern = re.compile(r"ghcr\.io/astral-sh/uv:latest")
    assert latest_pattern.search(text) is None, (
        "Dockerfile must not reference 'ghcr.io/astral-sh/uv:latest'; pin to an explicit semver tag"
    )

    semver_pattern = re.compile(r"ghcr\.io/astral-sh/uv:\d+\.\d+\.\d+")
    assert semver_pattern.search(text) is not None, (
        "Dockerfile must reference a pinned uv image matching "
        "'ghcr.io/astral-sh/uv:<MAJOR>.<MINOR>.<PATCH>'"
    )


def test_docker_context_keeps_public_doc_contract_schema() -> None:
    """Asserts Docker builds can see the canonical document harness schema.

    ``specs/`` is excluded from the Docker build context by default, but
    hatchling must read this force-included contract file while building the
    project wheel. Keep the carve-out narrow so the image context stays small.
    """
    dockerfile_text = _read_dockerfile()
    dockerignore_text = _read_dockerignore()

    assert _PUBLIC_DOC_CONTRACT_DIR in dockerfile_text, (
        "Dockerfile must copy the public document harness contract before uv installs the project"
    )
    assert f"!{_PUBLIC_DOC_CONTRACT}" in dockerignore_text, (
        ".dockerignore must explicitly unignore the public document harness contract schema"
    )
