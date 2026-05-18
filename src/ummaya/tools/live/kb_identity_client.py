# SPDX-License-Identifier: Apache-2.0
"""KB국민인증서 identity-check HTTP client and redaction helpers."""

from __future__ import annotations

from collections.abc import Mapping

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

JsonObject = dict[str, object]

_IDENTITY_KEY_NAMES = frozenset(
    {
        "ci",
        "di",
        "usernm",
        "birthday",
        "receiverhp",
        "receivername",
        "receiverbirthday",
        "gender",
        "krnfrgndstcd",
        "phone",
        "name",
        "birthdate",
    }
)
_REQUEST_ENDPOINT = "/kbsign/api/sign_request2"
_RESULT_ENDPOINT = "/kbsign/api/sign_result"


class KbIdentityClientError(Exception):
    """Sanitized KB identity client failure."""

    def __init__(
        self,
        message: str,
        *,
        reason: str = "kb_identity_error",
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.retryable = retryable


class KbIdentityConfig(BaseModel):
    """Runtime configuration for KB identity calls."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    base_url: str = Field(min_length=1)
    api_key: str = Field(min_length=1)
    hs_key: str = Field(min_length=1)
    company_cd: str = Field(min_length=1)
    request_type: str = Field(default="NONE", min_length=1)
    timeout_seconds: float = Field(default=30.0, gt=0)

    @field_validator("base_url")
    @classmethod
    def _normalize_base_url(cls, value: str) -> str:
        return value.strip().rstrip("/")

    @field_validator("api_key", "hs_key", "company_cd", "request_type")
    @classmethod
    def _strip_required_strings(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must not be blank")
        return stripped


class KbIdentityReceipt(BaseModel):
    """Sanitized KB transaction receipt metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    req_tx_id: str = Field(min_length=1)
    cert_tx_id: str = Field(min_length=1)
    call_url: str | None = None
    result_code: str = Field(min_length=1)
    client_message: str | None = None
    system_message: str | None = None
    identity_evidence_present: bool = False


class KbIdentityClient:
    """Small HTTP client for KB identity request/result endpoints."""

    def __init__(
        self,
        config: KbIdentityConfig,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config
        self._http_client = http_client

    def build_headers(self) -> dict[str, str]:
        """Build KB headers without logging or exposing secrets."""
        return {
            "Accept": "application/json",
            "Content-Type": "application/json; charset=UTF-8",
            "apiKey": self._config.api_key,
            "hsKey": self._config.hs_key,
        }

    def build_request_body(
        self,
        *,
        req_tx_id: str,
        request_type: str | None = None,
    ) -> JsonObject:
        req_tx_id = _require_non_blank(req_tx_id, "reqTxId")
        request_type = _require_non_blank(request_type or self._config.request_type, "requestType")
        return {
            "dataHeader": {},
            "dataBody": {
                "companyCd": self._config.company_cd,
                "reqTxId": req_tx_id,
                "requestType": request_type,
            },
        }

    def build_result_body(
        self,
        *,
        req_tx_id: str,
        cert_tx_id: str,
        request_type: str | None = None,
    ) -> JsonObject:
        req_tx_id = _require_non_blank(req_tx_id, "reqTxId")
        cert_tx_id = _require_non_blank(cert_tx_id, "certTxId")
        request_type = _require_non_blank(request_type or self._config.request_type, "requestType")
        return {
            "dataHeader": {},
            "dataBody": {
                "companyCd": self._config.company_cd,
                "reqTxId": req_tx_id,
                "certTxId": cert_tx_id,
                "requestType": request_type,
            },
        }

    async def request_identity(
        self,
        *,
        req_tx_id: str,
        request_type: str | None = None,
    ) -> KbIdentityReceipt:
        body = self.build_request_body(req_tx_id=req_tx_id, request_type=request_type)
        payload = await self._post(_REQUEST_ENDPOINT, body)
        return self.parse_request_response(payload, expected_req_tx_id=req_tx_id)

    async def lookup_result(
        self,
        *,
        req_tx_id: str,
        cert_tx_id: str,
        request_type: str | None = None,
    ) -> KbIdentityReceipt:
        body = self.build_result_body(
            req_tx_id=req_tx_id,
            cert_tx_id=cert_tx_id,
            request_type=request_type,
        )
        payload = await self._post(_RESULT_ENDPOINT, body)
        return self.parse_result_response(
            payload,
            expected_req_tx_id=req_tx_id,
            expected_cert_tx_id=cert_tx_id,
        )

    def parse_request_response(
        self,
        payload: Mapping[str, object],
        *,
        expected_req_tx_id: str | None = None,
    ) -> KbIdentityReceipt:
        return self._parse_response(
            payload,
            expected_req_tx_id=expected_req_tx_id,
            expected_cert_tx_id=None,
            require_identity_evidence=False,
        )

    def parse_result_response(
        self,
        payload: Mapping[str, object],
        *,
        expected_req_tx_id: str,
        expected_cert_tx_id: str | None = None,
    ) -> KbIdentityReceipt:
        return self._parse_response(
            payload,
            expected_req_tx_id=expected_req_tx_id,
            expected_cert_tx_id=expected_cert_tx_id,
            require_identity_evidence=True,
        )

    async def _post(self, endpoint: str, body: JsonObject) -> JsonObject:
        url = f"{self._config.base_url}{endpoint}"
        headers = self.build_headers()
        timeout = httpx.Timeout(self._config.timeout_seconds)
        try:
            if self._http_client is not None:
                response = await self._http_client.post(url, json=body, headers=headers)
            else:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(url, json=body, headers=headers)
        except httpx.TimeoutException as exc:
            raise KbIdentityClientError(
                "KB identity upstream timeout.",
                reason="timeout",
                retryable=True,
            ) from exc
        except httpx.RequestError as exc:
            raise KbIdentityClientError(
                "KB identity upstream request failed.",
                reason="request_error",
                retryable=True,
            ) from exc

        if response.status_code < 200 or response.status_code >= 300:
            raise KbIdentityClientError(
                f"KB identity upstream HTTP {response.status_code}.",
                reason="upstream_http_error",
                retryable=response.status_code in {500, 502, 503, 504},
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise KbIdentityClientError(
                "KB identity upstream returned non-JSON payload.",
                reason="invalid_json",
            ) from exc
        if not isinstance(payload, dict):
            raise KbIdentityClientError(
                "KB identity upstream returned non-object payload.",
                reason="invalid_json",
            )
        return {str(key): value for key, value in payload.items()}

    def _parse_response(
        self,
        payload: Mapping[str, object],
        *,
        expected_req_tx_id: str | None,
        expected_cert_tx_id: str | None,
        require_identity_evidence: bool,
    ) -> KbIdentityReceipt:
        data_header = _mapping_at(payload, "dataHeader")
        data_body = _mapping_at(payload, "dataBody")
        sanitized_body = sanitize_identity_payload(data_body)

        result_code = str(data_body.get("result-code") or "")
        header_result = str(data_header.get("resultCode") or "")
        success_code = str(data_header.get("successCode") or "")
        if header_result != "0000" or success_code != "0" or result_code != "ok":
            safe_payload = sanitize_identity_payload(payload)
            raise KbIdentityClientError(
                f"KB identity response failed: {safe_payload!r}",
                reason="failed_status",
                retryable=False,
            )

        req_tx_id = _require_non_blank(str(data_body.get("reqTxId") or ""), "reqTxId")
        cert_tx_id = _require_non_blank(str(data_body.get("certTxId") or ""), "certTxId")
        if expected_req_tx_id is not None and req_tx_id != expected_req_tx_id:
            raise KbIdentityClientError("KB identity reqTxId mismatch.", reason="mismatch")
        if expected_cert_tx_id is not None and cert_tx_id != expected_cert_tx_id:
            raise KbIdentityClientError("KB identity certTxId mismatch.", reason="mismatch")

        identity_evidence_present = _has_identity_evidence(data_body)
        if require_identity_evidence and not identity_evidence_present:
            raise KbIdentityClientError(
                "KB identity result did not contain expected identity evidence.",
                reason="missing_identity_evidence",
            )

        safe_body = sanitized_body if isinstance(sanitized_body, dict) else {}
        return KbIdentityReceipt(
            req_tx_id=req_tx_id,
            cert_tx_id=cert_tx_id,
            call_url=_optional_str(safe_body.get("callUrl")),
            result_code=result_code,
            client_message=_optional_str(safe_body.get("client-message")),
            system_message=_optional_str(safe_body.get("system-message")),
            identity_evidence_present=identity_evidence_present,
        )


def sanitize_identity_payload(value: object) -> object:
    """Recursively drop identity-bearing fields from a JSON-like value."""
    if isinstance(value, dict):
        sanitized: JsonObject = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            if key.lower() in _IDENTITY_KEY_NAMES:
                continue
            sanitized[key] = sanitize_identity_payload(raw_value)
        return sanitized
    if isinstance(value, list):
        return [sanitize_identity_payload(item) for item in value]
    return value


def _mapping_at(payload: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise KbIdentityClientError(
            f"KB identity payload missing object field {key}.",
            reason="invalid_payload",
        )
    return {str(inner_key): inner_value for inner_key, inner_value in value.items()}


def _require_non_blank(value: str, field_name: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise KbIdentityClientError(f"{field_name} is required.", reason="missing_field")
    return stripped


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _has_identity_evidence(data_body: Mapping[str, object]) -> bool:
    for key, value in data_body.items():
        if str(key).lower() in _IDENTITY_KEY_NAMES and value not in (None, ""):
            return True
    return False
