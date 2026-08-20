"""Durable Landscape Intelligence storage and compact summaries."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .models import HealthState, LandscapeIntelligenceProfile, summarize_health
from .zone1 import build_zone_1_landscape_intelligence

STORE_VERSION = 1


class LandscapeIntelligenceManager:
    """Own the advisory landscape-intelligence persistence boundary."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store = Store[dict[str, Any]](
            hass,
            STORE_VERSION,
            f"irrigationos.{entry_id}.landscape_intelligence",
        )
        self._zone1: LandscapeIntelligenceProfile | None = None

    async def async_initialize(self, *, initial_observed_at: datetime) -> None:
        """Seed the reviewed v1 profile without synthesizing image evidence."""
        self._zone1 = build_zone_1_landscape_intelligence(initial_observed_at)
        stored = await self._store.async_load()
        if stored is None:
            await self._store.async_save(
                {"schema_version": STORE_VERSION, "zone_1": self._zone1.to_dict()}
            )

    @property
    def zone1(self) -> LandscapeIntelligenceProfile:
        """Return the commissioned Zone 1 profile."""
        if self._zone1 is None:
            raise RuntimeError("landscape intelligence not initialized")
        return self._zone1

    def compact_summary(self, area_slot: int) -> dict[str, Any] | None:
        """Return Recorder-safe summary data without longitudinal history."""
        if area_slot != 1 or self._zone1 is None:
            return None
        profile = self._zone1
        summaries = [
            summarize_health(profile, group.plant_group_id)
            for group in profile.plant_groups
        ]
        exceptions = [
            summary
            for summary in summaries
            if summary.latest_state in {HealthState.STRESSED, HealthState.SEVERELY_STRESSED}
        ]
        return {
            "schema_version": profile.schema_version,
            "hydrozone_type": profile.hydrozone_type.value,
            "hydrozone_quality": profile.hydrozone_quality.value,
            "plant_group_count": len(profile.plant_groups),
            "health_exception_count": len(exceptions),
            "plant_factor_status": profile.plant_factor_status,
            "landscape_factor_status": profile.landscape_factor_status,
            "execution_authorized": False,
            "live_control_authorized": False,
        }

    def diagnostics(self) -> dict[str, Any]:
        """Return detailed profile evidence outside Home Assistant state attributes."""
        return {"zone_1": self.zone1.to_dict()} if self._zone1 is not None else {}
