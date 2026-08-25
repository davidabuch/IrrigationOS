"""Strict plain-data restoration for canonical Water Delivery evidence."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from typing import Any, overload

from .models import (
    ApproximateFlowRange,
    AreaUnit,
    CalibrationMeasurement,
    CalibrationMeasurementType,
    CalibrationPhotoReference,
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


def water_delivery_profile_from_dict(value: object) -> WaterDeliveryProfile:
    """Restore deterministic canonical delivery evidence without provider payloads."""
    item = _mapping(value)
    return WaterDeliveryProfile(
        profile_id=str(item["profile_id"]),
        area_id=str(item["area_id"]),
        display_name=str(item["display_name"]),
        assessed_at=_datetime(item["assessed_at"]),
        components=tuple(
            _component(component) for component in _sequence(item["components"])
        ),
        calibrations=tuple(
            _calibration(calibration)
            for calibration in _sequence(item.get("calibrations", []))
        ),
        notes=None if item.get("notes") is None else str(item["notes"]),
    )


def _component(value: object) -> DeliveryComponent:
    item = _mapping(value)
    served_area = item.get("served_area_unit")
    flow_range = item.get("approximate_flow_range")
    return DeliveryComponent(
        component_id=str(item["component_id"]),
        area_id=str(item["area_id"]),
        display_name=str(item["display_name"]),
        delivery_type=WaterDeliveryType(str(item["delivery_type"])),
        quantity_mode=DeliveryQuantityMode(str(item["quantity_mode"])),
        quantity=_fact(item["quantity"], float),
        flow_basis=FlowBasis(str(item["flow_basis"])),
        nominal_flow_liters_per_hour=_fact(
            item["nominal_flow_liters_per_hour"], float
        ),
        measured_flow_liters_per_hour=_fact(
            item["measured_flow_liters_per_hour"], float
        ),
        application_rate_mm_per_hour=_fact(item["application_rate_mm_per_hour"], float),
        radius_meters=_fact(item["radius_meters"], float),
        arc_degrees=_fact(item["arc_degrees"], float),
        spray_pattern=_fact(item["spray_pattern"], SprayPattern),
        efficiency=_fact(item["efficiency"], float),
        pressure_compensation=_fact(
            item["pressure_compensation"], PressureCompensation
        ),
        clogging_risk=_fact(item["clogging_risk"], CloggingRisk),
        calibration_ids=tuple(str(value) for value in _sequence(item.get("calibration_ids", []))),
        served_area_unit=None if served_area is None else AreaUnit(str(served_area)),
        manufacturer=None if item.get("manufacturer") is None else str(item["manufacturer"]),
        model=None if item.get("model") is None else str(item["model"]),
        approximate_flow_range=(
            None if flow_range is None else _flow_range(flow_range)
        ),
        emitter_class=(
            None if item.get("emitter_class") is None else str(item["emitter_class"])
        ),
        plants_per_emitter=_optional_integer(item.get("plants_per_emitter")),
        visual_assessment_ids=tuple(
            str(value) for value in _sequence(item.get("visual_assessment_ids", []))
        ),
        visual_evidence_ids=tuple(
            str(value) for value in _sequence(item.get("visual_evidence_ids", []))
        ),
    )


def _flow_range(value: object) -> ApproximateFlowRange:
    item = _mapping(value)
    provenance = _mapping(item["provenance"])
    return ApproximateFlowRange(
        minimum_liters_per_hour=float(item["minimum_liters_per_hour"]),
        maximum_liters_per_hour=float(item["maximum_liters_per_hour"]),
        reference_id=str(item["reference_id"]),
        confidence=float(item["confidence"]),
        provenance=DeliveryProvenance(
            source=str(provenance["source"]),
            detail=None if provenance.get("detail") is None else str(provenance["detail"]),
        ),
        assessed_at=_datetime(item["assessed_at"]),
    )


@overload
def _fact(value: object, converter: type[float]) -> DeliveryFact[float]: ...


@overload
def _fact(value: object, converter: type[SprayPattern]) -> DeliveryFact[SprayPattern]: ...


@overload
def _fact(
    value: object, converter: type[PressureCompensation]
) -> DeliveryFact[PressureCompensation]: ...


@overload
def _fact(value: object, converter: type[CloggingRisk]) -> DeliveryFact[CloggingRisk]: ...


def _fact(
    value: object, converter: Callable[[str], StrEnum] | type[float]
) -> DeliveryFact[Any]:
    item = _mapping(value)
    raw = item.get("value")
    converted: object
    if raw is None:
        converted = None
    elif converter is float:
        if isinstance(raw, bool) or not isinstance(raw, int | float):
            raise ValueError("numeric delivery fact must be a plain number")
        converted = float(raw)
    else:
        converted = converter(str(raw))
    provenance = _mapping(item["provenance"])
    return DeliveryFact(
        value=converted,
        confidence=float(item["confidence"]),
        provenance=DeliveryProvenance(
            source=str(provenance["source"]),
            detail=(
                None if provenance.get("detail") is None else str(provenance["detail"])
            ),
        ),
        assessed_at=_datetime(item["assessed_at"]),
        evidence_level=DeliveryEvidenceLevel(
            str(item.get("evidence_level", DeliveryEvidenceLevel.UNKNOWN.value))
        ),
    )


def _calibration(value: object) -> GuidedCalibration:
    item = _mapping(value)
    requested_unit = item.get("requested_unit")
    completed_at = item.get("completed_at")
    return GuidedCalibration(
        calibration_id=str(item["calibration_id"]),
        area_id=str(item["area_id"]),
        component_id=str(item["component_id"]),
        test_type=CalibrationTestType(str(item["test_type"])),
        state=CalibrationState(str(item["state"])),
        why_it_matters=str(item["why_it_matters"]),
        instructions=tuple(str(value) for value in _sequence(item["instructions"])),
        safety_note=str(item["safety_note"]),
        created_at=_datetime(item["created_at"]),
        updated_at=_datetime(item["updated_at"]),
        requested_unit=(
            None if requested_unit is None else MeasurementUnit(str(requested_unit))
        ),
        timer_duration_seconds=_optional_integer(item.get("timer_duration_seconds")),
        measurements=tuple(
            _measurement(measurement)
            for measurement in _sequence(item.get("measurements", []))
        ),
        photo_references=tuple(
            _photo(photo) for photo in _sequence(item.get("photo_references", []))
        ),
        completed_at=None if completed_at is None else _datetime(completed_at),
    )


def _measurement(value: object) -> CalibrationMeasurement:
    item = _mapping(value)
    measurement_type = CalibrationMeasurementType(str(item["measurement_type"]))
    raw = item["value"]
    if measurement_type is CalibrationMeasurementType.FUNCTIONAL:
        if not isinstance(raw, bool):
            raise ValueError("functional measurement must be boolean")
        measurement_value: int | float | bool = raw
    else:
        if isinstance(raw, bool) or not isinstance(raw, int | float):
            raise ValueError("physical measurement must be numeric")
        measurement_value = float(raw)
    provenance = _mapping(item["provenance"])
    return CalibrationMeasurement(
        measurement_id=str(item["measurement_id"]),
        measurement_type=measurement_type,
        value=measurement_value,
        unit=MeasurementUnit(str(item["unit"])),
        observed_at=_datetime(item["observed_at"]),
        provenance=DeliveryProvenance(
            str(provenance["source"]),
            None if provenance.get("detail") is None else str(provenance["detail"]),
        ),
        confidence=float(item["confidence"]),
    )


def _photo(value: object) -> CalibrationPhotoReference:
    item = _mapping(value)
    return CalibrationPhotoReference(
        photo_id=str(item["photo_id"]),
        opaque_reference=str(item["opaque_reference"]),
        captured_at=_datetime(item["captured_at"]),
        source=str(item["source"]),
        note=None if item.get("note") is None else str(item["note"]),
    )


def _mapping(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("water delivery persistence value must be a mapping")
    return value


def _sequence(value: object) -> list[object]:
    if not isinstance(value, list):
        raise ValueError("water delivery persistence value must be a list")
    return value


def _datetime(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("water delivery timestamp must be ISO text")
    return datetime.fromisoformat(value)


def _optional_integer(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("delivery duration must be an integer")
    return value
