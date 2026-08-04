"""Behavioral tests for deterministic Plant Knowledge profile resolution."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.plant_knowledge_fixtures import (
    PK,
    REGION,
    base_components,
    build_library,
    claim,
    profile,
)


def request(**values: object) -> object:
    """Build a canonical exact-match request."""
    return PK.PlantKnowledgeResolutionRequest(
        request_id="pk.request.synthetic_resolution",
        **values,
    )


@pytest.mark.parametrize(
    ("request_values", "expected_id", "expected_level", "expected_reason"),
    (
        (
            {"scientific_name": "  EXAMPLEGENUS   FICTICIA ", "cultivar": " demo "},
            "pk.cultivar.example_plant.demo",
            PK.ProfileResolutionLevel.CULTIVAR,
            PK.ResolutionReasonCode.EXACT_CULTIVAR_MATCH,
        ),
        (
            {"scientific_name": "Examplegenus ficticia"},
            "pk.species.example_plant",
            PK.ProfileResolutionLevel.SPECIES,
            PK.ResolutionReasonCode.EXACT_SPECIES_MATCH,
        ),
        (
            {"scientific_name": "Examplegenus"},
            "pk.genus.example",
            PK.ProfileResolutionLevel.GENUS,
            PK.ResolutionReasonCode.EXACT_GENUS_MATCH,
        ),
        (
            {"functional_group_hints": ("pk.group.synthetic_fruit_membership",)},
            "pk.group.synthetic_fruit_tree",
            PK.ProfileResolutionLevel.FUNCTIONAL_GROUP,
            PK.ResolutionReasonCode.FUNCTIONAL_GROUP_MATCH,
        ),
        (
            {"broad_category": PK.PlantCategory.TREE},
            "pk.category.synthetic_tree",
            PK.ProfileResolutionLevel.CATEGORY_FALLBACK,
            PK.ResolutionReasonCode.CATEGORY_FALLBACK,
        ),
        (
            {},
            "pk.fallback.unknown_tree",
            PK.ProfileResolutionLevel.UNKNOWN_FALLBACK,
            PK.ResolutionReasonCode.UNKNOWN_FALLBACK,
        ),
    ),
)
def test_resolution_precedence_is_exact_and_deterministic(
    request_values: dict[str, object],
    expected_id: str,
    expected_level: object,
    expected_reason: object,
) -> None:
    """The documented seven-level fallback chain selects exact canonical profiles."""
    result = PK.resolve_plant_knowledge(build_library(), request(**request_values))
    assert result.selected_profile_id == expected_id
    assert result.selected_resolution_level is expected_level
    assert result.reason_code is expected_reason
    assert result.algorithm_version == "1.0.0"
    assert result == PK.resolve_plant_knowledge(build_library(), request(**request_values))


def test_user_confirmed_override_has_highest_precedence() -> None:
    """A valid explicit user choice overrides competing identity inputs."""
    result = PK.resolve_plant_knowledge(
        build_library(),
        request(
            user_confirmed_profile_id="pk.category.synthetic_tree",
            scientific_name="Examplegenus ficticia",
            cultivar="Demo",
        ),
    )
    assert result.selected_profile_id == "pk.category.synthetic_tree"
    assert result.reason_code is PK.ResolutionReasonCode.USER_CONFIRMED_OVERRIDE
    assert result.fallback_chain == ()
    with pytest.raises(ValueError, match="does not exist"):
        PK.resolve_plant_knowledge(
            build_library(),
            request(user_confirmed_profile_id="pk.species.missing"),
        )


def test_resolution_preserves_inheritance_origins_and_override_traces() -> None:
    """Child claims override by field while every inherited origin remains visible."""
    result = PK.resolve_plant_knowledge(
        build_library(),
        request(scientific_name="Examplegenus ficticia", cultivar="Demo"),
    )
    assert result.profile_inheritance_chain == (
        "pk.category.synthetic_tree",
        "pk.group.synthetic_fruit_tree",
        "pk.species.example_plant",
        "pk.cultivar.example_plant.demo",
    )
    visual = next(
        item for item in result.effective_claims if item.field_path == "visual.leaf_shape"
    )
    assert visual.claim_id == "pk.claim.cultivar_visual"
    assert visual.originating_profile_id == "pk.cultivar.example_plant.demo"
    assert visual.inherited is False
    category_trace = next(
        item for item in result.claim_traces if item.claim_id == "pk.claim.category_visual"
    )
    assert category_trace.disposition is PK.ClaimTraceDisposition.OVERRIDDEN
    assert category_trace.overridden_by_claim_id == "pk.claim.cultivar_visual"
    assert "pk.claim.category_visual" in result.explanation.overridden_claim_ids
    assert result.explanation.evidence_source_ids == ("pk.source.synthetic_approved",)


def test_explicit_claim_resolution_selects_one_conflict_without_deleting_evidence() -> None:
    """A reviewed conflict resolution selects effectively and retains both traces."""
    components = base_components()
    first = claim(
        "pk.claim.species_conflict_a",
        "visual.leaf_shape",
        PK.LeafShape.BROAD,
        unresolved_conflict=True,
    )
    second = claim(
        "pk.claim.species_conflict_b",
        "visual.leaf_shape",
        PK.LeafShape.LINEAR,
        unresolved_conflict=True,
    )
    resolution = PK.ClaimResolution(
        resolution_id="pk.resolution.species_conflict",
        field_path="visual.leaf_shape",
        competing_claim_ids=(first.claim_id, second.claim_id),
        selected_claim_id=second.claim_id,
        resolved_range=None,
        regional_weights=(),
        resolution_method=PK.ClaimResolutionMethod.REVIEWER_DECISION,
        resolver_identity="reviewer.synthetic",
        confidence=0.9,
        unresolved_issues=(),
        version=1,
        created_at=components["claims"][0].created_at,
    )
    profiles = tuple(
        replace(item, claim_ids=tuple(sorted((*item.claim_ids, first.claim_id, second.claim_id))))
        if item.profile_id == "pk.species.example_plant"
        else item
        for item in components["profiles"]
    )
    library = build_library(
        claims=(*components["claims"], first, second),
        claim_resolutions=(resolution,),
        profiles=profiles,
    )
    result = PK.resolve_plant_knowledge(
        library,
        request(scientific_name="Examplegenus ficticia"),
    )
    effective = next(
        item for item in result.effective_claims if item.field_path == "visual.leaf_shape"
    )
    assert effective.claim_id == second.claim_id
    traces = {item.claim_id: item.disposition for item in result.claim_traces}
    assert traces[first.claim_id] is PK.ClaimTraceDisposition.CONFLICT_RETAINED
    assert traces[second.claim_id] is PK.ClaimTraceDisposition.EFFECTIVE
    assert result.unresolved_ambiguity is False


def test_resolved_range_is_exposed_with_its_resolution_and_provenance() -> None:
    """A range resolution is effective while every supporting claim remains traceable."""
    components = base_components()
    first = claim(
        "pk.claim.species_depth_a",
        "growth.typical_root_depth_meters",
        PK.KnowledgeRange(0.1, 0.3, PK.KnowledgeUnit.METERS),
        unit=PK.KnowledgeUnit.METERS,
        unresolved_conflict=True,
    )
    second = claim(
        "pk.claim.species_depth_b",
        "growth.typical_root_depth_meters",
        PK.KnowledgeRange(0.2, 0.4, PK.KnowledgeUnit.METERS),
        unit=PK.KnowledgeUnit.METERS,
        unresolved_conflict=True,
    )
    resolved_range = PK.KnowledgeRange(
        0.15,
        0.35,
        PK.KnowledgeUnit.METERS,
        typical=0.25,
    )
    resolution = PK.ClaimResolution(
        resolution_id="pk.resolution.species_depth",
        field_path="growth.typical_root_depth_meters",
        competing_claim_ids=(first.claim_id, second.claim_id),
        selected_claim_id=None,
        resolved_range=resolved_range,
        regional_weights=(),
        resolution_method=PK.ClaimResolutionMethod.RESOLVED_RANGE,
        resolver_identity="reviewer.synthetic",
        confidence=0.85,
        unresolved_issues=(),
        version=1,
        created_at=components["claims"][0].created_at,
    )
    profiles = tuple(
        replace(item, claim_ids=tuple(sorted((*item.claim_ids, first.claim_id, second.claim_id))))
        if item.profile_id == "pk.species.example_plant"
        else item
        for item in components["profiles"]
    )
    library = build_library(
        claims=(*components["claims"], first, second),
        claim_resolutions=(resolution,),
        profiles=profiles,
    )
    result = PK.resolve_plant_knowledge(
        library,
        request(scientific_name="Examplegenus ficticia"),
    )
    effective = next(
        item
        for item in result.effective_claims
        if item.field_path == "growth.typical_root_depth_meters"
    )
    assert effective.claim_resolution_id == resolution.resolution_id
    assert effective.resolved_range == resolved_range
    assert result.unresolved_ambiguity is False
    assert result.explanation.evidence_source_ids == ("pk.source.synthetic_approved",)


def test_regional_scoring_is_fixed_versioned_and_separate_from_identity() -> None:
    """Regional context adds +10/+5/0/-10 without changing match precedence."""
    library = build_library()
    exact = PK.resolve_plant_knowledge(
        library,
        request(
            scientific_name="Examplegenus ficticia",
            country="XZ",
            state_or_province="Synthetic Province",
            climate_zone_ids=("synthetic-climate-1",),
            wucols_region="synthetic-wucols-1",
            usda_hardiness_zone="9b",
            coastal=True,
            inland=False,
        ),
    )
    candidate = next(
        item for item in exact.candidates if item.profile_id == exact.selected_profile_id
    )
    assert candidate.identity_score == 80
    assert candidate.regional_score == 10
    assert candidate.total_score == 90
    assert exact.resolution_confidence == round(90 / 110, 6)
    mismatch = PK.resolve_plant_knowledge(
        library,
        request(scientific_name="Examplegenus ficticia", country="YY"),
    )
    mismatch_candidate = next(
        item for item in mismatch.candidates if item.profile_id == mismatch.selected_profile_id
    )
    assert mismatch_candidate.identity_score == 80
    assert mismatch_candidate.regional_score == -10
    assert mismatch.explanation.mismatched_regional_attributes == ("country",)


def test_ambiguity_is_reported_with_deterministic_tie_breaking() -> None:
    """Equal common-name candidates remain visible and request user verification."""
    components = base_components()
    alternate_claim = claim(
        "pk.claim.alternate_species_identity",
        "identity.scientific_name",
        "Alternategenus ficticia",
    )
    alternate = profile(
        "pk.species.alternate_plant",
        "Example Plant",
        PK.ProfileResolutionLevel.SPECIES,
        (alternate_claim.claim_id,),
        scientific_name="Alternategenus ficticia",
        parent_profile_id="pk.category.synthetic_tree",
    )
    library = build_library(
        claims=(*components["claims"], alternate_claim),
        profiles=(*components["profiles"], alternate),
    )
    result = PK.resolve_plant_knowledge(library, request(common_name="example plant"))
    assert result.selected_profile_id == "pk.species.alternate_plant"
    assert result.unresolved_ambiguity is True
    assert result.reason_code is PK.ResolutionReasonCode.AMBIGUOUS_MATCH
    assert result.suggested_verification_action is not None
    assert {item.profile_id for item in result.candidates if item.identity_score == 80} == {
        "pk.species.alternate_plant",
        "pk.species.example_plant",
    }


def test_deprecated_and_superseded_profiles_are_excluded_by_default() -> None:
    """Inactive profiles remain auditable candidates but cannot be selected."""
    components = base_components()
    species = next(
        item for item in components["profiles"] if item.profile_id == "pk.species.example_plant"
    )
    deprecated_profiles = tuple(
        replace(item, lifecycle_state=PK.LifecycleState.DEPRECATED) if item is species else item
        for item in components["profiles"]
    )
    deprecated_library = build_library(profiles=deprecated_profiles)
    deprecated_result = PK.resolve_plant_knowledge(
        deprecated_library,
        request(scientific_name="Examplegenus ficticia"),
    )
    assert deprecated_result.selected_profile_id != species.profile_id
    excluded = next(
        item for item in deprecated_result.candidates if item.profile_id == species.profile_id
    )
    assert excluded.eligible is False

    successor = replace(species, profile_id="pk.species.example_plant_v2")
    superseded_profiles = tuple(
        replace(
            item,
            lifecycle_state=PK.LifecycleState.SUPERSEDED,
            superseded_profile_id=successor.profile_id,
        )
        if item is species
        else item
        for item in components["profiles"]
    )
    library = build_library(profiles=(*superseded_profiles, successor))
    result = PK.resolve_plant_knowledge(
        library,
        request(scientific_name="Examplegenus ficticia"),
    )
    assert result.selected_profile_id == successor.profile_id
    with pytest.raises(ValueError, match="deprecated or superseded"):
        PK.resolve_plant_knowledge(
            library,
            request(user_confirmed_profile_id=species.profile_id),
        )


def test_no_eligible_profile_is_explainable() -> None:
    """A library without a matching fallback returns an explicit non-match result."""
    components = base_components()
    profiles = tuple(
        item
        for item in components["profiles"]
        if item.resolution_level is not PK.ProfileResolutionLevel.UNKNOWN_FALLBACK
    )
    result = PK.resolve_plant_knowledge(build_library(profiles=profiles), request())
    assert result.selected_profile_id is None
    assert result.reason_code is PK.ResolutionReasonCode.NO_ELIGIBLE_PROFILE
    assert result.resolution_confidence == 0
    assert result.explanation.unavailable_regional_attributes == ("profile_match",)


def test_matched_aliases_fallback_chain_and_explanation_are_machine_readable() -> None:
    """Resolution exposes all candidates, successful precedence, aliases, and evidence."""
    result = PK.resolve_plant_knowledge(
        build_library(),
        request(common_name=" fictional   example "),
    )
    assert result.selected_profile_id == "pk.species.example_plant"
    assert result.matched_aliases == ("Fictional Example",)
    assert result.fallback_chain == (
        PK.ProfileResolutionLevel.CULTIVAR,
        PK.ProfileResolutionLevel.SPECIES,
    )
    assert result.explanation.reason_code is PK.ResolutionReasonCode.EXACT_SPECIES_MATCH
    assert result.explanation.algorithm_version == result.algorithm_version
    assert result.explanation.candidate_profile_ids == tuple(
        item.profile_id for item in result.candidates
    )
    assert "exact matching" in result.explanation.summary


def test_public_api_is_explicit_and_has_no_forbidden_runtime_surfaces() -> None:
    """The stable package boundary contains models, validation, and resolution only."""
    public_names = set(PK.__all__)
    assert "PlantKnowledgeLibrary" in public_names
    assert "resolve_plant_knowledge" in public_names
    assert "calculate_library_checksum" in public_names
    assert not any(name.startswith("_") for name in public_names)
    forbidden_fragments = (
        "OpenAI",
        "WeatherProvider",
        "Controller",
        "IrrigationCommand",
        "WaterDemandCalculator",
        "DiseaseDiagnosis",
        "Schedule",
        "execute",
        "recommend_irrigation",
    )
    assert not any(hasattr(PK, name) for name in forbidden_fragments)
    assert REGION.to_dict()["countries"] == ["XZ"]
