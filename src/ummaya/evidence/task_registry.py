# SPDX-License-Identifier: Apache-2.0
"""Harbor-style task registry for Evidence Fabric v2.

The registry mirrors Harbor's task boundary: a task has an instruction,
metadata/configuration, and a verifier script. UMMAYA keeps execution local and
deterministic; this module only resolves and validates task definitions.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Literal, cast

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BANNED_MODEL_VISIBLE_KEYS = frozenset(
    {
        "adapter_id",
        "tool_id",
        "expected_tool_id",
        "fixture_refs",
        "fixture_ref",
        "current_adapter_id",
    }
)


class TaskRegistryError(ValueError):
    """Raised when an Evidence Fabric task registry is invalid."""


class EvidenceTask(BaseModel):
    """One resolved Harbor-style evidence task."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str
    task_dir: Path
    instruction_path: Path
    verifier_path: Path
    description: str
    dataset_id: str
    keywords: tuple[str, ...] = Field(default_factory=tuple)
    environment_os: Literal["linux", "windows"] = "linux"
    allow_internet: bool = False
    verifier_timeout_sec: float = 120.0


class EvidenceDatasetRef(BaseModel):
    """A dataset reference resolved from the local task registry."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ref: str
    dataset_id: str
    scenario_path: Path
    tasks: tuple[EvidenceTask, ...]


class EvidenceTaskRegistry(BaseModel):
    """Resolved Evidence Fabric task registry."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: int
    registry_id: str
    datasets: tuple[EvidenceDatasetRef, ...]

    def resolve_dataset(self, ref: str) -> EvidenceDatasetRef:
        """Return the dataset entry matching a Harbor-style dataset ref."""

        for dataset in self.datasets:
            if dataset.ref == ref:
                return dataset
        raise TaskRegistryError(f"dataset ref not found in task registry: {ref}")


def _load_yaml_mapping(path: Path) -> Mapping[str, object]:
    if not path.exists():
        raise TaskRegistryError(f"task registry not found: {path}")
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, Mapping):
        raise TaskRegistryError(f"task registry must be a mapping: {path}")
    return cast(Mapping[str, object], loaded)


def _find_banned_keys(value: object, path: str = "$") -> tuple[str, ...]:
    if isinstance(value, Mapping):
        hits: list[str] = []
        for key, nested in value.items():
            key_text = str(key)
            nested_path = f"{path}.{key_text}"
            if key_text in _BANNED_MODEL_VISIBLE_KEYS:
                hits.append(nested_path)
            hits.extend(_find_banned_keys(nested, nested_path))
        return tuple(hits)
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        hits = []
        for index, nested in enumerate(value):
            hits.extend(_find_banned_keys(nested, f"{path}[{index}]"))
        return tuple(hits)
    return ()


def _read_path(path: Path) -> Path:
    return path if path.is_absolute() else _REPO_ROOT / path


def _require_existing_files(paths: tuple[Path, ...]) -> None:
    for required in paths:
        if not _read_path(required).exists():
            raise TaskRegistryError(f"task file missing: {required}")


def _require_mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TaskRegistryError(f"{label} must be a mapping")
    return cast(Mapping[str, object], value)


