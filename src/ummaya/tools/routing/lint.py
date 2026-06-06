# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from ummaya.tools.routing.types import (
    RAW_SCHEMA_MARKERS,
    AdapterCard,
    AdapterCardQualityViolation,
)


def lint_adapter_card(card: AdapterCard) -> tuple[AdapterCardQualityViolation, ...]:
    violations: list[AdapterCardQualityViolation] = []
    if card.source_mode in ("live", "mock") and not card.policy_authority_url:
        violations.append(
            AdapterCardQualityViolation(
                code="missing_policy_citation",
                message="live/mock adapter cards must cite an agency policy URL",
            )
        )
    if not card.input_schema_summary:
        violations.append(
            AdapterCardQualityViolation(
                code="missing_required_slot_metadata",
                message="adapter cards must summarize input slots",
            )
        )
    if not card.safety_annotations:
        violations.append(
            AdapterCardQualityViolation(
                code="missing_safety_annotations",
                message="adapter cards must expose safety annotations",
            )
        )
    if not card.credential_requirements:
        violations.append(
            AdapterCardQualityViolation(
                code="missing_credential_requirements",
                message="adapter cards must expose credential requirements",
            )
        )
    if not card.examples_ko or not card.examples_en:
        violations.append(
            AdapterCardQualityViolation(
                code="missing_examples",
                message="adapter cards must include Korean and English examples",
            )
        )
    if not card.negative_examples:
        violations.append(
            AdapterCardQualityViolation(
                code="missing_negative_examples",
                message="adapter cards must include negative examples",
            )
        )
    if not card.limitations:
        violations.append(
            AdapterCardQualityViolation(
                code="missing_limitations",
                message="adapter cards must state routing limitations",
            )
        )
    if any(marker in card.routing_text for marker in RAW_SCHEMA_MARKERS):
        violations.append(
            AdapterCardQualityViolation(
                code="raw_schema_leakage",
                message="routing_text must not embed raw JSON schema",
            )
        )
    return tuple(violations)


def assert_adapter_card_quality(card: AdapterCard) -> None:
    violations = lint_adapter_card(card)
    if not violations:
        return
    detail = ", ".join(f"{violation.code}: {violation.message}" for violation in violations)
    raise ValueError(f"AdapterCard quality violations: {detail}")
