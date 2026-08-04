"""Tests for the canonical curated Plant Knowledge library boundary."""

from __future__ import annotations

from tests.helpers import load_integration_module

PK = load_integration_module("plant_knowledge")


def test_curated_library_builds_as_empty_valid_versioned_aggregate() -> None:
    """The infrastructure milestone builds one valid immutable empty aggregate."""
    library = PK.build_curated_plant_knowledge_library()

    assert library.manifest.library_version == "1.0.0"
    assert library.manifest.schema_version == PK.PLANT_KNOWLEDGE_SCHEMA_VERSION
    assert library.manifest.profile_count == 0
    assert library.manifest.source_count == 0
    assert library.manifest.claim_count == 0
    assert library.sources == ()
    assert library.claims == ()
    assert library.claim_resolutions == ()
    assert library.functional_groups == ()
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
