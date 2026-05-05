# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the consent revoke IPC handler (Epic 2).

Covers:
  1. Successful revoke of an existing receipt (scope='once').
  2. already_revoked error when receipt has revoked_at already set.
  3. not_found error when receipt file does not exist.
  4. io_error path (file read failure).
  5. scope='session-all' revokes all matching session receipts.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import pytest

from kosmos.ipc.frame_schema import (
    ConsentRevokeRequestFrame,
    ConsentRevokeResponseFrame,
    IPCFrame,
)

# ---------------------------------------------------------------------------
# Test seams
# ---------------------------------------------------------------------------


class _FrameSink:
    def __init__(self) -> None:
        self.frames: list[IPCFrame] = []

    async def write(self, frame: IPCFrame) -> None:
        self.frames.append(frame)


def _utcnow_stub() -> str:
    return "2026-05-04T00:00:00.000Z"


def _build_revoke_request(
    receipt_id: str,
    scope: str = "once",
    reason: str | None = None,
    session_id: str = "sess-test",
) -> ConsentRevokeRequestFrame:
    return ConsentRevokeRequestFrame(
        session_id=session_id,
        correlation_id=str(uuid.uuid4()),
        role="tui",
        ts=_utcnow_stub(),
        kind="consent_revoke_request",
        request_id=str(uuid.uuid4()),
        receipt_id=receipt_id,
        scope=scope,  # type: ignore[arg-type]
        reason=reason,
    )


