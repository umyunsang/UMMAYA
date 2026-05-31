# SPDX-License-Identifier: Apache-2.0
"""Canonical tool tree tests.

The tool-system ownership path is primitive -> agency -> agency service -> adapter.
"""

from __future__ import annotations

import re

from ummaya.tools.canonical_tree import canonical_tool_tree_path
from ummaya.tools.executor import ToolExecutor
from ummaya.tools.register_all import register_all_tools
from ummaya.tools.registry import ToolRegistry


def test_all_registered_tools_have_unique_canonical_tree_paths() -> None:
    """Every registered tool maps to a non-empty primitive/agency/service/adapter path."""

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_all_tools(registry, executor)

    paths: dict[str, str] = {}
    for tool in registry._tools.values():  # noqa: SLF001
        tree_path = canonical_tool_tree_path(tool)
        for part in tree_path.parts:
            assert re.fullmatch(r"[a-z][a-z0-9_]*", part), tree_path.package_path
        assert tree_path.package_path not in paths, (
            f"Duplicate canonical path {tree_path.package_path!r} for "
            f"{paths[tree_path.package_path]!r} and {tool.id!r}"
        )
        paths[tree_path.package_path] = tool.id


def test_representative_tools_follow_primitive_agency_service_adapter_tree() -> None:
    """Representative live, mock, locate, and APIHub tools use the canonical tree."""

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_all_tools(registry, executor)

    expected = {
        "kma_current_observation": (
            "find/kma/vilage_fcst_info_service_2_0/kma_current_observation"
        ),
        "kma_apihub_url_air_metar_decoded": (
            "find/kma/url_air_metar_decoded/kma_apihub_url_air_metar_decoded"
        ),
        "tago_bus_route_search": "find/molit/tago_bus_route/tago_bus_route_search",
        "kakao_address_search": "locate/ummaya/kakao_local/kakao_address_search",
        "mock_kftc_opengiro_bill_send_v1": ("send/kftc/opengiro/mock_kftc_opengiro_bill_send_v1"),
        "mock_verify_mobile_id": "check/mobile_id/verify/mock_verify_mobile_id",
    }

    for tool_id, expected_path in expected.items():
        assert canonical_tool_tree_path(registry.find(tool_id)).package_path == expected_path
