# SPDX-License-Identifier: Apache-2.0
"""HTTP gateway for operator-managed live public API adapters."""

from __future__ import annotations

import hmac
import os
import uuid
from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from threading import Lock
from time import monotonic
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from starlette.responses import Response

from ummaya._dotenv import load_repo_dotenv
from ummaya._version import get_version
from ummaya.ipc.adapter_manifest_emitter import build_manifest_frame
from ummaya.tools.executor import ToolExecutor
from ummaya.tools.live_proxy import is_proxyable_live_adapter
from ummaya.tools.models import GovAPITool
from ummaya.tools.register_all import register_all_tools
from ummaya.tools.registry import ToolRegistry


class LiveAdapterGatewayRequest(BaseModel):
    """Wire request accepted from packaged CLI live-adapter proxy clients."""

    schema_version: Literal["ummaya.live_adapter.v1"]
    tool_id: str
    primitive: Literal["find", "locate"] | None = None
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    params: dict[str, Any] = Field(default_factory=dict)
    session_identity: str | None = None


@dataclass(frozen=True, slots=True)
class GatewayState:
    registry: ToolRegistry
    executor: ToolExecutor


_auth_header = APIKeyHeader(name="Authorization", auto_error=False)
_rate_limit_lock = Lock()
_REQUIRED_OPERATOR_ENV_NAMES = (
    "UMMAYA_DATA_GO_KR_API_KEY",
    "UMMAYA_KMA_API_HUB_AUTH_KEY",
    "UMMAYA_KAKAO_API_KEY",
    "UMMAYA_JUSO_CONFM_KEY",
    "UMMAYA_SGIS_KEY",
    "UMMAYA_SGIS_SECRET",
)


def create_app(  # noqa: C901
    *,
    registry: ToolRegistry | None = None,
    executor: ToolExecutor | None = None,
) -> FastAPI:
    """Create the ASGI app.

    Tests may pass an explicit registry/executor pair. Production startup
    builds the full registry once in the lifespan hook.
    """
    if (registry is None) != (executor is None):
        raise ValueError("registry and executor must be provided together")

    provided_state = (
        GatewayState(registry=registry, executor=executor)
        if registry is not None and executor is not None
        else None
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        load_repo_dotenv()
        app.state.gateway = provided_state or _build_gateway_state()
        yield

    app = FastAPI(
        title="UMMAYA Live Adapter Gateway",
        version=get_version(),
        lifespan=lifespan,
    )
    app.state.gateway_rate_limit_windows = {}

    @app.middleware("http")
    async def request_size_guard(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        max_body_bytes = _configured_max_body_bytes()
        raw_length = request.headers.get("content-length", "")
        if raw_length:
            try:
                content_length = int(raw_length)
            except ValueError:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "Invalid Content-Length header."},
                )
            if content_length > max_body_bytes:
                return JSONResponse(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    content={"detail": "Live adapter gateway request body is too large."},
                )
        return await call_next(request)

    @app.get("/healthz")
    @app.get("/readyz")
    async def healthz(request: Request) -> dict[str, object]:
        state_ = _state(request)
        tools = state_.registry.all_tools()
        return {
            "ok": True,
            "tool_count": len(tools),
            "proxyable_live_adapter_count": sum(is_proxyable_live_adapter(tool) for tool in tools),
        }

    @app.get("/v1/manifest")
    async def adapter_manifest(request: Request) -> JSONResponse:
        state_ = _state(request)
        frame = build_manifest_frame(state_.registry)
        return JSONResponse(content=jsonable_encoder(frame))

    @app.post("/v1/adapters/{tool_id}")
    async def invoke_adapter(
        request: Request,
        tool_id: str,
        body: LiveAdapterGatewayRequest,
        _: None = Depends(_require_gateway_token),
        __: None = Depends(_enforce_gateway_rate_limit),
    ) -> dict[str, object]:
        if body.tool_id != tool_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Path tool_id and body tool_id must match.",
            )

        state_ = _state(request)
        tool = _gateway_tool(state_.registry, tool_id)
        if body.primitive is not None and body.primitive != tool.primitive:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Request primitive does not match the registered adapter primitive.",
            )

        if tool.primitive == "locate":
            result = await state_.executor.invoke_raw(
                tool_id,
                body.params,
                body.request_id,
                session_identity=body.session_identity,
            )
        elif tool.primitive == "find":
            result = await state_.executor.invoke(
                tool_id,
                body.params,
                body.request_id,
                session_identity=body.session_identity,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only find and locate live adapters are gateway-callable.",
            )

        return {"ok": True, "result": jsonable_encoder(result)}

    return app


