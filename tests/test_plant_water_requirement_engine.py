"""Behavioral tests for deterministic Plant Water Requirement assessment."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

import pytest

from tests.helpers import load_integration_module
from tests.plant_knowledge_fixtures import REGION, base_components, build_library, claim

PK = load_integration_module("plant_knowledge")
WATER = load_integration_module("plant_water_requirement")

NOW = datetime(2026, 8, 4, 14, 0, tzinfo=UTC)
TARGET_PATH = "water.plant_factor"


def _resolution(
    value: object = 0.6,
    *,
    region: Any = REGION,
    review_state: Any = None,
    evidence_grade: Any = None,
    confidence: float = 0.91,
    source_ids: tuple[str, ...] = ("pk.source.synthetic_approved",),
    claim_version: int = 3,
    claim_path: str = TARGET_PATH,
    consumers: tuple[Any, ...] = (PK.ConsumerCapability.WATER_DEMAND,),
    origin_profile_id: str = "pk.species.example_plant",
) -> Any:
    """Resolve one synthetic self-contained water-evidence snapshot."""
    components = base_components()
    water_claim = replace(
        claim(
            "pk.claim.synthetic_plant_factor",
            claim_path,
            value,
            unit=PK.KnowledgeUnit.RATIO,
            source_ids=source_ids,
            confidence=confidence,
            evidence_grade=evidence_grade or PK.EvidenceGrade.HIGH,
        ),
        regional_applicability=region,
        review_state=review_state or PK.ReviewState.APPROVED,
        intended_consumer_capabilities=consumers,
        claim_version=claim_version,
    )
    profiles = tuple(
        replace(item, claim_ids=tuple(sorted((*item.claim_ids, water_claim.claim_id))))
        if item.profile_id == origin_profile_id
        else item
        for item in components["profiles"]
    )
    library = build_library(claims=(*components["claims"], water_claim), profiles=profiles)
    return PK.resolve_plant_knowledge(
        library,
        PK.PlantKnowledgeResolutionRequest(
            request_id="pk.request.water_engine",
            scientific_name="Examplegenus ficticia",
        ),
    )


def _context(region: Any = REGION) -> Any:
    return WATER.PlantWaterRequirementContext(
        regional_applicability=region,
        season=PK.Season.SUMMER,
        establishment_stage=WATER.EstablishmentStage.ESTABLISHED,
        exposure=WATER.ExposureClassification.TYPICAL,
        microclimate=WATER.MicroclimateClassification.TYPICAL,
    )


def _policy(**changes: object) -> Any:
    values: dict[str, object] = {
        "policy_id": "water-policy",
        "policy_version": "1.2.0",
        "accepted_claim_paths": (TARGET_PATH,),
        "minimum_review_state": PK.ReviewState.APPROVED,
        "minimum_evidence_grade": PK.EvidenceGrade.MODERATE,
        "minimum_confidence": 0.75,
        "require_regional_match": True,
        "range_handling": WATER.RangeHandling.PRESERVE,
        "missing_data_behavior": WATER.MissingDataBehavior.RETURN_UNAVAILABLE,
        "conflict_behavior": WATER.ConflictBehavior.RETURN_CONFLICT,
    }
    values.update(changes)
    return WATER.PlantWaterRequirementPolicy(**values)


def _request(**changes: object) -> Any:
    values: dict[str, object] = {
        "request_id": "water-request-deterministic",
        "knowledge_resolution": _resolution(),
        "context": _context(),
        "policy": _policy(),
        "created_at": NOW,
    }
    values.update(changes)
    return WATER.PlantWaterRequirementRequest(**values)


def _factor(result: Any) -> Any:
    return next(item for item in result.effective_claims if item.field_path == TARGET_PATH)


def test_available_scalar_is_deterministic_and_preserves_evidence() -> None:
    """A matching admitted scalar becomes a complete immutable assessment."""
    request = _request()
    first = WATER.assess_plant_water_requirement(request)
    second = WATER.assess_plant_water_requirement(request)
    expected_digest = sha256(request.request_id.encode("utf-8")).hexdigest()

    assert first == second
    assert first.to_dict() == second.to_dict()
    assert first.assessment_id == f"pwr.assessment.{expected_digest}"
    assert first.created_at == request.created_at
    assert first.status is WATER.PlantWaterRequirementStatus.AVAILABLE
    assert first.value == 0.6
    assert first.unit is PK.KnowledgeUnit.RATIO
    assert first.regional_result is WATER.RegionalApplicabilityResult.MATCH
    assert first.applicable_region == _factor(request.knowledge_resolution).regional_applicability
    assert first.confidence.confidence == 0.91
    assert first.confidence.completeness == 1.0
    assert first.confidence.known_required_input_count == 2
    assert first.confidence.required_input_count == 2
    assert first.claim_ids == ("pk.claim.synthetic_plant_factor",)
    assert first.source_ids == ("pk.source.synthetic_approved",)
    assert first.claim_resolution_ids == ()
    assert first.policy_id == request.policy.policy_id
    assert first.policy_version == request.policy.policy_version
    assert first.algorithm_version == request.algorithm_version
    assert first.explanation.reason_codes == (
        WATER.PlantWaterRequirementReasonCode.REQUIREMENT_AVAILABLE,
    )
    assert "profile=pk.species.example_plant" in first.explanation.detail
    assert "claim=pk.claim.synthetic_plant_factor" in first.explanation.detail
    assert "value=0.6" in first.explanation.detail


def test_range_preservation_and_typical_policy_are_exact() -> None:
    """Ranges are preserved unless the policy explicitly selects an existing typical."""
    value = PK.KnowledgeRange(
        minimum=0.3,
        typical=0.5,
        maximum=0.7,
        unit=PK.KnowledgeUnit.RATIO,
    )
    preserve = WATER.assess_plant_water_requirement(
        _request(knowledge_resolution=_resolution(value))
    )
    assert preserve.value == value
    assert preserve.explanation.reason_codes == (
        WATER.PlantWaterRequirementReasonCode.RANGE_PRESERVED,
        WATER.PlantWaterRequirementReasonCode.REQUIREMENT_AVAILABLE,
    )

    typical = WATER.assess_plant_water_requirement(
        _request(
            knowledge_resolution=_resolution(value),
            policy=_policy(range_handling=WATER.RangeHandling.USE_TYPICAL_IF_PRESENT),
        )
    )
    assert typical.value == 0.5
    assert WATER.PlantWaterRequirementReasonCode.RANGE_PRESERVED not in (
        typical.explanation.reason_codes
    )

    no_typical = PK.KnowledgeRange(0.3, 0.7, PK.KnowledgeUnit.RATIO)
    fallback = WATER.assess_plant_water_requirement(
        _request(
            knowledge_resolution=_resolution(no_typical),
            policy=_policy(range_handling=WATER.RangeHandling.USE_TYPICAL_IF_PRESENT),
        )
    )
    assert fallback.value == no_typical
    assert WATER.PlantWaterRequirementReasonCode.RANGE_PRESERVED in (
        fallback.explanation.reason_codes
    )


def test_missing_profile_and_evidence_are_typed_zero_completeness_results() -> None:
    """Ordinary missing knowledge never invents a value or a partial result."""
    components = base_components()
    profiles = tuple(
        item
        for item in components["profiles"]
        if item.resolution_level is not PK.ProfileResolutionLevel.UNKNOWN_FALLBACK
    )
    unresolved = PK.resolve_plant_knowledge(
        build_library(profiles=profiles),
        PK.PlantKnowledgeResolutionRequest(request_id="pk.request.no_match"),
    )
    no_profile = WATER.assess_plant_water_requirement(
        _request(knowledge_resolution=unresolved)
    )
    assert no_profile.status is WATER.PlantWaterRequirementStatus.UNAVAILABLE
    assert no_profile.selected_profile_id is None
    assert no_profile.explanation.reason_codes == (
        WATER.PlantWaterRequirementReasonCode.PROFILE_NOT_RESOLVED,
    )
    assert no_profile.confidence.confidence == 0
    assert no_profile.confidence.completeness == 0

    missing_resolution = PK.resolve_plant_knowledge(
        build_library(),
        PK.PlantKnowledgeResolutionRequest(
            request_id="pk.request.no_water",
            scientific_name="Examplegenus ficticia",
        ),
    )
    for behavior in WATER.MissingDataBehavior:
        missing = WATER.assess_plant_water_requirement(
            _request(
                knowledge_resolution=missing_resolution,
                policy=_policy(missing_data_behavior=behavior),
            )
        )
        assert missing.status is WATER.PlantWaterRequirementStatus.UNAVAILABLE
        assert missing.value is None
        assert missing.explanation.reason_codes == (
            WATER.PlantWaterRequirementReasonCode.MISSING_WATER_EVIDENCE,
        )


def test_unresolved_conflict_precedes_policy_admission() -> None:
    """An unresolved target conflict remains typed under either conflict policy."""
    resolution = _resolution()
    conflicted = replace(_factor(resolution), conflict_unresolved=True)
    resolution = replace(
        resolution,
        effective_claims=tuple(
            conflicted if item.field_path == TARGET_PATH else item
            for item in resolution.effective_claims
        ),
    )
    for behavior in WATER.ConflictBehavior:
        result = WATER.assess_plant_water_requirement(
            _request(
                knowledge_resolution=resolution,
                policy=_policy(
                    accepted_claim_paths=("identity.scientific_name",),
                    conflict_behavior=behavior,
                ),
            )
        )
        assert result.status is WATER.PlantWaterRequirementStatus.CONFLICTING_EVIDENCE
        assert result.claim_ids == ("pk.claim.synthetic_plant_factor",)
        assert result.explanation.reason_codes == (
            WATER.PlantWaterRequirementReasonCode.CONFLICTING_WATER_EVIDENCE,
        )


@pytest.mark.parametrize(
    ("resolution", "policy", "issue"),
    (
        (
            _resolution(review_state=PK.ReviewState.REVIEWED),
            _policy(minimum_review_state=PK.ReviewState.APPROVED),
            "claim review state is below policy",
        ),
        (
            _resolution(evidence_grade=PK.EvidenceGrade.PROVISIONAL),
            _policy(minimum_evidence_grade=PK.EvidenceGrade.LIMITED),
            "claim evidence grade is below policy",
        ),
        (
            _resolution(confidence=0.5),
            _policy(minimum_confidence=0.75),
            "claim confidence is below policy",
        ),
        (
            _resolution(consumers=(PK.ConsumerCapability.LEARNING,)),
            _policy(),
            "claim does not declare the water_demand consumer",
        ),
        (
            _resolution(),
            _policy(accepted_claim_paths=("identity.scientific_name",)),
            "policy does not admit water.plant_factor",
        ),
    ),
)
def test_evidence_admission_failures_are_explicit(
    resolution: Any,
    policy: Any,
    issue: str,
) -> None:
    """Field, consumer, quality, review, and confidence gates are deterministic."""
    result = WATER.assess_plant_water_requirement(
        _request(knowledge_resolution=resolution, policy=policy)
    )
    assert result.status is WATER.PlantWaterRequirementStatus.INSUFFICIENT_QUALITY
    assert result.value is None
    assert issue in result.unresolved_issues
    assert result.confidence.confidence == 0
    assert result.confidence.completeness == 0


def test_review_and_evidence_grade_tables_do_not_use_enum_order() -> None:
    """Approved and expert-consensus evidence follow the documented explicit tables."""
    approved_for_reviewed = WATER.assess_plant_water_requirement(
        _request(policy=_policy(minimum_review_state=PK.ReviewState.REVIEWED))
    )
    assert approved_for_reviewed.status is WATER.PlantWaterRequirementStatus.AVAILABLE

    consensus = WATER.assess_plant_water_requirement(
        _request(
            knowledge_resolution=_resolution(
                evidence_grade=PK.EvidenceGrade.EXPERT_CONSENSUS
            ),
            policy=_policy(minimum_evidence_grade=PK.EvidenceGrade.MODERATE),
        )
    )
    assert consensus.status is WATER.PlantWaterRequirementStatus.AVAILABLE

    consensus_not_high = WATER.assess_plant_water_requirement(
        _request(
            knowledge_resolution=_resolution(
                evidence_grade=PK.EvidenceGrade.EXPERT_CONSENSUS
            ),
            policy=_policy(minimum_evidence_grade=PK.EvidenceGrade.HIGH),
        )
    )
    assert (
        consensus_not_high.status
        is WATER.PlantWaterRequirementStatus.INSUFFICIENT_QUALITY
    )


def test_rejected_and_deprecated_claims_are_never_admitted() -> None:
    """Terminal review states cannot be enabled through a permissive threshold."""
    for state in (PK.ReviewState.REJECTED, PK.ReviewState.DEPRECATED):
        resolution = _resolution()
        effective = replace(_factor(resolution), review_state=state)
        resolution = replace(
            resolution,
            effective_claims=tuple(
                effective if item.field_path == TARGET_PATH else item
                for item in resolution.effective_claims
            ),
        )
        result = WATER.assess_plant_water_requirement(
            _request(
                knowledge_resolution=resolution,
                policy=_policy(minimum_review_state=PK.ReviewState.UNREVIEWED),
            )
        )
        assert result.status is WATER.PlantWaterRequirementStatus.INSUFFICIENT_QUALITY
        assert f"claim review state is {state.value}" in result.unresolved_issues


def test_wrong_field_is_missing_and_wrong_unit_is_rejected_defensively() -> None:
    """Only the closed plant-factor field and ratio unit can reach assessment output."""
    wrong_path = WATER.assess_plant_water_requirement(
        _request(
            knowledge_resolution=_resolution(
                claim_path="water.landscape_coefficient"
            )
        )
    )
    assert wrong_path.status is WATER.PlantWaterRequirementStatus.UNAVAILABLE
    assert wrong_path.explanation.reason_codes == (
        WATER.PlantWaterRequirementReasonCode.MISSING_WATER_EVIDENCE,
    )

    resolution = _resolution()
    invalid_effective = _factor(resolution)
    object.__setattr__(invalid_effective, "unit", PK.KnowledgeUnit.METERS)
    wrong_unit = WATER.assess_plant_water_requirement(
        _request(knowledge_resolution=resolution)
    )
    assert wrong_unit.status is WATER.PlantWaterRequirementStatus.INSUFFICIENT_QUALITY
    assert "water.plant_factor must use the ratio unit" in wrong_unit.unresolved_issues


def test_regional_results_cover_unrestricted_match_partial_unavailable_and_mismatch() -> None:
    """Claim scope and property context remain separate deterministic decisions."""
    unrestricted = PK.RegionalApplicability(scope=PK.RegionalScope.UNRESTRICTED)
    assert WATER.assess_plant_water_requirement(
        _request(knowledge_resolution=_resolution(region=unrestricted))
    ).regional_result is WATER.RegionalApplicabilityResult.UNRESTRICTED

    partial_context = PK.RegionalApplicability(
        scope=PK.RegionalScope.REGIONAL,
        countries=("XZ",),
    )
    partial = WATER.assess_plant_water_requirement(
        _request(context=_context(partial_context))
    )
    assert partial.status is WATER.PlantWaterRequirementStatus.PARTIAL
    assert partial.regional_result is WATER.RegionalApplicabilityResult.PARTIAL_MATCH
    assert partial.confidence.confidence == 0.91
    assert partial.confidence.completeness == 0.5

    unavailable_context = PK.RegionalApplicability(scope=PK.RegionalScope.UNRESTRICTED)
    unavailable = WATER.assess_plant_water_requirement(
        _request(context=_context(unavailable_context))
    )
    assert unavailable.status is WATER.PlantWaterRequirementStatus.PARTIAL
    assert (
        unavailable.regional_result
        is WATER.RegionalApplicabilityResult.UNAVAILABLE_CONTEXT
    )

    mismatch_context = replace(REGION, countries=("YY",))
    mismatch = WATER.assess_plant_water_requirement(
        _request(context=_context(mismatch_context))
    )
    assert mismatch.status is WATER.PlantWaterRequirementStatus.REGIONAL_MISMATCH
    assert mismatch.regional_result is WATER.RegionalApplicabilityResult.MISMATCH
    assert mismatch.value is None

    permitted = WATER.assess_plant_water_requirement(
        _request(
            context=_context(mismatch_context),
            policy=_policy(require_regional_match=False),
        )
    )
    assert permitted.status is WATER.PlantWaterRequirementStatus.PARTIAL
    assert permitted.value == 0.6
    assert permitted.confidence.completeness == 1.0


def test_each_regional_attribute_can_match_or_contradict() -> None:
    """All supported region dimensions participate in one contradiction-first policy."""
    assert WATER.assess_plant_water_requirement(_request()).regional_result is (
        WATER.RegionalApplicabilityResult.MATCH
    )
    mismatches = (
        replace(REGION, states_or_provinces=("Other Province",)),
        replace(REGION, climate_zone_ids=("other-climate",)),
        replace(REGION, wucols_regions=("other-wucols",)),
        replace(REGION, usda_zone_minimum="1a", usda_zone_maximum="2b"),
        replace(REGION, coastal=PK.CoastalApplicability.DOES_NOT_APPLY),
        replace(REGION, inland=PK.InlandApplicability.APPLIES),
        replace(REGION, elevation_minimum_meters=1000, elevation_maximum_meters=1200),
        replace(REGION, seasons=(PK.Season.WINTER,)),
    )
    for regional_context in mismatches:
        result = WATER.assess_plant_water_requirement(
            _request(context=_context(regional_context))
        )
        assert result.regional_result is WATER.RegionalApplicabilityResult.MISMATCH

    year_round_evidence = replace(REGION, seasons=(PK.Season.YEAR_ROUND,))
    year_round = WATER.assess_plant_water_requirement(
        _request(knowledge_resolution=_resolution(region=year_round_evidence))
    )
    assert year_round.regional_result is WATER.RegionalApplicabilityResult.MATCH


def test_inherited_and_overridden_target_traces_are_preserved() -> None:
    """The assessment retains target-field provenance traces from profile resolution."""
    components = base_components()
    parent = replace(
        claim(
            "pk.claim.parent_plant_factor",
            TARGET_PATH,
            0.4,
            unit=PK.KnowledgeUnit.RATIO,
        ),
        intended_consumer_capabilities=(PK.ConsumerCapability.WATER_DEMAND,),
    )
    child = replace(
        claim(
            "pk.claim.child_plant_factor",
            TARGET_PATH,
            0.6,
            unit=PK.KnowledgeUnit.RATIO,
        ),
        intended_consumer_capabilities=(PK.ConsumerCapability.WATER_DEMAND,),
    )
    profiles = tuple(
        replace(item, claim_ids=tuple(sorted((*item.claim_ids, parent.claim_id))))
        if item.profile_id == "pk.group.synthetic_fruit_tree"
        else replace(item, claim_ids=tuple(sorted((*item.claim_ids, child.claim_id))))
        if item.profile_id == "pk.species.example_plant"
        else item
        for item in components["profiles"]
    )
    resolution = PK.resolve_plant_knowledge(
        build_library(
            claims=(*components["claims"], parent, child),
            profiles=profiles,
        ),
        PK.PlantKnowledgeResolutionRequest(
            request_id="pk.request.inherited_water",
            scientific_name="Examplegenus ficticia",
        ),
    )
    result = WATER.assess_plant_water_requirement(
        _request(knowledge_resolution=resolution)
    )
    assert result.value == 0.6
    assert tuple(trace.claim_id for trace in result.claim_traces) == (
        parent.claim_id,
        child.claim_id,
    )
    assert result.claim_traces[0].disposition is PK.ClaimTraceDisposition.OVERRIDDEN
    assert result.claim_traces[1].disposition is PK.ClaimTraceDisposition.EFFECTIVE


def test_resolved_conflict_reference_and_competing_traces_are_preserved() -> None:
    """Reviewed conflict metadata survives in the existing explanation and trace fields."""
    components = base_components()
    first = replace(
        claim(
            "pk.claim.factor_competitor_a",
            TARGET_PATH,
            0.4,
            unit=PK.KnowledgeUnit.RATIO,
            unresolved_conflict=True,
        ),
        intended_consumer_capabilities=(PK.ConsumerCapability.WATER_DEMAND,),
    )
    second = replace(
        claim(
            "pk.claim.factor_competitor_b",
            TARGET_PATH,
            0.6,
            unit=PK.KnowledgeUnit.RATIO,
            unresolved_conflict=True,
        ),
        intended_consumer_capabilities=(PK.ConsumerCapability.WATER_DEMAND,),
    )
    claim_resolution = PK.ClaimResolution(
        resolution_id="pk.resolution.synthetic_plant_factor",
        field_path=TARGET_PATH,
        competing_claim_ids=(first.claim_id, second.claim_id),
        selected_claim_id=second.claim_id,
        resolved_range=None,
        regional_weights=(),
        resolution_method=PK.ClaimResolutionMethod.SELECTED_CLAIM,
        resolver_identity="reviewer.synthetic",
        confidence=0.9,
        unresolved_issues=(),
        version=1,
        created_at=components["claims"][0].created_at,
    )
    profiles = tuple(
        replace(
            item,
            claim_ids=tuple(sorted((*item.claim_ids, first.claim_id, second.claim_id))),
        )
        if item.profile_id == "pk.species.example_plant"
        else item
        for item in components["profiles"]
    )
    resolution = PK.resolve_plant_knowledge(
        build_library(
            claims=(*components["claims"], first, second),
            claim_resolutions=(claim_resolution,),
            profiles=profiles,
        ),
        PK.PlantKnowledgeResolutionRequest(
            request_id="pk.request.resolved_water_conflict",
            scientific_name="Examplegenus ficticia",
        ),
    )
    result = WATER.assess_plant_water_requirement(
        _request(knowledge_resolution=resolution)
    )
    assert result.status is WATER.PlantWaterRequirementStatus.AVAILABLE
    assert result.value == 0.6
    assert result.claim_ids == (second.claim_id,)
    assert result.claim_resolution_ids == (claim_resolution.resolution_id,)
    assert {trace.claim_id for trace in result.claim_traces} == {
        first.claim_id,
        second.claim_id,
    }
    assert f"resolution={claim_resolution.resolution_id}" in result.explanation.detail
    assert "resolution_method=selected_claim" in result.explanation.detail
    without_detail = replace(
        result,
        explanation=replace(result.explanation, detail=None),
    )
    assert without_detail.claim_resolution_ids == (claim_resolution.resolution_id,)
    assert result.to_dict() == WATER.assess_plant_water_requirement(
        _request(knowledge_resolution=resolution)
    ).to_dict()

    unresolved_effective = replace(_factor(resolution), conflict_unresolved=True)
    unresolved_resolution = replace(
        resolution,
        effective_claims=tuple(
            unresolved_effective if item.field_path == TARGET_PATH else item
            for item in resolution.effective_claims
        ),
    )
    unresolved = WATER.assess_plant_water_requirement(
        _request(knowledge_resolution=unresolved_resolution)
    )
    assert unresolved.status is WATER.PlantWaterRequirementStatus.CONFLICTING_EVIDENCE
    assert unresolved.claim_resolution_ids == (claim_resolution.resolution_id,)


def test_resolved_range_preserves_typed_resolution_reference() -> None:
    """A resolved-range assessment exposes its resolution ID without the full record."""
    components = base_components()
    first = replace(
        claim(
            "pk.claim.factor_range_a",
            TARGET_PATH,
            PK.KnowledgeRange(0.3, 0.6, PK.KnowledgeUnit.RATIO),
            unit=PK.KnowledgeUnit.RATIO,
            unresolved_conflict=True,
        ),
        intended_consumer_capabilities=(PK.ConsumerCapability.WATER_DEMAND,),
    )
    second = replace(
        claim(
            "pk.claim.factor_range_b",
            TARGET_PATH,
            PK.KnowledgeRange(0.4, 0.7, PK.KnowledgeUnit.RATIO),
            unit=PK.KnowledgeUnit.RATIO,
            unresolved_conflict=True,
        ),
        intended_consumer_capabilities=(PK.ConsumerCapability.WATER_DEMAND,),
    )
    resolved_range = PK.KnowledgeRange(
        minimum=0.35,
        typical=0.5,
        maximum=0.65,
        unit=PK.KnowledgeUnit.RATIO,
    )
    claim_resolution = PK.ClaimResolution(
        resolution_id="pk.resolution.synthetic_plant_factor_range",
        field_path=TARGET_PATH,
        competing_claim_ids=(first.claim_id, second.claim_id),
        selected_claim_id=None,
        resolved_range=resolved_range,
        regional_weights=(),
        resolution_method=PK.ClaimResolutionMethod.RESOLVED_RANGE,
        resolver_identity="reviewer.synthetic",
        confidence=0.9,
        unresolved_issues=(),
        version=1,
        created_at=components["claims"][0].created_at,
    )
    profiles = tuple(
        replace(
            item,
            claim_ids=tuple(sorted((*item.claim_ids, first.claim_id, second.claim_id))),
        )
        if item.profile_id == "pk.species.example_plant"
        else item
        for item in components["profiles"]
    )
    resolution = PK.resolve_plant_knowledge(
        build_library(
            claims=(*components["claims"], first, second),
            claim_resolutions=(claim_resolution,),
            profiles=profiles,
        ),
        PK.PlantKnowledgeResolutionRequest(
            request_id="pk.request.resolved_water_range",
            scientific_name="Examplegenus ficticia",
        ),
    )
    result = WATER.assess_plant_water_requirement(
        _request(knowledge_resolution=resolution)
    )
    assert result.status is WATER.PlantWaterRequirementStatus.AVAILABLE
    assert result.value == resolved_range
    assert result.claim_resolution_ids == (claim_resolution.resolution_id,)
    assert result.to_dict()["claim_resolution_ids"] == [
        claim_resolution.resolution_id
    ]


def test_assessment_needs_no_library_and_imports_no_forbidden_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The public function consumes only the request's self-contained snapshots."""
    request = _request()

    def reject_lookup(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("assessment must not look up the Plant Knowledge library")

    monkeypatch.setattr(PK.PlantKnowledgeLibrary, "get_claim", reject_lookup)
    result = WATER.assess_plant_water_requirement(request)
    assert result.status is WATER.PlantWaterRequirementStatus.AVAILABLE
    assert "assess_plant_water_requirement" in WATER.__all__
    forbidden = (
        "homeassistant",
        "requests",
        "aiohttp",
        "openai",
        "controller",
        "schedule",
        "recommendation",
    )
    engine_source = __import__("inspect").getsource(
        load_integration_module("plant_water_requirement.engine")
    ).casefold()
    assert not any(fragment in engine_source for fragment in forbidden)
