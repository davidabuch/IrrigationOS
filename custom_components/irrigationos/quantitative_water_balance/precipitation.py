"""Shared deterministic effective-precipitation policy boundary."""

from __future__ import annotations

from .models import EffectivePrecipitationPolicy, WaterQuantity


def apply_effective_precipitation_policy(
    value: WaterQuantity | None,
    policy: EffectivePrecipitationPolicy | None,
) -> WaterQuantity | None:
    """Apply explicit site policy; exact zero requires no transformation policy."""
    if value is None:
        return None
    upper = value.scalar if value.scalar is not None else value.maximum
    if upper == 0:
        return WaterQuantity.millimeters(0)
    if policy is None:
        return None
    factor = policy.effective_fraction
    if value.scalar is not None:
        return WaterQuantity.millimeters(value.scalar * factor)
    return WaterQuantity(
        minimum=value.minimum * factor if value.minimum is not None else None,
        typical=value.typical * factor if value.typical is not None else None,
        maximum=value.maximum * factor if value.maximum is not None else None,
    )
