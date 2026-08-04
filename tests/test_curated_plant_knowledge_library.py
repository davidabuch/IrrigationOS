"""Tests for the canonical curated Plant Knowledge library boundary."""

from __future__ import annotations

from tests.helpers import load_integration_module

PK = load_integration_module("plant_knowledge")

_EXPECTED_SOURCE_IDS = (
    "pk.source.calflora_database",
    "pk.source.kew_powo",
    "pk.source.usda_plants",
    "pk.source.wucols_iv",
    "pk.source.wucols_v",
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
    "pk.claim.cynodon_dactylon.plant_factor",
    "pk.claim.cynodon_dactylon.scientific_name",
    "pk.claim.dymondia_margaretae.plant_factor",
    "pk.claim.dymondia_margaretae.scientific_name",
    "pk.claim.heteromeles_arbutifolia.scientific_name",
    "pk.claim.lagerstroemia_indica.scientific_name",
    "pk.claim.muhlenbergia_rigens.plant_factor",
    "pk.claim.muhlenbergia_rigens.scientific_name",
    "pk.claim.quercus_agrifolia.scientific_name",
    "pk.claim.rhaphiolepis_indica.plant_factor",
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
_EXPECTED_CHECKSUM = "640fb7a1e4c2520f44ea2fb691fde23e0cd1c78c4f0708e83d25e4a7f5a22636"
_EXPECTED_WATER_PROFILE_IDS = {
    "pk.species.cynodon_dactylon",
    "pk.species.dymondia_margaretae",
    "pk.species.muhlenbergia_rigens",
    "pk.species.rhaphiolepis_indica",
}


def test_curated_library_builds_with_published_identity_profiles() -> None:
    """The curated boundary builds one fully validated v1.3.0 aggregate."""
    library = PK.build_curated_plant_knowledge_library()

    assert library.manifest.library_version == "1.3.0"
    assert library.manifest.previous_library_version == "1.2.0"
    assert library.manifest.schema_version == PK.PLANT_KNOWLEDGE_SCHEMA_VERSION
    assert library.manifest.source_count == 5
    assert library.manifest.functional_group_count == 10
    assert library.manifest.profile_count == 8
    assert library.manifest.species_count == 8
    assert library.manifest.published_profile_count == 8
    assert library.manifest.claim_count == 12
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
    """Every profile retains its approved POWO-backed identity claim."""
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
        identity_claim = next(
            claims[claim_id]
            for claim_id in profile.claim_ids
            if claims[claim_id].field_path == "identity.scientific_name"
        )
        assert identity_claim.field_path == "identity.scientific_name"
        assert identity_claim.value == scientific_name
        assert identity_claim.review_state is PK.ReviewState.APPROVED
        assert identity_claim.evidence_grade is PK.EvidenceGrade.HIGH
        assert identity_claim.source_ids == ("pk.source.kew_powo",)
        assert set(identity_claim.intended_consumer_capabilities) & set(
            profile.intended_consumer_capabilities
        )
        if profile.profile_id in _EXPECTED_WATER_PROFILE_IDS:
            assert profile.profile_version == 2
            assert PK.ConsumerCapability.WATER_DEMAND in profile.intended_consumer_capabilities
            assert len(profile.claim_ids) == 2
        else:
            assert profile.profile_version == 1
            assert PK.ConsumerCapability.WATER_DEMAND not in profile.intended_consumer_capabilities
            assert len(profile.claim_ids) == 1


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
    """Profile, water, and taxonomy applicability retain separate explicit scopes."""
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
    identity_claims = tuple(
        claim for claim in library.claims if claim.field_path == "identity.scientific_name"
    )
    water_claims = tuple(
        claim for claim in library.claims if claim.field_path == "water.plant_factor"
    )
    assert all(
        claim.regional_applicability.scope is PK.RegionalScope.UNRESTRICTED
        for claim in identity_claims
    )
    assert all(
        claim.regional_applicability.scope is PK.RegionalScope.REGIONAL
        and claim.regional_applicability.countries == ("US",)
        and claim.regional_applicability.states_or_provinces == ("California",)
        for claim in water_claims
    )


def test_curated_water_evidence_preserves_source_values_and_context() -> None:
    """Water claims preserve scalar-versus-range form and exact WUCOLS regional scope."""
    library = PK.build_curated_plant_knowledge_library()
    sources = {source.source_id: source for source in library.sources}
    water_claims = {
        claim.claim_id: claim
        for claim in library.claims
        if claim.field_path == "water.plant_factor"
    }

    assert set(water_claims) == {
        "pk.claim.cynodon_dactylon.plant_factor",
        "pk.claim.dymondia_margaretae.plant_factor",
        "pk.claim.muhlenbergia_rigens.plant_factor",
        "pk.claim.rhaphiolepis_indica.plant_factor",
    }
    bermudagrass = water_claims["pk.claim.cynodon_dactylon.plant_factor"]
    assert bermudagrass.value == 0.6
    assert not isinstance(bermudagrass.value, PK.KnowledgeRange)
    assert bermudagrass.regional_applicability.wucols_regions == ()
    assert bermudagrass.evidence_grade is PK.EvidenceGrade.HIGH
    assert bermudagrass.confidence == 0.9

    expected_regions = {
        "pk.claim.dymondia_margaretae.plant_factor": (
            "3_south_coastal",
            "4_south_inland",
        ),
        "pk.claim.muhlenbergia_rigens.plant_factor": (
            "3_south_coastal",
            "4_south_inland",
        ),
        "pk.claim.rhaphiolepis_indica.plant_factor": (
            "3_south_coastal",
        ),
    }
    for claim_id, regions in expected_regions.items():
        claim = water_claims[claim_id]
        assert claim.value == PK.KnowledgeRange(
            minimum=0.1,
            maximum=0.3,
            unit=PK.KnowledgeUnit.RATIO,
        )
        assert claim.regional_applicability.wucols_regions == regions
        assert claim.evidence_grade is PK.EvidenceGrade.EXPERT_CONSENSUS
        assert claim.confidence == 0.85

    for claim in water_claims.values():
        assert claim.unit is PK.KnowledgeUnit.RATIO
        assert claim.review_state is PK.ReviewState.APPROVED
        assert claim.reviewed_at is not None
        assert claim.source_ids == ("pk.source.wucols_v",)
        assert sources[claim.source_ids[0]].review_state is PK.ReviewState.APPROVED
        assert claim.intended_consumer_capabilities == (
            PK.ConsumerCapability.WATER_DEMAND,
        )


def test_curated_coverage_is_explicit_and_does_not_force_water_evidence() -> None:
    """Coverage reports identity and water evidence without manufacturing missing claims."""
    library = PK.build_curated_plant_knowledge_library()
    claims = {claim.claim_id: claim for claim in library.claims}
    published = tuple(
        profile
        for profile in library.profiles
        if profile.lifecycle_state is PK.LifecycleState.PUBLISHED
    )
    profiles_with_identity = {
        profile.profile_id
        for profile in published
        if any(
            claims[claim_id].field_path == "identity.scientific_name"
            for claim_id in profile.claim_ids
        )
    }
    profiles_with_water = {
        profile.profile_id
        for profile in published
        if any(
            claims[claim_id].field_path == "water.plant_factor"
            for claim_id in profile.claim_ids
        )
    }

    assert len(published) == 8
    assert len(profiles_with_identity) == 8
    assert profiles_with_water == _EXPECTED_WATER_PROFILE_IDS
    assert {profile.profile_id for profile in published} - profiles_with_water == {
        "pk.species.agave_attenuata",
        "pk.species.heteromeles_arbutifolia",
        "pk.species.lagerstroemia_indica",
        "pk.species.quercus_agrifolia",
    }
    assert sum(
        claim.field_path == "identity.scientific_name" for claim in library.claims
    ) == 8
    assert sum(
        claim.field_path == "water.plant_factor" for claim in library.claims
    ) == 4
    assert {claim.field_path for claim in library.claims} == {
        "identity.scientific_name",
        "water.plant_factor",
    }


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
        claim_count=12,
        minimum=0.85,
        maximum=1.0,
        mean=0.954167,
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
