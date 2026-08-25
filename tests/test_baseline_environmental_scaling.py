"""Focused tests for advisory ET0 baseline scaling."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from tests.helpers import load_integration_module

A = load_integration_module("landscape_intelligence.admission")
B = load_integration_module("landscape_intelligence.baseline_scaling")
C = load_integration_module("landscape_intelligence.commissioning")
E = load_integration_module("landscape_intelligence.editing")
M = load_integration_module("landscape_intelligence.models")
ONBOARDING = load_integration_module("landscape_intelligence.onboarding")
Q = load_integration_module("quantitative_water_balance.models")
P = load_integration_module("landscape_intelligence.persistence")
W = load_integration_module("weather.models")

NOW = datetime(2026, 8, 24, 18, tzinfo=UTC)


def _fact(value: object, observed_at: datetime, *, source: str = "synthetic.station") -> Any:
    return W.WeatherFact(
        value=value,
        confidence=0.9,
        provenance=W.WeatherProvenance(source, W.WeatherSourceType.STATION),
        verification_status=W.WeatherVerificationStatus.PROVIDER_VALIDATED,
        observed_at=observed_at,
        quality=W.WeatherQualityMetadata(W.WeatherQualityStatus.GOOD),
    )


def _facts(
    observed_at: datetime, et0: float, rain: float, *, source: str = "synthetic.station"
) -> Any:
    unknown = W.WeatherFact(
        value=None,
        confidence=0,
        provenance=W.WeatherProvenance("synthetic", W.WeatherSourceType.OTHER),
        verification_status=W.WeatherVerificationStatus.UNVERIFIED,
        observed_at=observed_at,
        quality=W.WeatherQualityMetadata(
            W.WeatherQualityStatus.UNAVAILABLE, reason="not used by this fixture"
        ),
    )
    values = {name: unknown for name in W.EnvironmentalWeatherFacts.__dataclass_fields__}
    values["air_temperature_celsius"] = _fact(23.8889, observed_at, source=source)
    values["precipitation_mm"] = _fact(rain, observed_at, source=source)
    values["reference_evapotranspiration_mm"] = _fact(et0, observed_at, source=source)
    return W.EnvironmentalWeatherFacts(**values)


def _observations(
    et0: tuple[float, float],
    rain: tuple[float, float] = (0, 0),
    *,
    source: str = "synthetic.station",
) -> Any:
    start = NOW - timedelta(hours=2)
    records = tuple(
        W.HistoricalWeatherObservation(
            f"obs.{index}",
            "location.synthetic",
            start + timedelta(hours=index),
            start + timedelta(hours=index, seconds=10),
            _facts(
                start + timedelta(hours=index),
                et0[index],
                rain[index],
                source=source,
            ),
        )
        for index in range(2)
    )
    return W.ObservationWindow(
        "window.synthetic", "location.synthetic", start, NOW, records
    )


def _forecast(total_rain: float, *, generated_at: datetime = NOW) -> Any:
    valid_from = NOW + timedelta(hours=1)
    record = W.HourlyWeatherForecast(
        "forecast.synthetic",
        "location.synthetic",
        generated_at,
        valid_from,
        valid_from + timedelta(hours=1),
        _facts(valid_from, 0, total_rain),
    )
    return W.ForecastWindow(
        "forecast.window.synthetic",
        "location.synthetic",
        generated_at,
        valid_from,
        valid_from + timedelta(hours=1),
        hourly_forecasts=(record,),
    )


def _profile(
    *,
    reference_et0: float | None = 4.0,
    baseline_confidence: Any = M.Confidence.HIGH,
) -> Any:
    reference = (
        None
        if reference_et0 is None
        else C.BaselineEnvironmentalReference(
            reference_et0, 2, NOW - timedelta(days=30), "user calibration", M.Confidence.HIGH
        )
    )
    baseline = C.UserCalibratedBaseline(
        720,
        (75 - 32) * 5 / 9,
        0,
        "dry reference",
        NOW - timedelta(days=30),
        baseline_confidence,
        reference,
    )
    return ONBOARDING.map_zone_onboarding(
        ONBOARDING.ZoneOnboardingRequest(
            C.CanonicalZoneIdentity("property.synthetic", "zone.baseline", 1, 7),
            "Unrelated baseline zone",
            C.ZoneDemandSourceMode.USER_CALIBRATED_BASELINE,
            NOW - timedelta(days=30),
            calibrated_baseline=baseline,
        )
    )


def _assess(
    observations: Any,
    *,
    profile: Any | None = None,
    forecast: Any = None,
    precipitation_policy: Any = None,
    generated_at: datetime = NOW,
) -> Any:
    profile = profile or _profile()
    return B.assess_baseline_environmental_scaling(
        profile,
        A.assess_commissioning(profile),
        observations=observations,
        forecast=forecast,
        generated_at=generated_at,
        effective_precipitation_policy=precipitation_policy,
    )


def test_reference_like_high_and_low_demand_use_et0_ratio() -> None:
    reference = _assess(_observations((2, 2)))
    high = _assess(_observations((3, 3)))
    low = _assess(_observations((1.5, 1.5)))

    assert reference.scaling_factor == 1
    assert reference.advisory_runtime_seconds == 720
    assert high.raw_demand_ratio == 1.5
    assert high.scaling_factor == 1.5
    assert low.raw_demand_ratio == 0.75
    assert low.scaling_factor == 0.75


def test_policy_bounds_extreme_environmental_samples() -> None:
    high = _assess(_observations((10, 10)))
    low = _assess(_observations((0.1, 0.1)))
    assert high.scaling_factor == 1.5
    assert low.scaling_factor == 0.5
    assert "environmental_scaling_bounded_by_policy" in high.advisory_codes


def test_recent_effective_rain_can_hold_but_requires_explicit_policy() -> None:
    observations = _observations((1, 1), (2, 2))
    withheld = _assess(observations)
    policy = Q.EffectivePrecipitationPolicy("policy.synthetic", 0.8, 0.8, "site_policy")
    held = _assess(observations, precipitation_policy=policy)

    assert "effective_precipitation_policy_unavailable" in withheld.blocker_codes
    assert held.status is B.BaselineScalingStatus.PRECIPITATION_HOLD
    assert held.advisory_runtime_seconds == 0


def test_forecast_hold_is_separate_and_trace_rain_does_not_hold() -> None:
    policy = Q.EffectivePrecipitationPolicy("policy.synthetic", 0.8, 0.8, "site_policy")
    held = _assess(
        _observations((2, 2)),
        forecast=_forecast(8),
        precipitation_policy=policy,
    )
    trace = _assess(
        _observations((2, 2)),
        forecast=_forecast(1),
        precipitation_policy=policy,
    )
    assert held.status is B.BaselineScalingStatus.FORECAST_HOLD
    assert held.advisory_runtime_seconds is None
    assert trace.status is B.BaselineScalingStatus.READY
    assert trace.advisory_runtime_seconds == 720


def test_missing_stale_and_reference_evidence_fail_closed() -> None:
    missing = _assess(None)
    stale = _assess(_observations((2, 2)), generated_at=NOW + timedelta(hours=7))
    no_reference = _assess(_observations((2, 2)), profile=_profile(reference_et0=None))

    assert missing.status is B.BaselineScalingStatus.SCALING_WITHHELD
    assert "current_environmental_evidence_unavailable" in missing.blocker_codes
    assert stale.status is B.BaselineScalingStatus.STALE_ENVIRONMENTAL_DATA
    assert no_reference.advisory_runtime_seconds is None
    assert "reference_et0_unavailable" in no_reference.blocker_codes


def test_baseline_mode_needs_no_plant_identity_and_never_authorizes_control() -> None:
    result = _assess(_observations((2, 2)))
    assert result.status is B.BaselineScalingStatus.READY
    assert result.identity.zone_id == "zone.baseline"
    assert result.execution_authorized is False
    assert result.live_control_authorized is False
    assert result.to_dict() == result.to_dict()
    assert all("provider" not in item.source for item in result.evidence)


def test_nonadmissible_baseline_is_withheld() -> None:
    result = _assess(
        _observations((2, 2)),
        profile=_profile(baseline_confidence=M.Confidence.LOW),
    )
    assert result.status is B.BaselineScalingStatus.INSUFFICIENT_EVIDENCE
    assert "baseline_not_admissible" in result.blocker_codes
    assert result.advisory_runtime_seconds is None


def test_unresolved_plant_conflict_does_not_override_valid_baseline_path() -> None:
    baseline_profile = _profile()
    baseline = baseline_profile.demand_sources[0].calibrated_baseline
    manual = ONBOARDING.ManualPlantOnboardingInput(
        "plant.primary",
        "Citrus",
        "Citrus spp.",
        M.EstablishmentState.ESTABLISHED,
        NOW,
    )
    visual = ONBOARDING.ApprovedVisualPlantFinding(
        "plant.primary",
        "assessment.synthetic",
        ("evidence.synthetic",),
        "Avocado",
        "Persea americana",
        M.Confidence.MODERATE,
        M.EstablishmentState.ESTABLISHED,
        NOW,
    )
    conflicted = ONBOARDING.map_zone_onboarding(
        ONBOARDING.ZoneOnboardingRequest(
            baseline_profile.identity,
            "Conflicted hybrid",
            C.ZoneDemandSourceMode.HYBRID,
            NOW,
            manual_plants=(manual,),
            visual_findings=(visual,),
            calibrated_baseline=baseline,
        )
    )
    commissioning = A.assess_commissioning(conflicted)
    assert "commissioning_conflict_unresolved" in commissioning.blocker_codes
    result = B.assess_baseline_environmental_scaling(
        conflicted,
        commissioning,
        observations=_observations((2, 2)),
        forecast=None,
        generated_at=NOW,
    )
    assert result.status is B.BaselineScalingStatus.READY


def test_normalized_weather_source_is_provider_independent() -> None:
    first = _assess(_observations((2, 2), source="normalized.source.a"))
    second = _assess(_observations((2, 2), source="normalized.source.b"))
    assert first.scaling_factor == second.scaling_factor == 1
    assert first.advisory_runtime_seconds == second.advisory_runtime_seconds == 720
    assert first.evidence[0].source != second.evidence[0].source


def test_review_carries_bounded_advisory_summary_without_authority() -> None:
    profile = _profile()
    scaling = _assess(_observations((2, 2)), profile=profile)
    review = E.build_commissioning_review(
        profile, baseline_scaling_assessment=scaling
    )
    assert review.baseline_scaling_assessment == scaling
    assert review.execution_authorized is False
    assert len(str(review.to_dict())) < 20_000


def test_reference_evidence_round_trip_and_schema_three_migration() -> None:
    profile = _profile()
    restored = P.commissioned_zone_from_dict(profile.to_dict())
    baseline = restored.demand_sources[0].calibrated_baseline
    assert baseline is not None
    assert baseline.environmental_reference is not None
    assert baseline.environmental_reference.reference_et0_mm == 4

    legacy = profile.to_dict()
    legacy["schema_version"] = 3
    legacy["demand_sources"][0]["calibrated_baseline"].pop(
        "environmental_reference"
    )
    migrated = P.commissioned_zone_from_dict(legacy)
    migrated_baseline = migrated.demand_sources[0].calibrated_baseline
    assert migrated.schema_version == 4
    assert migrated_baseline is not None
    assert migrated_baseline.environmental_reference is None