def _require_non_empty_str(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise TaskRegistryError(f"{label} must be a non-empty string")
    return value


def _require_sequence(value: object, label: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        raise TaskRegistryError(f"{label} must be a list")
    return cast(Sequence[object], value)


def _optional_float(value: object, label: str, default: float) -> float:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, str | int | float):
        raise TaskRegistryError(f"{label} must be a number")
    return float(value)


def _load_task_toml(task_toml: Path) -> Mapping[str, object]:
    raw = tomllib.loads(_read_path(task_toml).read_text(encoding="utf-8"))
    banned = _find_banned_keys(raw)
    if banned:
        raise TaskRegistryError(
            "model-visible task registry contains banned implementation keys: " + ", ".join(banned)
        )
    return cast(Mapping[str, object], raw)


def _build_task(
    *,
    task_dir: Path,
    instruction_path: Path,
    verifier_path: Path,
    raw: Mapping[str, object],
) -> EvidenceTask:
    task_section = _require_mapping(raw.get("task"), "task.toml [task]")
    metadata_section = _require_mapping(raw.get("metadata", {}), "task.toml [metadata]")
    environment_section = _require_mapping(raw.get("environment", {}), "task.toml [environment]")
    verifier_section = _require_mapping(raw.get("verifier", {}), "task.toml [verifier]")
    keywords = _require_sequence(task_section.get("keywords", ()), "task.toml [task].keywords")

    try:
        return EvidenceTask(
            task_id=_require_non_empty_str(task_section.get("name"), "task.toml [task].name"),
            task_dir=task_dir,
            instruction_path=instruction_path,
            verifier_path=verifier_path,
            description=_require_non_empty_str(
                task_section.get("description"),
                "task.toml [task].description",
            ),
            dataset_id=_require_non_empty_str(
                metadata_section.get("dataset_id"),
                "task.toml [metadata].dataset_id",
            ),
            keywords=tuple(str(keyword) for keyword in keywords),
            environment_os=cast(
                Literal["linux", "windows"],
                environment_section.get("os", "linux"),
            ),
            allow_internet=bool(environment_section.get("allow_internet", False)),
            verifier_timeout_sec=_optional_float(
                verifier_section.get("timeout_sec"),
                "task.toml [verifier].timeout_sec",
                120.0,
            ),
        )
    except ValidationError as exc:
        raise TaskRegistryError(str(exc)) from exc


def _load_task(task_dir: Path) -> EvidenceTask:
    task_toml = task_dir / "task.toml"
    instruction_path = task_dir / "instruction.md"
    verifier_path = task_dir / "tests" / "test.sh"
    _require_existing_files((task_toml, instruction_path, verifier_path))
    return _build_task(
        task_dir=task_dir,
        instruction_path=instruction_path,
        verifier_path=verifier_path,
        raw=_load_task_toml(task_toml),
    )


def _load_dataset_ref(index: int, dataset_raw: object) -> EvidenceDatasetRef:
    dataset_map = _require_mapping(dataset_raw, f"datasets[{index}]")
    ref = _require_non_empty_str(dataset_map.get("ref"), f"datasets[{index}].ref")
    dataset_id = _require_non_empty_str(
        dataset_map.get("dataset_id"),
        f"datasets[{index}].dataset_id",
    )
    scenario_path = _require_non_empty_str(
        dataset_map.get("scenario_path"),
        f"datasets[{index}].scenario_path",
    )
    task_paths = _require_sequence(dataset_map.get("task_paths"), f"datasets[{index}].task_paths")

    tasks = tuple(_load_task(Path(str(task_path))) for task_path in task_paths)
    mismatched = tuple(task.task_id for task in tasks if task.dataset_id != dataset_id)
    if mismatched:
        raise TaskRegistryError(
            f"dataset {ref} has tasks with mismatched dataset_id: {', '.join(mismatched)}"
        )
    return EvidenceDatasetRef(
        ref=ref,
        dataset_id=dataset_id,
        scenario_path=Path(scenario_path),
        tasks=tasks,
    )


def load_task_registry(path: Path) -> EvidenceTaskRegistry:
    """Load and validate a Harbor-style Evidence Fabric task registry."""

    raw = _load_yaml_mapping(path)
    banned = _find_banned_keys(raw)
    if banned:
        raise TaskRegistryError(
            "model-visible task registry contains banned implementation keys: " + ", ".join(banned)
        )

    version = raw.get("version")
    if not isinstance(version, int):
        raise TaskRegistryError("task registry version must be an integer")
    registry_id = _require_non_empty_str(raw.get("registry_id"), "task registry_id")
    datasets = _require_sequence(raw.get("datasets"), "task registry datasets")
    resolved_datasets = tuple(
        _load_dataset_ref(index, dataset_raw) for index, dataset_raw in enumerate(datasets)
    )

    try:
        return EvidenceTaskRegistry(
            version=version,
            registry_id=registry_id,
            datasets=resolved_datasets,
        )
    except ValidationError as exc:
        raise TaskRegistryError(str(exc)) from exc
