"""Durable Landscape Intelligence storage and compact summaries."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .commissioning import CommissionedZoneProfile
from .factor_resolution import ZoneFactorResolution, resolve_zone_factor
from .models import HealthState, LandscapeIntelligenceProfile, summarize_health
from .zone1 import build_zone_1_commissioning_profile
from .zone1_factor_evidence import zone_1_factor_evidence

STORE_VERSION = 1


class LandscapeIntelligenceManager:
    """Own the advisory landscape-intelligence persistence boundary."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store = Store[dict[str, Any]](
            hass,
            STORE_VERSION,
            f"irrigationos.{entry_id}.landscape_intelligence",
        )
        self._zones: dict[int, CommissionedZoneProfile] = {}
        self._factor_resolutions: dict[int, ZoneFactorResolution] = {}

    async def async_initialize(self, *, initial_observed_at: datetime) -> None:
        """Seed the reviewed v1 profile without synthesizing image evidence."""
        zone1 = build_zone_1_commissioning_profile(initial_observed_at)
        self._zones = {1: zone1}
        self._factor_resolutions = {
            1: resolve_zone_factor(
                zone1.to_landscape_intelligence_profile(), zone_1_factor_evidence()
            )
        }
        stored = await self._store.async_load()
        if stored is None:
            await self._store.async_save(
                {
                    "schema_version": STORE_VERSION,
                    "zone_1": zone1.to_landscape_intelligence_profile().to_dict(),
                    "commissioned_zones": [zone1.to_dict()],
                }
            )

    @property
    def zone1(self) -> LandscapeIntelligenceProfile:
        """Return the commissioned Zone 1 profile."""
        zone = self._zones.get(1)
        if zone is None:
            raise RuntimeError("landscape intelligence not initialized")
        return zone.to_landscape_intelligence_profile()

    @property
    def commissioned_zones(self) -> tuple[CommissionedZoneProfile, ...]:
        """Return generic commissioned zones in deterministic slot order."""
        return tuple(self._zones[slot] for slot in sorted(self._zones))

    def compact_summary(self, area_slot: int) -> dict[str, Any] | None:
        """Return Recorder-safe summary data without longitudinal history."""
        commissioned = self._zones.get(area_slot)
        if commissioned is None:
            return None
        profile = commissioned.to_landscape_intelligence_profile()
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
            "factor_resolution_status": (
                None
                if area_slot not in self._factor_resolutions
                else self._factor_resolutions[area_slot].status.value
            ),
            "landscape_factor_status": profile.landscape_factor_status,
            "execution_authorized": False,
            "live_control_authorized": False,
        }

    def diagnostics(self) -> dict[str, Any]:
        """Return detailed profile evidence outside Home Assistant state attributes."""
        if not self._zones:
            return {}
        return {
            "zone_1": self.zone1.to_dict(),
            "commissioned_zones": [zone.to_dict() for zone in self.commissioned_zones],
            "zone_1_factor_resolution": (
                None
                if 1 not in self._factor_resolutions
                else self._factor_resolutions[1].to_dict()
            ),
        }
