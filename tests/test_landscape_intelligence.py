from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from tests.helpers import load_integration_module

M = load_integration_module("landscape_intelligence.models")
Z = load_integration_module("landscape_intelligence.zone1")


def test_zone1_commissioning_preserves_reviewed_facts_and_safety_boundary() -> None:
    profile = Z.build_zone_1_landscape_intelligence(
        datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
    )
    groups = {group.plant_group_id: group for group in profile.plant_groups}

    assert groups["mature_palms"].irrigation_role is M.IrrigationRole.INCIDENTAL
    assert groups["mature_palms"].controls_zone_demand is False
    assert groups["citrus"].establishment_state is M.EstablishmentState.ESTABLISHING
    assert (
        groups["podocarpus"].emitter_relationship
        == "one_two_sided_microjet_serves_two_trees"
    )
    assert profile.health_observations[0].plant_group_id == "peruvian_lilies"
    assert profile.health_observations[0].overall_state is M.HealthState.STRESSED
    assert profile.execution_authorized is False
    assert profile.live_control_authorized is False
    assert profile.plant_factor_status == "unresolved"


def test_incidental_plant_cannot_control_demand() -> None:
    try:
        M.PlantGroup(
            "p",
            "Palm",
            None,
            M.Confidence.HIGH,
            M.IrrigationRole.INCIDENTAL,
            M.EstablishmentState.ESTABLISHED,
            False,
            False,
            controls_zone_demand=True,
        )
    except ValueError as exc:
        assert "cannot control" in str(exc)
    else:
        raise AssertionError("unsafe incidental control accepted")


def test_health_observation_requires_timezone_and_cannot_adjust_runtime() -> None:
    kwargs = {
        "observation_id": "o",
        "plant_group_id": "p",
        "source": M.ObservationSource.HUMAN_DIRECT,
        "confidence": M.Confidence.HIGH,
        "overall_state": M.HealthState.STRESSED,
        "findings": (),
        "direct_irrigation": True,
        "visible_coverage_problem": False,
        "application_adequacy": "unresolved",
        "suspected_water_stress": "possible",
        "diagnosis": "unresolved",
    }

    try:
        M.PlantHealthObservation(observed_at=datetime(2026, 8, 19), **kwargs)
    except ValueError as exc:
        assert "timezone-aware" in str(exc)
    else:
        raise AssertionError("naive timestamp accepted")

    try:
        M.PlantHealthObservation(
            observed_at=datetime.now(UTC),
            automatic_runtime_adjustment=True,
            **kwargs,
        )
    except ValueError as exc:
        assert "cannot authorize" in str(exc)
    else:
        raise AssertionError("runtime authority accepted")


def _profile_with_states(states: list[Any]) -> Any:
    base = Z.build_zone_1_landscape_intelligence(datetime(2026, 8, 1, tzinfo=UTC))
    observations = []
    for index, state in enumerate(states):
        observations.append(
            M.PlantHealthObservation(
                f"o{index}",
                "peruvian_lilies",
                datetime(2026, 8, 1, tzinfo=UTC) + timedelta(days=index),
                M.ObservationSource.HUMAN_REVIEWED_PHOTO,
                M.Confidence.MODERATE,
                state,
                (),
                True,
                False,
                "unresolved",
                "possible",
                "unresolved",
            )
        )

    return M.LandscapeIntelligenceProfile(
        base.schema_version,
        base.area_slot,
        base.profile_status,
        base.hydrozone_type,
        base.hydrozone_quality,
        base.irrigation_method,
        base.emitter_family,
        base.predominant_radius_ft,
        base.predominant_emitter_color,
        base.application_rate_status,
        base.plant_groups,
        tuple(observations),
    )


def test_longitudinal_health_trends_are_deterministic() -> None:
    one_observation = _profile_with_states([M.HealthState.STRESSED])
    improving = _profile_with_states(
        [M.HealthState.STRESSED, M.HealthState.MILDLY_STRESSED]
    )
    stable = _profile_with_states([M.HealthState.STRESSED, M.HealthState.STRESSED])
    worsening = _profile_with_states(
        [M.HealthState.MILDLY_STRESSED, M.HealthState.STRESSED]
    )

    assert (
        M.summarize_health(one_observation, "peruvian_lilies").trend
        is M.HealthTrend.INSUFFICIENT_HISTORY
    )
    assert (
        M.summarize_health(improving, "peruvian_lilies").trend
        is M.HealthTrend.IMPROVING
    )
    assert (
        M.summarize_health(stable, "peruvian_lilies").trend
        is M.HealthTrend.STABLE
    )
    assert (
        M.summarize_health(worsening, "peruvian_lilies").trend
        is M.HealthTrend.WORSENING
    )


def test_full_history_can_grow_without_becoming_entity_payload() -> None:
    profile = _profile_with_states([M.HealthState.STRESSED] * 250)
    assert len(json.dumps(profile.to_dict()).encode()) > 8192

    compact = {
        "schema_version": profile.schema_version,
        "hydrozone_type": profile.hydrozone_type.value,
        "plant_group_count": len(profile.plant_groups),
        "health_exception_count": 1,
        "plant_factor_status": profile.plant_factor_status,
        "landscape_factor_status": profile.landscape_factor_status,
        "execution_authorized": False,
        "live_control_authorized": False,
    }
    assert len(json.dumps(compact).encode()) < 8192


def test_landscape_intelligence_is_wired_to_storage_and_diagnostics() -> None:
    root = Path(__file__).resolve().parents[1]
    coordinator = (root / "custom_components/irrigationos/coordinator.py").read_text()
    diagnostics = (root / "custom_components/irrigationos/diagnostics.py").read_text()
    assert "LandscapeIntelligenceManager" in coordinator
    assert "landscape_intelligence.diagnostics()" in diagnostics
