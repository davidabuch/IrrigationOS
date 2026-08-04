"""Behavioral tests for the Plant Stress Risk foundation."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from typing import Any

import pytest

from tests.helpers import load_integration_module
from tests.test_environment_models import report
from tests.test_plant_water_requirement_models import assessment, resolved_knowledge

PK = load_integration_module("plant_knowledge")
MODULE = load_integration_module("plant_stress.models")

NOW = datetime(2026, 8, 4, 13, 0, tzinfo=UTC)


def region() -> Any:
    """Build explicit Southern California applicability."""
    return PK.RegionalApplicability(
        scope=PK.RegionalScope.REGIONAL,
        countries=("US",),
        states_or_provinces=("California",),
        seasons=(PK.Season.SUMMER,),
    )


def context(**changes: object) -> Any:
    """Build one valid stress-risk context."""
    values: dict[str, object] = {
        "location_id": "property-1",
        "analysis_window_id": "window-1",
        "regional_applicability": region(),
        "season": PK.Season.SUMMER,
    }
    values.update(changes)
    return MODULE.PlantStressRiskContext(**values)


def policy(**changes: object) -> Any:
    """Build one explicit foundation policy."""
    values: dict[str, object] = {
        "policy_id": "plant-stress-policy",
        "policy_version": "1.0.0",
        "enabled_dimensions": (
            MODULE.PlantStressDimension.FREEZE,
            MODULE.PlantStressDimension.HEAT,
            MODULE.PlantStressDimension.WATER_DEFICIT,
        ),
        "minimum_confidence": 0.75,
        "partial_evidence_behavior": MODULE.PartialEvidenceBehavior.RETURN_PARTIAL,
        "missing_evidence_behavior": MODULE.MissingEvidenceBehavior.RETURN_SPECIFIC_STATUS,
        "overall_risk_aggregation": MODULE.OverallRiskAggregation.NONE,
    }
    values.update(changes)
    return MODULE.PlantStressRiskPolicy(**values)


def request(**changes: object) -> Any:
    """Build one valid foundation request."""
    values: dict[str, object] = {
        "request_id": "plant-stress-request-1",
        "knowledge_resolution": resolved_knowledge(),
        "water_requirement_assessment": assessment(),
        "environmental_report": report(),
        "context": context(),
        "policy": policy(),
        "created_at": NOW,
    }
    values.update(changes)
    return MODULE.PlantStressRiskRequest(**values)


def confidence(**changes: object) -> Any:
    """Build valid confidence and completeness."""
    values: dict[str, object] = {
        "confidence": 0.8,
        "completeness": 1.0,
        "known_required_input_count": 2,
        "required_input_count": 2,
    }
    values.update(changes)
    return MODULE.PlantStressRiskConfidence(**values)


def explanation(**changes: object) -> Any:
    """Build deterministic explanation data."""
    values: dict[str, object] = {
        "reason_codes": ("environmental_exposure_available", "plant_susceptibility_available"),
        "summary": "Plant susceptibility and environmental exposure are available.",
    }
    values.update(changes)
    return MODULE.PlantStressRiskExplanation(**values)


def dimension(**changes: object) -> Any:
    """Build one valid independent dimension assessment."""
    values: dict[str, object] = {
        "assessment_id": "plant-stress-dimension-water-1",
        "dimension": MODULE.PlantStressDimension.WATER_DEFICIT,
        "status": MODULE.PlantStressRiskStatus.AVAILABLE,
        "risk": MODULE.PlantStressRiskClassification.MODERATE,
        "confidence": confidence(),
        "selected_profile_id": "pk.profile.acacia_example",
        "plant_knowledge_claim_ids": ("pk.claim.acacia.water",),
        "plant_knowledge_source_ids": ("pk.source.primary",),
        "water_requirement_assessment_id": "water-assessment-1",
        "environmental_report_id": "report-1",
        "environmental_signal_ids": ("signal-1",),
        "regional_applicability": region(),
        "policy_id": "plant-stress-policy",
        "policy_version": "1.0.0",
        "algorithm_version": "1.0.0",
        "explanation": explanation(),
        "unresolved_issues": (),
    }
    values.update(changes)
    return MODULE.PlantStressDimensionAssessment(**values)


def aggregate(**changes: object) -> Any:
    """Build one valid aggregate envelope without implementing aggregation."""
    values: dict[str, object] = {
        "assessment_id": "plant-stress-assessment-1",
        "request_id": "plant-stress-request-1",
        "selected_profile_id": "pk.profile.acacia_example",
        "location_id": "property-1",
        "analysis_window_id": "window-1",
        "dimensions": (dimension(),),
        "overall_status": MODULE.PlantStressRiskStatus.AVAILABLE,
        "overall_risk": None,
        "confidence": confidence(),
        "knowledge_resolution_id": "pk.resolution.example",
        "water_requirement_assessment_id": "water-assessment-1",
        "environmental_report_id": "report-1",
        "policy_id": "plant-stress-policy",
        "policy_version": "1.0.0",
        "algorithm_version": "1.0.0",
        "explanation": explanation(),
        "unresolved_issues": (),
        "created_at": NOW,
    }
    values.update(changes)
    return MODULE.PlantStressRiskAssessment(**values)


def test_request_is_frozen_slotted_and_serializes_deterministically() -> None:
    """Requests retain immutable upstream assessments and stable serialization."""
    current = request()
    assert current.to_dict() == current.to_dict()
    assert current.to_dict()["environmental_report"]["report_id"] == "report-1"
    assert current.selected_profile_id is not None
    with pytest.raises(FrozenInstanceError):
        current.__setattr__("request_id", "changed")
    with pytest.raises((AttributeError, TypeError)):
        current.__setattr__("unexpected", "value")


def test_policy_requires_canonical_sorted_unique_dimensions() -> None:
    """Policy dimensions are explicit, unique, and deterministic."""
    with pytest.raises(ValueError, match="at least one"):
        policy(enabled_dimensions=())
    with pytest.raises(ValueError, match="duplicates"):
        policy(
            enabled_dimensions=(
                MODULE.PlantStressDimension.HEAT,
                MODULE.PlantStressDimension.HEAT,
            )
        )
    with pytest.raises(ValueError, match="deterministic ordering"):
        policy(
            enabled_dimensions=(
                MODULE.PlantStressDimension.WATER_DEFICIT,
                MODULE.PlantStressDimension.HEAT,
            )
        )
    with pytest.raises(ValueError, match=r"between 0\.0 and 1\.0"):
        policy(minimum_confidence=1.1)


def test_context_and_request_enforce_upstream_contracts() -> None:
    """Requests reject mismatched locations, windows, and untyped inputs."""
    with pytest.raises(ValueError, match="location must agree"):
        request(context=context(location_id="property-2"))
    with pytest.raises(ValueError, match="analysis window must agree"):
        request(context=context(analysis_window_id="window-2"))
    with pytest.raises(ValueError, match="PlantKnowledgeResolution"):
        request(knowledge_resolution={})
    with pytest.raises(ValueError, match="EnvironmentalIntelligenceReport"):
        request(environmental_report={})


def test_versions_and_timestamps_are_strict() -> None:
    """Public contracts reject invalid versions and naive timestamps."""
    with pytest.raises(ValueError, match=r"MAJOR\.MINOR\.PATCH"):
        policy(policy_version="v1")
    with pytest.raises(ValueError, match="timezone-aware"):
        request(created_at=datetime(2026, 8, 4, 13, 0))
    with pytest.raises(ValueError, match="unsupported"):
        request(schema_version=2)


def test_confidence_and_completeness_remain_distinct() -> None:
    """High confidence does not imply complete evidence."""
    current = confidence(
        confidence=0.95,
        completeness=0.5,
        known_required_input_count=1,
    )
    assert current.confidence == 0.95
    assert current.completeness == 0.5
    with pytest.raises(ValueError, match="must match"):
        confidence(completeness=0.5)
    with pytest.raises(ValueError, match="cannot exceed"):
        confidence(known_required_input_count=3)


def test_dimension_outcomes_reject_fabricated_or_missing_risk() -> None:
    """Only successful dimension outcomes may carry concrete risk."""
    with pytest.raises(ValueError, match="concrete risk"):
        dimension(risk=MODULE.PlantStressRiskClassification.UNKNOWN)
    unavailable = dimension(
        status=MODULE.PlantStressRiskStatus.INSUFFICIENT_ENVIRONMENTAL_EVIDENCE,
        risk=MODULE.PlantStressRiskClassification.UNKNOWN,
        environmental_report_id=None,
        environmental_signal_ids=(),
        confidence=confidence(
            confidence=0.0,
            completeness=0.0,
            known_required_input_count=0,
        ),
        unresolved_issues=("environmental evidence unavailable",),
    )
    assert unavailable.risk is MODULE.PlantStressRiskClassification.UNKNOWN
    with pytest.raises(ValueError, match="unknown risk"):
        dimension(status=MODULE.PlantStressRiskStatus.UNAVAILABLE)


def test_dimension_preserves_machine_readable_provenance() -> None:
    """Independent dimensions retain every upstream evidence reference."""
    current = dimension()
    data = current.to_dict()
    assert data["plant_knowledge_claim_ids"] == ["pk.claim.acacia.water"]
    assert data["plant_knowledge_source_ids"] == ["pk.source.primary"]
    assert data["water_requirement_assessment_id"] == "water-assessment-1"
    assert data["environmental_signal_ids"] == ["signal-1"]


def test_dimension_collections_require_deterministic_order() -> None:
    """Evidence references and issues reject duplicates and unstable order."""
    with pytest.raises(ValueError, match="deterministic ordering"):
        dimension(
            plant_knowledge_claim_ids=("pk.claim.z", "pk.claim.a")
        )
    with pytest.raises(ValueError, match="duplicates"):
        dimension(environmental_signal_ids=("signal-1", "signal-1"))
    with pytest.raises(ValueError, match="deterministic ordering"):
        dimension(unresolved_issues=("z issue", "a issue"))


def test_aggregate_dimensions_are_independent_unique_and_ordered() -> None:
    """Aggregates preserve dimensions without averaging or duplicate identity."""
    heat = dimension(
        assessment_id="plant-stress-dimension-heat-1",
        dimension=MODULE.PlantStressDimension.HEAT,
    )
    water = dimension()
    current = aggregate(dimensions=(heat, water))
    assert tuple(item.dimension for item in current.dimensions) == (
        MODULE.PlantStressDimension.HEAT,
        MODULE.PlantStressDimension.WATER_DEFICIT,
    )
    with pytest.raises(ValueError, match="duplicates"):
        aggregate(dimensions=(water, water))
    with pytest.raises(ValueError, match="deterministic ordering"):
        aggregate(dimensions=(water, heat))


def test_aggregate_does_not_require_or_fabricate_overall_risk() -> None:
    """Foundation aggregates may preserve independent dimensions without scoring."""
    current = aggregate(overall_risk=None)
    assert current.overall_risk is None
    with pytest.raises(ValueError, match="concrete or omitted"):
        aggregate(overall_risk=MODULE.PlantStressRiskClassification.UNKNOWN)
    with pytest.raises(ValueError, match="requires dimensions"):
        aggregate(dimensions=())


def test_explanations_are_deterministic_and_machine_readable() -> None:
    """Explanation reason codes remain stable and ordered."""
    with pytest.raises(ValueError, match="lower_snake_case"):
        explanation(reason_codes=("Bad Reason",))
    with pytest.raises(ValueError, match="duplicates"):
        explanation(reason_codes=("evidence_available", "evidence_available"))
    with pytest.raises(ValueError, match="deterministic ordering"):
        explanation(reason_codes=("z_reason", "a_reason"))


def test_public_contracts_have_no_runtime_or_control_dependencies() -> None:
    """The foundation remains pure domain modeling with no downstream authority."""
    module_names = {
        MODULE.PlantStressRiskRequest.__module__,
        MODULE.PlantStressRiskAssessment.__module__,
    }
    forbidden = ("homeassistant", "controller", "schedule", "recommend", "network")
    assert not any(term in name for name in module_names for term in forbidden)