def _build_gateway_state() -> GatewayState:
    _verify_gateway_operator_keys()
    registry = ToolRegistry()
    executor = ToolExecutor(registry=registry, live_adapter_mode="direct")
    register_all_tools(registry, executor)
    return GatewayState(registry=registry, executor=executor)


def _verify_gateway_operator_keys() -> None:
    missing = _missing_gateway_operator_keys()
    if missing:
        raise RuntimeError(
            "ummaya-live-gateway requires all operator provider keys; missing: "
            + ", ".join(missing)
        )


def _missing_gateway_operator_keys() -> tuple[str, ...]:
    return tuple(
        name for name in _REQUIRED_OPERATOR_ENV_NAMES if not os.environ.get(name, "").strip()
    )


def _state(request: Request) -> GatewayState:
    state_ = getattr(request.app.state, "gateway", None)
    if not isinstance(state_, GatewayState):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gateway is not initialized.",
        )
    return state_


def _gateway_tool(registry: ToolRegistry, tool_id: str) -> GovAPITool:
    try:
        tool = registry.find(tool_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No live adapter registered with id {tool_id!r}.",
        ) from exc

    if not is_proxyable_live_adapter(tool):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Adapter is not eligible for the live adapter gateway.",
        )
    return tool


async def _require_gateway_token(authorization: str | None = Depends(_auth_header)) -> None:
    token = _configured_gateway_token()
    if not token:
        return
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing live adapter gateway bearer token.",
        )
    presented = authorization.removeprefix("Bearer ").strip()
    if not hmac.compare_digest(presented, token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid live adapter gateway bearer token.",
        )


def _configured_gateway_token() -> str:
    return os.environ.get("UMMAYA_LIVE_ADAPTER_GATEWAY_TOKEN", "").strip()


async def _enforce_gateway_rate_limit(request: Request) -> None:
    limit = _configured_rate_limit_per_minute()
    tool_id = request.path_params.get("tool_id", "")
    key = (_client_identifier(request), str(tool_id))
    now = monotonic()
    cutoff = now - 60.0

    with _rate_limit_lock:
        windows = _rate_limit_windows_for(request)
        window = windows.setdefault(key, deque())
        while window and window[0] < cutoff:
            window.popleft()
        if len(window) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Live adapter gateway rate limit exceeded.",
            )
        window.append(now)


def _client_identifier(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for.strip():
        return forwarded_for.split(",", 1)[0].strip()
    if request.client is None:
        return "unknown"
    return request.client.host


def _rate_limit_windows_for(request: Request) -> dict[tuple[str, str], deque[float]]:
    windows = getattr(request.app.state, "gateway_rate_limit_windows", None)
    if not isinstance(windows, dict):
        windows = {}
        request.app.state.gateway_rate_limit_windows = windows
    return windows


def _configured_rate_limit_per_minute() -> int:
    raw = os.environ.get("UMMAYA_LIVE_ADAPTER_GATEWAY_RATE_LIMIT_PER_MINUTE", "120")
    try:
        parsed = int(raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="UMMAYA_LIVE_ADAPTER_GATEWAY_RATE_LIMIT_PER_MINUTE must be an integer.",
        ) from exc
    return max(1, parsed)


def _configured_max_body_bytes() -> int:
    raw = os.environ.get("UMMAYA_LIVE_ADAPTER_GATEWAY_MAX_BODY_BYTES", "65536")
    try:
        parsed = int(raw)
    except ValueError:
        return 65_536
    return max(1024, parsed)


def main() -> None:
    """Run the gateway with Uvicorn."""
    import uvicorn  # noqa: PLC0415

    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run("ummaya.gateway.app:app", host="0.0.0.0", port=port)  # noqa: S104


app = create_app()
