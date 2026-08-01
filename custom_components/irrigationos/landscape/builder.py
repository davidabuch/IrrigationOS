"""Build Landscape Digital Twin profiles from controller facts and user overrides."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any

from ..controllers import ControllerRegistrySnapshot, IrrigationArea
from .models import (
    IrrigationAreaProfile,
    IrrigationMethod,
    LandscapeProfile,
    PlantType,
    ProfileValue,
    ProfileValueSource,
    SoilTexture,
    SunExposure,
)

LANDSCAPE_SCHEMA_VERSION = 1


def build_landscape_profile(
    snapshot: ControllerRegistrySnapshot,
    overrides: Mapping[str, Any] | None = None,
) -> LandscapeProfile:
    """Build a canonical landscape profile from observations and stored overrides."""
    normalized_overrides = overrides or {}
    return LandscapeProfile(
        schema_version=LANDSCAPE_SCHEMA_VERSION,
        areas=tuple(
            build_area_profile(area, normalized_overrides.get(area.area_id, {}))
            for area in snapshot.areas
        ),
    )


def build_area_profile(
    area: IrrigationArea,
    override: Mapping[str, Any] | None = None,
) -> IrrigationAreaProfile:
    """Build one area profile without conflating controller and landscape facts."""
    user = override or {}
    plant_type = _user_enum(user, "plant_type", PlantType) or _derive_plant_type(area.crop_name)
    irrigation_method = _user_enum(
        user, "irrigation_method", IrrigationMethod
    ) or _derive_irrigation_method(area.nozzle_name)
    soil_texture = _user_enum(user, "soil_texture", SoilTexture) or _derive_soil_texture(
        area.soil_name
    )

    return IrrigationAreaProfile(
        area_id=area.area_id,
        display_name=_value(
            _user_text(user, "display_name") or area.name,
            user_has_value="display_name" in user,
            fallback_source=ProfileValueSource.CONTROLLER,
            fallback_confidence=100,
            user=user,
            field="display_name",
        ),
        plant_type=plant_type,
        plant_description=_value(
            _user_nullable_text(user, "plant_description", area.crop_name),
            user_has_value="plant_description" in user,
            fallback_source=(
                ProfileValueSource.CONTROLLER
                if area.crop_name is not None
                else ProfileValueSource.UNKNOWN
            ),
            fallback_confidence=60 if area.crop_name is not None else 0,
            user=user,
            field="plant_description",
        ),
        irrigation_method=irrigation_method,
        sun_exposure=_user_enum(user, "sun_exposure", SunExposure)
        or ProfileValue(SunExposure.UNKNOWN, ProfileValueSource.UNKNOWN, 0),
        slope_percent=_numeric_value(
            user,
            "slope_percent",
            fallback=None,
            fallback_source=ProfileValueSource.UNKNOWN,
            fallback_confidence=0,
            minimum=0,
            maximum=100,
        ),
        soil_texture=soil_texture,
        soil_description=_value(
            _user_nullable_text(user, "soil_description", area.soil_name),
            user_has_value="soil_description" in user,
            fallback_source=(
                ProfileValueSource.CONTROLLER
                if area.soil_name is not None
                else ProfileValueSource.UNKNOWN
            ),
            fallback_confidence=60 if area.soil_name is not None else 0,
            user=user,
            field="soil_description",
        ),
        root_depth_inches=_numeric_value(
            user,
            "root_depth_inches",
            fallback=area.root_zone_depth_inches,
            fallback_source=(
                ProfileValueSource.CONTROLLER
                if area.root_zone_depth_inches is not None
                else ProfileValueSource.UNKNOWN
            ),
            fallback_confidence=80 if area.root_zone_depth_inches is not None else 0,
            minimum=0.1,
            maximum=120,
        ),
        application_rate_inches_per_hour=_numeric_value(
            user,
            "application_rate_inches_per_hour",
            fallback=area.nozzle_inches_per_hour,
            fallback_source=(
                ProfileValueSource.CONTROLLER
                if area.nozzle_inches_per_hour is not None
                else ProfileValueSource.UNKNOWN
            ),
            fallback_confidence=85 if area.nozzle_inches_per_hour is not None else 0,
            minimum=0.01,
            maximum=20,
        ),
        distribution_efficiency=_numeric_value(
            user,
            "distribution_efficiency",
            fallback=area.efficiency,
            fallback_source=(
                ProfileValueSource.CONTROLLER
                if area.efficiency is not None
                else ProfileValueSource.UNKNOWN
            ),
            fallback_confidence=70 if area.efficiency is not None else 0,
            minimum=0.01,
            maximum=1,
        ),
    )


def _derive_plant_type(value: str | None) -> ProfileValue[PlantType]:
    if value is None:
        return ProfileValue(PlantType.UNKNOWN, ProfileValueSource.UNKNOWN, 0)
    normalized = value.casefold()
    mappings = (
        (("turf", "grass", "fescue"), PlantType.TURF_COOL_SEASON),
        (("bermuda", "zoysia", "warm season"), PlantType.TURF_WARM_SEASON),
        (("hedge", "podocarpus"), PlantType.HEDGE),
        (("tree", "avocado", "citrus"), PlantType.TREE),
        (("shrub",), PlantType.SHRUB),
        (("succulent", "cactus"), PlantType.SUCCULENT),
        (("vegetable", "garden"), PlantType.VEGETABLE),
        (("flower", "annual"), PlantType.FLOWER),
    )
    for terms, plant_type in mappings:
        if any(term in normalized for term in terms):
            return ProfileValue(plant_type, ProfileValueSource.DERIVED, 45)
    return ProfileValue(PlantType.CUSTOM, ProfileValueSource.CONTROLLER, 40)


def _derive_irrigation_method(value: str | None) -> ProfileValue[IrrigationMethod]:
    if value is None:
        return ProfileValue(IrrigationMethod.UNKNOWN, ProfileValueSource.UNKNOWN, 0)
    normalized = value.casefold()
    mappings = (
        (("rotor", "rotary"), IrrigationMethod.ROTOR),
        (("drip", "emitter"), IrrigationMethod.DRIP),
        (("bubbler",), IrrigationMethod.BUBBLER),
        (("micro",), IrrigationMethod.MICRO_SPRAY),
        (("spray", "fixed"), IrrigationMethod.SPRAY),
    )
    for terms, method in mappings:
        if any(term in normalized for term in terms):
            return ProfileValue(method, ProfileValueSource.DERIVED, 55)
    return ProfileValue(IrrigationMethod.CUSTOM, ProfileValueSource.CONTROLLER, 40)


def _derive_soil_texture(value: str | None) -> ProfileValue[SoilTexture]:
    if value is None:
        return ProfileValue(SoilTexture.UNKNOWN, ProfileValueSource.UNKNOWN, 0)
    normalized = value.casefold()
    mappings = (
        ("sandy loam", SoilTexture.SANDY_LOAM),
        ("silt loam", SoilTexture.SILT_LOAM),
        ("clay loam", SoilTexture.CLAY_LOAM),
        ("sand", SoilTexture.SAND),
        ("loam", SoilTexture.LOAM),
        ("clay", SoilTexture.CLAY),
        ("amended", SoilTexture.AMENDED),
        ("container", SoilTexture.CONTAINER),
    )
    for term, texture in mappings:
        if term in normalized:
            return ProfileValue(texture, ProfileValueSource.DERIVED, 45)
    return ProfileValue(SoilTexture.CUSTOM, ProfileValueSource.CONTROLLER, 35)


def _user_enum[E: StrEnum](
    user: Mapping[str, Any],
    field: str,
    enum_type: type[E],
) -> ProfileValue[E] | None:
    if field not in user:
        return None
    try:
        value = enum_type(user[field])
    except (TypeError, ValueError):
        return None
    return ProfileValue(value, ProfileValueSource.USER, _confidence(user, field, 100))


def _numeric_value(
    user: Mapping[str, Any],
    field: str,
    *,
    fallback: float | None,
    fallback_source: ProfileValueSource,
    fallback_confidence: int,
    minimum: float,
    maximum: float,
) -> ProfileValue[float | None]:
    if field in user:
        value = _optional_float(user[field])
        if value is not None and not minimum <= value <= maximum:
            value = None
        return ProfileValue(value, ProfileValueSource.USER, _confidence(user, field, 100))
    if fallback is None or not minimum <= fallback <= maximum:
        return ProfileValue(None, ProfileValueSource.UNKNOWN, 0)
    return ProfileValue(fallback, fallback_source, fallback_confidence)


def _value[T](
    value: T,
    *,
    user_has_value: bool,
    fallback_source: ProfileValueSource,
    fallback_confidence: int,
    user: Mapping[str, Any],
    field: str,
) -> ProfileValue[T]:
    if user_has_value:
        return ProfileValue(value, ProfileValueSource.USER, _confidence(user, field, 100))
    return ProfileValue(value, fallback_source, fallback_confidence)


def _user_text(user: Mapping[str, Any], field: str) -> str | None:
    value = user.get(field)
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _user_nullable_text(
    user: Mapping[str, Any], field: str, fallback: str | None
) -> str | None:
    if field not in user:
        return fallback
    value = user[field]
    if value is None:
        return None
    if not isinstance(value, str):
        return fallback
    stripped = value.strip()
    return stripped or None


def _confidence(user: Mapping[str, Any], field: str, default: int) -> int:
    value = user.get(f"{field}_confidence", default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return max(0, min(100, round(float(value))))


def _optional_float(value: object) -> float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None
