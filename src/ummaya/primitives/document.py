# SPDX-License-Identifier: Apache-2.0
"""Document primitive placeholder.

The model-facing `document` tool is registered as a concrete GovAPITool by the
document harness. This coroutine exists so primitive registries and IPC guards
can identify `document` as an allowed top-level primitive name.
"""

from __future__ import annotations

from typing import Any


async def document(*_args: object, **_kwargs: object) -> dict[str, Any]:
    """Document primitive marker.

    Runtime execution is owned by `ummaya.tools.documents.registry` because it
    needs session-local artifact stores and format-engine adapters.
    """

    return {
        "kind": "error",
        "reason": "direct_document_primitive_not_bound",
        "message": "The document primitive must be executed through the registered document tool.",
    }


__all__ = ["document"]
