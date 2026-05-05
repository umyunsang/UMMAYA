# SPDX-License-Identifier: Apache-2.0
"""Spec 031 US3 — ``subscribe`` primitive: CBS / REST-pull / RSS 2.0 unified iterator.

Architecture:
- ``subscribe(inp)`` returns an ``AsyncIterator[SubscriptionEvent]``.
- A shared ``asyncio.Queue(maxsize=64)`` provides back-pressure between the
  3 internal drivers and the consumer (FR-015).
- Lifetime enforcement via ``asyncio.wait_for`` / ``asyncio.timeout`` (FR-014).
- No webhook field anywhere (FR-013); harness is client-side only.
- RSS guid de-duplication is stateful per subscription via ``RssGuidTracker``.

Reference: specs/031-five-primitive-harness/data-model.md § 3.
Reference: specs/031-five-primitive-harness/research.md § 4.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

from opentelemetry import trace
from pydantic import BaseModel, ConfigDict, Field

from kosmos.primitives._errors import AdapterNotFoundError, SubscriptionBackpressureDrop

logger = logging.getLogger(__name__)

_tracer = trace.get_tracer("kosmos.primitives.subscribe")

# ---------------------------------------------------------------------------
# T051 — Data models
# ---------------------------------------------------------------------------

# Sentinel placed on the queue by a driver to signal it has finished.
_DRIVER_DONE = object()

# Minimum polling interval enforced by the harness (FR REST-pull, research §4)
_MIN_POLLING_INTERVAL_SECONDS: float = 10.0

# Queue buffer capacity (FR-015)
_QUEUE_MAXSIZE: int = 64

# Modality flag names — adapter declares one of these in its params
MODALITY_CBS = "cbs_broadcast"
MODALITY_REST_PULL = "rest_pull"
MODALITY_RSS = "rss"


class SubscribeInput(BaseModel):
    """Main-surface input for the ``subscribe`` primitive.

    FR-011: ``lifetime_seconds`` ceiling = 31_536_000 (365 days).
    FR-013: No inbound-receiver URL field (no webhook_url / callback_url).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    tool_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[a-z][a-z0-9_]*$",
        description="Registered mock adapter tool_id.",
    )
    params: dict[str, object] = Field(
        default_factory=dict,
        description=(
            "Adapter-specific subscription parameters (e.g. region filter for CBS, "
            "polling_interval for REST pull, rss_feed_url for RSS 2.0). "
            "All URL fields in params are outbound-only (data source URLs)."
        ),
    )
    lifetime_seconds: int = Field(
        ge=1,
        le=31_536_000,  # FR-011: 365-day ceiling
        description=(
            "Bounded lifetime required (FR-011). Ceiling = 365 days. "
            "Harness releases resources on expiry (FR-014)."
        ),
    )


class CbsBroadcastEvent(BaseModel):
    """Event from a 3GPP TS 23.041 CBS (Cell Broadcast Service) message.

    cbs_message_id range 4370–4385 covers the ATIS-0700007 CMAS categories
    adopted by the Korean CBS profile.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["cbs_broadcast"] = "cbs_broadcast"
    cbs_message_id: Literal[
        4370,
        4371,
        4372,
        4373,
        4374,
        4375,
        4376,
        4377,
        4378,
        4379,
        4380,
        4381,
        4382,
        4383,
        4384,
        4385,
    ]
    received_at: datetime
    payload_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    language: Literal["ko", "en"]
    body: str


class RestPullTickEvent(BaseModel):
    """Event emitted on each successful REST-pull polling tick."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["rest_pull_tick"] = "rest_pull_tick"
    tool_id: str
    tick_at: datetime
    response_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    payload: dict[str, object]


class RssItemEvent(BaseModel):
    """Event for a new RSS 2.0 item (after guid de-duplication)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["rss_item"] = "rss_item"
    feed_tool_id: str
    guid: str
    published_at: datetime | None = None
    title: str
    link: str | None = None
    description: str | None = None


SubscriptionEvent = Annotated[
    CbsBroadcastEvent | RestPullTickEvent | RssItemEvent | SubscriptionBackpressureDrop,
    Field(discriminator="kind"),
]
"""Discriminated union on ``kind``. All 4 variants per data-model.md §3."""


class SubscriptionHandle(BaseModel):
    """Synchronous handle returned at subscription open time."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    subscription_id: str
    tool_id: str
    opened_at: datetime
    closes_at: datetime  # opened_at + lifetime_seconds