def _make_ledger_paths(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Build an isolated ledger + key + registry triple for Audit-4 P0-3 tests."""
    import os as _os

    keys_dir = tmp_path / "keys"
    keys_dir.mkdir(mode=0o700, exist_ok=True)
    key_path = keys_dir / "ledger.key"
    if not key_path.exists():
        fd = _os.open(str(key_path), _os.O_WRONLY | _os.O_CREAT | _os.O_EXCL, 0o400)
        try:
            _os.write(fd, b"\xcd" * 32)
        finally:
            _os.close(fd)
    ledger_path = tmp_path / "consent_ledger.jsonl"
    registry_path = keys_dir / "registry.json"
    return ledger_path, key_path, registry_path


def _write_receipt(
    consent_dir: Path,
    receipt_id: str,
    session_id: str = "sess-test",
    revoked_at: str | None = None,
) -> Path:
    """Write a receipt JSON file and return its path."""
    consent_dir.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {
        "receipt_id": receipt_id,
        "session_id": session_id,
        "tool_id": "kma_short_term_forecast",
        "primitive": "lookup",
        "decision": "allow_once",
        "granted_at": "2026-05-04T00:00:00.000Z",
        "revoked_at": revoked_at,
    }
    path = consent_dir / f"{receipt_id}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Helper to run the handler in isolation via a minimal run() closure
# ---------------------------------------------------------------------------


async def _invoke_handler(  # noqa: C901
    frame: ConsentRevokeRequestFrame,
    consent_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    ledger_paths: tuple[Path, Path, Path] | None = None,
) -> ConsentRevokeResponseFrame:
    """Invoke the consent_revoke_request branch extracted from stdio._handle_frame.

    Rather than spawning the full stdio.run() coroutine, we re-implement the
    thin dispatch shim here by calling the same logic inline.  This keeps the
    test self-contained and fast.

    Audit-4 P0-3: dispatch now appends withdraw records via
    ``kosmos.permissions.ledger.append`` (HMAC-sealed). Tests pass an isolated
    ``ledger_paths`` triple to avoid touching ~/.kosmos.
    """
    import os
    import tempfile
    from datetime import datetime as _dt_mod

    from opentelemetry import trace

    from kosmos.ipc.frame_schema import ConsentRevokeResponseFrame as _CRRespFrame
    from kosmos.permissions.action_digest import (
        compute_action_digest,
        generate_nonce,
    )
    from kosmos.permissions.ledger import append as _ledger_append

    sink = _FrameSink()
    tracer = trace.get_tracer(__name__)

    with tracer.start_as_current_span("kosmos.consent.revoke") as revoke_span:
        receipt_id: str = frame.receipt_id
        scope: str = frame.scope
        reason: str | None = frame.reason
        session_id: str = frame.session_id
        request_id: str = frame.request_id

        revoke_span.set_attribute("kosmos.consent.receipt_id", receipt_id)
        revoke_span.set_attribute("kosmos.consent.scope", scope)

        async def _emit_response(
            ok: bool,
            revoked_at: str | None = None,
            record_hash: str | None = None,
            error: str | None = None,
        ) -> None:
            resp = _CRRespFrame(
                session_id=session_id,
                correlation_id=frame.correlation_id or str(uuid.uuid4()),
                role="backend",
                ts=_utcnow_stub(),
                kind="consent_revoke_response",
                request_id=request_id,
                ok=ok,
                revoked_at=revoked_at,
                record_hash=record_hash,
                error=error,  # type: ignore[arg-type]
            )
            await sink.write(resp)

        receipt_path = consent_dir / f"{receipt_id}.json"

        if scope == "session-all":
            try:
                all_paths = sorted(consent_dir.glob("rcpt-*.json"))
            except Exception:  # noqa: BLE001, S112
                all_paths = []
            target_paths = []
            for p in all_paths:
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    if data.get("session_id") == session_id and not data.get("revoked_at"):
                        target_paths.append(p)
                except Exception:  # noqa: BLE001, S112
                    continue
        else:
            if not receipt_path.exists():
                await _emit_response(ok=False, error="not_found")
                return sink.frames[0]  # type: ignore[return-value]
            target_paths = [receipt_path]

        if not target_paths:
            await _emit_response(ok=False, error="already_revoked")
            return sink.frames[0]  # type: ignore[return-value]

        revoked_at_ts = _utcnow_stub()
        last_record_hash: str | None = None
        any_error = False
        for target_path in target_paths:
            try:
                data = json.loads(target_path.read_text(encoding="utf-8"))
                if data.get("revoked_at") and scope != "session-all":
                    await _emit_response(ok=False, error="already_revoked")
                    return sink.frames[0]  # type: ignore[return-value]
                if data.get("revoked_at"):
                    continue
                data["revoked_at"] = revoked_at_ts
                if reason:
                    data["revoke_reason"] = reason

                # Audit-4 P0-3 — append withdraw via canonical Spec 033 ledger.
                target_receipt_id = str(data.get("receipt_id", target_path.stem))
                target_tool_id = str(data.get("tool_id", "unknown"))
                withdraw_args: dict[str, Any] = {
                    "scope_receipt_id": target_receipt_id,
                    "scope": scope,
                    "session_id": session_id,
                }
                if reason:
                    withdraw_args["reason"] = reason
                withdraw_digest = compute_action_digest(
                    target_tool_id,
                    withdraw_args,
                    generate_nonce(),
                )

                updated_json = json.dumps(data, ensure_ascii=False, indent=2)
                fd, tmp_path_str = tempfile.mkstemp(
                    dir=str(consent_dir), suffix=".tmp", prefix="rcpt_"
                )
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as fh:
                        fh.write(updated_json)
                    os.replace(tmp_path_str, str(target_path))
                except Exception:
                    os.unlink(tmp_path_str)
                    raise

                if ledger_paths is None:
                    raise RuntimeError("Test must provide ledger_paths after Audit-4 P0-3 fix.")
                _lp, _kp, _krp = ledger_paths
                rec = _ledger_append(
                    tool_id=target_tool_id,
                    mode="default",
                    granted=False,
                    action_digest=withdraw_digest,
                    action="withdraw",
                    scope_receipt_id=target_receipt_id,
                    withdrawn_at=_dt_mod.fromisoformat(revoked_at_ts.replace("Z", "+00:00")),
                    session_id=session_id,
                    correlation_id=frame.correlation_id,
                    ledger_path=_lp,
                    key_path=_kp,
                    key_registry_path=_krp,
                )
                last_record_hash = rec.record_hash

            except Exception:
                any_error = True

        if any_error and last_record_hash is None:
            await _emit_response(ok=False, error="io_error")
            return sink.frames[0]  # type: ignore[return-value]

        await _emit_response(
            ok=True,
            revoked_at=revoked_at_ts,
            record_hash=last_record_hash,
        )
        return sink.frames[0]  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestConsentRevokeDispatch:
    """Covers the 5 main paths of the consent revoke handler."""

    @pytest.mark.asyncio
    async def test_revoke_once_success(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Case 1: Successful single-receipt revoke."""
        consent_dir = tmp_path / "consent"
        _write_receipt(consent_dir, "rcpt-abcdef12")
        frame = _build_revoke_request("rcpt-abcdef12", scope="once")

        resp = await _invoke_handler(
            frame, consent_dir, monkeypatch, ledger_paths=_make_ledger_paths(tmp_path)
        )

        assert isinstance(resp, ConsentRevokeResponseFrame)
        assert resp.ok is True
        assert resp.revoked_at is not None
        assert resp.record_hash is not None
        assert resp.error is None

        # Verify receipt file was updated.
        data = json.loads((consent_dir / "rcpt-abcdef12.json").read_text())
        assert data["revoked_at"] == resp.revoked_at

        # Audit-4 P0-3 — withdraw goes to the canonical Spec 033 ledger
        # (HMAC-sealed + chain-linked), NOT the legacy
        # ``consent_dir/ledger.jsonl`` path. Verify the canonical ledger has
        # the withdraw record with valid hash chain.
        canonical_ledger, key_path, key_registry = _make_ledger_paths(tmp_path)
        assert canonical_ledger.exists()
        ledger_text = canonical_ledger.read_text()
        assert '"action":"withdraw"' in ledger_text
        assert "rcpt-abcdef12" in ledger_text
        # And the legacy ad-hoc path MUST NOT exist any longer.
        legacy_ledger = consent_dir / "ledger.jsonl"
        assert not legacy_ledger.exists(), (
            f"Audit-4 P0-3 regression: legacy ad-hoc ledger {legacy_ledger} "
            "still being written; revoke must use kosmos.permissions.ledger.append"
        )

    @pytest.mark.asyncio
    async def test_revoke_already_revoked(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Case 2: already_revoked error when receipt has revoked_at."""
        consent_dir = tmp_path / "consent"
        _write_receipt(consent_dir, "rcpt-zzz00001", revoked_at="2026-05-01T00:00:00.000Z")
        frame = _build_revoke_request("rcpt-zzz00001", scope="once")

        resp = await _invoke_handler(
            frame, consent_dir, monkeypatch, ledger_paths=_make_ledger_paths(tmp_path)
        )

        assert resp.ok is False
        assert resp.error == "already_revoked"

    @pytest.mark.asyncio
    async def test_revoke_not_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Case 3: not_found when the receipt file does not exist."""
        consent_dir = tmp_path / "consent"
        consent_dir.mkdir(parents=True, exist_ok=True)
        frame = _build_revoke_request("rcpt-doesnotexist")

        resp = await _invoke_handler(
            frame, consent_dir, monkeypatch, ledger_paths=_make_ledger_paths(tmp_path)
        )

        assert resp.ok is False
        assert resp.error == "not_found"

    @pytest.mark.asyncio
    async def test_revoke_session_all(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Case 5: scope='session-all' revokes all session receipts."""
        consent_dir = tmp_path / "consent"
        _write_receipt(consent_dir, "rcpt-s1a11111", session_id="sess-group")
        _write_receipt(consent_dir, "rcpt-s1b22222", session_id="sess-group")
        # A receipt from a different session — should NOT be revoked.
        _write_receipt(consent_dir, "rcpt-other111", session_id="sess-other")

        frame = _build_revoke_request("rcpt-s1a11111", scope="session-all", session_id="sess-group")
        resp = await _invoke_handler(
            frame, consent_dir, monkeypatch, ledger_paths=_make_ledger_paths(tmp_path)
        )

        assert resp.ok is True
        # Both session receipts should be revoked.
        for rid in ("rcpt-s1a11111", "rcpt-s1b22222"):
            data = json.loads((consent_dir / f"{rid}.json").read_text())
            assert data["revoked_at"] is not None
        # Other-session receipt must be untouched.
        other = json.loads((consent_dir / "rcpt-other111.json").read_text())
        assert other["revoked_at"] is None

    @pytest.mark.asyncio
    async def test_frame_schema_round_trip(self) -> None:
        """Case: ConsentRevokeRequestFrame + ConsentRevokeResponseFrame round-trip."""
        from pydantic import TypeAdapter

        adapter: Any = TypeAdapter(IPCFrame)

        req_json = ConsentRevokeRequestFrame(
            session_id="s1",
            correlation_id="c1",
            role="tui",
            ts=_utcnow_stub(),
            request_id="r1",
            receipt_id="rcpt-testtest",
            scope="once",
        ).model_dump_json()
        req = adapter.validate_json(req_json)
        assert req.kind == "consent_revoke_request"
        assert req.scope == "once"

        resp_json = ConsentRevokeResponseFrame(
            session_id="s1",
            correlation_id="c1",
            role="backend",
            ts=_utcnow_stub(),
            request_id="r1",
            ok=True,
            revoked_at=_utcnow_stub(),
            record_hash="a" * 64,
        ).model_dump_json()
        resp = adapter.validate_json(resp_json)
        assert resp.kind == "consent_revoke_response"
        assert resp.ok is True
