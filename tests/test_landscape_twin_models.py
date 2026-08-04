"""Behavioral tests for the canonical Landscape Digital Twin domain."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from tests.helpers import load_integration_module

MODULE = load_integration_module("landscape_twin.models")
LANDSCAPE_TWIN_SCHEMA_VERSION = MODULE.LANDSCAPE_TWIN_SCHEMA_VERSION
AreaUnit = MODULE.AreaUnit
BindingStatus = MODULE.BindingStatus
ControllerBinding = MODULE.ControllerBinding
DrainageClass = MODULE.DrainageClass
EstablishmentStage = MODULE.EstablishmentStage
FactProvenance = MODULE.FactProvenance
GoalPriority = MODULE.GoalPriority
HealthObservation = MODULE.HealthObservation
HealthStatus = MODULE.HealthStatus
HeatExposure = MODULE.HeatExposure
IrrigationDeliveryMethod = MODULE.IrrigationDeliveryMethod
IrrigationDeliveryProfile = MODULE.IrrigationDeliveryProfile
LandscapeArea = MODULE.LandscapeArea
LandscapeDigitalTwin = MODULE.LandscapeDigitalTwin
LandscapeFact = MODULE.LandscapeFact
LandscapeGoal = MODULE.LandscapeGoal
LandscapeGoalType = MODULE.LandscapeGoalType
ObservationSeverity = MODULE.ObservationSeverity
PlantGroup = MODULE.PlantGroup
PlantGroupType = MODULE.PlantGroupType
PlantQuantityMode = MODULE.PlantQuantityMode
PropertyProfile = MODULE.PropertyProfile
SoilProfile = MODULE.SoilProfile
SoilTexture = MODULE.SoilTexture
SunExposure = MODULE.SunExposure
VerificationStatus = MODULE.VerificationStatus
WaterDemandBasis = MODULE.WaterDemandBasis
WaterDemandProfile = MODULE.WaterDemandProfile
WeatherExposureProfile = MODULE.WeatherExposureProfile
WindExposure = MODULE.WindExposure

NOW = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=1)


def fact(
    value: object,
    *,
    confidence: float = 0.9,
    status: Any = VerificationStatus.UNVERIFIED,
    source: str = "user_setup",
) -> Any:
    """Build a typed landscape fact for tests."""
    return LandscapeFact(
        value=value,
        confidence=confidence,
        provenance=FactProvenance(source=source),
        verification_status=status,
        assessed_at=NOW,
    )


def unknown() -> Any:
    """Build an explicitly unknown landscape fact."""
    return fact(None, confidence=0, source="unknown")


def build_full_twin(**twin_changes: object) -> Any:
    """Build a fully linked canonical twin with all planning facts known."""
    property_profile = PropertyProfile(
        property_id="property-1",
        display_name="Home",
        timezone="America/Los_Angeles",
        area_ids=("area-1",),
        total_landscape_area_square_meters=fact(100.0),
        climate_zone=fact("10b"),
        created_at=NOW,
        updated_at=LATER,
    )
    plant = PlantGroup(
        plant_group_id="plant-group-1",
        area_id="area-1",
        display_name="Citrus trees",
        category=fact(PlantGroupType.TREE),
        quantity_mode=PlantQuantityMode.COUNT,
        quantity=fact(2.0),
        establishment_stage=fact(EstablishmentStage.MATURE),
        root_depth_meters=fact(0.8),
        common_name=fact("Lemon tree"),
        botanical_name=fact("Citrus limon"),
        canopy_diameter_meters=fact(3.0),
    )
    soil = SoilProfile(
        soil_profile_id="soil-1",
        area_id="area-1",
        texture=fact(SoilTexture.CLAY_LOAM),
        infiltration_rate_mm_per_hour=fact(12.0),
        available_water_capacity_mm_per_meter=fact(160.0),
        drainage_class=fact(DrainageClass.MODERATE),
        root_zone_depth_meters=fact(0.8),
        organic_matter_percent=fact(4.0),
        ph=fact(6.8),
        description=fact("Amended clay loam"),
    )
    delivery = IrrigationDeliveryProfile(
        delivery_profile_id="delivery-1",
        area_id="area-1",
        method=fact(IrrigationDeliveryMethod.DRIP),
        application_rate_mm_per_hour=fact(15.0),
        distribution_efficiency=fact(0.9),
        distribution_uniformity=fact(0.85),
        nominal_flow_liters_per_minute=fact(4.0),
        minimum_cycle_minutes=fact(5.0),
        maximum_cycle_minutes=fact(30.0),
    )
    exposure = WeatherExposureProfile(
        exposure_profile_id="exposure-1",
        area_id="area-1",
        sun_exposure=fact(SunExposure.FULL_SUN),
        direct_sun_hours=fact(8.0),
        wind_exposure=fact(WindExposure.MODERATE),
        heat_exposure=fact(HeatExposure.HIGH),
        shade_percent=fact(10.0),
        microclimate_notes=fact("Warm south-facing wall"),
    )
    health = HealthObservation(
        observation_id="health-1",
        area_id="area-1",
        plant_group_id="plant-group-1",
        observed_at=NOW,
        status=fact(HealthStatus.HEALTHY),
        severity=fact(ObservationSeverity.INFORMATIONAL),
        summary="No visible water stress",
        symptoms=(),
        evidence_ids=("evidence-1",),
    )
    demand = WaterDemandProfile(
        demand_profile_id="demand-1",
        area_id="area-1",
        basis=fact(WaterDemandBasis.CROP_COEFFICIENT),
        crop_coefficient=fact(0.65),
        peak_daily_demand_mm=fact(5.0),
        allowable_depletion_fraction=fact(0.4),
        seasonal_adjustment_factor=fact(1.0),
        target_soil_moisture_fraction=fact(0.7),
    )
    goal = LandscapeGoal(
        goal_id="goal-1",
        area_id="area-1",
        goal_type=LandscapeGoalType.PLANT_HEALTH,
        priority=GoalPriority.HIGH,
        description="Maintain healthy established citrus",
        target=fact("No visible water stress"),
        created_at=NOW,
    )
    binding = ControllerBinding(
        binding_id="binding-1",
        area_id="area-1",
        controller_id="controller-1",
        slot_number=4,
        provider="rachio",
        status=BindingStatus.ACTIVE,
        bound_at=NOW,
        vendor_controller_id="vendor-controller-42",
        vendor_area_id="vendor-zone-99",
    )
    area = LandscapeArea(
        area_id="area-1",
        property_id="property-1",
        display_name="Back orchard",
        area_square_meters=fact(100.0),
        slope_percent=fact(3.0),
        plant_group_ids=(plant.plant_group_id,),
        soil_profile_id=soil.soil_profile_id,
        irrigation_delivery_profile_id=delivery.delivery_profile_id,
        weather_exposure_profile_id=exposure.exposure_profile_id,
        water_demand_profile_id=demand.demand_profile_id,
        health_observation_ids=(health.observation_id,),
        goal_ids=(goal.goal_id,),
        controller_binding_ids=(binding.binding_id,),
    )
    values: dict[str, object] = {
        "twin_id": "twin-1",
        "schema_version": LANDSCAPE_TWIN_SCHEMA_VERSION,
        "property_profile": property_profile,
        "created_at": NOW,
        "updated_at": LATER,
        "areas": (area,),
        "plant_groups": (plant,),
        "soil_profiles": (soil,),
        "irrigation_delivery_profiles": (delivery,),
        "weather_exposure_profiles": (exposure,),
        "health_observations": (health,),
        "water_demand_profiles": (demand,),
        "goals": (goal,),
        "controller_bindings": (binding,),
    }
    values.update(twin_changes)
    return LandscapeDigitalTwin(**values)


def replace_area(twin: Any, **changes: object) -> Any:
    """Return a twin with its single area consistently replaced."""
    area = replace(twin.areas[0], **changes)
    return replace(twin, areas=(area,))


def test_full_twin_constructs_and_serializes_deterministically() -> None:
    """The full aggregate produces stable plain data for persistence and audit."""
    twin = build_full_twin()

    first = twin.to_dict()
    second = twin.to_dict()

    assert first == second
    assert first["schema_version"] == 1
    assert first["created_at"] == "2026-08-03T12:00:00+00:00"
    assert first["areas"][0]["area_id"] == "area-1"
    assert first["plant_groups"][0]["category"]["value"] == "tree"
    assert first["controller_bindings"][0]["provider"] == "rachio"
    assert isinstance(first["areas"], list)


def test_models_are_immutable() -> None:
    """Canonical twin state cannot be changed in place."""
    twin = build_full_twin()
    with pytest.raises(FrozenInstanceError):
        twin.__setattr__("twin_id", "different")


@pytest.mark.parametrize("confidence", [-0.01, 1.01, float("inf"), float("nan")])
def test_landscape_fact_rejects_invalid_confidence(confidence: float) -> None:
    """Confidence is a finite normalized fraction."""
    with pytest.raises(ValueError, match="confidence"):
        fact("value", confidence=confidence)


def test_unknown_fact_requires_zero_confidence() -> None:
    """Unknown values cannot carry misleading confidence."""
    with pytest.raises(ValueError, match="zero confidence"):
        fact(None, confidence=0.5)
    with pytest.raises(ValueError, match="zero confidence"):
        fact(SoilTexture.UNKNOWN, confidence=0.5)
    assert unknown().is_known is False


def test_landscape_fact_rejects_non_scalar_and_non_finite_values() -> None:
    """Durable facts cannot carry provider payloads, bytes, or non-finite values."""
    with pytest.raises(TypeError, match="plain scalar"):
        fact(b"opaque provider payload")
    with pytest.raises(ValueError, match="finite"):
        fact(float("inf"))


def test_fact_supersession_preserves_provenance_history() -> None:
    """User correction wins without destroying the original inferred value."""
    inferred = fact(SoilTexture.SANDY_LOAM, confidence=0.55, source="visual_assessment")

    corrected = inferred.supersede(
        SoilTexture.CLAY_LOAM,
        confidence=1.0,
        provenance=FactProvenance(source="user_infiltration_test"),
        verification_status=VerificationStatus.USER_CORRECTED,
        assessed_at=LATER,
    )

    assert corrected.value is SoilTexture.CLAY_LOAM
    assert corrected.effective_confidence == 1.0
    assert corrected.history[0].value is SoilTexture.SANDY_LOAM
    assert corrected.history[0].provenance.source == "visual_assessment"


def test_fact_history_cannot_postdate_current_value() -> None:
    """Revision chronology must remain auditable."""
    later_fact = LandscapeFact(
        value="future",
        confidence=0.5,
        provenance=FactProvenance(source="test"),
        verification_status=VerificationStatus.UNVERIFIED,
        assessed_at=LATER,
    )
    with pytest.raises(ValueError, match="cannot postdate"):
        LandscapeFact(
            value="current",
            confidence=0.5,
            provenance=FactProvenance(source="test"),
            verification_status=VerificationStatus.UNVERIFIED,
            assessed_at=NOW,
            history=(
                MODULE.FactRevision(
                    value=later_fact.value,
                    confidence=later_fact.confidence,
                    provenance=later_fact.provenance,
                    verification_status=later_fact.verification_status,
                    assessed_at=later_fact.assessed_at,
                ),
            ),
        )


def test_canonical_identity_is_independent_of_names_and_vendor_binding() -> None:
    """Renames and controller replacement preserve canonical property and area IDs."""
    twin = build_full_twin()
    renamed_property = replace(twin.property_profile, display_name="Renamed home")
    replacement_binding = replace(
        twin.controller_bindings[0],
        controller_id="controller-2",
        vendor_controller_id="new-vendor-controller",
        vendor_area_id="new-vendor-zone",
    )
    renamed_area = replace(twin.areas[0], display_name="Renamed orchard")
    changed = replace(
        twin,
        property_profile=renamed_property,
        areas=(renamed_area,),
        controller_bindings=(replacement_binding,),
    )

    assert changed.property_profile.property_id == "property-1"
    assert changed.areas[0].area_id == "area-1"
    assert changed.controller_bindings[0].area_id == "area-1"


def test_controller_binding_requires_valid_slot_and_retirement_lifecycle() -> None:
    """Bindings are descriptive, slot-based, and explicitly retired."""
    binding = build_full_twin().controller_bindings[0]
    with pytest.raises(ValueError, match="positive integer"):
        replace(binding, slot_number=0)
    with pytest.raises(ValueError, match="require retired_at"):
        replace(binding, status=BindingStatus.RETIRED)
    retired = replace(binding, status=BindingStatus.RETIRED, retired_at=LATER)
    assert retired.status is BindingStatus.RETIRED


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("ph", 14.1, "at most 14"),
        ("organic_matter_percent", 101, "at most 100"),
        ("root_zone_depth_meters", 0, "at least 0.01"),
    ],
)
def test_soil_profile_rejects_impossible_values(
    field_name: str, value: float, message: str
) -> None:
    """Impossible soil quantities fail at the domain boundary."""
    soil = build_full_twin().soil_profiles[0]
    with pytest.raises(ValueError, match=message):
        replace(soil, **{field_name: fact(value)})


def test_irrigation_delivery_rejects_efficiency_and_cycle_range_errors() -> None:
    """Delivery observations remain physically and internally consistent."""
    delivery = build_full_twin().irrigation_delivery_profiles[0]
    with pytest.raises(ValueError, match="at most 1"):
        replace(delivery, distribution_efficiency=fact(1.1))
    with pytest.raises(ValueError, match="cannot exceed"):
        replace(
            delivery,
            minimum_cycle_minutes=fact(40.0),
            maximum_cycle_minutes=fact(30.0),
        )


def test_weather_exposure_rejects_impossible_hours_and_shade() -> None:
    """Static exposure values reject impossible quantities."""
    exposure = build_full_twin().weather_exposure_profiles[0]
    with pytest.raises(ValueError, match="at most 24"):
        replace(exposure, direct_sun_hours=fact(25.0))
    with pytest.raises(ValueError, match="at most 100"):
        replace(exposure, shade_percent=fact(101.0))


def test_water_demand_rejects_impossible_fractions() -> None:
    """Demand fractions and coefficients are safely bounded."""
    demand = build_full_twin().water_demand_profiles[0]
    with pytest.raises(ValueError, match="at most 1"):
        replace(demand, allowable_depletion_fraction=fact(1.2))
    with pytest.raises(ValueError, match="at most 2"):
        replace(demand, crop_coefficient=fact(2.1))


def test_count_and_area_plant_groups_coexist_without_percentage_coercion() -> None:
    """Counted trees and measured shrub area keep independent quantity semantics."""
    twin = build_full_twin()
    shrubs = replace(
        twin.plant_groups[0],
        plant_group_id="plant-group-2",
        display_name="Shrub bed",
        category=fact(PlantGroupType.SHRUB),
        quantity_mode=PlantQuantityMode.AREA,
        quantity=fact(30.0),
        area_unit=AreaUnit.SQUARE_METERS,
    )
    area = replace(
        twin.areas[0], plant_group_ids=("plant-group-1", "plant-group-2")
    )
    mixed = replace(twin, areas=(area,), plant_groups=(*twin.plant_groups, shrubs))

    assert mixed.plant_groups[0].quantity_mode is PlantQuantityMode.COUNT
    assert mixed.plant_groups[1].quantity_mode is PlantQuantityMode.AREA


def test_percentage_plant_groups_cannot_exceed_area_share() -> None:
    """Percentage-based plant groups are bounded independently of counts and areas."""
    twin = build_full_twin()
    first = replace(
        twin.plant_groups[0],
        quantity_mode=PlantQuantityMode.PERCENTAGE,
        quantity=fact(60.0),
    )
    second = replace(
        first,
        plant_group_id="plant-group-2",
        display_name="Second planting",
        quantity=fact(50.0),
    )
    area = replace(
        twin.areas[0], plant_group_ids=("plant-group-1", "plant-group-2")
    )
    with pytest.raises(ValueError, match="cannot total more than 100"):
        replace(twin, areas=(area,), plant_groups=(first, second))


def test_complete_twin_reports_full_completeness() -> None:
    """A twin with every planning-critical fact known is complete."""
    report = build_full_twin().completeness

    assert report.completeness_percent == 100
    assert report.known_fact_count == report.required_fact_count
    assert report.missing_fact_paths == ()
    assert report.is_complete is True
    assert build_full_twin().is_complete is True


def test_missing_profile_reduces_completeness_with_actionable_paths() -> None:
    """Missing facts are named without inventing unsafe defaults."""
    twin = build_full_twin()
    area = replace(twin.areas[0], soil_profile_id=None)
    without_soil = replace(twin, areas=(area,), soil_profiles=())

    report = without_soil.completeness

    assert report.required_fact_count == 21
    assert report.known_fact_count == 18
    assert report.completeness_percent == 86
    assert report.missing_fact_paths == (
        "areas.area-1.soil.texture",
        "areas.area-1.soil.infiltration_rate_mm_per_hour",
        "areas.area-1.soil.available_water_capacity_mm_per_meter",
    )


def test_inactive_area_is_excluded_from_planning_completeness() -> None:
    """Unavailable or retired landscape areas do not create readiness debt."""
    twin = build_full_twin()
    inactive = replace_area(twin, active=False)

    assert inactive.completeness.required_fact_count == 2
    assert inactive.completeness_percent == 100


def test_confidence_debt_is_separate_from_missing_fact_completeness() -> None:
    """Debt measures uncertainty among known facts; missing facts remain completeness debt."""
    full = build_full_twin()
    area = replace(full.areas[0], soil_profile_id=None)
    without_soil = replace(full, areas=(area,), soil_profiles=())

    assert full.confidence_debt.known_fact_count == 21
    assert full.confidence_debt_percent == 10
    assert without_soil.confidence_debt.known_fact_count == 18
    assert without_soil.confidence_debt_percent == 10
    assert without_soil.completeness_percent < full.completeness_percent


def test_user_confirmed_fact_retires_its_confidence_debt() -> None:
    """Explicitly verified facts are trusted while their original confidence remains auditable."""
    twin = build_full_twin()
    property_profile = replace(
        twin.property_profile,
        climate_zone=fact(
            "10b",
            confidence=0.2,
            status=VerificationStatus.USER_CONFIRMED,
        ),
    )
    verified = replace(twin, property_profile=property_profile)

    report = verified.calculate_confidence_debt(threshold=0.95)

    assert verified.property_profile.climate_zone.confidence == 0.2
    assert verified.property_profile.climate_zone.effective_confidence == 1.0
    assert "property.climate_zone" not in {item.fact_path for item in report.items}


def test_low_confidence_items_are_actionable_and_threshold_is_configurable() -> None:
    """The debt report identifies known facts that most need verification."""
    twin = build_full_twin()
    area = replace(twin.areas[0], slope_percent=fact(3.0, confidence=0.4))
    changed = replace(twin, areas=(area,))

    report = changed.calculate_confidence_debt(threshold=0.8)

    assert "areas.area-1.slope_percent" in {item.fact_path for item in report.items}
    assert report.has_review_items is True
    with pytest.raises(ValueError, match="confidence"):
        changed.calculate_confidence_debt(threshold=1.1)


def test_property_area_cross_reference_must_be_exact() -> None:
    """The property index cannot omit or invent canonical areas."""
    twin = build_full_twin()
    profile = replace(twin.property_profile, area_ids=())
    with pytest.raises(ValueError, match="exactly match"):
        replace(twin, property_profile=profile)


def test_area_forward_reference_must_exist() -> None:
    """Unknown profile IDs fail rather than producing partial dangling objects."""
    twin = build_full_twin()
    area = replace(twin.areas[0], soil_profile_id="soil-missing")
    with pytest.raises(ValueError, match="unknown soil profile"):
        replace(twin, areas=(area,))


def test_orphaned_reverse_reference_is_rejected() -> None:
    """Aggregate children must appear in their owning area's stable ID indexes."""
    twin = build_full_twin()
    area = replace(twin.areas[0], health_observation_ids=())
    with pytest.raises(ValueError, match="exactly match"):
        replace(twin, areas=(area,))


