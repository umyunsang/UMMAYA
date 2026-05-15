# SPDX-License-Identifier: Apache-2.0
"""Verified public-data adapter wave registration."""

from __future__ import annotations

from importlib import import_module
from types import ModuleType
from typing import Protocol, cast

from pydantic import BaseModel

from ummaya.tools.executor import ToolExecutor
from ummaya.tools.models import GovAPITool
from ummaya.tools.registry import ToolRegistry
from ummaya.tools.verified_data_go_kr._manifest import (
    VERIFIED_DATA_GO_KR_ADAPTERS,
    require_spec,
)
from ummaya.tools.verified_data_go_kr._models import VerifiedAdapterSpec


class VerifiedAdapterModule(Protocol):
    """Public shape exposed by each thin adapter module."""

    INPUT_SCHEMA: type[BaseModel]
    TOOL: GovAPITool

    def register(self, registry: ToolRegistry, executor: ToolExecutor) -> None:
        """Register module-owned tool and executor binding."""


def module_for_tool_id(tool_id: str) -> VerifiedAdapterModule:
    """Import the module that owns *tool_id*."""

    spec = require_spec(tool_id)
    module: ModuleType = import_module(f"{__name__}.{spec.module_name}")
    return cast(VerifiedAdapterModule, module)


def register(registry: ToolRegistry, executor: ToolExecutor) -> None:
    """Register all direct-curl verified public-data adapters."""

    for spec in VERIFIED_DATA_GO_KR_ADAPTERS:
        module_for_tool_id(spec.tool_id).register(registry, executor)


__all__ = [
    "VERIFIED_DATA_GO_KR_ADAPTERS",
    "VerifiedAdapterSpec",
    "module_for_tool_id",
    "register",
]
