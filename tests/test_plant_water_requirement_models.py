"""Behavioral tests for the Plant Water Requirement foundation."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from typing import Any

import pytest

from tests.helpers import load_integration_module
from tests.plant_knowledge_fixtures import build_library

PK = load_integration_module("plant_knowledge")
RESOLUTION = load_integration_module("plant_knowledge.resolution")
MODULE = load_integration_module("plant_water_requirement.models")

NOW = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)


def resolved_knowledge() -> Any:
    """Build one valid deterministic Plant Knowledge resolution."""
    library = build_library()
    request = PK.PlantKnowledgeResolutionRequest(
        request_id="pk.request.water_requirement_fixture",
        scientific_name="Examplegenus ficticia",
    )
    return RESOLUTION.resolve_plant_knowledge(library, request)


def context(**changes: object) -> Any:
    """Build valid explicit evaluation context."""
    values: dict[str, object] = {
        "regional_applicability": PK.RegionalApplicability(
            scope=PK.RegionalScope.REGIONAL,
            countries=("US",),
            states_or_provinces=("California",),
            seasons=(PK.Season.SUMMER,),
        ),
        "season": PK.Season.SUMMER,
        "establishment_stage": MODULE.EstablishmentStage.ESTABLISHED,
        "exposure": MODULE.ExposureClassification.TYPICAL,
        "microclimate": MODULE.MicroclimateClassification.TYPICAL,
    }
    values.update(changes)
    return MODULE.PlantWaterRequirementContext(**values)


def policy(**changes: object) -> Any:
    """Build one explicit evidence-admission policy."""
    values: dict[str, object] = {
        "policy_id": "water-requirement-policy",
        "policy_version": "1.0.0",
        "accepted_claim_paths": ("water.plant_factor",),
        "minimum_review_state": PK.ReviewState.APPROVED,
        "minimum_evidence_grade": PK.EvidenceGrade.MODERATE,
        "minimum_confidence": 0.75,
        "require_regional_match": True,
        "range_handling": MODULE.RangeHandling.PRESERVE,
        "missing_data_behavior": MODULE.MissingDataBehavior.RETURN_UNAVAILABLE,
        "conflict_behavior": MODULE.ConflictBehavior.RETURN_CONFLICT,
    }
    values.update(changes)
    return MODULE.PlantWaterRequirementPolicy(**values)


def request(**changes: object) -> Any:
    """Build one valid foundation request."""
    values: dict[str, object] = {
        "request_id": "water-request-1",
        "knowledge_resolution": resolved_knowledge(),
        "context": context(),
        "policy": policy(),
        "created_at": NOW,
    }
    values.update(changes)
    return MODULE.PlantWaterRequirementRequest(**values)


def confidence(**changes: object) -> Any:
    """Build valid confidence and completeness."""
    values: dict[str, object] = {
        "confidence": 0.8,
        "completeness": 0.5,
        "known_required_input_count": 1,
        "required_input_count": 2,
    }
    values.update(changes)
    return MODULE.PlantWaterRequirementConfidence(**values)


def explanation(*codes: Any) -> Any:
    """Build a deterministic explanation."""
    return MODULE.PlantWaterRequirementExplanation(
        reason_codes=tuple(sorted(codes, key=lambda code: code.value)),
        summary="Evidence-backed relative plant water requirement.",
    )


def assessment(**changes: object) -> Any:
    """Build one valid available assessment envelope."""
    values: dict[str, object] = {
        "assessment_id": "water-assessment-1",
        "request_id": "water-request-1",
        "selected_profile_id": "pk.profile.acacia_example",
        "status": MODULE.PlantWaterRequirementStatus.AVAILABLE,
        "value": 0.5,
        "unit": PK.KnowledgeUnit.RATIO,
        "regional_result": MODULE.RegionalApplicabilityResult.MATCH,
        "applicable_region": context().regional_applicability,
        "applicable_season": PK.Season.SUMMER,
        "confidence": confidence(completeness=1.0, known_required_input_count=2),
        "claim_ids": ("pk.claim.acacia.water",),
        "source_ids": ("pk.source.primary",),
        "claim_traces": (),
        "policy_id": "water-requirement-policy",
        "policy_version": "1.0.0",
        "algorithm_version": "1.0.0",
        "explanation": explanation(MODULE.PlantWaterRequirementReasonCode.REQUIREMENT_AVAILABLE),
        "unresolved_issues": (),
        "created_at": NOW,
    }
    values.update(changes)
    return MODULE.PlantWaterRequirementAssessment(**values)


def test_request_is_immutable_and_serializes_deterministically() -> None:
    """Foundation requests preserve resolved knowledge without mutation."""
    current = request()
    first = current.to_dict()
    assert first == current.to_dict()
    assert current.selected_profile_id is not None
    assert first["knowledge_resolution"]["selected_profile_id"] is not None
    assert first["policy"]["accepted_claim_paths"] == ["water.plant_factor"]
    with pytest.raises(FrozenInstanceError):
        current.__setattr__("request_id", "changed")


def test_policy_rejects_hidden_defaults_and_invalid_paths() -> None:
    """Policies require explicit deterministic evidence rules."""
    with pytest.raises(ValueError, match="at least one"):
        policy(accepted_claim_paths=())
    with pytest.raises(ValueError, match="canonical field paths"):
        policy(accepted_claim_paths=("Bad Path",))
    with pytest.raises(ValueError, match=r"between 0\.0 and 1\.0"):
        policy(minimum_confidence=1.1)


def test_confidence_keeps_completeness_separate_and_consistent() -> None:
    """Evidence confidence cannot be conflated with input completeness."""
    assert confidence(confidence=0.95, completeness=0.5).confidence == 0.95
    with pytest.raises(ValueError, match="must match"):
        confidence(completeness=1.0)
    with pytest.raises(ValueError, match="cannot exceed"):
        confidence(known_required_input_count=3)


def test_assessment_preserves_ranges_and_typed_non_success_outcomes() -> None:
    """Result envelopes preserve uncertainty and prohibit silent fallback values."""
    requirement_range = PK.KnowledgeRange(
        minimum=0.3,
        typical=0.5,
        maximum=0.7,
        unit=PK.KnowledgeUnit.RATIO,
    )
    current = assessment(value=requirement_range)
    assert current.to_dict()["value"]["minimum"] == 0.3
    unavailable = assessment(
        status=MODULE.PlantWaterRequirementStatus.UNAVAILABLE,
        selected_profile_id=None,
        value=None,
        unit=None,
        regional_result=MODULE.RegionalApplicabilityResult.NOT_EVALUATED,
        confidence=confidence(confidence=0.0, completeness=0.0, known_required_input_count=0),
        claim_ids=(),
        source_ids=(),
        explanation=explanation(
            MODULE.PlantWaterRequirementReasonCode.MISSING_WATER_EVIDENCE
        ),
        unresolved_issues=("water claim unavailable",),
    )
    assert unavailable.status is MODULE.PlantWaterRequirementStatus.UNAVAILABLE
    with pytest.raises(ValueError, match="must not contain a value"):
        assessment(status=MODULE.PlantWaterRequirementStatus.UNAVAILABLE)


def test_explanations_and_collections_require_deterministic_order() -> None:
    """Audit data rejects duplicate or unstable reason and evidence ordering."""
    with pytest.raises(ValueError, match="unique and deterministically ordered"):
        explanation(
            MODULE.PlantWaterRequirementReasonCode.REQUIREMENT_AVAILABLE,
            MODULE.PlantWaterRequirementReasonCode.REQUIREMENT_AVAILABLE,
        )
    with pytest.raises(ValueError, match="deterministic ordering"):
        assessment(claim_ids=("pk.claim.z", "pk.claim.a"))


def test_context_and_request_reject_wrong_domain_types() -> None:
    """Foundation boundaries reject untyped regional or resolution payloads."""
    with pytest.raises(ValueError, match="Plant Knowledge contract"):
        context(regional_applicability={})
    with pytest.raises(ValueError, match="PlantKnowledgeResolution"):
        request(knowledge_resolution={})
