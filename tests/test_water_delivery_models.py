"""Behavioral tests for the canonical water-delivery domain."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from tests.helpers import load_integration_module

MODULE = load_integration_module("water_delivery.models")
AreaUnit = MODULE.AreaUnit
CalibrationMeasurement = MODULE.CalibrationMeasurement
CalibrationMeasurementType = MODULE.CalibrationMeasurementType
CalibrationPhotoReference = MODULE.CalibrationPhotoReference
CalibrationState = MODULE.CalibrationState
CalibrationTestType = MODULE.CalibrationTestType
CloggingRisk = MODULE.CloggingRisk
DeliveryComponent = MODULE.DeliveryComponent
DeliveryFact = MODULE.DeliveryFact
DeliveryProvenance = MODULE.DeliveryProvenance
DeliveryQuantityMode = MODULE.DeliveryQuantityMode
FlowBasis = MODULE.FlowBasis
GuidedCalibration = MODULE.GuidedCalibration
MeasurementUnit = MODULE.MeasurementUnit
PressureCompensation = MODULE.PressureCompensation
SprayPattern = MODULE.SprayPattern
WaterDeliveryProfile = MODULE.WaterDeliveryProfile
WaterDeliveryType = MODULE.WaterDeliveryType

NOW = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(minutes=10)


def fact(value: object, confidence: float = 0.9, source: str = "user_setup") -> Any:
    """Build a delivery fact for tests."""
    return DeliveryFact(
        value=value,
        confidence=confidence,
        provenance=DeliveryProvenance(source=source),
        assessed_at=NOW,
    )


def unknown() -> Any:
    """Build an explicitly unknown delivery fact."""
    return fact(None, confidence=0, source="unknown")


def component(**changes: object) -> Any:
    """Build a fully described dripper component."""
    values: dict[str, object] = {
        "component_id": "component-1",
        "area_id": "area-1",
        "display_name": "Tree drippers",
        "delivery_type": WaterDeliveryType.DRIPPER,
        "quantity_mode": DeliveryQuantityMode.COUNT,
        "quantity": fact(4.0),
        "flow_basis": FlowBasis.PER_EMITTER,
        "nominal_flow_liters_per_hour": fact(7.6, source="manufacturer_specification"),
        "measured_flow_liters_per_hour": unknown(),
        "application_rate_mm_per_hour": fact(12.0),
        "radius_meters": unknown(),
        "arc_degrees": unknown(),
        "spray_pattern": fact(SprayPattern.POINT_SOURCE),
        "efficiency": fact(0.9),
        "pressure_compensation": fact(PressureCompensation.PRESSURE_COMPENSATING),
        "clogging_risk": fact(CloggingRisk.MODERATE),
    }
    values.update(changes)
    return DeliveryComponent(**values)


def measurement(
    measurement_type: Any,
    value: int | float | bool,
    unit: Any,
    *,
    measurement_id: str = "measurement-1",
) -> Any:
    """Build a typed calibration measurement."""
    return CalibrationMeasurement(
        measurement_id=measurement_id,
        measurement_type=measurement_type,
        value=value,
        unit=unit,
        observed_at=LATER,
        provenance=DeliveryProvenance(source="user_guided_calibration"),
    )


def calibration(**changes: object) -> Any:
    """Build a requested collected-volume calibration."""
    values: dict[str, object] = {
        "calibration_id": "calibration-1",
        "area_id": "area-1",
        "component_id": "component-1",
        "test_type": CalibrationTestType.COLLECTED_VOLUME,
        "state": CalibrationState.REQUESTED,
        "why_it_matters": "Measured volume establishes actual emitter flow",
        "instructions": (
            "Place a marked container beneath one emitter",
            "Collect water for sixty seconds",
        ),
        "safety_note": "Keep electrical equipment dry",
        "created_at": NOW,
        "updated_at": NOW,
        "requested_unit": MeasurementUnit.MILLILITERS,
        "timer_duration_seconds": 60,
    }
    values.update(changes)
    return GuidedCalibration(**values)


def profile(
    *,
    components: tuple[Any, ...] | None = None,
    calibrations: tuple[Any, ...] = (),
) -> Any:
    """Build a linked water-delivery profile."""
    profile_components = components or (component(),)
    return WaterDeliveryProfile(
        profile_id="delivery-profile-1",
        area_id="area-1",
        display_name="Back orchard delivery",
        assessed_at=NOW,
        components=profile_components,
        calibrations=calibrations,
    )


def test_profile_serializes_deterministically_to_plain_data() -> None:
    """Canonical water delivery produces stable adapter- and audit-safe data."""
    current = profile()

    first = current.to_dict()
    second = current.to_dict()

    assert first == second
    assert first["profile_id"] == "delivery-profile-1"
    assert first["assessed_at"] == "2026-08-03T12:00:00+00:00"
    assert first["components"][0]["delivery_type"] == "dripper"
    assert first["components"][0]["quantity"]["value"] == 4.0
    assert isinstance(first["components"], list)


def test_models_are_frozen_and_slotted() -> None:
    """Delivery state cannot be changed or extended in place."""
    current = component()
    with pytest.raises(FrozenInstanceError):
        current.__setattr__("display_name", "Changed")
    with pytest.raises((AttributeError, TypeError)):
        current.__setattr__("unexpected", "value")


@pytest.mark.parametrize("confidence", [-0.01, 1.01, float("inf"), float("nan")])
def test_delivery_fact_rejects_invalid_confidence(confidence: float) -> None:
    """Confidence must be a finite normalized fraction."""
    with pytest.raises(ValueError, match="confidence"):
        fact(1.0, confidence=confidence)


def test_unknown_facts_require_zero_confidence() -> None:
    """Unknown delivery facts cannot claim confidence."""
    with pytest.raises(ValueError, match="zero confidence"):
        fact(None, confidence=0.5)
    with pytest.raises(ValueError, match="zero confidence"):
        fact(SprayPattern.UNKNOWN, confidence=0.5)
    assert unknown().is_known is False


def test_delivery_facts_reject_raw_or_structured_provider_payloads() -> None:
    """Domain facts accept scalars and stable enums rather than provider payloads."""
    with pytest.raises(TypeError, match="plain scalar"):
        fact(b"raw data")
    with pytest.raises(TypeError, match="plain scalar"):
        fact({"provider": "payload"})


@pytest.mark.parametrize(
    "delivery_type",
    [
        WaterDeliveryType.DRIPPER,
        WaterDeliveryType.MICROJET,
        WaterDeliveryType.MISTER,
        WaterDeliveryType.SPRAY,
        WaterDeliveryType.ROTOR,
        WaterDeliveryType.BUBBLER,
        WaterDeliveryType.SUBSURFACE_DRIP,
        WaterDeliveryType.MANUAL_WATERING,
    ],
)
def test_all_required_delivery_types_are_supported(delivery_type: Any) -> None:
    """Every required automatic and manual delivery type is canonical."""
    current = component(delivery_type=delivery_type)
    assert current.delivery_type is delivery_type


def test_mixed_delivery_types_are_preserved_in_order() -> None:
    """Mixed systems remain separate components rather than one lossy type."""
    drippers = component()
    microjets = component(
        component_id="component-2",
        display_name="Shrub microjets",
        delivery_type=WaterDeliveryType.MICROJET,
        quantity= fact(6.0),
        spray_pattern=fact(SprayPattern.FULL_CIRCLE),
        radius_meters=fact(1.2),
        arc_degrees=fact(360.0),
    )
    manual = component(
        component_id="component-3",
        display_name="Manual hose watering",
        delivery_type=WaterDeliveryType.MANUAL_WATERING,
        quantity_mode=DeliveryQuantityMode.SERVED_AREA,
        quantity=fact(12.0),
        served_area_unit=AreaUnit.SQUARE_METERS,
        flow_basis=FlowBasis.MANUAL_SOURCE,
        spray_pattern=fact(SprayPattern.MANUAL),
    )
    mixed = profile(components=(drippers, microjets, manual))

    assert mixed.is_mixed is True
    assert mixed.delivery_types == (
        WaterDeliveryType.DRIPPER,
        WaterDeliveryType.MICROJET,
        WaterDeliveryType.MANUAL_WATERING,
    )


def test_repeated_components_of_one_type_are_not_reported_as_mixed() -> None:
    """Mixed means multiple delivery types, not merely multiple component groups."""
    first = component()
    second = component(component_id="component-2", display_name="Second dripper group")
    current = profile(components=(first, second))
    assert current.is_mixed is False
    assert current.delivery_types == (WaterDeliveryType.DRIPPER,)


def test_count_percentage_and_served_area_quantities_are_independent() -> None:
    """Quantity modes retain distinct units and aggregation semantics."""
    counted = component()
    percentage = component(
        component_id="component-2",
        display_name="Rotor share",
        delivery_type=WaterDeliveryType.ROTOR,
        quantity_mode=DeliveryQuantityMode.PERCENTAGE,
        quantity=fact(40.0),
    )
    served_area = component(
        component_id="component-3",
        display_name="Hand-watered bed",
        delivery_type=WaterDeliveryType.MANUAL_WATERING,
        quantity_mode=DeliveryQuantityMode.SERVED_AREA,
        quantity=fact(20.0),
        served_area_unit=AreaUnit.SQUARE_METERS,
    )
    current = profile(components=(counted, percentage, served_area))

    assert current.components[0].quantity.value == 4.0
    assert current.components[1].quantity.value == 40.0
    assert current.components[2].served_area_unit is AreaUnit.SQUARE_METERS


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"quantity": fact(0.0)}, "positive"),
        ({"quantity": fact(1.5)}, "whole number"),
        (
            {
                "quantity_mode": DeliveryQuantityMode.PERCENTAGE,
                "quantity": fact(101.0),
            },
            "cannot exceed 100",
        ),
        (
            {
                "quantity_mode": DeliveryQuantityMode.SERVED_AREA,
                "quantity": fact(10.0),
            },
            "requires served_area_unit",
        ),
    ],
)
def test_invalid_quantity_combinations_are_rejected(
    changes: dict[str, object], message: str
) -> None:
    """Counts, shares, and served areas reject impossible combinations."""
    with pytest.raises(ValueError, match=message):
        component(**changes)


def test_percentage_components_cannot_total_more_than_one_hundred() -> None:
    """Percentage groups are bounded without involving count or area groups."""
    first = component(
        quantity_mode=DeliveryQuantityMode.PERCENTAGE,
        quantity=fact(60.0),
    )
    second = component(
        component_id="component-2",
        display_name="Second share",
        quantity_mode=DeliveryQuantityMode.PERCENTAGE,
        quantity=fact(50.0),
    )
    with pytest.raises(ValueError, match="cannot total more than 100"):
        profile(components=(first, second))


def test_measured_flow_is_preferred_without_losing_nominal_flow() -> None:
    """Direct calibration takes precedence while nominal provenance remains."""
    current = component(measured_flow_liters_per_hour=fact(7.1, source="collected_volume"))

    assert current.preferred_flow_liters_per_hour == 7.1
    assert current.nominal_flow_liters_per_hour.value == 7.6
    assert current.nominal_flow_liters_per_hour.provenance.source == (
        "manufacturer_specification"
    )


def test_nominal_flow_is_used_when_measurement_is_unknown() -> None:
    """Nominal flow remains an explicit fallback rather than becoming measured data."""
    current = component()
    assert current.preferred_flow_liters_per_hour == 7.6
    assert current.measured_flow_liters_per_hour.is_known is False


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("nominal_flow_liters_per_hour", 0.0, "must be positive"),
        ("measured_flow_liters_per_hour", -1.0, "at least 0"),
        ("application_rate_mm_per_hour", 0.0, "must be positive"),
        ("radius_meters", 0.0, "must be positive"),
        ("arc_degrees", 361.0, "cannot exceed 360"),
        ("efficiency", 1.01, "cannot exceed 1"),
    ],
)
def test_physical_delivery_values_are_bounded(
    field_name: str, value: float, message: str
) -> None:
    """Impossible hydraulic and coverage values fail at construction."""
    with pytest.raises(ValueError, match=message):
        component(**{field_name: fact(value)})


def test_zero_efficiency_represents_observed_failure() -> None:
    """A known nonfunctional component may have zero efficiency."""
    current = component(efficiency=fact(0.0))
    assert current.efficiency.value == 0.0


def test_pressure_compensation_clogging_and_pattern_are_serialized() -> None:
    """Qualitative delivery characteristics retain confidence and provenance."""
    serialized = component().to_dict()
    assert serialized["pressure_compensation"]["value"] == "pressure_compensating"
    assert serialized["clogging_risk"]["value"] == "moderate"
    assert serialized["spray_pattern"]["value"] == "point_source"


@pytest.mark.parametrize(
    ("test_type", "measurement_type", "value", "unit"),
    [
        (
            CalibrationTestType.DRIP_COUNTING,
            CalibrationMeasurementType.DRIP_COUNT,
            24,
            MeasurementUnit.COUNT,
        ),
        (
            CalibrationTestType.COLLECTED_VOLUME,
            CalibrationMeasurementType.COLLECTED_VOLUME,
            125.0,
            MeasurementUnit.MILLILITERS,
        ),
        (
            CalibrationTestType.SPRAY_RADIUS,
            CalibrationMeasurementType.RADIUS,
            1.8,
            MeasurementUnit.METERS,
        ),
        (
            CalibrationTestType.SPRAY_ARC,
            CalibrationMeasurementType.ARC,
            180.0,
            MeasurementUnit.DEGREES,
        ),
        (
            CalibrationTestType.FUNCTION_INSPECTION,
            CalibrationMeasurementType.FUNCTIONAL,
            True,
            MeasurementUnit.BOOLEAN,
        ),
    ],
)
def test_guided_measurement_calibrations_complete_with_typed_results(
    test_type: Any,
    measurement_type: Any,
    value: int | float | bool,
    unit: Any,
) -> None:
    """Every measurement-based guided calibration validates its result type."""
    result = measurement(measurement_type, value, unit)
    current = calibration(
        test_type=test_type,
        state=CalibrationState.COMPLETED,
        requested_unit=unit,
        measurements=(result,),
        updated_at=LATER,
        completed_at=LATER,
    )
    assert current.state is CalibrationState.COMPLETED
    assert current.measurements == (result,)


def test_completed_photo_reference_calibration_uses_opaque_token() -> None:
    """Photo-based calibration records only opaque evidence references."""
    photo = CalibrationPhotoReference(
        photo_id="photo-1",
        opaque_reference="local-evidence:asset-42",
        captured_at=LATER,
        source="user_capture",
    )
    current = calibration(
        test_type=CalibrationTestType.PHOTO_REFERENCE,
        state=CalibrationState.COMPLETED,
        requested_unit=None,
        photo_references=(photo,),
        updated_at=LATER,
        completed_at=LATER,
    )
    assert current.photo_references[0].opaque_reference == "local-evidence:asset-42"


@pytest.mark.parametrize(
    "reference",
    [b"raw-image", bytearray(b"raw-image"), "data:image/jpeg;base64,abc"],
)
def test_photo_references_reject_embedded_image_data(reference: object) -> None:
    """No raw image bytes or data URLs can enter the domain model."""
    with pytest.raises((TypeError, ValueError), match=r"raw image bytes|embed image data"):
        CalibrationPhotoReference(
            photo_id="photo-unsafe",
            opaque_reference=reference,
            captured_at=NOW,
            source="user_capture",
        )


def test_completed_calibration_requires_matching_evidence() -> None:
    """Completion cannot be claimed without the expected evidence type."""
    with pytest.raises(ValueError, match="requires a measurement"):
        calibration(
            state=CalibrationState.COMPLETED,
            updated_at=LATER,
            completed_at=LATER,
        )
    wrong = measurement(
        CalibrationMeasurementType.RADIUS,
        1.0,
        MeasurementUnit.METERS,
    )
    with pytest.raises(ValueError, match="inconsistent with test type"):
        calibration(measurements=(wrong,))


def test_measurement_type_and_unit_must_agree() -> None:
    """Calibration results reject dimensionally invalid units."""
    with pytest.raises(ValueError, match="unit is inconsistent"):
        measurement(
            CalibrationMeasurementType.COLLECTED_VOLUME,
            100.0,
            MeasurementUnit.DEGREES,
        )
    with pytest.raises(ValueError, match="boolean"):
        measurement(
            CalibrationMeasurementType.FUNCTIONAL,
            1,
            MeasurementUnit.BOOLEAN,
        )


def test_drip_count_is_whole_and_spray_arc_is_bounded() -> None:
    """Count and angle measurements enforce their physical semantics."""
    with pytest.raises(ValueError, match="whole number"):
        measurement(
            CalibrationMeasurementType.DRIP_COUNT,
            2.5,
            MeasurementUnit.COUNT,
        )
    with pytest.raises(ValueError, match="cannot exceed 360"):
        measurement(
            CalibrationMeasurementType.ARC,
            361.0,
            MeasurementUnit.DEGREES,
        )


def test_requested_unit_must_match_calibration_type() -> None:
    """Guidance cannot request an incompatible measurement unit."""
    with pytest.raises(ValueError, match="requested_unit is inconsistent"):
        calibration(
            test_type=CalibrationTestType.SPRAY_RADIUS,
            requested_unit=MeasurementUnit.DEGREES,
        )
    with pytest.raises(ValueError, match="does not request a unit"):
        calibration(
            test_type=CalibrationTestType.PHOTO_REFERENCE,
            requested_unit=MeasurementUnit.METERS,
        )


def test_calibration_lifecycle_and_timestamps_are_consistent() -> None:
    """Calibration state retains unambiguous, ordered chronology."""
    with pytest.raises(ValueError, match="only valid for completed"):
        calibration(completed_at=LATER)
    with pytest.raises(ValueError, match="cannot follow updated_at"):
        calibration(
            state=CalibrationState.COMPLETED,
            measurements=(
                measurement(
                    CalibrationMeasurementType.COLLECTED_VOLUME,
                    100.0,
                    MeasurementUnit.MILLILITERS,
                ),
            ),
            completed_at=LATER,
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        calibration(created_at=datetime(2026, 8, 3, 12, 0))


def test_profile_cross_references_calibrations_bidirectionally() -> None:
    """Calibration evidence cannot be dangling or orphaned."""
    current_calibration = calibration()
    linked_component = component(calibration_ids=("calibration-1",))
    linked = profile(
        components=(linked_component,), calibrations=(current_calibration,)
    )
    assert linked.calibrations[0].component_id == linked.components[0].component_id

    with pytest.raises(ValueError, match="exactly match"):
        profile(calibrations=(current_calibration,))
    with pytest.raises(ValueError, match="unknown delivery component"):
        profile(
            calibrations=(replace(current_calibration, component_id="component-missing"),)
        )


def test_profile_rejects_cross_area_components_and_calibrations() -> None:
    """A profile cannot silently combine records from another landscape area."""
    with pytest.raises(ValueError, match="components must belong"):
        profile(components=(component(area_id="area-2"),))
    cross_area = calibration(area_id="area-2")
    with pytest.raises(ValueError, match="calibrations must belong"):
        profile(calibrations=(cross_area,))


def test_invalid_identifiers_are_rejected() -> None:
    """Stable identity never comes from a mutable display-name string."""
    with pytest.raises(ValueError, match="stable identifier"):
        component(component_id="Back Yard Sprays")


def test_enum_values_are_stable_public_vocabulary() -> None:
    """Serialized delivery and calibration vocabulary remains explicit."""
    assert [item.value for item in WaterDeliveryType] == [
        "dripper",
        "microjet",
        "mister",
        "spray",
        "rotor",
        "bubbler",
        "subsurface_drip",
        "manual_watering",
        "unknown",
    ]
    assert DeliveryQuantityMode.SERVED_AREA.value == "served_area"
    assert CalibrationTestType.FUNCTION_INSPECTION.value == "function_inspection"
    assert PressureCompensation.PRESSURE_COMPENSATING.value == "pressure_compensating"


def test_profile_exposes_no_execution_or_controller_surface() -> None:
    """The canonical model remains observation and calibration only."""
    current = profile()
    for name in (
        "start",
        "stop",
        "schedule",
        "execute",
        "set_duration",
        "set_rain_delay",
        "controller",
    ):
        assert not hasattr(current, name)
