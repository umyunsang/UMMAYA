# SPDX-License-Identifier: Apache-2.0
"""BaroCert identity-check client boundary and sanitized parsers."""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BarocertProvider(StrEnum):
    """Supported BaroCert identity providers for this adapter family."""

    toss = "toss"
    kakao = "kakao"
    naver = "naver"


class BarocertProviderError(ValueError):
    """Fail-closed provider parsing/runtime error with a stable reason code."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(f"{reason}: {message}")
        self.reason = reason
        self.message = message


class BarocertProviderMetadata(BaseModel):
    """Provider-specific SDK method names."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: BarocertProvider
    service_class: str
    request_object_class: str
    request_method: str
    status_method: str
    verify_method: str
    request_method_aliases: tuple[str, ...] = ()
    status_method_aliases: tuple[str, ...] = ()
    verify_method_aliases: tuple[str, ...] = ()


_PROVIDER_METADATA: dict[BarocertProvider, BarocertProviderMetadata] = {
    BarocertProvider.toss: BarocertProviderMetadata(
        provider=BarocertProvider.toss,
        service_class="TosscertService",
        request_object_class="TossUserIdentity",
        request_method="requestUserIdentity",
        status_method="getUserIdentityStatus",
        verify_method="verifyUserIdentity",
        request_method_aliases=("requestIdentity",),
        status_method_aliases=("getIdentityStatus",),
        verify_method_aliases=("verifyIdentity",),
    ),
    BarocertProvider.kakao: BarocertProviderMetadata(
        provider=BarocertProvider.kakao,
        service_class="KakaocertService",
        request_object_class="KakaoIdentity",
        request_method="requestIdentity",
        status_method="getIdentityStatus",
        verify_method="verifyIdentity",
    ),
    BarocertProvider.naver: BarocertProviderMetadata(
        provider=BarocertProvider.naver,
        service_class="NavercertService",
        request_object_class="NaverIdentity",
        request_method="requestIdentity",
        status_method="getIdentityStatus",
        verify_method="verifyIdentity",
    ),
}


def _coerce_provider(provider: BarocertProvider | str) -> BarocertProvider:
    try:
        return provider if isinstance(provider, BarocertProvider) else BarocertProvider(provider)
    except ValueError as exc:
        raise BarocertProviderError(
            "unsupported_provider",
            f"unsupported provider {provider!r}",
        ) from exc


def provider_metadata(provider: BarocertProvider | str) -> BarocertProviderMetadata:
    """Return provider-specific method metadata."""

    return _PROVIDER_METADATA[_coerce_provider(provider)]


_SENSITIVE_KEYS = frozenset(
    {
        "ci",
        "di",
        "signeddata",
        "receiverhp",
        "receiverphone",
        "receivername",
        "receiverbirthday",
        "receiverbirth",
        "receiveryear",
        "receiverday",
        "receivergender",
        "receiverforeign",
        "receiveragegroup",
        "name",
        "birthday",
        "birthdate",
        "phone",
        "hp",
    }
)


def _normalize_key(key: object) -> str:
    return "".join(ch for ch in str(key).lower() if ch.isalnum())


def redact_barocert_payload(payload: Any) -> Any:
    """Return a recursively redacted copy of a BaroCert payload."""

    if isinstance(payload, dict):
        redacted: dict[str, Any] = {}
        for key, value in payload.items():
            if _normalize_key(key) in _SENSITIVE_KEYS:
                redacted[str(key)] = "<redacted>"
            else:
                redacted[str(key)] = redact_barocert_payload(value)
        return redacted
    if isinstance(payload, list):
        return [redact_barocert_payload(item) for item in payload]
    if isinstance(payload, tuple):
        return tuple(redact_barocert_payload(item) for item in payload)
    return payload


