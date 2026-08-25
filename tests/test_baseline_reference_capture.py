"""Guided baseline-reference capture remains evidence-only and fail closed."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from tests.helpers import load_integration_module

A = load_integration_module("landscape_intelligence.admission")
B = load_integration_module("landscape_intelligence.baseline_reference")
S = load_integration_module("landscape_intelligence.baseline_scaling")
C = load_integration_module("landscape_intelligence.commissioning")
M = load_integration_module("landscape_intelligence.models")
ONBOARDING = load_integration_module("landscape_intelligence.onboarding")
P = load_integration_module("landscape_intelligence.persistence")
W = load_integration_module("weather.models")

NOW = datetime(2026, 8, 24, 18, tzinfo=UTC)


def _fact(value: object, observed_at: datetime, *, confidence: float = 0.9) -> Any:
    return W.WeatherFact(
        value=value,
        confidence=confidence,
        provenance=W.WeatherProvenance(
            "normalized.synthetic.station", W.WeatherSourceType.STATION
        ),
        verification_status=W.WeatherVerificationStatus.PROVIDER_VALIDATED,
        observed_at=observed_at,
        quality=W.WeatherQualityMetadata(W.WeatherQualityStatus.GOOD),
    )


def _facts(observed_at: datetime, *, et0: float = 0.2, rain: float = 0.0) -> Any:
    unknown = W.WeatherFact(
        value=None,
        confidence=0,
        provenance=W.WeatherProvenance("synthetic", W.WeatherSourceType.OTHER),
        verification_status=W.WeatherVerificationStatus.UNVERIFIED,
        observed_at=observed_at,
        quality=W.WeatherQualityMetadata(
            W.WeatherQualityStatus.UNAVAILABLE, reason="not used by capture fixture"
        ),
    )
    values = {name: unknown for name in W.EnvironmentalWeatherFacts.__dataclass_fields__}
    values["reference_evapotranspiration_mm"] = _fact(et0, observed_at)
    values["precipitation_mm"] = _fact(rain, observed_at)
    values["air_temperature_celsius"] = _fact(23.7, observed_at)
    return W.EnvironmentalWeatherFacts(**values)


def _observations(
    *,
    hours: int = 24,
    rain_hour: int | None = None,
    missing_hour: int | None = None,
) -> Any:
    start = NOW - timedelta(hours=hours)
    records = tuple(
        W.HistoricalWeatherObservation(
            f"observation.{index}",
            "location.synthetic",
            start + timedelta(hours=index),
            start + timedelta(hours=index, minutes=1),
            _facts(
                start + timedelta(hours=index),
                rain=1.0 if rain_hour == index else 0.0,
            ),
        )
        for index in range(hours)
        if index != missing_hour
    )
    return W.ObservationWindow(
        "window.synthetic", "location.synthetic", start, NOW, records
    )


def _profile(*, reference: Any = None) -> Any:
    baseline = C.UserCalibratedBaseline(
        720,
        (75 - 32) * 5 / 9,
        0,
        "representative dry day",
        NOW - timedelta(days=30),
        M.Confidence.HIGH,
        reference,
    )
    return ONBOARDING.map_zone_onboarding(
        ONBOARDING.ZoneOnboardingRequest(
            C.CanonicalZoneIdentity("property.unrelated", "zone.baseline", 2, 8),
            "Synthetic baseline zone",
            C.ZoneDemandSourceMode.USER_CALIBRATED_BASELINE,
            NOW - timedelta(days=30),
            calibrated_baseline=baseline,
        )
    )


def _request(profile: Any, **changes: Any) -> Any:
    values = {
        "identity": profile.identity,
        "expected_baseline_runtime_seconds": 720,
        "period_hours": 24,
        "representative_dry_condition_confirmed": True,
        "replace_existing_reference_confirmed": False,
        "captured_at": NOW,
    }
    values.update(changes)
    return B.CaptureBaselineReferenceRequest(**values)


def _capture(profile: Any, observations: Any, **request_changes: Any) -> Any:
    return B.capture_baseline_environmental_reference(
        profile,
        A.assess_commissioning(profile),
        _request(profile, **request_changes),
        observations=observations,
    )


def test_valid_dry_capture_preserves_exact_normalized_et0_and_scales_immediately() -> None:
    profile = _profile()
    result = _capture(profile, _observations())
    assert result.status is B.BaselineReferenceCaptureStatus.READY
    assert result.proposed_reference.reference_et0_mm == pytest.approx(4.8)
    assert result.proposed_reference.period_hours == 24
    assert result.proposed_reference.observed_air_temperature_celsius == pytest.approx(23.7)
    assert result.proposed_reference.capture_method.value == "observed_environment_capture"
    assert result.execution_authorized is False
    assert result.live_control_authorized is False

    updated = B.apply_baseline_reference_capture(profile, result)
    scaling = S.assess_baseline_environmental_scaling(
        updated,
        A.assess_commissioning(updated),
        observations=_observations(),
        forecast=None,
        generated_at=NOW,
    )
    assert scaling.status is S.BaselineScalingStatus.READY
    assert scaling.scaling_factor == 1
    assert scaling.advisory_runtime_seconds == 720


def test_supported_48_hour_reference_uses_the_same_exact_period_as_scaling() -> None:
    profile = _profile()
    result = _capture(
        profile,
        _observations(hours=48),
        period_hours=48,
    )
    assert result.status is B.BaselineReferenceCaptureStatus.READY
    assert result.proposed_reference.reference_et0_mm == pytest.approx(9.6)
    assert result.proposed_reference.period_hours == 48


@pytest.mark.parametrize(
    ("observations", "captured_at", "blocker"),
    [
        (None, NOW, "environmental_observations_unavailable"),
        (_observations(missing_hour=5), NOW, "reference_period_incomplete"),
        (_observations(), NOW + timedelta(hours=7), "environmental_observations_stale"),
        (_observations(rain_hour=5), NOW, "rainy_period_not_valid_dry_reference"),
    ],
)
def test_capture_fails_closed_for_missing_stale_incomplete_or_rainy_evidence(
    observations: Any, captured_at: datetime, blocker: str
) -> None:
    result = _capture(_profile(), observations, captured_at=captured_at)
    assert result.status is B.BaselineReferenceCaptureStatus.BLOCKED
    assert blocker in result.blocker_codes
    assert result.proposed_reference is None


def test_capture_requires_admitted_unambiguous_baseline_but_not_plant_identity() -> None:
    profile = _profile()
    low_baseline = profile.demand_sources[0].calibrated_baseline
    low_profile = replace(
        profile,
        demand_sources=(
            C.ZoneDemandSource(
                profile.demand_sources[0].source_id,
                C.ZoneDemandSourceMode.USER_CALIBRATED_BASELINE,
                calibrated_baseline=C.UserCalibratedBaseline(
                    low_baseline.runtime_seconds,
                    low_baseline.reference_air_temperature_celsius,
                    0,
                    "dry",
                    low_baseline.calibrated_at,
                    M.Confidence.LOW,
                ),
            ),
        ),
    )
    blocked = _capture(low_profile, _observations())
    assert "baseline_not_admissible" in blocked.blocker_codes
    assert profile.landscape_profile.plant_groups == ()


def test_recalibration_requires_confirmation_and_preserves_reference_history() -> None:
    old = C.BaselineEnvironmentalReference(
        4.0,
        24,
        NOW - timedelta(days=30),
        "normalized.old.station",
        M.Confidence.HIGH,
    )
    profile = _profile(reference=old)
    blocked = _capture(profile, _observations())
    assert "reference_replacement_not_confirmed" in blocked.blocker_codes
    result = _capture(
        profile,
        _observations(),
        replace_existing_reference_confirmed=True,
    )
    updated = B.apply_baseline_reference_capture(profile, result)
    baseline = updated.demand_sources[0].calibrated_baseline
    assert baseline.reference_history == (old,)
    assert baseline.environmental_reference != old

    repeated = _capture(
        updated,
        _observations(),
        captured_at=NOW + timedelta(minutes=5),
        replace_existing_reference_confirmed=True,
    )
    assert B.apply_baseline_reference_capture(updated, repeated) == updated

    zone1 = load_integration_module(
        "landscape_intelligence.zone1"
    ).build_zone_1_commissioning_profile(NOW)
    payload = P.build_store_payload(
        (zone1, updated),
        (),
        legacy_zone1=zone1.to_landscape_intelligence_profile().to_dict(),
    )
    restored = P.restore_store_payload(payload, fallback_zone1=zone1)
    restored_profile = next(
        zone for zone in restored.zones if zone.identity == updated.identity
    )
    restored_baseline = restored_profile.demand_sources[0].calibrated_baseline
    assert restored_baseline.to_dict() == baseline.to_dict()
