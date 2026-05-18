# SPDX-License-Identifier: Apache-2.0
"""MobileID verification daemon client helpers."""

from __future__ import annotations

import base64
import json
from collections.abc import Mapping
from typing import Final

import httpx
from pydantic import BaseModel

from ummaya.tools.errors import UmmayaToolError

_CONTENT_TYPE: Final = "application/json; charset=utf-8"
_DEFAULT_TIMEOUT_SECONDS: Final = 10.0

_REDACT_KEYS: Final[frozenset[str]] = frozenset(
    {
        "vp",
        "data",
        "ci",
        "di",
        "rrn",
        "residentregistrationnumber",
        "jumin",
        "phone",
        "phonenumber",
        "receiverhp",
        "birth",
        "birthdate",
        "name",
    }
)

_SUCCESS_STATUSES: Final[frozenset[str]] = frozenset(
    {
        "00",
        "0000",
        "200",
        "400",
        "complete",
        "completed",
        "done",
        "success",
        "succeeded",
        "verified",
        "valid",
    }
)

_FAILURE_STATUSES: Final[frozenset[str]] = frozenset(
    {
        "cancel",
        "canceled",
        "cancelled",
        "error",
        "expired",
        "fail",
        "failed",
        "invalid",
        "pending",
        "timeout",
        "wait",
        "waiting",
    }
)


class MobileIdEnvelopeError(UmmayaToolError):
    """The MobileID MIP envelope was malformed."""


class MobileIdUpstreamError(UmmayaToolError):
    """The MobileID daemon returned an upstream transport or HTTP error."""


class MobileIdVerificationError(UmmayaToolError):
    """The MobileID daemon did not produce verified identity evidence."""


def encode_mip_envelope(inner: Mapping[str, object]) -> dict[str, str]:
    """Encode an inner MobileID JSON object into the official MIP envelope."""
    try:
        raw = json.dumps(
            dict(inner),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise MobileIdEnvelopeError("MobileID inner payload must be JSON serializable.") from exc
    return {"data": base64.b64encode(raw).decode("ascii")}


def decode_mip_envelope(payload: object) -> dict[str, object]:
    """Decode an official MobileID MIP envelope into an inner JSON object."""
    if not isinstance(payload, dict):
        raise MobileIdEnvelopeError("MobileID envelope must be a JSON object.")
    encoded = payload.get("data")
    if not isinstance(encoded, str) or not encoded:
        raise MobileIdEnvelopeError("MobileID envelope must contain a non-empty data field.")
    try:
        raw = base64.b64decode(encoded.encode("ascii"), validate=True)
    except (UnicodeEncodeError, ValueError) as exc:
        raise MobileIdEnvelopeError("MobileID envelope data is not valid base64.") from exc
    try:
        inner = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MobileIdEnvelopeError("MobileID envelope data is not valid inner JSON.") from exc
    if not isinstance(inner, dict):
        raise MobileIdEnvelopeError("MobileID envelope inner JSON must be an object.")
    return {str(k): v for k, v in inner.items()}


def redact_mobileid_identity_fields(value: object) -> object:
    """Recursively redact identity-bearing fields from MobileID-shaped values."""
    if isinstance(value, dict):
        redacted: dict[str, object] = {}
        for key, item in value.items():
            key_str = str(key)
            normalized = key_str.replace("_", "").replace("-", "").lower()
            if normalized in _REDACT_KEYS:
                redacted[key_str] = "REDACTED"
            else:
                redacted[key_str] = redact_mobileid_identity_fields(item)
        return redacted
    if isinstance(value, list):
        return [redact_mobileid_identity_fields(item) for item in value]
    return value


def ensure_verified_response(payload: Mapping[str, object], *, source: str) -> None:
    """Fail closed unless the upstream response carries explicit success evidence."""
    result = payload.get("result")
    if result is False:
        raise MobileIdVerificationError(f"MobileID {source} returned result=false.")

    status = _extract_status(payload)
    if status is None:
        if result is True:
            return
        raise MobileIdVerificationError(f"MobileID {source} did not include a success status.")

    status_normalized = status.strip().lower()
    if status_normalized in _FAILURE_STATUSES:
        raise MobileIdVerificationError(f"MobileID {source} returned status={status!r}.")
    if status_normalized not in _SUCCESS_STATUSES:
        raise MobileIdVerificationError(
            f"MobileID {source} returned unsupported status={status!r}."
        )


def _extract_status(payload: Mapping[str, object]) -> str | None:
    for key in (
        "status",
        "trxsts",
        "trxStatus",
        "transactionStatus",
        "statusCode",
        "resultCode",
        "code",
    ):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, int):
            return str(value)
    return None


class MobileIdClient:
    """Small async client for the MobileID verification daemon envelope contract."""

    def __init__(
        self,
        *,
        base_url: str,
        client_id: str,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        clean_base_url = base_url.strip().rstrip("/")
        clean_client_id = client_id.strip()
        if not clean_base_url:
            raise MobileIdUpstreamError("MobileID base URL is required.")
        if not clean_client_id:
            raise MobileIdUpstreamError("MobileID client id is required.")
        if timeout_seconds <= 0:
            raise MobileIdUpstreamError("MobileID timeout_seconds must be positive.")
        self._base_url = clean_base_url
        self._client_id = clean_client_id
        self._timeout_seconds = timeout_seconds
        self._http_client = http_client

    async def post_envelope(self, path: str, inner: Mapping[str, object]) -> dict[str, object]:
        """POST one encoded MIP envelope and decode the response envelope."""
        if not path.startswith("/"):
            path = f"/{path}"
        headers = {
            "Content-Type": _CONTENT_TYPE,
            "X-MobileID-Client-ID": self._client_id,
        }
        envelope = encode_mip_envelope(inner)
        if self._http_client is not None:
            response = await self._http_client.post(path, json=envelope, headers=headers)
        else:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout_seconds,
            ) as client:
                response = await client.post(path, json=envelope, headers=headers)
        if response.status_code < 200 or response.status_code >= 300:
            raise MobileIdUpstreamError(
                f"MobileID upstream returned HTTP {response.status_code} for {path}."
            )
        try:
            outer = response.json()
        except json.JSONDecodeError as exc:
            raise MobileIdEnvelopeError("MobileID upstream response was not JSON.") from exc
        return decode_mip_envelope(outer)

    async def verify_vp(
        self,
        *,
        trxcode: str,
        vp: BaseModel | Mapping[str, object],
    ) -> dict[str, object]:
        """Call `/mip/vp` for an encrypted VP presentation."""
        vp_payload = (
            vp.model_dump(mode="python", by_alias=True, exclude_none=True)
            if isinstance(vp, BaseModel)
            else dict(vp)
        )
        return await self.post_envelope(
            "/mip/vp",
            {
                "type": "mip",
                "version": "1.0.0",
                "cmd": 400,
                "request": "presentation",
                "trxcode": trxcode,
                "vp": vp_payload,
            },
        )

    async def transaction_status(self, trxcode: str) -> dict[str, object]:
        """Call `/mip/trxsts` for transaction status."""
        return await self.post_envelope("/mip/trxsts", {"trxcode": trxcode})
