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


F = load_integration_module("landscape_intelligence.factor_resolution")
E = load_integration_module("landscape_intelligence.zone1_factor_evidence")


def test_zone1_factor_resolution_v2_is_partial_and_advisory() -> None:
    profile = Z.build_zone_1_landscape_intelligence(datetime(2026, 8, 20, tzinfo=UTC))
    result = F.resolve_zone_factor(profile, E.zone_1_factor_evidence())
    groups = {item.plant_group_id: item for item in result.group_resolutions}

    assert result.algorithm_version == "1.1.0"
    assert result.status is F.FactorResolutionStatus.PARTIALLY_RESOLVED
    assert result.plant_factor is None
    assert result.controlling_group_id is None
    assert result.execution_authorized is False
    assert result.live_control_authorized is False
    assert result.density_factor_status == "not_required_for_plant_factor_v2"
    assert "density_factor_unresolved" not in result.blocker_codes

    assert groups["mature_palms"].status is F.FactorResolutionStatus.EXCLUDED
    assert groups["podocarpus"].admitted_factor == 0.5
    assert groups["fig"].status is F.FactorResolutionStatus.RESOLVED
    assert groups["fig"].admitted_factor == 0.8
    assert groups["passion_fruit"].status is F.FactorResolutionStatus.RESOLVED
    assert groups["passion_fruit"].admitted_factor == 0.5
    assert groups["peruvian_lilies"].status is F.FactorResolutionStatus.RESOLVED
    assert groups["peruvian_lilies"].admitted_factor == 0.5

    assert groups["citrus"].status is F.FactorResolutionStatus.PARTIALLY_RESOLVED
    assert groups["citrus"].admitted_factor == 1.0
    assert "establishment_management_unresolved" in groups["citrus"].blocker_codes
    assert "plant_group_factor_unresolved" not in groups["citrus"].blocker_codes

    assert groups["drought_tolerant_ornamentals"].admitted_factor is None
    assert "hydrozone_controlling_group_unresolved" in result.blocker_codes


def test_agricultural_kc_cannot_be_authoritative_landscape_pf() -> None:
    try:
        F.PlantFactorEvidence(
            "citrus",
            F.EvidenceClass.AGRICULTURAL_CROP_COEFFICIENT,
            F.FactorRange(0.65, 0.70),
            None,
            "source",
            "source",
            "https://example.invalid",
            "high",
            True,
            "not admissible",
        )
    except ValueError as exc:
        assert "cannot directly authorize" in str(exc)
    else:
        raise AssertionError("agricultural Kc was admitted as landscape PF")


def test_factor_ranges_preserve_source_uncertainty_without_midpoint() -> None:
    evidence = {item.plant_group_id: item for item in E.zone_1_factor_evidence()}
    drought = evidence["drought_tolerant_ornamentals"]
    assert isinstance(drought.factor, F.FactorRange)
    assert drought.factor.minimum == 0.1
    assert drought.factor.maximum == 0.3
    assert "typical" not in drought.factor.to_dict()


def test_direct_residential_pf_outranks_agricultural_context() -> None:
    evidence = E.zone_1_factor_evidence()
    profile = Z.build_zone_1_landscape_intelligence(datetime(2026, 8, 20, tzinfo=UTC))
    result = F.resolve_zone_factor(profile, evidence)
    groups = {item.plant_group_id: item for item in result.group_resolutions}

    assert groups["fig"].evidence_class is F.EvidenceClass.URBAN_HORTICULTURE
    assert groups["fig"].admitted_factor == 0.8
    assert "ucanr.fig_crop_water_research" in groups["fig"].source_ids

    assert groups["citrus"].evidence_class is F.EvidenceClass.URBAN_HORTICULTURE
    assert groups["citrus"].admitted_factor == 1.0
    assert "ucanr.young_orchard_irrigation.citrus" in groups["citrus"].source_ids


def test_mixed_zone_resolves_to_highest_pf_when_all_controllers_have_factors() -> None:
    profile = Z.build_zone_1_landscape_intelligence(datetime(2026, 8, 20, tzinfo=UTC))
    evidence = (
        *(
            item
            for item in E.zone_1_factor_evidence()
            if item.plant_group_id != "drought_tolerant_ornamentals"
        ),
        F.PlantFactorEvidence(
            "drought_tolerant_ornamentals",
            F.EvidenceClass.URBAN_HORTICULTURE,
            0.3,
            "desert_adapted",
            "test.authoritative_ornamental_pf",
            "Test source",
            "https://example.invalid",
            "high",
            True,
            "Test-only admitted factor.",
        ),
    )

    result = F.resolve_zone_factor(profile, evidence)

    assert result.status is F.FactorResolutionStatus.PARTIALLY_RESOLVED
    assert result.plant_factor == 1.0
    assert result.controlling_group_id == "citrus"
    assert "hydrozone_controlling_group_unresolved" not in result.blocker_codes
    assert "establishment_management_unresolved" in result.blocker_codes
    assert result.execution_authorized is False
    assert result.live_control_authorized is False
