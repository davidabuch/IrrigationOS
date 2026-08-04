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


def test_curated_library_builds_with_sources_and_functional_groups() -> None:
    """The evidence milestone builds one valid immutable aggregate without profiles."""
    library = PK.build_curated_plant_knowledge_library()

    assert library.manifest.library_version == "1.1.0"
    assert library.manifest.previous_library_version == "1.0.0"
    assert library.manifest.schema_version == PK.PLANT_KNOWLEDGE_SCHEMA_VERSION
    assert library.manifest.source_count == 4
    assert library.manifest.functional_group_count == 10
    assert library.manifest.profile_count == 0
    assert library.manifest.claim_count == 0
    assert tuple(source.source_id for source in library.sources) == _EXPECTED_SOURCE_IDS
    assert tuple(group.group_id for group in library.functional_groups) == _EXPECTED_GROUP_IDS
    assert library.claims == ()
    assert library.claim_resolutions == ()
    assert library.profiles == ()


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


def test_curated_functional_group_hierarchy_is_descriptive_only() -> None:
    """Groups remain deterministic membership metadata and do not introduce claims."""
    library = PK.build_curated_plant_knowledge_library()
    by_id = {group.group_id: group for group in library.functional_groups}

    assert by_id["pk.group.woody.tree"].parent_group_id == "pk.group.woody"
    assert by_id["pk.group.woody.shrub"].parent_group_id == "pk.group.woody"
    assert (
        by_id["pk.group.herbaceous.groundcover"].parent_group_id
        == "pk.group.herbaceous"
    )
    assert library.claims == ()
    assert library.profiles == ()


def test_curated_library_is_deterministic_and_checksummed() -> None:
    """Repeated builds serialize identically and retain the calculated checksum."""
    first = PK.build_curated_plant_knowledge_library()
    second = PK.build_curated_plant_knowledge_library()

    assert first == second
    assert first.to_dict() == second.to_dict()
    assert first.manifest.validation_checksum == PK.calculate_library_checksum(
        manifest=first.manifest,
        sources=first.sources,
        claims=first.claims,
        claim_resolutions=first.claim_resolutions,
        functional_groups=first.functional_groups,
        profiles=first.profiles,
    )
