"""Generic irrigation-delivery calibration and persistence tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tests.helpers import load_integration_module

C = load_integration_module("water_delivery.calibration")
M = load_integration_module("water_delivery.models")
P = load_integration_module("water_delivery.persistence")
COMMISSIONING_PERSISTENCE = load_integration_module(
    "landscape_intelligence.persistence"
)
COMMISSIONING = load_integration_module("landscape_intelligence.commissioning")
LANDSCAPE_MODELS = load_integration_module("landscape_intelligence.models")
ONBOARDING = load_integration_module("landscape_intelligence.onboarding")
ZONE1 = load_integration_module("landscape_intelligence.zone1")

NOW = datetime(2026, 8, 24, 18, tzinfo=UTC)


def _request(**changes: object) -> object:
    values = {
        "profile_id": "delivery.property.other.zone.4",
        "area_id": "zone.4",
        "component_id": "component.microjet.shared.1",
        "display_name": "Shared blue microjet",
        "delivery_type": M.WaterDeliveryType.MICROJET,
        "component_count": 1,
        "flow_evidence_level": M.DeliveryEvidenceLevel.UNKNOWN,
        "observed_at": NOW,
    }
    values.update(changes)
    return C.DeliveryComponentCalibrationRequest(**values)


def test_unknown_rated_and_estimated_flow_remain_distinct_evidence() -> None:
    unknown = C.calibrate_delivery_component(_request())
    rated = C.calibrate_delivery_component(
        _request(
            flow_evidence_level=M.DeliveryEvidenceLevel.MANUFACTURER_RATED,
            flow_basis=M.FlowBasis.PER_EMITTER,
            flow_liters_per_hour=20.0,
        )
    )
    estimated = C.calibrate_delivery_component(
        _request(
            flow_evidence_level=M.DeliveryEvidenceLevel.USER_ESTIMATED,
            flow_liters_per_hour=18.0,
        )
    )
    assert unknown.components[0].preferred_flow_liters_per_hour is None
    assert rated.components[0].nominal_flow_liters_per_hour.evidence_level.value == (
        "manufacturer_rated"
    )
    assert rated.components[0].flow_basis is M.FlowBasis.PER_EMITTER
    assert estimated.components[0].nominal_flow_liters_per_hour.evidence_level.value == (
        "user_estimated"
    )
    assert rated.components[0].measured_flow_liters_per_hour.value is None


def test_one_gallon_over_five_minutes_derives_only_measured_flow() -> None:
    profile = C.calibrate_delivery_component(
        _request(
            flow_evidence_level=M.DeliveryEvidenceLevel.MEASURED,
            collected_volume=1.0,
            collected_volume_unit=M.MeasurementUnit.US_GALLONS,
            collection_duration_seconds=300,
            radius_meters=0.9144,
        )
    )
    component = profile.components[0]
    assert component.measured_flow_liters_per_hour.value == pytest.approx(
        45.424941408
    )
    assert component.application_rate_mm_per_hour.value is None
    assert component.efficiency.value is None
    assert profile.calibrations[0].measurements[0].value == 1
    assert profile.calibrations[0].measurements[0].unit.value == "us_gallons"
    assert profile.calibrations[0].timer_duration_seconds == 300


@pytest.mark.parametrize(
    "changes",
    [
        {"flow_evidence_level": M.DeliveryEvidenceLevel.MEASURED},
        {
            "flow_evidence_level": M.DeliveryEvidenceLevel.MEASURED,
            "collected_volume": -1,
            "collected_volume_unit": M.MeasurementUnit.LITERS,
            "collection_duration_seconds": 60,
        },
        {
            "flow_evidence_level": M.DeliveryEvidenceLevel.MEASURED,
            "collected_volume": 1,
            "collected_volume_unit": M.MeasurementUnit.LITERS,
            "collection_duration_seconds": 0,
        },
        {"flow_evidence_level": M.DeliveryEvidenceLevel.USER_ESTIMATED},
        {"flow_liters_per_hour": 5.0},
    ],
)
def test_invalid_measurement_and_mismatched_evidence_fail_closed(
    changes: dict[str, object]
) -> None:
    with pytest.raises(ValueError):
        C.calibrate_delivery_component(_request(**changes))


def test_recalibration_preserves_measurements_and_round_trips() -> None:
    first = C.calibrate_delivery_component(
        _request(
            flow_evidence_level=M.DeliveryEvidenceLevel.MEASURED,
            collected_volume=1,
            collected_volume_unit=M.MeasurementUnit.LITERS,
            collection_duration_seconds=300,
        )
    )
    second = C.calibrate_delivery_component(
        _request(
            observed_at=datetime(2026, 9, 1, 18, tzinfo=UTC),
            flow_evidence_level=M.DeliveryEvidenceLevel.MEASURED,
            collected_volume=1.2,
            collected_volume_unit=M.MeasurementUnit.LITERS,
            collection_duration_seconds=300,
        ),
        existing_profile=first,
    )
    assert len(second.calibrations) == 2
    assert len(second.components[0].calibration_ids) == 2
    assert P.water_delivery_profile_from_dict(second.to_dict()) == second

    zone1 = ZONE1.build_zone_1_commissioning_profile(NOW)
    payload = COMMISSIONING_PERSISTENCE.build_store_payload(
        (zone1,),
        (),
        legacy_zone1=zone1.to_landscape_intelligence_profile().to_dict(),
        delivery_profiles=(second,),
    )
    restored = COMMISSIONING_PERSISTENCE.restore_store_payload(
        payload, fallback_zone1=zone1
    )
    assert restored.delivery_profiles == (second,)


def test_shared_component_is_one_physical_identity_not_one_emitter_per_plant() -> None:
    profile = C.calibrate_delivery_component(_request())
    plant_group_ids = ("plant.podocarpus.1", "plant.podocarpus.2")
    links = tuple(
        COMMISSIONING.IrrigationDeliveryLink(
            f"{plant_id}.delivery",
            plant_id,
            COMMISSIONING.DeliveryLinkStatus.DOCUMENTED,
            profile.profile_id,
            (profile.components[0].component_id,),
            False,
        )
        for plant_id in plant_group_ids
    )
    assert len(profile.components) == 1
    assert links[0].component_ids == links[1].component_ids
    assert all(link.dedicated_delivery is False for link in links)


def test_calibration_improves_advisory_evidence_without_authorizing_runtime() -> None:
    unknown = C.calibrate_delivery_component(_request())
    plant = ONBOARDING.ManualPlantOnboardingInput(
        "plant.synthetic",
        "Synthetic establishing tree",
        None,
        LANDSCAPE_MODELS.EstablishmentState.ESTABLISHING,
        NOW,
    )
    link = COMMISSIONING.IrrigationDeliveryLink(
        "plant.synthetic.delivery",
        "plant.synthetic",
        COMMISSIONING.DeliveryLinkStatus.DOCUMENTED,
        unknown.profile_id,
        (unknown.components[0].component_id,),
        False,
    )
    zone = ONBOARDING.map_zone_onboarding(
        ONBOARDING.ZoneOnboardingRequest(
            COMMISSIONING.CanonicalZoneIdentity(
                "property.synthetic", "zone.4", 2, 4
            ),
            "Unrelated property",
            COMMISSIONING.ZoneDemandSourceMode.MANUAL_PLANT_PROFILE,
            NOW,
            manual_plants=(plant,),
            delivery_links=(link,),
        )
    )
    compatibility = COMMISSIONING.assess_delivery_compatibility(zone, (unknown,))
    assert "delivery_flow_quantification_unavailable" in {
        advisory.code for advisory in compatibility.advisories
    }
    assert zone.execution_authorized is False
    assert zone.live_control_authorized is False
