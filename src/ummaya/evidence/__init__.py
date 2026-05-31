# SPDX-License-Identifier: Apache-2.0
"""Evidence Fabric v2 public API."""

from ummaya.evidence.models import EvidenceGate, EvidenceStatus, RunEvidence
from ummaya.evidence.runner import EvidenceContractError, run_dataset
from ummaya.evidence.task_registry import (
    EvidenceDatasetRef,
    EvidenceTask,
    EvidenceTaskRegistry,
    TaskRegistryError,
    load_task_registry,
)

__all__ = [
    "EvidenceDatasetRef",
    "EvidenceContractError",
    "EvidenceGate",
    "EvidenceStatus",
    "EvidenceTask",
    "EvidenceTaskRegistry",
    "RunEvidence",
    "TaskRegistryError",
    "load_task_registry",
    "run_dataset",
]