# ---------------------------------------------------------------------------
# T055 — RSS guid de-duplication state (per subscription handle)
# ---------------------------------------------------------------------------


class RssGuidTracker:
    """Per-subscription RSS guid de-duplication tracker.

    Tracks which guids have been seen within this subscription.
    ``is_new(guid)`` returns True and marks the guid as seen in one call.
    ``reset()`` clears all state — previously-seen guids become new again.

    Edge Case (research.md §4): Reset guids on the publisher side MUST surface
    as new items. ``reset()`` implements this by clearing the seen set.
    """

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def is_new(self, guid: str) -> bool:
        """Return True if the guid has not been seen; mark it as seen.

        Auto-marks the guid on first call, so duplicate calls return False.
        """
        if guid in self._seen:
            return False
        self._seen.add(guid)
        return True

    def mark_seen(self, guid: str) -> None:
        """Explicitly mark a guid as seen (idempotent)."""
        self._seen.add(guid)

    def reset(self) -> None:
        """Clear all tracked guids. Previously-seen guids become new again."""
        self._seen.clear()


# ---------------------------------------------------------------------------
# Internal adapter registry (for subscribe primitive only)
# ---------------------------------------------------------------------------

# Maps tool_id → (modality, adapter_fn)
# Modality is one of MODALITY_CBS / MODALITY_REST_PULL / MODALITY_RSS.
SubscribeAdapterFn = Callable[[SubscribeInput, "SubscriptionHandle"], AsyncIterator[Any]]
_SUBSCRIBE_ADAPTERS: dict[str, tuple[str, SubscribeAdapterFn]] = {}


def register_subscribe_adapter(
    tool_id: str,
    modality: str,
    adapter_fn: SubscribeAdapterFn,  # async generator (inp, handle) -> AsyncIterator
) -> None:
    """Register a subscribe-primitive adapter.

    Args:
        tool_id: Unique adapter identifier.
        modality: One of MODALITY_CBS / MODALITY_REST_PULL / MODALITY_RSS.
        adapter_fn: Async generator that yields events into the provided queue.
    """
    _SUBSCRIBE_ADAPTERS[tool_id] = (modality, adapter_fn)
    logger.debug("Registered subscribe adapter %r modality=%r", tool_id, modality)


# ---------------------------------------------------------------------------
# T052 — Modality muxer + T053/T054/T055 drivers
# ---------------------------------------------------------------------------


async def _run_driver(
    tool_id: str,
    modality: str,
    adapter_fn: SubscribeAdapterFn,
    inp: SubscribeInput,
    handle: SubscriptionHandle,
    queue: asyncio.Queue[Any],
    drop_counter: list[int],
) -> None:
    """Run the adapter driver and funnel events into the shared queue.

    Drop events when the queue is full (back-pressure, FR-015).
    """
    try:
        async for event in adapter_fn(inp, handle):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                drop_counter[0] += 1
                logger.debug(
                    "subscribe back-pressure drop for %r (total dropped: %d)",
                    handle.subscription_id,
                    drop_counter[0],
                )
    except asyncio.CancelledError:
        logger.debug("Driver for %r cancelled (lifetime expiry or cancel)", tool_id)
        raise
    finally:
        await queue.put(_DRIVER_DONE)


# ---------------------------------------------------------------------------
# T053 — CBS broadcast driver
# ---------------------------------------------------------------------------


async def _cbs_driver(
    inp: SubscribeInput,
    handle: SubscriptionHandle,
    queue: asyncio.Queue[Any],
    drop_counter: list[int],
) -> None:
    """CBS adapter driver — delegates to the registered CBS adapter."""
    tool_id = inp.tool_id
    _, adapter_fn = _SUBSCRIBE_ADAPTERS[tool_id]
    await _run_driver(tool_id, MODALITY_CBS, adapter_fn, inp, handle, queue, drop_counter)


# ---------------------------------------------------------------------------
# T054 — REST-pull driver
# ---------------------------------------------------------------------------


async def _rest_pull_driver(
    inp: SubscribeInput,
    handle: SubscriptionHandle,
    queue: asyncio.Queue[Any],
    drop_counter: list[int],
) -> None:
    """REST-pull driver — enforces minimum 10s polling interval (research §4)."""
    tool_id = inp.tool_id
    _, adapter_fn = _SUBSCRIBE_ADAPTERS[tool_id]
    await _run_driver(tool_id, MODALITY_REST_PULL, adapter_fn, inp, handle, queue, drop_counter)


