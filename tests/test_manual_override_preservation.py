"""Tests for deterministic non-actuating manual override preservation."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tests.helpers import load_integration_module

manual_override = load_integration_module("manual_override_preservation")
observation_models = load_integration_module("observation_history.models")
WateringAttribution = observation_models.WateringAttribution

NOW = datetime(2026, 8, 11, 22, 30, tzinfo=UTC)


def test_no_active_watering_requires_no_preservation() -> None:
    assert manual_override.evaluate_preservation_reasons(()) == ()
    assert manual_override.preservation_required(()) is False


def test_irrigationos_owned_watering_does_not_block_itself() -> None:
    assert manual_override.evaluate_preservation_reasons(
        (WateringAttribution.IRRIGATIONOS,)
    ) == ()


def test_manual_watering_is_preserved() -> None:
    reasons = manual_override.evaluate_preservation_reasons(
        (WateringAttribution.MANUAL,)
    )
    assert reasons == ("manual_watering_preserved",)
    assert manual_override.preservation_required((WateringAttribution.MANUAL,)) is True


def test_provider_schedule_is_preserved() -> None:
    assert manual_override.evaluate_preservation_reasons(
        (WateringAttribution.PROVIDER_SCHEDULE,)
    ) == ("provider_schedule_preserved",)


def test_ambiguous_external_watering_fails_closed() -> None:
    assert manual_override.evaluate_preservation_reasons(
        (WateringAttribution.EXTERNAL_UNKNOWN,)
    ) == ("ambiguous_external_watering_preserved",)


def test_unknown_attribution_fails_closed() -> None:
    assert manual_override.evaluate_preservation_reasons(("future_provider_mode",)) == (
        "unknown_attribution_preserved",
    )


def test_mixed_sessions_preserve_any_non_irrigationos_activity() -> None:
    reasons = manual_override.evaluate_preservation_reasons(
        (
            WateringAttribution.IRRIGATIONOS,
            WateringAttribution.MANUAL,
            WateringAttribution.EXTERNAL_UNKNOWN,
        )
    )
    assert reasons == (
        "ambiguous_external_watering_preserved",
        "manual_watering_preserved",
    )


def test_event_is_deterministic_and_non_actuating() -> None:
    first = manual_override.build_manual_override_preservation_event(
        command_id="command-1",
        evaluated_at=NOW,
        active_attributions=(WateringAttribution.MANUAL,),
    )
    second = manual_override.build_manual_override_preservation_event(
        command_id="command-1",
        evaluated_at=NOW,
        active_attributions=(WateringAttribution.MANUAL,),
    )
    assert first == second
    assert first.synthetic_only is True
    assert first.dispatch_capability is False
    assert first.detail_code == "manual_override_preservation_required"
    assert first.active_session_count == 1
    assert first.protected_session_count == 1
    assert first.ambiguous_attribution_present is False


def test_event_records_ambiguous_attribution_without_identifiers() -> None:
    event = manual_override.build_manual_override_preservation_event(
        command_id="command-1",
        evaluated_at=NOW,
        active_attributions=(WateringAttribution.EXTERNAL_UNKNOWN,),
    )
    payload = event.to_dict()
    assert event.ambiguous_attribution_present is True
    assert payload["reason_codes"] == ["ambiguous_external_watering_preserved"]
    assert "area_id" not in payload
    assert "controller_id" not in payload


def test_event_rejects_non_preservation_case() -> None:
    with pytest.raises(ValueError, match="manual_override_preservation_not_required"):
        manual_override.build_manual_override_preservation_event(
            command_id="command-1",
            evaluated_at=NOW,
            active_attributions=(WateringAttribution.IRRIGATIONOS,),
        )


def test_event_requires_timezone_aware_time() -> None:
    with pytest.raises(ValueError, match="evaluated_at_timezone_required"):
        manual_override.build_manual_override_preservation_event(
            command_id="command-1",
            evaluated_at=datetime(2026, 8, 11, 22, 30),
            active_attributions=(WateringAttribution.MANUAL,),
        )
