"""Release launcher contract tests.

These tests guard the installed npm/Homebrew entrypoint behavior without
starting the interactive TUI.
"""

from __future__ import annotations

import json
import shlex
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NODE = shutil.which("node")
assert NODE is not None


def _run_node(script: str) -> dict[str, object]:
    result = subprocess.run(  # noqa: S603 - script is a trusted test fixture.
        [NODE, "--input-type=module", "--eval", script],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(result.stdout)


def test_packaged_launcher_overrides_stale_backend_env(tmp_path: Path) -> None:
    package_root = tmp_path / "package root with spaces"
    package_root.mkdir()

    payload = _run_node(
        f"""
        import {{ configurePackageEnv }} from './bin/ummaya'

        const env = {{
          UMMAYA_PACKAGE_ROOT: '/stale/package',
          UMMAYA_BACKEND_CMD_JSON: '["uv","run","ummaya","--ipc","stdio"]',
        }}
        configurePackageEnv({json.dumps(str(package_root))}, env)
        console.log(JSON.stringify(env))
        """,
    )

    assert payload["UMMAYA_PACKAGE_ROOT"] == str(package_root)
    assert json.loads(str(payload["UMMAYA_BACKEND_CMD_JSON"])) == [
        "uv",
        "--directory",
        str(package_root),
        "run",
        "--frozen",
        "--no-dev",
        "ummaya",
        "--ipc",
        "stdio",
    ]
    assert payload["UMMAYA_TUI_PRIMITIVE_TIMEOUT_MS"] == "90000"


def test_packaged_launcher_prefers_existing_python_venv(tmp_path: Path) -> None:
    package_root = tmp_path / "package"
    python_path = package_root / ".venv" / "bin" / "python"
    probe_log = tmp_path / "python-probe.log"
    python_path.parent.mkdir(parents=True)
    python_path.write_text(
        "\n".join(
            [
                "#!/bin/sh",
                f"printf '%s\\n' \"$@\" >> {shlex.quote(str(probe_log))}",
                'if [ "$#" -eq 2 ] && [ "$1" = "-c" ] && [ "$2" = "import ummaya.cli" ]; then',
                "  exit 0",
                "fi",
                "exit 1",
                "",
            ]
        ),
        encoding="utf-8",
    )
    python_path.chmod(0o755)

    payload = _run_node(
        f"""
        import {{ buildBackendCommand, configurePackageEnv }} from './bin/ummaya'

        const env = {{}}
        const root = {json.dumps(str(package_root))}
        configurePackageEnv(root, env)
        console.log(JSON.stringify({{env, command: buildBackendCommand(root)}}))
        """,
    )

    expected = [str(python_path), "-m", "ummaya.cli", "--ipc", "stdio"]
    assert payload["command"] == expected
    assert json.loads(str(payload["env"]["UMMAYA_BACKEND_CMD_JSON"])) == expected
    assert probe_log.read_text(encoding="utf-8").splitlines() == [
        "-c",
        "import ummaya.cli",
        "-c",
        "import ummaya.cli",
    ]


def test_packaged_launcher_ignores_unimportable_python_venv(tmp_path: Path) -> None:
    package_root = tmp_path / "package"
    python_path = package_root / ".venv" / "bin" / "python"
    python_path.parent.mkdir(parents=True)
    python_path.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    python_path.chmod(0o755)

    payload = _run_node(
        f"""
        import {{ buildBackendCommand, configurePackageEnv }} from './bin/ummaya'

        const env = {{}}
        const root = {json.dumps(str(package_root))}
        configurePackageEnv(root, env)
        console.log(JSON.stringify({{env, command: buildBackendCommand(root)}}))
        """,
    )

    expected = [
        "uv",
        "--directory",
        str(package_root),
        "run",
        "--frozen",
        "--no-dev",
        "ummaya",
        "--ipc",
        "stdio",
    ]
    assert payload["command"] == expected
    assert json.loads(str(payload["env"]["UMMAYA_BACKEND_CMD_JSON"])) == expected


def test_packaged_launcher_allows_explicit_backend_debug_override(
    tmp_path: Path,
) -> None:
    package_root = tmp_path / "package"
    package_root.mkdir()

    payload = _run_node(
        f"""
        import {{ configurePackageEnv }} from './bin/ummaya'

        const env = {{
          UMMAYA_ALLOW_BACKEND_CMD_OVERRIDE: '1',
          UMMAYA_BACKEND_CMD_JSON: '["custom","backend"]',
        }}
        configurePackageEnv({json.dumps(str(package_root))}, env)
        console.log(JSON.stringify(env))
        """,
    )

    assert payload["UMMAYA_PACKAGE_ROOT"] == str(package_root)
    assert payload["UMMAYA_BACKEND_CMD_JSON"] == '["custom","backend"]'


def test_homebrew_wrapper_exports_backend_contract() -> None:
    builder = (ROOT / "scripts/build-homebrew-cask-artifact.mjs").read_text(
        encoding="utf-8",
    )

    assert "UMMAYA_PACKAGE_ROOT" in builder
    assert "UMMAYA_BACKEND_CMD_JSON" in builder
    assert "UMMAYA_ALLOW_BACKEND_CMD_OVERRIDE" in builder
    assert "json_escape" in builder
    assert "--frozen" in builder
    assert "--no-dev" in builder
    assert "smokeWrapper" in builder
    assert "createTar" in builder
    assert "portable: true" in builder
    assert "mtime: ARCHIVE_MTIME" in builder
    assert "'tar'" in builder
    assert "--no-recursion" not in builder
    assert "--uname" not in builder
    assert "run('gzip'" not in builder


def test_homebrew_artifact_workflow_renders_cask_from_ci_artifacts() -> None:
    workflow = (ROOT / ".github/workflows/publish-homebrew-cask-artifacts.yml").read_text(
        encoding="utf-8"
    )

    assert "Render release cask from artifacts" in workflow
    assert "dist/homebrew/ummaya.rb" in workflow
    assert 'ruby -c "dist/homebrew/ummaya.rb"' in workflow
    assert "Casks/ummaya.rb does not match generated Homebrew artifacts" not in workflow


def test_homebrew_tap_cask_is_generated_from_public_artifacts() -> None:
    publish_tap = (ROOT / ".github/workflows/publish-homebrew.yml").read_text(encoding="utf-8")
    renderer = (ROOT / "scripts/render-homebrew-cask.mjs").read_text(encoding="utf-8")
    package_check = (ROOT / "scripts/check-npm-package.mjs").read_text(encoding="utf-8")

    assert "dist/homebrew/ummaya.rb" in publish_tap
    assert "cp dist/homebrew/ummaya.rb tap/Casks/ummaya.rb" in publish_tap
    assert "outputPath = 'dist/homebrew/ummaya.rb'" in renderer
    assert "readHomebrewCask" not in package_check
    assert "Casks/ummaya.rb" not in package_check


def test_installer_health_check_exercises_launcher_contract() -> None:
    installer = (ROOT / "install.sh").read_text(encoding="utf-8")

    assert "verify_launcher_health" in installer
    assert "UMMAYA_LAUNCHER_INSPECT=1" in installer
    assert 'UMMAYA_BACKEND_CMD_JSON=\'["stale","backend"]\'' in installer
    assert '"primitiveTimeoutMs":"90000"' in installer


def test_stdio_prompt_loader_uses_cwd_independent_manifest() -> None:
    stdio = (ROOT / "src/ummaya/ipc/stdio.py").read_text(encoding="utf-8")
    ensure_prompt = stdio.split("async def _ensure_system_prompt()", 1)[1].split(
        "async def _handle_user_input_llm",
        1,
    )[0]

    assert "default_manifest_path" in ensure_prompt
    assert 'Path("prompts")' not in ensure_prompt