# ---------------------------------------------------------------------------
# T055 — RSS 2.0 driver
# ---------------------------------------------------------------------------


async def _rss_driver(
    inp: SubscribeInput,
    handle: SubscriptionHandle,
    queue: asyncio.Queue[Any],
    drop_counter: list[int],
) -> None:
    """RSS 2.0 driver with per-handle guid de-duplication."""
    tool_id = inp.tool_id
    _, adapter_fn = _SUBSCRIBE_ADAPTERS[tool_id]
    await _run_driver(tool_id, MODALITY_RSS, adapter_fn, inp, handle, queue, drop_counter)


# ---------------------------------------------------------------------------
# T056 — Lifetime enforcement + main subscribe() function
# ---------------------------------------------------------------------------


def subscribe(
    inp: SubscribeInput,
) -> AsyncIterator[SubscriptionEvent] | AdapterNotFoundError:
    """Open a subscription and return an ``AsyncIterator[SubscriptionEvent]``.

    The iterator is bounded by ``inp.lifetime_seconds`` (FR-011, FR-014).
    Back-pressure is handled by a 64-event queue (FR-015).
    No webhook field anywhere (FR-013).

    Registry miss surfaces synchronously as an :class:`AdapterNotFoundError`
    sibling return, matching :func:`kosmos.primitives.submit.submit` and
    :func:`kosmos.primitives.verify.verify` rather than leaking the error into
    the event stream (where it would violate the :data:`SubscriptionEvent`
    discriminated-union contract).

    Modality dispatch (T052):
    - ``MODALITY_CBS`` → CBS broadcast driver (T053)
    - ``MODALITY_REST_PULL`` → REST-pull driver with 10s minimum interval (T054)
    - ``MODALITY_RSS`` → RSS 2.0 driver with guid de-dup (T055)
    """
    if inp.tool_id not in _SUBSCRIBE_ADAPTERS:
        logger.warning("subscribe: adapter not found: %s", inp.tool_id)
        return AdapterNotFoundError(
            tool_id=inp.tool_id,
            message=(
                f"No subscribe adapter registered for tool_id={inp.tool_id!r}. "
                "Check that the adapter module is imported before calling subscribe()."
            ),
        )
    return _SubscribeIterator(inp)


