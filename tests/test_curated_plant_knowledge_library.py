"""Tests for the canonical curated Plant Knowledge library boundary."""

from __future__ import annotations

from tests.helpers import load_integration_module

PK = load_integration_module("plant_knowledge")

_EXPECTED_SOURCE_IDS = (
    "pk.source.calflora_database",
    "pk.source.kew_powo",
    "pk.source.usda_plants",
    "pk.source.wucols_iv",
)
_EXPECTED_GROUP_IDS = (
    "pk.group.california_native",
    "pk.group.herbaceous",
    "pk.group.herbaceous.groundcover",
    "pk.group.herbaceous.ornamental_grass",
    "pk.group.mediterranean_climate",
    "pk.group.succulent",
    "pk.group.turfgrass",
    "pk.group.woody",
    "pk.group.woody.shrub",
    "pk.group.woody.tree",
)
_EXPECTED_CLAIM_IDS = (
    "pk.claim.agave_attenuata.scientific_name",
    "pk.claim.cynodon_dactylon.scientific_name",
    "pk.claim.dymondia_margaretae.scientific_name",
    "pk.claim.heteromeles_arbutifolia.scientific_name",
    "pk.claim.lagerstroemia_indica.scientific_name",
    "pk.claim.muhlenbergia_rigens.scientific_name",
    "pk.claim.quercus_agrifolia.scientific_name",
    "pk.claim.rhaphiolepis_indica.scientific_name",
)
_EXPECTED_PROFILE_IDS = (
    "pk.species.agave_attenuata",
    "pk.species.cynodon_dactylon",
    "pk.species.dymondia_margaretae",
    "pk.species.heteromeles_arbutifolia",
    "pk.species.lagerstroemia_indica",
    "pk.species.muhlenbergia_rigens",
    "pk.species.quercus_agrifolia",
    "pk.species.rhaphiolepis_indica",
)
_EXPECTED_IDENTITIES = {
    "pk.species.agave_attenuata": ("Agave attenuata", "Foxtail agave"),
    "pk.species.cynodon_dactylon": ("Cynodon dactylon", "Bermudagrass"),
    "pk.species.dymondia_margaretae": ("Dymondia margaretae", "Dymondia"),
    "pk.species.heteromeles_arbutifolia": ("Heteromeles arbutifolia", "Toyon"),
    "pk.species.lagerstroemia_indica": ("Lagerstroemia indica", "Crape myrtle"),
    "pk.species.muhlenbergia_rigens": ("Muhlenbergia rigens", "Deer grass"),
    "pk.species.quercus_agrifolia": ("Quercus agrifolia", "Coast live oak"),
    "pk.species.rhaphiolepis_indica": ("Rhaphiolepis indica", "Indian hawthorn"),
}
_EXPECTED_CHECKSUM = "36e347349ca2107d9754346e209bc1668dc66a9a5856044b4dfb1db19ae5c1d8"


def test_curated_library_builds_with_published_identity_profiles() -> None:
    """The curated boundary builds one fully validated v1.2.0 aggregate."""
    library = PK.build_curated_plant_knowledge_library()

    assert library.manifest.library_version == "1.2.0"
    assert library.manifest.previous_library_version == "1.1.0"
    assert library.manifest.schema_version == PK.PLANT_KNOWLEDGE_SCHEMA_VERSION
    assert library.manifest.source_count == 4
    assert library.manifest.functional_group_count == 10
    assert library.manifest.profile_count == 8
    assert library.manifest.species_count == 8
    assert library.manifest.published_profile_count == 8
    assert library.manifest.claim_count == 8
    assert library.manifest.claim_resolution_count == 0
    assert tuple(source.source_id for source in library.sources) == _EXPECTED_SOURCE_IDS
    assert tuple(group.group_id for group in library.functional_groups) == _EXPECTED_GROUP_IDS
    assert tuple(claim.claim_id for claim in library.claims) == _EXPECTED_CLAIM_IDS
    assert tuple(profile.profile_id for profile in library.profiles) == _EXPECTED_PROFILE_IDS
    assert library.claim_resolutions == ()


def test_curated_sources_are_approved_and_auditable() -> None:
    """Every canonical source has a complete chronological approval history."""
    library = PK.build_curated_plant_knowledge_library()

    for source in library.sources:
        assert source.review_state is PK.ReviewState.APPROVED
        assert tuple(record.state for record in source.review_history) == (
            PK.ReviewState.UNREVIEWED,
            PK.ReviewState.REVIEWED,
            PK.ReviewState.APPROVED,
        )
        assert source.url is not None
        assert source.licensing_notes is not None


def test_curated_profiles_and_claims_satisfy_publication_requirements() -> None:
    """All initial profiles use one approved POWO-backed identity claim."""
    library = PK.build_curated_plant_knowledge_library()
    claims = {claim.claim_id: claim for claim in library.claims}

    for profile in library.profiles:
        scientific_name, preferred_common_name = _EXPECTED_IDENTITIES[profile.profile_id]
        assert profile.lifecycle_state is PK.LifecycleState.PUBLISHED
        assert profile.resolution_level is PK.ProfileResolutionLevel.SPECIES
        assert profile.scientific_name == scientific_name
        assert profile.preferred_common_name == preferred_common_name
        assert profile.aliases
        assert profile.reviewed_at is not None
        assert len(profile.claim_ids) == 1
        identity_claim = claims[profile.claim_ids[0]]
        assert identity_claim.field_path == "identity.scientific_name"
        assert identity_claim.value == scientific_name
        assert identity_claim.review_state is PK.ReviewState.APPROVED
        assert identity_claim.evidence_grade is PK.EvidenceGrade.HIGH
        assert identity_claim.source_ids == ("pk.source.kew_powo",)
        assert set(identity_claim.intended_consumer_capabilities) & set(
            profile.intended_consumer_capabilities
        )


