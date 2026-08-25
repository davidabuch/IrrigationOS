"""Pure guided delivery calibration using canonical Water Delivery models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .models import (
    CalibrationMeasurement,
    CalibrationMeasurementType,
    CalibrationState,
    CalibrationTestType,
    CloggingRisk,
    DeliveryComponent,
    DeliveryEvidenceLevel,
    DeliveryFact,
    DeliveryProvenance,
    DeliveryQuantityMode,
    FlowBasis,
    GuidedCalibration,
    MeasurementUnit,
    PressureCompensation,
    SprayPattern,
    WaterDeliveryProfile,
    WaterDeliveryType,
)


@dataclass(frozen=True, slots=True)
class DeliveryComponentCalibrationRequest:
    """Explicit evidence used to add or recalibrate one physical component."""

    profile_id: str
    area_id: str
    component_id: str
    display_name: str
    delivery_type: WaterDeliveryType
    component_count: int
    flow_evidence_level: DeliveryEvidenceLevel
    observed_at: datetime
    flow_basis: FlowBasis = FlowBasis.COMPONENT_TOTAL
    flow_liters_per_hour: float | None = None
    collected_volume: float | None = None
    collected_volume_unit: MeasurementUnit | None = None
    collection_duration_seconds: int | None = None
    radius_meters: float | None = None


def calibrate_delivery_component(
    request: DeliveryComponentCalibrationRequest,
    *,
    existing_profile: WaterDeliveryProfile | None = None,
) -> WaterDeliveryProfile:
    """Build canonical evidence; never infer pressure, coverage, or runtime."""
    if (
        not isinstance(request.observed_at, datetime)
        or request.observed_at.tzinfo is None
        or request.observed_at.utcoffset() is None
    ):
        raise ValueError("delivery calibration observed_at must be timezone-aware")
    if isinstance(request.component_count, bool) or request.component_count <= 0:
        raise ValueError("component_count must be positive")
    if existing_profile is not None and (
        existing_profile.profile_id != request.profile_id
        or existing_profile.area_id != request.area_id
    ):
        raise ValueError("delivery calibration does not match existing profile")
    calibration: GuidedCalibration | None = None
    nominal_flow = _unknown_fact(request.observed_at, float)
    measured_flow = _unknown_fact(request.observed_at, float)
    if request.flow_evidence_level is DeliveryEvidenceLevel.UNKNOWN:
        if any(
            value is not None
            for value in (
                request.flow_liters_per_hour,
                request.collected_volume,
                request.collected_volume_unit,
                request.collection_duration_seconds,
            )
        ):
            raise ValueError("unknown flow cannot claim quantitative evidence")
    elif request.flow_evidence_level in {
        DeliveryEvidenceLevel.MANUFACTURER_RATED,
        DeliveryEvidenceLevel.USER_ESTIMATED,
    }:
        if any(
            value is not None
            for value in (
                request.collected_volume,
                request.collected_volume_unit,
                request.collection_duration_seconds,
            )
        ):
            raise ValueError("rated or estimated flow cannot claim a measurement")
        if request.flow_liters_per_hour is None or request.flow_liters_per_hour <= 0:
            raise ValueError("rated or estimated flow must be positive")
        nominal_flow = DeliveryFact(
            request.flow_liters_per_hour,
            0.85
            if request.flow_evidence_level is DeliveryEvidenceLevel.MANUFACTURER_RATED
            else 0.6,
            DeliveryProvenance(request.flow_evidence_level.value),
            request.observed_at,
            request.flow_evidence_level,
        )
    elif request.flow_evidence_level is DeliveryEvidenceLevel.MEASURED:
        if request.flow_liters_per_hour is not None:
            raise ValueError("measured flow must be derived from the raw measurement")
        flow = derive_collected_volume_flow_liters_per_hour(
            request.collected_volume,
            request.collected_volume_unit,
            request.collection_duration_seconds,
        )
        calibration_id = (
            f"{request.component_id}.calibration."
            f"{request.observed_at.strftime('%Y%m%dT%H%M%S%f')}"
        )
        measurement = CalibrationMeasurement(
            measurement_id=f"{calibration_id}.volume",
            measurement_type=CalibrationMeasurementType.COLLECTED_VOLUME,
            value=request.collected_volume if request.collected_volume is not None else 0,
            unit=(
                request.collected_volume_unit
                if request.collected_volume_unit is not None
                else MeasurementUnit.LITERS
            ),
            observed_at=request.observed_at,
            provenance=DeliveryProvenance("user_guided_collected_volume"),
            confidence=1.0,
        )
        calibration = GuidedCalibration(
            calibration_id=calibration_id,
            area_id=request.area_id,
            component_id=request.component_id,
            test_type=CalibrationTestType.COLLECTED_VOLUME,
            state=CalibrationState.COMPLETED,
            why_it_matters="Measured volume over time establishes component flow",
            instructions=(
                "Collect output in a marked container for the recorded duration",
            ),
            safety_note="Keep electrical equipment dry and do not leave watering unattended",
            created_at=request.observed_at,
            updated_at=request.observed_at,
            requested_unit=request.collected_volume_unit,
            timer_duration_seconds=request.collection_duration_seconds,
            measurements=(measurement,),
            completed_at=request.observed_at,
        )
        measured_flow = DeliveryFact(
            flow,
            1.0,
            DeliveryProvenance(
                "user_guided_collected_volume", detail=calibration_id
            ),
            request.observed_at,
            DeliveryEvidenceLevel.MEASURED,
        )
    else:  # pragma: no cover - closed enum
        raise ValueError("unsupported delivery evidence level")

    prior_component = None
    if existing_profile is not None:
        prior_component = next(
            (
                item
                for item in existing_profile.components
                if item.component_id == request.component_id
            ),
            None,
        )
    calibration_ids = () if prior_component is None else prior_component.calibration_ids
    if calibration is not None:
        calibration_ids = (*calibration_ids, calibration.calibration_id)
    component = DeliveryComponent(
        component_id=request.component_id,
        area_id=request.area_id,
        display_name=request.display_name,
        delivery_type=request.delivery_type,
        quantity_mode=DeliveryQuantityMode.COUNT,
        quantity=DeliveryFact(
            float(request.component_count),
            1.0,
            DeliveryProvenance("user_confirmed_component_count"),
            request.observed_at,
            DeliveryEvidenceLevel.MEASURED,
        ),
        flow_basis=request.flow_basis,
        nominal_flow_liters_per_hour=nominal_flow,
        measured_flow_liters_per_hour=measured_flow,
        application_rate_mm_per_hour=_unknown_fact(request.observed_at, float),
        radius_meters=(
            _unknown_fact(request.observed_at, float)
            if request.radius_meters is None
            else DeliveryFact(
                request.radius_meters,
                0.6,
                DeliveryProvenance("user_estimated_radius"),
                request.observed_at,
                DeliveryEvidenceLevel.USER_ESTIMATED,
            )
        ),
        arc_degrees=_unknown_fact(request.observed_at, float),
        spray_pattern=_unknown_fact(request.observed_at, SprayPattern),
        efficiency=_unknown_fact(request.observed_at, float),
        pressure_compensation=_unknown_fact(
            request.observed_at, PressureCompensation
        ),
        clogging_risk=_unknown_fact(request.observed_at, CloggingRisk),
        calibration_ids=calibration_ids,
    )
    prior_components = () if existing_profile is None else existing_profile.components
    components = tuple(
        item for item in prior_components if item.component_id != request.component_id
    )
    prior_calibrations = () if existing_profile is None else existing_profile.calibrations
    calibrations = (
        prior_calibrations if calibration is None else (*prior_calibrations, calibration)
    )
    return WaterDeliveryProfile(
        profile_id=request.profile_id,
        area_id=request.area_id,
        display_name=(
            f"Delivery for {request.area_id}"
            if existing_profile is None
            else existing_profile.display_name
        ),
        assessed_at=request.observed_at,
        components=tuple(sorted((*components, component), key=lambda item: item.component_id)),
        calibrations=tuple(
            sorted(calibrations, key=lambda item: item.calibration_id)
        ),
        notes=None if existing_profile is None else existing_profile.notes,
    )


def derive_collected_volume_flow_liters_per_hour(
    volume: float | None,
    unit: MeasurementUnit | None,
    duration_seconds: int | None,
) -> float:
    """Convert only observed volume and duration into component flow."""
    if volume is None or volume <= 0:
        raise ValueError("collected volume must be positive")
    if duration_seconds is None or duration_seconds <= 0:
        raise ValueError("collection duration must be positive")
    if unit is None:
        raise ValueError("collected volume unit is unsupported")
    liters = {
        MeasurementUnit.MILLILITERS: volume / 1000,
        MeasurementUnit.LITERS: volume,
        MeasurementUnit.US_GALLONS: volume * 3.785411784,
    }.get(unit)
    if liters is None:
        raise ValueError("collected volume unit is unsupported")
    return liters * 3600 / duration_seconds


def _unknown_fact[T](observed_at: datetime, _value_type: type[T]) -> DeliveryFact[T]:
    return DeliveryFact[T](
        None,
        0.0,
        DeliveryProvenance("unknown"),
        observed_at,
        DeliveryEvidenceLevel.UNKNOWN,
    )