class BarocertIdentityRequest(BaseModel):
    """Sanitized request-start model.

    Values for receiver fields and token must already be encrypted placeholders
    when supplied to this model. The model deliberately does not expose helpers
    that accept raw phone, name, birthday, CI, or DI.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: BarocertProvider
    client_code: str = Field(min_length=1)
    receiver_hp_encrypted: str = Field(min_length=1)
    receiver_name_encrypted: str = Field(min_length=1)
    receiver_birthday_encrypted: str = Field(min_length=1)
    token: str = Field(min_length=1)
    expire_in: int = Field(default=300, ge=1, le=1800)
    app_use_yn: bool = False
    device_os_type: Literal["ANDROID", "IOS"] | None = None
    return_url: str | None = None

    @model_validator(mode="after")
    def _validate_app_to_app_fields(self) -> BarocertIdentityRequest:
        if self.app_use_yn and not self.return_url:
            raise ValueError("return_url is required when app_use_yn=True")
        if self.app_use_yn and self.provider is BarocertProvider.toss and not self.device_os_type:
            raise ValueError("device_os_type is required for Toss app-to-app requests")
        return self

    def to_user_identity_payload(self) -> dict[str, object]:
        """Return the provider SDK payload with encrypted-placeholder values only."""

        payload: dict[str, object] = {
            "receiverHP": self.receiver_hp_encrypted,
            "receiverName": self.receiver_name_encrypted,
            "receiverBirthday": self.receiver_birthday_encrypted,
            "token": self.token,
            "expireIn": self.expire_in,
            "appUseYN": self.app_use_yn,
        }
        if self.device_os_type is not None:
            payload["deviceOSType"] = self.device_os_type
        if self.return_url is not None:
            payload["returnURL"] = self.return_url
        return payload


class BarocertIdentityReceipt(BaseModel):
    """Sanitized request receipt metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: BarocertProvider
    receipt_id: str = Field(min_length=1)
    scheme: str | None = None


BarocertStatusState = Literal["pending", "complete", "expired", "failed"]


class BarocertIdentityStatus(BaseModel):
    """Normalized BaroCert identity status metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: BarocertProvider
    receipt_id: str = Field(min_length=1)
    state: BarocertStatusState
    raw_state: int | str
    expire_dt: str | None = None

    @property
    def is_complete(self) -> bool:
        return self.state == "complete"


class BarocertIdentityVerification(BaseModel):
    """Sanitized verification summary."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: BarocertProvider
    receipt_id: str = Field(min_length=1)
    state: Literal["complete"]
    identity_evidence_present: bool
    signed_data_present: bool
    verified_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    sanitized_receipt_metadata: dict[str, object] = Field(default_factory=dict)


def _payload_to_dict(payload: Any) -> dict[str, object]:
    if isinstance(payload, BaseModel):
        return payload.model_dump(by_alias=True)
    if isinstance(payload, dict):
        return {str(k): v for k, v in payload.items()}
    if hasattr(payload, "__dict__"):
        return {str(k): v for k, v in vars(payload).items() if not str(k).startswith("_")}
    raise BarocertProviderError("malformed_payload", "provider payload is not object-like")


def _raise_for_upstream_error(payload: dict[str, object]) -> None:
    code = payload.get("Code", payload.get("code"))
    if code is None:
        return
    try:
        code_value = int(str(code))
    except ValueError:
        code_value = -1
    if code_value != 0:
        message = str(payload.get("message", payload.get("Message", "provider error")))
        raise BarocertProviderError("upstream_error", message)


def _require_matching_provider(
    expected_provider: BarocertProvider,
    payload: dict[str, object],
) -> None:
    raw_provider = payload.get("provider")
    if raw_provider is None:
        return
    try:
        observed = _coerce_provider(str(raw_provider))
    except BarocertProviderError as exc:
        raise BarocertProviderError("provider_mismatch", str(raw_provider)) from exc
    if observed is not expected_provider:
        raise BarocertProviderError(
            "provider_mismatch",
            f"expected {expected_provider.value}, got {observed.value}",
        )


def _extract_receipt_id(payload: dict[str, object]) -> str:
    receipt = payload.get("receiptID", payload.get("receiptId", payload.get("receipt_id")))
    if not isinstance(receipt, str) or not receipt.strip():
        raise BarocertProviderError("missing_receipt_id", "receiptID is required")
    return receipt.strip()


