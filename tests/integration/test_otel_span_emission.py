# SPDX-License-Identifier: Apache-2.0
"""T085 — OTEL span parity across submit / verify primitives.

Asserts that active gated primitives emit a ``gen_ai.tool_loop.iteration``
span carrying ``gen_ai.tool.name`` (the shared Spec 022 attribute shape)
whenever they are invoked on the main surface.

Strategy: per-primitive fixture that monkeypatches the module-level ``_tracer``
(or the module's local ``tracer = trace.get_tracer(...)`` call for submit) with
a dedicated ``TracerProvider`` backed by ``InMemorySpanExporter``. This mirrors
the pattern used by ``tests/observability/test_tool_execute_span.py``.

Reference: specs/031-five-primitive-harness/spec.md FR-031.
Reference: specs/031-five-primitive-harness/tasks.md T085.
"""

from __future__ import annotations

import importlib
from datetime import UTC, datetime

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from kosmos.tools.models import AdapterRealDomainPolicy

# ``kosmos.primitives.__init__`` re-exports the primitive *functions* under the
# same names as the submodules, which shadows them in the package namespace.
# Resolve the modules via importlib to get the real module objects.
submit_mod = importlib.import_module("kosmos.primitives.submit")
verify_mod = importlib.import_module("kosmos.primitives.verify")

from kosmos.primitives.submit import (  # noqa: E402
    SubmitOutput,
    SubmitStatus,
    register_submit_adapter,
    submit,
)
from kosmos.primitives.verify import (  # noqa: E402
    GanpyeonInjeungContext,
    register_verify_adapter,
    verify,
)
from kosmos.tools.registry import (  # noqa: E402
    AdapterPrimitive,
    AdapterRegistration,
    AdapterSourceMode,
)

_SPAN_NAME = "gen_ai.tool_loop.iteration"


@pytest.fixture(autouse=True)
def _enable_otel_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neutralise CI's ``OTEL_SDK_DISABLED=true`` for the duration of the test.

    The OpenTelemetry SDK honours ``OTEL_SDK_DISABLED=true`` globally: any
    ``TracerProvider()`` constructed while it is set emits no spans, which
    breaks the in-memory exporter assertions below. Local runs pass because
    the variable is unset; CI sets it via ``ci.yml`` to silence the real
    exporter. We explicitly clear it here so the test's isolated
    ``TracerProvider`` can route spans to ``InMemorySpanExporter``.
    """
    monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)


def _fresh_exporter() -> tuple[InMemorySpanExporter, TracerProvider]:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    exporter.clear()
    return exporter, provider


# ---------------------------------------------------------------------------
# submit primitive parity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_emits_gen_ai_tool_loop_iteration_span(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exporter, provider = _fresh_exporter()
    monkeypatch.setattr(
        submit_mod.trace,
        "get_tracer",
        lambda _name: provider.get_tracer("kosmos.primitives.submit"),
    )

    tool_id = "mock_otel_parity_submit_v1"
    registration = AdapterRegistration(
        tool_id=tool_id,
        primitive=AdapterPrimitive.submit,
        module_path="tests.integration.test_otel_span_emission",
        input_model_ref="tests.integration.test_otel_span_emission:_NoopIn",
        source_mode=AdapterSourceMode.HARNESS_ONLY,
        published_tier_minimum="ganpyeon_injeung_kakao_aal2",
        nist_aal_hint="AAL2",
        is_concurrency_safe=False,
        cache_ttl_seconds=0,
        rate_limit_per_minute=10,
        search_hint={"ko": ["otel"], "en": ["otel"]},
        auth_type="oauth",
        policy=AdapterRealDomainPolicy(
            real_classification_url="https://example.gov.kr/policy/submit",
            real_classification_text="OTEL 테스트 submit 정책",
            citizen_facing_gate="submit",
            last_verified=datetime(2026, 4, 29, tzinfo=UTC),
        ),
    )

    async def _invoke(_params: dict[str, object]) -> SubmitOutput:
        return SubmitOutput(
            transaction_id="urn:kosmos:submit:test",
            status=SubmitStatus.succeeded,
            adapter_receipt={"ok": True},
        )

    # Snapshot previous _ADAPTER_REGISTRY entry (if any) so we can restore on
    # teardown — leaving the fixture adapter in the global registry pollutes
    # later tests' counts (Spec 2296 T035 surfaces this when running the full
    # suite). Mirrors the verify-test pattern below at line 188.
    from kosmos.primitives.submit import _ADAPTER_REGISTRY as _submit_registry  # noqa: N811

    _previous_submit = _submit_registry.get(tool_id)
    register_submit_adapter(registration, _invoke)
    try:

        class _GanpyeonCtx:
            published_tier = "ganpyeon_injeung_kakao_aal2"

        result = await submit(
            tool_id=tool_id,
            params={},
            auth_context=_GanpyeonCtx(),
            session_id="otel-test",
        )

        assert isinstance(result, SubmitOutput)
        spans = exporter.get_finished_spans()
        names = [s.name for s in spans]
        assert _SPAN_NAME in names, f"submit did not emit {_SPAN_NAME}; got {names}"

        parity_span = next(s for s in spans if s.name == _SPAN_NAME)
        attrs = dict(parity_span.attributes or {})
        assert attrs.get("gen_ai.tool.name") == tool_id
    finally:
        if _previous_submit is None:
            _submit_registry.pop(tool_id, None)
        else:
            _submit_registry[tool_id] = _previous_submit


# ---------------------------------------------------------------------------
# verify primitive parity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_emits_gen_ai_tool_loop_iteration_span(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exporter, provider = _fresh_exporter()
    monkeypatch.setattr(
        verify_mod,
        "_tracer",
        provider.get_tracer("kosmos.primitives.verify"),
    )

    family = "ganpyeon_injeung"

    async def _adapter(_session_context: dict[str, object]):
        return GanpyeonInjeungContext(
            family="ganpyeon_injeung",
            provider="kakao",
            verified_at=datetime.now(UTC),
            published_tier="ganpyeon_injeung_kakao_aal2",
            nist_aal_hint="AAL2",
        )

    # Snapshot the previously-registered adapter so we can restore it on
    # teardown — leaking the async test adapter into the global
    # _VERIFY_ADAPTERS registry corrupts later unit tests
    # (test_adapter_returns_auth_context_shape calls the adapter
    # synchronously and gets a coroutine back). Pre-existing leak documented
    # in tests/ipc/test_stdio.py:107; closed here.
    from kosmos.primitives.verify import _VERIFY_ADAPTERS

    _previous_adapter = _VERIFY_ADAPTERS.get(family)
    register_verify_adapter(family, _adapter)
    try:
        result = await verify(family_hint=family)
        assert isinstance(result, GanpyeonInjeungContext)

        spans = exporter.get_finished_spans()
        names = [s.name for s in spans]
        assert _SPAN_NAME in names, f"verify did not emit {_SPAN_NAME}; got {names}"

        parity_span = next(s for s in spans if s.name == _SPAN_NAME)
        attrs = dict(parity_span.attributes or {})
        assert attrs.get("gen_ai.tool.name") == f"verify:{family}"
    finally:
        # Restore the original adapter (or remove ours if nothing was there).
        if _previous_adapter is not None:
            register_verify_adapter(family, _previous_adapter)
        else:
            _VERIFY_ADAPTERS.pop(family, None)
