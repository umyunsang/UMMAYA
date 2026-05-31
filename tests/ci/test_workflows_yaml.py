# tests/ci/test_workflows_yaml.py
#
# CI Workflow YAML validation tests.
#
# YAML 1.1 QUIRK: PyYAML's safe_load interprets the bare `on:` key in GitHub
# Actions workflow files as the Python boolean True (because `on` is a YAML 1.1
# boolean literal).  Access workflow triggers via workflow[True], NOT workflow["on"].
# A helper _get_triggers() handles both True and the string "on" for robustness.
#
# Evidence Fabric v2 supersedes the previous split verification workflows.
# This file now checks that the new evidence gate exists while
# preserving release and core CI workflow checks.

from __future__ import annotations

import pathlib

import pytest
import yaml

# ---------------------------------------------------------------------------
# Repo root resolution — two levels up from tests/ci/
# ---------------------------------------------------------------------------
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_WORKFLOWS_DIR = _REPO_ROOT / ".github" / "workflows"

# ---------------------------------------------------------------------------
# File paths under test
# ---------------------------------------------------------------------------
_EVIDENCE_YML = _WORKFLOWS_DIR / "evidence.yml"
_RELEASE_MANIFEST_YML = _WORKFLOWS_DIR / "release-manifest.yml"
_CI_YML = _WORKFLOWS_DIR / "ci.yml"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_workflow(path: pathlib.Path) -> dict:
    """Load a GitHub Actions workflow YAML.  Raises pytest.fail if file absent."""
    if not path.exists():
        pytest.fail(
            f"Workflow file not found: {path}\n"
            f"This test is expected to be RED until the file is created."
        )
    with path.open() as fh:
        return yaml.safe_load(fh)


def _get_triggers(wf: dict) -> dict:
    """Return the triggers dict, handling the YAML 1.1 True/`on` quirk."""
    # PyYAML safe_load maps bare `on:` → True; some loaders may keep the string.
    return wf.get(True) or wf.get("on") or {}


class TestEvidenceWorkflow:
    def test_evidence_workflow_triggers_on_verification_surfaces(self):
        wf = _load_workflow(_EVIDENCE_YML)
        triggers = _get_triggers(wf)

        pr_trigger = triggers.get("pull_request", {})
        paths = pr_trigger.get("paths", [])

        assert "evidence/**" in paths  # Covers evidence/registry.yaml and evidence/tasks/**.
        assert "src/ummaya/evidence/**" in paths
        assert "tests/evidence/**" in paths
        assert "prompts/**" in paths

    def test_evidence_workflow_runs_evidence_module(self):
        wf = _load_workflow(_EVIDENCE_YML)
        jobs: dict = wf.get("jobs", {})

        assert jobs, "evidence.yml has no jobs defined"
        commands: list[str] = []
        for job in jobs.values():
            if not isinstance(job, dict):
                continue
            for step in job.get("steps", []):
                if isinstance(step, dict) and isinstance(step.get("run"), str):
                    commands.append(step["run"])

        joined = "\n".join(commands)
        assert "uv run python -m ummaya.evidence" in joined
        assert "uv run pytest tests/evidence tests/ci" in joined


# ---------------------------------------------------------------------------
# T023c — FR-F04
# release-manifest.yml triggers only on push.tags v*.*.*
# ---------------------------------------------------------------------------


class TestReleaseManifestWorkflow:
    def test_release_manifest_triggers_on_version_tags(self):
        """T023c (FR-F04): release-manifest must trigger on push.tags v*.*.* and
        must NOT have a pull_request trigger."""
        wf = _load_workflow(_RELEASE_MANIFEST_YML)
        triggers = _get_triggers(wf)

        # Must have push trigger
        push_trigger = triggers.get("push", {})
        assert push_trigger, "release-manifest.yml on.push trigger is missing"

        tags: list = push_trigger.get("tags", [])
        assert "v*.*.*" in tags, (
            f"Expected 'v*.*.*' in release-manifest.yml on.push.tags, got: {tags}"
        )

        # Must NOT have a pull_request trigger (version-tag-only discipline)
        assert "pull_request" not in triggers, (
            "release-manifest.yml must not have a pull_request trigger — "
            "it should fire only on version tag pushes (FR-F04)"
        )