def test_curated_ids_and_collections_are_unique_and_canonically_ordered() -> None:
    """Canonical record identities are unique and deterministic."""
    library = PK.build_curated_plant_knowledge_library()

    for identifiers in (
        tuple(source.source_id for source in library.sources),
        tuple(claim.claim_id for claim in library.claims),
        tuple(group.group_id for group in library.functional_groups),
        tuple(profile.profile_id for profile in library.profiles),
    ):
        assert identifiers == tuple(sorted(identifiers))
        assert len(identifiers) == len(set(identifiers))


def test_curated_functional_group_memberships_resolve_to_existing_groups() -> None:
    """Every profile membership resolves without importing group claims."""
    library = PK.build_curated_plant_knowledge_library()
    group_ids = {group.group_id for group in library.functional_groups}
    profiles = {profile.profile_id: profile for profile in library.profiles}

    assert set(profiles["pk.species.agave_attenuata"].functional_group_ids) == {
        "pk.group.mediterranean_climate",
        "pk.group.succulent",
    }
    assert set(profiles["pk.species.cynodon_dactylon"].functional_group_ids) == {
        "pk.group.turfgrass"
    }
    assert set(profiles["pk.species.quercus_agrifolia"].functional_group_ids) == {
        "pk.group.california_native",
        "pk.group.mediterranean_climate",
        "pk.group.woody.tree",
    }
    assert all(
        set(profile.functional_group_ids) <= group_ids for profile in library.profiles
    )
    assert all(profile.parent_profile_id is None for profile in library.profiles)


def test_curated_regional_applicability_is_explicit() -> None:
    """Profile curation scope is regional while taxonomy claims are explicitly broad."""
    library = PK.build_curated_plant_knowledge_library()

    for profile in library.profiles:
        applicability = profile.regional_applicability
        assert applicability.scope is PK.RegionalScope.REGIONAL
        assert applicability.countries == ("US",)
        assert applicability.states_or_provinces == ("California",)
        assert applicability.climate_zone_ids == (
            "southern_california_mediterranean",
        )
        assert applicability.notes is not None
    assert all(
        claim.regional_applicability.scope is PK.RegionalScope.UNRESTRICTED
        for claim in library.claims
    )


def test_curated_scientific_common_and_alias_resolution() -> None:
    """Representative accepted, preferred, and alias names resolve exactly."""
    library = PK.build_curated_plant_knowledge_library()

    scientific = PK.resolve_plant_knowledge(
        library,
        PK.PlantKnowledgeResolutionRequest(
            request_id="pk.request.curated_scientific",
            scientific_name="Quercus agrifolia",
            country="US",
            state_or_province="California",
            climate_zone_ids=("southern_california_mediterranean",),
        ),
    )
    common = PK.resolve_plant_knowledge(
        library,
        PK.PlantKnowledgeResolutionRequest(
            request_id="pk.request.curated_common",
            common_name="Toyon",
        ),
    )
    alias = PK.resolve_plant_knowledge(
        library,
        PK.PlantKnowledgeResolutionRequest(
            request_id="pk.request.curated_alias",
            common_name="  CREPE   MYRTLE ",
        ),
    )

    assert scientific.selected_profile_id == "pk.species.quercus_agrifolia"
    assert scientific.selected_resolution_level is PK.ProfileResolutionLevel.SPECIES
    assert scientific.explanation.evidence_source_ids == ("pk.source.kew_powo",)
    assert common.selected_profile_id == "pk.species.heteromeles_arbutifolia"
    assert alias.selected_profile_id == "pk.species.lagerstroemia_indica"
    assert alias.matched_aliases == ("Crepe myrtle",)
    assert not scientific.unresolved_ambiguity
    assert not common.unresolved_ambiguity
    assert not alias.unresolved_ambiguity


def test_curated_manifest_counts_statistics_and_checksum_match_content() -> None:
    """The manifest exactly describes its records and locks the reviewed checksum."""
    library = PK.build_curated_plant_knowledge_library()
    manifest = library.manifest

    assert manifest.supported_climate_regions == (
        "southern_california_mediterranean",
    )
    assert manifest.category_count == 0
    assert manifest.genus_count == 0
    assert manifest.cultivar_count == 0
    assert manifest.confidence_statistics == PK.ClaimConfidenceStatistics(
        claim_count=8,
        minimum=1.0,
        maximum=1.0,
        mean=1.0,
    )
    assert manifest.validation_checksum == _EXPECTED_CHECKSUM
    assert manifest.validation_checksum == PK.calculate_library_checksum(
        manifest=manifest,
        sources=library.sources,
        claims=library.claims,
        claim_resolutions=library.claim_resolutions,
        functional_groups=library.functional_groups,
        profiles=library.profiles,
    )


def test_curated_library_rebuild_is_identical_and_has_no_runtime_surface() -> None:
    """Repeated builds are identical and expose no execution or provider behavior."""
    first = PK.build_curated_plant_knowledge_library()
    second = PK.build_curated_plant_knowledge_library()

    assert first == second
    assert first.to_dict() == second.to_dict()
    assert first.manifest.validation_checksum == second.manifest.validation_checksum
    for name in (
        "download",
        "execute",
        "persist",
        "recommend",
        "schedule",
        "update_remote",
    ):
        assert not hasattr(first, name)