def test_health_observation_plant_group_must_share_area() -> None:
    """Health findings cannot silently attach across landscape areas."""
    twin = build_full_twin()
    health = replace(twin.health_observations[0], plant_group_id="missing-plant")
    with pytest.raises(ValueError, match="unknown plant group"):
        replace(twin, health_observations=(health,))


def test_duplicate_active_area_binding_is_rejected() -> None:
    """A canonical area has at most one active controller-slot binding."""
    twin = build_full_twin()
    duplicate = replace(
        twin.controller_bindings[0],
        binding_id="binding-2",
        controller_id="controller-2",
    )
    area = replace(
        twin.areas[0], controller_binding_ids=("binding-1", "binding-2")
    )
    with pytest.raises(ValueError, match="only one active controller binding"):
        replace(
            twin,
            areas=(area,),
            controller_bindings=(*twin.controller_bindings, duplicate),
        )


def test_duplicate_active_controller_slot_is_rejected() -> None:
    """One physical slot cannot actively bind multiple canonical areas."""
    twin = build_full_twin()
    second_property = replace(
        twin.property_profile,
        area_ids=("area-1", "area-2"),
        total_landscape_area_square_meters=fact(200.0),
    )
    second_binding = replace(
        twin.controller_bindings[0], binding_id="binding-2", area_id="area-2"
    )
    second_area = replace(
        twin.areas[0],
        area_id="area-2",
        display_name="Second area",
        plant_group_ids=(),
        soil_profile_id=None,
        irrigation_delivery_profile_id=None,
        weather_exposure_profile_id=None,
        water_demand_profile_id=None,
        health_observation_ids=(),
        goal_ids=(),
        controller_binding_ids=("binding-2",),
    )
    with pytest.raises(ValueError, match="bind to only one"):
        replace(
            twin,
            property_profile=second_property,
            areas=(*twin.areas, second_area),
            controller_bindings=(*twin.controller_bindings, second_binding),
        )


