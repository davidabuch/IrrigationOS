"""Normalize Home Assistant scientific inputs without actuating hardware."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from math import isfinite
from typing import Any

from ..landscape import LandscapeProfile, PlantType
from ..plant_knowledge import (
    PlantCategory,
    PlantKnowledgeResolutionRequest,
    build_curated_plant_knowledge_library,
    resolve_plant_knowledge,
)
from .models import (
    AreaKnowledgeInput,
    ScientificInputSnapshot,
    ScientificInputStatus,
    WeatherInputSnapshot,
)


def build_scientific_input_snapshot(
    *,
    landscape: LandscapeProfile,
    weather_entities: Sequence[tuple[str, str, Mapping[str, Any]]],
    evaluated_at: datetime,
) -> ScientificInputSnapshot:
    """Build deterministic weather and plant-knowledge inputs for one refresh."""
    weather, weather_blockers = _resolve_weather(weather_entities, evaluated_at)
    area_knowledge = _resolve_area_knowledge(landscape)
    knowledge_blockers = tuple(
        dict.fromkeys(code for item in area_knowledge for code in item.blocker_codes)
    )
    blockers = tuple(dict.fromkeys((*weather_blockers, *knowledge_blockers)))

    if weather is None or not area_knowledge:
        status = ScientificInputStatus.BLOCKED
    elif blockers:
        status = ScientificInputStatus.PARTIAL
    else:
        status = ScientificInputStatus.READY

    return ScientificInputSnapshot(
        evaluated_at=evaluated_at,
        status=status,
        weather=weather,
        area_knowledge=area_knowledge,
        blocker_codes=blockers,
    )


def _resolve_weather(
    weather_entities: Sequence[tuple[str, str, Mapping[str, Any]]],
    evaluated_at: datetime,
) -> tuple[WeatherInputSnapshot | None, tuple[str, ...]]:
    available = tuple(
        item
        for item in weather_entities
        if item[1] not in {"unknown", "unavailable"}
    )
    if not available:
        return None, ("weather_entity_unavailable",)
    if len(available) > 1:
        return None, ("multiple_weather_entities_require_selection",)

    entity_id, condition, attributes = available[0]
    temperature = _temperature_celsius(
        attributes.get("temperature"), attributes.get("temperature_unit")
    )
    humidity = _bounded_number(attributes.get("humidity"), minimum=0, maximum=100)
    pressure = _pressure_hpa(attributes.get("pressure"), attributes.get("pressure_unit"))
    wind_speed = _wind_speed_mps(
        attributes.get("wind_speed"), attributes.get("wind_speed_unit")
    )
    wind_bearing = _bounded_number(
        attributes.get("wind_bearing"), minimum=0, maximum=360, maximum_exclusive=True
    )
    known = sum(
        value is not None
        for value in (condition or None, temperature, humidity, pressure, wind_speed, wind_bearing)
    )
    blockers: list[str] = []
    if temperature is None:
        blockers.append("weather_temperature_unavailable")
    if humidity is None:
        blockers.append("weather_humidity_unavailable")

    return (
        WeatherInputSnapshot(
            entity_id=entity_id,
            observed_at=evaluated_at,
            condition=condition or None,
            temperature_celsius=temperature,
            relative_humidity_percent=humidity,
            pressure_hpa=pressure,
            wind_speed_meters_per_second=wind_speed,
            wind_bearing_degrees=wind_bearing,
            attribution=_optional_text(attributes.get("attribution")),
            known_fact_count=known,
        ),
        tuple(blockers),
    )


def _resolve_area_knowledge(landscape: LandscapeProfile) -> tuple[AreaKnowledgeInput, ...]:
    library = build_curated_plant_knowledge_library()
    results: list[AreaKnowledgeInput] = []
    for profile in landscape.areas:
        requested_identity = (
            profile.plant_description.value or profile.display_name.value
        ).strip()
        safe_area_id = "".join(
            character if character.isalnum() or character == "_" else "_"
            for character in profile.area_id
        )
        resolution = resolve_plant_knowledge(
            library,
            PlantKnowledgeResolutionRequest(
                request_id=f"pk.request.{safe_area_id}",
                common_name=requested_identity,
                broad_category=_plant_category(profile.plant_type.value),
                country="US",
            ),
        )
        blockers = (
            ()
            if resolution.selected_profile_id is not None
            else ("plant_knowledge_profile_unresolved",)
        )
        results.append(
            AreaKnowledgeInput(
                area_id=profile.area_id,
                requested_identity=requested_identity,
                selected_profile_id=resolution.selected_profile_id,
                resolution_confidence=resolution.resolution_confidence,
                blocker_codes=blockers,
            )
        )
    return tuple(results)


def _plant_category(plant_type: PlantType) -> PlantCategory:
    return {
        PlantType.TREE: PlantCategory.TREE,
        PlantType.SHRUB: PlantCategory.SHRUB,
        PlantType.HEDGE: PlantCategory.SHRUB,
        PlantType.TURF_COOL_SEASON: PlantCategory.TURF,
        PlantType.TURF_WARM_SEASON: PlantCategory.TURF,
        PlantType.SUCCULENT: PlantCategory.SUCCULENT,
        PlantType.FLOWER: PlantCategory.HERBACEOUS,
        PlantType.VEGETABLE: PlantCategory.HERBACEOUS,
        PlantType.MIXED: PlantCategory.MIXED,
    }.get(plant_type, PlantCategory.UNKNOWN)


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _bounded_number(
    value: object,
    *,
    minimum: float,
    maximum: float,
    maximum_exclusive: bool = False,
) -> float | None:
    number = _finite_number(value)
    if number is None or number < minimum:
        return None
    if maximum_exclusive and number >= maximum:
        return None
    if not maximum_exclusive and number > maximum:
        return None
    return number


def _temperature_celsius(value: object, unit: object) -> float | None:
    number = _finite_number(value)
    if number is None:
        return None
    normalized = str(unit or "").strip().casefold()
    if normalized in {"°f", "f", "fahrenheit"}:
        return round((number - 32) * 5 / 9, 6)
    if normalized in {"k", "kelvin"}:
        return round(number - 273.15, 6)
    return number


def _pressure_hpa(value: object, unit: object) -> float | None:
    number = _finite_number(value)
    if number is None or number < 0:
        return None
    normalized = str(unit or "").strip().casefold()
    if normalized in {"inhg", "in_hg"}:
        return round(number * 33.8638866667, 6)
    if normalized in {"pa"}:
        return round(number / 100, 6)
    if normalized in {"kpa"}:
        return round(number * 10, 6)
    return number


def _wind_speed_mps(value: object, unit: object) -> float | None:
    number = _finite_number(value)
    if number is None or number < 0:
        return None
    normalized = str(unit or "").strip().casefold()
    if normalized in {"mph", "mi/h"}:
        return round(number * 0.44704, 6)
    if normalized in {"km/h", "kph"}:
        return round(number / 3.6, 6)
    if normalized in {"kn", "kt", "knot", "knots"}:
        return round(number * 0.514444, 6)
    return number


def _optional_text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None