def _require_receipt(receipt_id: str, payload: dict[str, object]) -> None:
    observed = _extract_receipt_id(payload)
    if observed != receipt_id:
        raise BarocertProviderError("receipt_mismatch", f"expected {receipt_id}, got {observed}")


def _state_from_payload(payload: dict[str, object]) -> tuple[int | str, BarocertStatusState]:
    raw_state_obj = payload.get("state")
    if raw_state_obj is None:
        raise BarocertProviderError("missing_state", "state is required")
    if not isinstance(raw_state_obj, int | str):
        raise BarocertProviderError("malformed_state", "state must be integer or string")
    raw_state: int | str = raw_state_obj
    if isinstance(raw_state, str):
        stripped = raw_state.strip().lower()
        state_by_name: dict[str, BarocertStatusState] = {
            "pending": "pending",
            "complete": "complete",
            "completed": "complete",
            "verified": "complete",
            "expired": "expired",
            "failed": "failed",
            "rejected": "failed",
        }
        named = state_by_name.get(stripped)
        if named is not None:
            return raw_state, named
        if stripped.isdigit():
            raw_state = int(stripped)
    if raw_state == 0:
        return raw_state, "pending"
    if raw_state == 1:
        return raw_state, "complete"
    if raw_state == 2:
        return raw_state, "expired"
    return raw_state, "failed"


def parse_identity_receipt(
    provider: BarocertProvider | str,
    payload: Any,
) -> BarocertIdentityReceipt:
    """Parse a request receipt into sanitized metadata."""

    provider_value = _coerce_provider(provider)
    data = _payload_to_dict(payload)
    _raise_for_upstream_error(data)
    _require_matching_provider(provider_value, data)
    scheme_value = data.get("scheme")
    return BarocertIdentityReceipt(
        provider=provider_value,
        receipt_id=_extract_receipt_id(data),
        scheme=scheme_value if isinstance(scheme_value, str) else None,
    )


def parse_identity_status(
    provider: BarocertProvider | str,
    receipt_id: str,
    payload: Any,
) -> BarocertIdentityStatus:
    """Parse a provider status payload into normalized metadata."""

    provider_value = _coerce_provider(provider)
    data = _payload_to_dict(payload)
    _raise_for_upstream_error(data)
    _require_matching_provider(provider_value, data)
    _require_receipt(receipt_id, data)
    raw_state, state = _state_from_payload(data)
    if state == "expired":
        raise BarocertProviderError("expired", "BaroCert receipt has expired")
    if state == "failed":
        raise BarocertProviderError("failed", f"BaroCert receipt state is {raw_state!r}")
    expire_dt_value = data.get("expireDT")
    return BarocertIdentityStatus(
        provider=provider_value,
        receipt_id=receipt_id,
        state=state,
        raw_state=raw_state,
        expire_dt=expire_dt_value if isinstance(expire_dt_value, str) else None,
    )


def parse_identity_verification(
    provider: BarocertProvider | str,
    receipt_id: str,
    payload: Any,
) -> BarocertIdentityVerification:
    """Parse a provider verification payload into a redacted summary."""

    provider_value = _coerce_provider(provider)
    data = _payload_to_dict(payload)
    _raise_for_upstream_error(data)
    _require_matching_provider(provider_value, data)
    _require_receipt(receipt_id, data)
    _, state = _state_from_payload(data)
    if state != "complete":
        raise BarocertProviderError(state, f"BaroCert verification state is {state}")

    signed_data_present = bool(data.get("signedData"))
    evidence_keys = (
        "ci",
        "di",
        "receiverName",
        "receiverYear",
        "receiverDay",
        "receiverGender",
        "receiverForeign",
        "receiverAgeGroup",
    )
    identity_evidence_present = any(bool(data.get(key)) for key in evidence_keys)
    if not identity_evidence_present:
        raise BarocertProviderError(
            "missing_identity_evidence",
            "no identity evidence fields found",
        )
    if not signed_data_present:
        raise BarocertProviderError("missing_signed_data", "signedData is required")

    return BarocertIdentityVerification(
        provider=provider_value,
        receipt_id=receipt_id,
        state="complete",
        identity_evidence_present=True,
        signed_data_present=True,
        sanitized_receipt_metadata={
            "provider": provider_value.value,
            "receiptID": receipt_id,
            "state": "complete",
            "identity_evidence_present": True,
            "signed_data_present": True,
        },
    )


