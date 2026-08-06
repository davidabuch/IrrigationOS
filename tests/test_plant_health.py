"""Behavioral tests for Plant Health foundation and engine."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from typing import Any

import pytest

from tests.helpers import load_integration_module
from tests.test_plant_stress_models import aggregate

HEALTH = load_integration_module("plant_health")
NOW = datetime(2026, 8, 5, 18, 0, tzinfo=UTC)


def evidence(
    evidence_id: str,
    indicator: Any,
    severity: Any,
    *,
    confidence: float = 0.9,
) -> Any:
    return HEALTH.PlantHealthEvidence(
        evidence_id=evidence_id,
        kind=HEALTH.PlantHealthEvidenceKind.MANUAL_OBSERVATION,
        indicator=indicator,
        severity=severity,
        confidence=confidence,
        observed_at=NOW,
        source_id="user-1",
    )


def request(*items: Any, minimum_count: int = 1) -> Any:
    return HEALTH.PlantHealthRequest(
        request_id="health-request-1",
        plant_instance_id="plant-1",
        selected_profile_id="pk.profile.acacia_example",
        direct_evidence=tuple(sorted(items, key=lambda item: item.evidence_id)),
        aggregate_stress=aggregate(),
        policy=HEALTH.PlantHealthPolicy(
            policy_id="health-policy",
            policy_version="1.0.0",
            minimum_direct_evidence_count=minimum_count,
            minimum_confidence=0.5,
        ),
        created_at=NOW,
    )


def test_insufficient_direct_evidence_returns_unknown() -> None:
    current = HEALTH.assess_plant_health(request(minimum_count=1))
    assert current.status is HEALTH.PlantHealthStatus.INSUFFICIENT_DIRECT_EVIDENCE
    assert current.classification is HEALTH.PlantHealthClassification.UNKNOWN
    assert "stress_context_not_diagnostic" in current.explanation.reason_codes


def test_moderate_direct_finding_classifies_fair_health() -> None:
    current = HEALTH.assess_plant_health(
        request(
            evidence(
                "evidence-1",
                HEALTH.PlantHealthIndicator.WILTING,
                HEALTH.PlantHealthSeverity.MODERATE,
            )
        )
    )
    assert current.status is HEALTH.PlantHealthStatus.AVAILABLE
    assert current.classification is HEALTH.PlantHealthClassification.FAIR


def test_critical_direct_finding_classifies_critical_health() -> None:
    current = HEALTH.assess_plant_health(
        request(
            evidence(
                "evidence-1",
                HEALTH.PlantHealthIndicator.TISSUE_DAMAGE,
                HEALTH.PlantHealthSeverity.CRITICAL,
            )
        )
    )
    assert current.classification is HEALTH.PlantHealthClassification.CRITICAL


def test_positive_vigor_and_recovery_classify_excellent_health() -> None:
    current = HEALTH.assess_plant_health(
        request(
            evidence(
                "evidence-1",
                HEALTH.PlantHealthIndicator.VIGOR,
                HEALTH.PlantHealthSeverity.NONE,
            ),
            evidence(
                "evidence-2",
                HEALTH.PlantHealthIndicator.RECOVERY,
                HEALTH.PlantHealthSeverity.MILD,
            ),
        )
    )
    assert current.classification is HEALTH.PlantHealthClassification.EXCELLENT


def test_low_confidence_evidence_is_not_admitted() -> None:
    current = HEALTH.assess_plant_health(
        request(
            evidence(
                "evidence-1",
                HEALTH.PlantHealthIndicator.WILTING,
                HEALTH.PlantHealthSeverity.SEVERE,
                confidence=0.2,
            )
        )
    )
    assert current.status is HEALTH.PlantHealthStatus.INSUFFICIENT_DIRECT_EVIDENCE


def test_models_are_immutable_and_serialize_deterministically() -> None:
    current = request(
        evidence(
            "evidence-1",
            HEALTH.PlantHealthIndicator.VIGOR,
            HEALTH.PlantHealthSeverity.NONE,
        )
    )
    assert current.to_dict() == current.to_dict()
    with pytest.raises(FrozenInstanceError):
        current.__setattr__("request_id", "changed")


def test_request_requires_sorted_unique_evidence() -> None:
    first = evidence(
        "evidence-1",
        HEALTH.PlantHealthIndicator.VIGOR,
        HEALTH.PlantHealthSeverity.NONE,
    )
    second = evidence(
        "evidence-2",
        HEALTH.PlantHealthIndicator.RECOVERY,
        HEALTH.PlantHealthSeverity.MILD,
    )
    with pytest.raises(ValueError, match="deterministic ordering"):
        HEALTH.PlantHealthRequest(
            request_id="health-request-1",
            plant_instance_id="plant-1",
            selected_profile_id=None,
            direct_evidence=(second, first),
            aggregate_stress=aggregate(),
            policy=HEALTH.PlantHealthPolicy(
                policy_id="health-policy",
                policy_version="1.0.0",
            ),
            created_at=NOW,
        )
