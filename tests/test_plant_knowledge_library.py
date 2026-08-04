"""Behavioral tests for Plant Knowledge aggregate validation and checksums."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from tests.plant_knowledge_fixtures import (
    NOW,
    PK,
    REGION,
    approved_source,
    base_components,
    build_library,
    claim,
    profile,
)


def _reconstruct(library: Any, manifest: Any) -> Any:
    return PK.PlantKnowledgeLibrary(
        manifest=manifest,
        sources=library.sources,
        claims=library.claims,
        claim_resolutions=library.claim_resolutions,
        functional_groups=library.functional_groups,
        profiles=library.profiles,
    )


def test_valid_library_serialization_manifest_counts_and_checksum() -> None:
    """A complete aggregate is auditable and exactly summarized by its manifest."""
    library = build_library()
    assert library.manifest.profile_count == len(library.profiles)
    assert library.manifest.functional_group_count == len(library.functional_groups)
    assert library.manifest.claim_count == len(library.claims)
    assert library.manifest.published_profile_count == len(library.profiles)
    assert len(library.manifest.validation_checksum) == 64
    assert library.to_dict() == library.to_dict()


def test_checksum_is_sha256_deterministic_and_collection_order_independent() -> None:
    """Canonical hashing sorts collections and excludes only its checksum field."""
    library = build_library()
    first = PK.calculate_library_checksum(
        manifest=library.manifest,
        sources=library.sources,
        claims=library.claims,
        claim_resolutions=library.claim_resolutions,
        functional_groups=library.functional_groups,
        profiles=library.profiles,
    )
    second = PK.calculate_library_checksum(
        manifest=library.manifest,
        sources=tuple(reversed(library.sources)),
        claims=tuple(reversed(library.claims)),
        claim_resolutions=tuple(reversed(library.claim_resolutions)),
        functional_groups=tuple(reversed(library.functional_groups)),
        profiles=tuple(reversed(library.profiles)),
    )
    assert first == second == library.manifest.validation_checksum


def test_manifest_count_and_checksum_mismatches_are_rejected() -> None:
    """Malformed manifests are rejected rather than silently repaired."""
    library = build_library()
    wrong_count = replace(
        library.manifest,
        profile_count=library.manifest.profile_count + 1,
    )
    with pytest.raises(ValueError, match="profile_count"):
        _reconstruct(library, wrong_count)
    wrong_checksum = replace(library.manifest, validation_checksum="f" * 64)
    with pytest.raises(ValueError, match="checksum"):
        _reconstruct(library, wrong_checksum)


def test_aggregate_rejects_unknown_source_claim_group_and_parent_references() -> None:
    """All cross-references must resolve inside the immutable aggregate."""
    components = base_components()
    bad_claim = replace(components["claims"][0], source_ids=("pk.source.missing",))
    with pytest.raises(ValueError, match="unknown sources"):
        build_library(claims=(bad_claim, *components["claims"][1:]))
    species = next(
        item for item in components["profiles"] if item.profile_id == "pk.species.example_plant"
    )
    with pytest.raises(ValueError, match="unknown claims"):
        build_library(
            profiles=tuple(
                replace(item, claim_ids=("pk.claim.missing",)) if item is species else item
                for item in components["profiles"]
            )
        )
    with pytest.raises(ValueError, match="unknown functional groups"):
        build_library(
            profiles=tuple(
                replace(item, functional_group_ids=("pk.group.missing",))
                if item is species
                else item
                for item in components["profiles"]
            )
        )


def test_functional_group_hierarchy_is_separate_acyclic_and_bounded() -> None:
    """Group membership does not import claims; the group graph is bounded."""
    library = build_library()
    group_profile = library.get_profile("pk.group.synthetic_fruit_tree")
    assert group_profile.claim_ids == ("pk.claim.group_identity",)
    assert "pk.claim.category_visual" not in group_profile.claim_ids
    first, second = library.functional_groups
    cyclic = (
        replace(first, parent_group_id=second.group_id),
        replace(second, parent_group_id=first.group_id),
    )
    with pytest.raises(ValueError, match="must be acyclic"):
        build_library(functional_groups=cyclic)
    deep_groups = tuple(
        PK.PlantFunctionalGroup(
            group_id=f"pk.group.depth_{index:02d}",
            display_name=f"Synthetic Group {index}",
            description="Fictional graph-depth test node.",
            intended_consumer_capabilities=(PK.ConsumerCapability.LEARNING,),
            lifecycle_state=PK.LifecycleState.DRAFT,
            version=1,
            parent_group_id=(f"pk.group.depth_{index - 1:02d}" if index > 1 else None),
        )
        for index in range(1, PK.MAX_FUNCTIONAL_GROUP_DEPTH + 2)
    )
    with pytest.raises(ValueError, match="exceeds maximum depth"):
        build_library(functional_groups=(*library.functional_groups, *deep_groups))


def test_profile_inheritance_is_acyclic_and_bounded() -> None:
    """Explicit parent-profile chains reject cycles and excessive depth."""
    components = base_components()
    category = next(
        item for item in components["profiles"] if item.profile_id == "pk.category.synthetic_tree"
    )
    species = next(
        item for item in components["profiles"] if item.profile_id == "pk.species.example_plant"
    )
    cyclic_profiles = tuple(
        replace(item, parent_profile_id=species.profile_id) if item is category else item
        for item in components["profiles"]
    )
    with pytest.raises(ValueError, match="profile inheritance must be acyclic"):
        build_library(profiles=cyclic_profiles)
    deep_profiles = tuple(
        profile(
            f"pk.category.depth_{index:02d}",
            f"Synthetic Depth {index}",
            PK.ProfileResolutionLevel.CATEGORY_FALLBACK,
            (),
            parent_profile_id=(f"pk.category.depth_{index - 1:02d}" if index > 1 else None),
            lifecycle_state=PK.LifecycleState.DRAFT,
        )
        for index in range(1, PK.MAX_PROFILE_INHERITANCE_DEPTH + 2)
    )
    with pytest.raises(ValueError, match="exceeds maximum depth"):
        build_library(profiles=(*components["profiles"], *deep_profiles))


def test_claim_and_profile_supersession_references_and_cycles_are_rejected() -> None:
    """Supersession preserves old records but requires valid acyclic successors."""
    components = base_components()
    original = components["claims"][0]
    with pytest.raises(ValueError, match="unknown superseding claim"):
        build_library(
            claims=(
                replace(original, superseded_claim_id="pk.claim.missing"),
                *components["claims"][1:],
            )
        )
    second = claim(
        "pk.claim.category_identity_next",
        original.field_path,
        "Synthetic Tree Category Next",
        superseded_claim_id=original.claim_id,
    )
    cycle_claims = (
        replace(original, superseded_claim_id=second.claim_id),
        second,
        *components["claims"][1:],
    )
    with pytest.raises(ValueError, match="claim supersession must be acyclic"):
        build_library(claims=cycle_claims)
    category = next(
        item for item in components["profiles"] if item.profile_id == "pk.category.synthetic_tree"
    )
    group = next(
        item
        for item in components["profiles"]
        if item.profile_id == "pk.group.synthetic_fruit_tree"
    )
    profile_cycle = tuple(
        replace(
            item,
            lifecycle_state=PK.LifecycleState.SUPERSEDED,
            superseded_profile_id=group.profile_id,
        )
        if item is category
        else replace(
            item,
            lifecycle_state=PK.LifecycleState.SUPERSEDED,
            superseded_profile_id=category.profile_id,
        )
        if item is group
        else item
        for item in components["profiles"]
    )
    with pytest.raises(ValueError, match="profile supersession must be acyclic"):
        build_library(profiles=profile_cycle)


def test_conflicting_claims_and_resolution_are_retained() -> None:
    """Competing claims survive aggregate validation alongside their resolution."""
    components = base_components()
    first = claim(
        "pk.claim.species_visual_a",
        "visual.leaf_shape",
        PK.LeafShape.BROAD,
        unresolved_conflict=True,
    )
    second = claim(
        "pk.claim.species_visual_b",
        "visual.leaf_shape",
        PK.LeafShape.LINEAR,
        unresolved_conflict=True,
    )
    resolution = PK.ClaimResolution(
        resolution_id="pk.resolution.species_visual",
        field_path="visual.leaf_shape",
        competing_claim_ids=(first.claim_id, second.claim_id),
        selected_claim_id=second.claim_id,
        resolved_range=None,
        regional_weights=(),
        resolution_method=PK.ClaimResolutionMethod.REVIEWER_DECISION,
        resolver_identity="reviewer.synthetic",
        confidence=0.7,
        unresolved_issues=("Fictional observations disagree",),
        version=1,
        created_at=NOW,
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
    assert library.get_claim(first.claim_id) is first
    assert library.get_claim(second.claim_id) is second
    assert library.claim_resolutions == (resolution,)


def test_claim_resolution_references_and_field_paths_are_validated() -> None:
    """Aggregate claim resolutions cannot point outside their competing field."""
    components = base_components()
    claims = components["claims"]
    resolution = PK.ClaimResolution(
        resolution_id="pk.resolution.invalid_field_mix",
        field_path=claims[0].field_path,
        competing_claim_ids=(claims[0].claim_id, claims[1].claim_id),
        selected_claim_id=claims[0].claim_id,
        resolved_range=None,
        regional_weights=(),
        resolution_method=PK.ClaimResolutionMethod.SELECTED_CLAIM,
        resolver_identity="algorithm.synthetic",
        confidence=0.5,
        unresolved_issues=(),
        version=1,
        created_at=NOW,
    )
    with pytest.raises(ValueError, match="share the resolution field path"):
        build_library(claim_resolutions=(resolution,))


def test_published_profiles_require_approved_source_backed_nonprovisional_evidence() -> None:
    """Published knowledge cannot rely on rejected or provisional-only evidence."""
    components = base_components()
    rejected = replace(
        approved_source(),
        review_state=PK.ReviewState.REJECTED,
        review_history=(
            PK.SourceReviewRecord(PK.ReviewState.UNREVIEWED, NOW, "reviewer.synthetic"),
            PK.SourceReviewRecord(
                PK.ReviewState.REJECTED,
                NOW.replace(day=3),
                "reviewer.synthetic",
            ),
        ),
    )
    with pytest.raises(ValueError, match="reviewed or approved sources"):
        build_library(sources=(rejected,))
    provisional = tuple(
        replace(item, evidence_grade=PK.EvidenceGrade.PROVISIONAL) for item in components["claims"]
    )
    with pytest.raises(ValueError, match="provisional evidence"):
        build_library(claims=provisional)


def test_duplicate_published_identity_and_fallback_scope_are_rejected() -> None:
    """Published identities must not be ambiguous within the same regional scope."""
    components = base_components()
    species = next(
        item for item in components["profiles"] if item.profile_id == "pk.species.example_plant"
    )
    duplicate_species = replace(
        species,
        profile_id="pk.species.example_duplicate",
        parent_profile_id="pk.category.synthetic_tree",
    )
    with pytest.raises(ValueError, match="scientific-name"):
        build_library(profiles=(*components["profiles"], duplicate_species))
    category = next(
        item for item in components["profiles"] if item.profile_id == "pk.category.synthetic_tree"
    )
    duplicate_category = replace(category, profile_id="pk.category.synthetic_tree_duplicate")
    with pytest.raises(ValueError, match="fallback identity"):
        build_library(profiles=(*components["profiles"], duplicate_category))


def test_library_contains_no_production_data_loader_or_mutation_surface() -> None:
    """The aggregate exposes validation and lookup, not persistence or remote updates."""
    library = build_library()
    for name in ("load", "save", "download", "update_remote", "publish", "mutate"):
        assert not hasattr(library, name)
    assert all("synthetic" in source.citation.casefold() for source in library.sources)
    assert REGION in tuple(item.regional_applicability for item in library.profiles)