@dataclass(frozen=True)
class BarocertIdentityClient:
    """Thin wrapper around the official BaroCert SDK.

    The SDK is imported only when a live invocation occurs. Tests use the parser
    functions above with fixtures and never instantiate this client.
    """

    provider: BarocertProvider
    link_id: str
    secret_key: str
    client_code: str
    ip_restrict_on_off: bool = True
    use_static_ip: bool = False

    @classmethod
    def from_env(cls, provider: BarocertProvider | str) -> BarocertIdentityClient:
        provider_value = _coerce_provider(provider)
        link_id = os.environ.get("UMMAYA_BAROCERT_LINK_ID", "").strip()
        secret_key = os.environ.get("UMMAYA_BAROCERT_SECRET_KEY", "").strip()
        client_code = os.environ.get("UMMAYA_BAROCERT_CLIENT_CODE", "").strip()
        missing = [
            name
            for name, value in (
                ("UMMAYA_BAROCERT_LINK_ID", link_id),
                ("UMMAYA_BAROCERT_SECRET_KEY", secret_key),
                ("UMMAYA_BAROCERT_CLIENT_CODE", client_code),
            )
            if not value
        ]
        if missing:
            raise BarocertProviderError("missing_credentials", ",".join(missing))
        return cls(
            provider=provider_value,
            link_id=link_id,
            secret_key=secret_key,
            client_code=client_code,
            ip_restrict_on_off=os.environ.get("UMMAYA_BAROCERT_IP_RESTRICT", "true").lower()
            not in {"0", "false", "no"},
            use_static_ip=os.environ.get("UMMAYA_BAROCERT_USE_STATIC_IP", "false").lower()
            in {"1", "true", "yes"},
        )

    def _service(self) -> object:
        metadata = provider_metadata(self.provider)
        try:
            barocert = importlib.import_module("barocert")
        except ImportError as exc:
            raise BarocertProviderError("sdk_unavailable", "install barocert SDK") from exc

        service_cls = getattr(barocert, metadata.service_class, None)
        if service_cls is None:
            raise BarocertProviderError("sdk_unavailable", f"{metadata.service_class} not found")
        service = service_cls(self.link_id, self.secret_key)
        if hasattr(service, "IPRestrictOnOff"):
            service.IPRestrictOnOff = self.ip_restrict_on_off
        if hasattr(service, "UseStaticIP"):
            service.UseStaticIP = self.use_static_ip
        return service

    def _call_service(
        self,
        method_name: str,
        aliases: tuple[str, ...],
        receipt_id: str,
    ) -> dict[str, object]:
        service = self._service()
        method = None
        for candidate in (method_name, *aliases):
            method = getattr(service, candidate, None)
            if method is not None:
                break
        if method is None:
            raise BarocertProviderError("sdk_unavailable", f"{method_name} not found")
        try:
            return _payload_to_dict(method(self.client_code, receipt_id))
        except Exception as exc:  # noqa: BLE001
            code = getattr(exc, "code", getattr(exc, "Code", ""))
            message = getattr(exc, "message", str(exc))
            raise BarocertProviderError("upstream_error", f"{code}:{message}") from exc

    def get_status(self, receipt_id: str) -> BarocertIdentityStatus:
        metadata = provider_metadata(self.provider)
        payload = self._call_service(
            metadata.status_method,
            metadata.status_method_aliases,
            receipt_id,
        )
        return parse_identity_status(self.provider, receipt_id, payload)

    def verify_identity(self, receipt_id: str) -> BarocertIdentityVerification:
        metadata = provider_metadata(self.provider)
        payload = self._call_service(
            metadata.verify_method,
            metadata.verify_method_aliases,
            receipt_id,
        )
        return parse_identity_verification(self.provider, receipt_id, payload)