class _SubscribeIterator:
    """Async iterator implementing subscribe() semantics."""

    def __init__(self, inp: SubscribeInput) -> None:
        self._inp = inp
        self._queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
        self._drop_counter: list[int] = [0]
        self._handle: SubscriptionHandle | None = None
        self._driver_task: asyncio.Task[None] | None = None
        self._started = False
        self._done = False

    def __aiter__(self) -> _SubscribeIterator:
        return self

    def peek_handle(self) -> SubscriptionHandle:
        """Return (creating on first call) the SubscriptionHandle synchronously.

        Audit-5 P0-2 fix (2026-05-04): the IPC stdio dispatcher needs the
        canonical ``subscription_id`` *before* the driver task starts so the
        backend → frontend correlation is deterministic. Previously
        ``stdio.py:_dispatch_primitive`` invented a synthetic ``uuid.uuid4()``
        envelope id, which the TUI ``subscriptionRegistry`` then used as the
        handle key — so the real ``SubscriptionHandle.subscription_id`` (the
        one carried by every ``SubscriptionBackpressureDrop`` /
        ``RssGuidTracker`` / OTEL span) and the TUI-visible id never matched.

        Idempotent: subsequent calls return the same handle. ``_start()``
        observes the pre-created handle when invoked from ``__anext__``.
        """
        if self._handle is None:
            now = datetime.now(UTC)
            self._handle = SubscriptionHandle(
                subscription_id=str(uuid.uuid4()),
                tool_id=self._inp.tool_id,
                opened_at=now,
                closes_at=now + timedelta(seconds=self._inp.lifetime_seconds),
            )
        return self._handle

    async def __anext__(self) -> Any:
        if not self._started:
            await self._start()

        if self._done:
            raise StopAsyncIteration

        inp = self._inp
        assert self._handle is not None  # set by _start() before any __anext__
        deadline = self._handle.closes_at.timestamp()
        now = datetime.now(UTC).timestamp()
        remaining = max(0.0, deadline - now)

        if remaining <= 0:
            await self._finalize()
            raise StopAsyncIteration

        try:
            item = await asyncio.wait_for(self._queue.get(), timeout=remaining + 0.1)
        except TimeoutError:
            await self._finalize()
            raise StopAsyncIteration from None

        if item is _DRIVER_DONE:
            self._done = True
            # Emit drop event if there were unflushed drops (FR-014)
            if self._drop_counter[0] > 0:
                assert self._handle is not None
                drop = SubscriptionBackpressureDrop(
                    subscription_id=self._handle.subscription_id,
                    events_dropped=self._drop_counter[0],
                    message=(
                        f"subscribe({inp.tool_id}): {self._drop_counter[0]} event(s) "
                        "dropped due to back-pressure queue overflow."
                    ),
                )
                self._drop_counter[0] = 0
                return drop
            raise StopAsyncIteration

        # Check lifetime hasn't expired mid-iteration
        now_after = datetime.now(UTC).timestamp()
        if now_after > deadline:
            await self._finalize()
            raise StopAsyncIteration

        return item

    async def _start(self) -> None:
        """Create the handle (if not pre-created) and start the driver task.

        Audit-5 P0-2 (2026-05-04): when ``peek_handle()`` was called by the
        IPC dispatcher before the iterator was awaited, ``self._handle`` is
        already populated — reuse it so the ``subscription_id`` printed to
        the TUI matches every subsequent OTEL span / drop event / consent
        ledger entry.
        """
        self._started = True
        inp = self._inp
        if self._handle is None:
            now = datetime.now(UTC)
            self._handle = SubscriptionHandle(
                subscription_id=str(uuid.uuid4()),
                tool_id=inp.tool_id,
                opened_at=now,
                closes_at=now + timedelta(seconds=inp.lifetime_seconds),
            )

        # FR-031: emit a single gen_ai.tool_loop.iteration span at handle-open
        # to mirror submit/verify parity. Subsequent event delivery happens on
        # the driver task; per-event spans would flood the exporter.
        with _tracer.start_as_current_span("gen_ai.tool_loop.iteration") as span:
            span.set_attribute("gen_ai.tool.name", inp.tool_id)
            span.set_attribute("kosmos.subscribe.subscription_id", self._handle.subscription_id)
            span.set_attribute("kosmos.subscribe.lifetime_seconds", float(inp.lifetime_seconds))

        # subscribe() already guards against registry misses before the iterator
        # is constructed, so _SUBSCRIBE_ADAPTERS[inp.tool_id] is guaranteed here.
        modality, adapter_fn = _SUBSCRIBE_ADAPTERS[inp.tool_id]
        drop_counter = self._drop_counter
        handle = self._handle
        queue = self._queue

        async def _driver_body() -> None:
            try:
                async for event in adapter_fn(inp, handle):
                    now_check = datetime.now(UTC).timestamp()
                    if now_check > handle.closes_at.timestamp():
                        break
                    try:
                        queue.put_nowait(event)
                    except asyncio.QueueFull:
                        drop_counter[0] += 1
            except asyncio.CancelledError:
                pass
            finally:
                await queue.put(_DRIVER_DONE)

        self._driver_task = asyncio.create_task(_driver_body())

    async def _finalize(self) -> None:
        """Cancel driver task and clean up resources."""
        self._done = True
        if self._driver_task and not self._driver_task.done():
            self._driver_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._driver_task


# ---------------------------------------------------------------------------
# Testing helper — exposes handle for integration tests (T048)
# ---------------------------------------------------------------------------


async def _get_handle_for_testing(inp: SubscribeInput) -> SubscriptionHandle:
    """Return a SubscriptionHandle for the given input without consuming events.

    For use only in integration tests (T048). Not part of the public API.
    """
    now = datetime.now(UTC)
    return SubscriptionHandle(
        subscription_id=str(uuid.uuid4()),
        tool_id=inp.tool_id,
        opened_at=now,
        closes_at=now + timedelta(seconds=inp.lifetime_seconds),
    )


__all__ = [
    "CbsBroadcastEvent",
    "RestPullTickEvent",
    "RssGuidTracker",
    "RssItemEvent",
    "SubscribeInput",
    "SubscriptionBackpressureDrop",
    "SubscriptionEvent",
    "SubscriptionHandle",
    "MODALITY_CBS",
    "MODALITY_REST_PULL",
    "MODALITY_RSS",
    "register_subscribe_adapter",
    "subscribe",
    "_get_handle_for_testing",
    "_MIN_POLLING_INTERVAL_SECONDS",
]