# ---------------------------------------------------------------------------
# T023d — FR-F02
# ci.yml has docker-build job with relevant path filters
#
# TEST-COMMENT: GitHub Actions does not support per-job path filters; they are
# expressed at the workflow trigger level.  This test therefore checks BOTH that
# a docker-build job exists AND that the workflow-level pull_request.paths
# includes docker/**, pyproject.toml, and uv.lock.  This is the simplest correct
# proxy for "the docker-build job only runs when Docker-related files change."
# ---------------------------------------------------------------------------


class TestCIDockerBuildJob:
    def test_ci_has_docker_build_job_with_path_filters(self):
        """T023d (FR-F02): ci.yml must define a docker-build job and the workflow-level
        pull_request trigger must include docker/**, pyproject.toml, uv.lock paths."""
        wf = _load_workflow(_CI_YML)
        jobs: dict = wf.get("jobs", {})

        # Assert docker-build job exists
        assert "docker-build" in jobs, (
            f"ci.yml does not have a 'docker-build' job.  Current jobs: {list(jobs.keys())}"
        )

        # Assert workflow-level path filters cover Docker-related files
        # TEST-COMMENT: Per-job path filtering is not supported in GH Actions;
        # the workflow trigger paths serve as the path gate for all jobs.
        triggers = _get_triggers(wf)
        pr_paths: list = triggers.get("pull_request", {}).get("paths", [])

        required_paths = ["docker/**", "pyproject.toml", "uv.lock"]
        missing = [p for p in required_paths if p not in pr_paths]
        assert not missing, (
            f"ci.yml on.pull_request.paths is missing: {missing}.  Current paths: {pr_paths}"
        )


# ---------------------------------------------------------------------------
# T023e — FR-F01
# ci.yml preserves existing jobs and coverage gate reference
#
# HARD-CODED EXISTING JOB NAMES (verified by reading ci.yml at authoring time):
#   lint, test, dead-code
#
# TEST-COMMENT: The coverage gate is expressed as part of the pytest invocation:
#   uv run pytest -n auto --cov=src/ummaya --cov-report=xml -m "not live"
# There is no --cov-fail-under flag currently; the gate is enforced via the
# upload-artifact step and external tooling.  This test therefore checks for
# the presence of the `--cov=src/ummaya` flag as the coverage gate token,
# which confirms the coverage collection step is preserved in the test job.
# ---------------------------------------------------------------------------


class TestCIPreservesExistingJobs:
    # Job names confirmed by reading .github/workflows/ci.yml before T039
    _EXPECTED_JOB_NAMES = ["lint", "test", "dead-code"]

    # Coverage gate token — present in the `run:` step of the `test` job
    _COVERAGE_TOKEN = "--cov=src/ummaya"  # noqa: S105 — CLI flag, not a credential

    def test_ci_preserves_existing_jobs_and_coverage_gate(self):
        """T023e (FR-F01): ci.yml must retain lint, test, dead-code jobs and the
        coverage collection flag in the test job steps."""
        wf = _load_workflow(_CI_YML)
        jobs: dict = wf.get("jobs", {})

        # Assert all pre-existing job names are still present
        missing_jobs = [name for name in self._EXPECTED_JOB_NAMES if name not in jobs]
        assert not missing_jobs, (
            f"ci.yml is missing previously-existing jobs: {missing_jobs}.  "
            f"Current jobs: {list(jobs.keys())}"
        )

        # Assert coverage gate token is present in at least one run step
        # TEST-COMMENT: Walk all steps of all jobs, collect run strings, and
        # check that --cov=src/ummaya appears in at least one.
        all_run_strings: list[str] = []
        for job in jobs.values():
            if not isinstance(job, dict):
                continue
            for step in job.get("steps", []):
                if isinstance(step, dict) and isinstance(step.get("run"), str):
                    all_run_strings.append(step["run"])

        found_coverage = any(self._COVERAGE_TOKEN in run_str for run_str in all_run_strings)
        assert found_coverage, (
            f"Coverage gate token '{self._COVERAGE_TOKEN}' not found in any "
            f"ci.yml job step run command.  "
            f"Run strings found: {all_run_strings}"
        )
