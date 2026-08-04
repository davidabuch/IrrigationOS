"""Canonical curated Plant Knowledge library construction."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from ..library import PlantKnowledgeLibrary, calculate_library_checksum
from ..models import (
    PLANT_KNOWLEDGE_SCHEMA_VERSION,
    ClaimConfidenceStatistics,
    PlantKnowledgeManifest,
)

CURATED_PLANT_KNOWLEDGE_LIBRARY_VERSION = "1.0.0"
_CURATED_LIBRARY_GENERATED_AT = datetime(2026, 8, 4, 0, 0, tzinfo=UTC)
_EMPTY_CHECKSUM = "0" * 64


def build_curated_plant_knowledge_library() -> PlantKnowledgeLibrary:
    """Build the immutable, validated curated Plant Knowledge library.

    Capability 6.2A establishes only the deterministic construction boundary. Botanical
    sources, claims, functional groups, and profiles are added by later curated-data
    milestones without changing this public API.
    """
    sources = ()
    claims = ()
    claim_resolutions = ()
    functional_groups = ()
    profiles = ()

    manifest = PlantKnowledgeManifest(
        schema_version=PLANT_KNOWLEDGE_SCHEMA_VERSION,
        library_version=CURATED_PLANT_KNOWLEDGE_LIBRARY_VERSION,
        generated_at=_CURATED_LIBRARY_GENERATED_AT,
        supported_climate_regions=(),
        usda_zone_minimum=None,
        usda_zone_maximum=None,
        profile_count=0,
        category_count=0,
        functional_group_count=0,
        genus_count=0,
        species_count=0,
        cultivar_count=0,
        source_count=0,
        claim_count=0,
        claim_resolution_count=0,
        published_profile_count=0,
        confidence_statistics=ClaimConfidenceStatistics(
            claim_count=0,
            minimum=None,
            maximum=None,
            mean=None,
        ),
        validation_checksum=_EMPTY_CHECKSUM,
    )
    manifest = replace(
        manifest,
        validation_checksum=calculate_library_checksum(
            manifest=manifest,
            sources=sources,
            claims=claims,
            claim_resolutions=claim_resolutions,
            functional_groups=functional_groups,
            profiles=profiles,
        ),
    )
    return PlantKnowledgeLibrary(
        manifest=manifest,
        sources=sources,
        claims=claims,
        claim_resolutions=claim_resolutions,
        functional_groups=functional_groups,
        profiles=profiles,
    )
