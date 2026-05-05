# SPDX-License-Identifier: Apache-2.0
"""Audit-5 P0-2 (2026-05-04) — `_SubscribeIterator.peek_handle()` regression test.

Background
----------
Before this fix, `kosmos.ipc.stdio.py:_dispatch_primitive` (subscribe branch)
returned a synthetic `uuid.uuid4()` envelope id while the real
`SubscriptionHandle.subscription_id` (created lazily by `_SubscribeIterator
._start()`) lived in driver-task memory. The TUI `subscriptionRegistry`
indexed by the synthetic id, so:

* OTEL spans (`kosmos.subscribe.subscription_id` attribute) referenced one id.
* SubscriptionBackpressureDrop events referenced the same real id.
* The frontend `/agents` panel and `worker_status` IPC frames referenced a
  *different* synthetic id.

Result: ID correlation broke across the IPC bridge.

Fix
---
`_SubscribeIterator.peek_handle()` materializes the canonical
`SubscriptionHandle` synchronously without starting the driver task. The
dispatcher calls it before emitting the tool_result envelope, so the
`subscription_id` written to the envelope, the `WorkerStatusFrame` worker_id,
and the eventual driver / OTEL emissions all agree.

This test asserts:

1. `peek_handle()` returns a `SubscriptionHandle` synchronously (no `await`).
2. The handle's `subscription_id` matches a UUIDv4 shape.
3. `peek_handle()` is idempotent — repeated calls return the same handle.
4. After `peek_handle()`, the iterator's `_handle` is populated and `_start()`
   reuses the same handle (does not overwrite with a fresh UUID).
5. The handle's `tool_id` and `closes_at` reflect the input.
"""

from __future__ import annotations

import asyncio
import re
import uuid
from typing import Any

import pytest

from kosmos.primitives.subscribe import (
    MODALITY_CBS,
    SubscribeInput,
    SubscriptionHandle,
    _SubscribeIterator,
    register_subscribe_adapter,
    subscribe,
)

_UUID4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


_TEST_TOOL_ID = "audit5_test_peek_v1"


@pytest.fixture(autouse=True)
def _register_test_adapter() -> Any:
    """Provide a no-op CBS adapter for the test tool_id.

    Subscribe registry is module-level state; this fixture registers + tears
    down a unique tool_id per test so the SC-003 canonical-count assertion
    in ``tests/unit/tools/test_registry_count_breakdown.py`` is not polluted
    by a stale ``audit5_test_peek_v1`` entry left over from this module.
    """

    async def _noop(_inp: SubscribeInput, _handle: SubscriptionHandle):
        # Empty async iterator — yields nothing, exits cleanly.
        if False:
            yield None  # pragma: no cover — generator marker

    register_subscribe_adapter(_TEST_TOOL_ID, MODALITY_CBS, _noop)
    try:
        yield
    finally:
        # Roll back the registry mutation so SC-003 sees the canonical 3 ids.
        from kosmos.primitives.subscribe import _SUBSCRIBE_ADAPTERS

        _SUBSCRIBE_ADAPTERS.pop(_TEST_TOOL_ID, None)


def _make_iterator() -> _SubscribeIterator:
    inp = SubscribeInput(
        tool_id="audit5_test_peek_v1",
        params={"region": "ALL"},
        lifetime_seconds=60,
    )
    iterator_or_error = subscribe(inp)
    assert isinstance(iterator_or_error, _SubscribeIterator), (
        "subscribe() must return an _SubscribeIterator for a registered adapter"
    )
    return iterator_or_error


class TestPeekHandle:
    def test_returns_handle_synchronously(self) -> None:
        it = _make_iterator()
        handle = it.peek_handle()
        assert isinstance(handle, SubscriptionHandle)

    def test_subscription_id_is_canonical_uuid4(self) -> None:
        it = _make_iterator()
        handle = it.peek_handle()
        assert _UUID4_RE.match(handle.subscription_id), (
            f"subscription_id {handle.subscription_id!r} is not a UUIDv4"
        )
        # Round-trip via uuid.UUID to assert structural validity.
        parsed = uuid.UUID(handle.subscription_id)
        assert parsed.version == 4

    def test_idempotent_returns_same_handle(self) -> None:
        it = _make_iterator()
        first = it.peek_handle()
        second = it.peek_handle()
        third = it.peek_handle()
        assert first is second is third
        assert first.subscription_id == second.subscription_id

    def test_tool_id_and_lifetime_preserved(self) -> None:
        it = _make_iterator()
        handle = it.peek_handle()
        assert handle.tool_id == "audit5_test_peek_v1"
        # closes_at - opened_at must equal lifetime_seconds (60s in the fixture).
        delta_seconds = (handle.closes_at - handle.opened_at).total_seconds()
        assert abs(delta_seconds - 60.0) < 0.001

    @pytest.mark.asyncio
    async def test_start_reuses_pre_created_handle(self) -> None:
        """`_start()` must not overwrite a handle pre-created by peek_handle()."""
        it = _make_iterator()
        pre_handle = it.peek_handle()
        # Drive __anext__ once; the empty generator immediately raises
        # StopAsyncIteration, but _start() runs as a side effect first.
        with pytest.raises(StopAsyncIteration):
            await it.__anext__()
        # Internal handle must be the SAME object peek returned.
        assert it._handle is pre_handle, (
            "_start() overwrote the pre-created handle — id correlation broken"
        )


class TestSubscribeReturnsRealHandle:
    """Confirm `subscribe()` + `peek_handle()` provide the canonical id the
    IPC dispatcher now consumes.

    Note: `_dispatch_primitive` is a nested closure inside `kosmos.ipc.stdio.run`
    and is not addressable from outside the function. We therefore exercise the
    same call shape the dispatcher uses (subscribe → isinstance(..., _SubscribeIterator)
    → peek_handle) and assert the resulting envelope payload structure.
    """

    def test_subscribe_returns_iterator_with_canonical_handle(self) -> None:
        inp = SubscribeInput(
            tool_id="audit5_test_peek_v1",
            params={"region": "ALL"},
            lifetime_seconds=60,
        )
        iterator_or_error = subscribe(inp)
        assert isinstance(iterator_or_error, _SubscribeIterator)
        handle = iterator_or_error.peek_handle()

        # Build the same payload shape stdio.py emits.
        payload = {
            "kind": "subscribe",
            "subscription_id": handle.subscription_id,
            "handle_id": handle.subscription_id,  # alias
            "tool_id": inp.tool_id,
            "opened_at": handle.opened_at.isoformat(),
            "closes_at": handle.closes_at.isoformat(),
            "lifetime_seconds": int(inp.lifetime_seconds),
            "status": "opened",
        }

        # Real UUIDv4 (not the synthetic one the old code generated).
        assert _UUID4_RE.match(payload["subscription_id"])
        # subscription_id and handle_id agree (TS-side accepts either key).
        assert payload["subscription_id"] == payload["handle_id"]
        # ISO 8601 timestamps round-trip.
        assert payload["opened_at"].endswith("+00:00")
        assert payload["closes_at"].endswith("+00:00")
