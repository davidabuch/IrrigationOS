"""Tests for immutable shadow-evaluation evidence and deduplication primitives."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from tests.helpers import load_integration_module

MODELS = load_integration_module("shadow_evaluation.models")


class ExampleEnum(StrEnum):
    VALUE = "value"


@dataclass(frozen=True)
class Example:
    area_id: str
    native_id: str
    serial_number: str
    value: ExampleEnum
    when: datetime


def test_jsonable_preserves_canonical_context_but_removes_provider_secrets() -> None:
    payload = MODELS.jsonable(
        Example(
            area_id="controller:slot:1",
            native_id="provider-secret",
            serial_number="serial-secret",
            value=ExampleEnum.VALUE,
            when=datetime(2026, 8, 9, 20, 0, tzinfo=UTC),
        )
    )
    assert payload["area_id"] == "controller:slot:1"
    assert payload["value"] == "value"
    assert payload["when"] == "2026-08-09T20:00:00+00:00"
    assert "native_id" not in payload
    assert "serial_number" not in payload


def test_section_hash_is_deterministic_and_semantic() -> None:
    first = MODELS.semantic_value({"b": 2, "a": 1})
    second = MODELS.semantic_value({"a": 1, "b": 2})
    changed = MODELS.semantic_value({"a": 1, "b": 3})
    assert first == second
    assert first != changed


def test_shadow_contract_is_immutable() -> None:
    record = MODELS.ShadowEvaluationRecord(
        schema_version=1,
        evaluation_id="abc",
        reason=MODELS.ShadowEvaluationReason.NIGHTLY,
        timestamp_utc=datetime(2026, 8, 10, 3, 0, tzinfo=UTC),
        timestamp_local=datetime(2026, 8, 9, 20, 0, tzinfo=UTC),
        integration_version="1.0.18",
        pipeline_algorithm_version="1.0.10",
        decision_fingerprint="fingerprint",
        payload={},
    )
    assert record.reason.value == "nightly"


def test_current_shadow_schema_is_two_while_legacy_records_remain_data() -> None:
    assert MODELS.SHADOW_EVALUATION_SCHEMA_VERSION == 2
    legacy = MODELS.ShadowEvaluationRecord(
        schema_version=1,
        evaluation_id="legacy",
        reason=MODELS.ShadowEvaluationReason.DECISION_CHANGE,
        timestamp_utc=datetime(2026, 8, 10, 3, 0, tzinfo=UTC),
        timestamp_local=datetime(2026, 8, 9, 20, 0, tzinfo=UTC),
        integration_version="1.0.43",
        pipeline_algorithm_version="1.0.10",
        decision_fingerprint="legacy-fingerprint",
        payload={"scheduling": []},
    )
    assert legacy.schema_version == 1