def test_active_area_total_cannot_exceed_property_landscape_area() -> None:
    """Known property and area geometry must be internally possible."""
    twin = build_full_twin()
    area = replace(twin.areas[0], area_square_meters=fact(101.0))
    with pytest.raises(ValueError, match="cannot exceed"):
        replace(twin, areas=(area,))


def test_malformed_timestamps_and_identifiers_are_rejected() -> None:
    """Canonical records require stable IDs and timezone-aware chronology."""
    twin = build_full_twin()
    with pytest.raises(ValueError, match="stable identifier"):
        replace(twin.property_profile, property_id="My Home")
    with pytest.raises(ValueError, match="timezone-aware"):
        replace(twin, updated_at=datetime(2026, 8, 3, 13, 0))
    with pytest.raises(ValueError, match="unsupported"):
        replace(twin, schema_version=2)


def test_health_observation_resolution_must_follow_observation() -> None:
    """Health history cannot resolve before it was observed."""
    health = build_full_twin().health_observations[0]
    with pytest.raises(ValueError, match="cannot precede"):
        replace(health, resolved_at=NOW - timedelta(seconds=1))


def test_goal_time_window_must_be_complete_and_ordered() -> None:
    """Time-bounded landscape goals require a valid closed interval."""
    goal = build_full_twin().goals[0]
    with pytest.raises(ValueError, match="require both"):
        replace(goal, starts_at=NOW)
    with pytest.raises(ValueError, match="must follow"):
        replace(goal, starts_at=LATER, ends_at=NOW)


def test_enum_values_are_stable_canonical_vocabulary() -> None:
    """Important serialized values remain stable across providers and hardware."""
    assert VerificationStatus.USER_CORRECTED.value == "user_corrected"
    assert PlantQuantityMode.AREA.value == "area"
    assert IrrigationDeliveryMethod.SUBSURFACE_DRIP.value == "subsurface_drip"
    assert WaterDemandBasis.REFERENCE_ET.value == "reference_et"
    assert BindingStatus.RETIRED.value == "retired"


def test_twin_has_no_irrigation_command_surface() -> None:
    """The milestone remains descriptive and advisory only."""
    twin = build_full_twin()
    for method_name in ("start", "stop", "schedule", "set_rain_delay", "execute"):
        assert not hasattr(twin, method_name)
