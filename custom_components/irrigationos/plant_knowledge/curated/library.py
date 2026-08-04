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
from .claims import curated_claims
from .functional_groups import curated_functional_groups
from .profiles import curated_profiles
from .sources import curated_sources

CURATED_PLANT_KNOWLEDGE_LIBRARY_VERSION = "1.2.0"
_CURATED_LIBRARY_GENERATED_AT = datetime(2026, 8, 4, 9, 0, tzinfo=UTC)
_EMPTY_CHECKSUM = "0" * 64


def build_curated_plant_knowledge_library() -> PlantKnowledgeLibrary:
    """Build the immutable, validated curated Plant Knowledge library.

    Capability 6.2C adds the first approved identity claims and published species profiles to the
    sources and descriptive functional-group hierarchy established by Capability 6.2B.
    """
    sources = curated_sources()
    claims = curated_claims()
    claim_resolutions = ()
    functional_groups = curated_functional_groups()
    profiles = curated_profiles()
    confidences = tuple(claim.confidence for claim in claims)

    manifest = PlantKnowledgeManifest(
        schema_version=PLANT_KNOWLEDGE_SCHEMA_VERSION,
        library_version=CURATED_PLANT_KNOWLEDGE_LIBRARY_VERSION,
        generated_at=_CURATED_LIBRARY_GENERATED_AT,
        supported_climate_regions=("southern_california_mediterranean",),
        usda_zone_minimum=None,
        usda_zone_maximum=None,
        profile_count=len(profiles),
        category_count=0,
        functional_group_count=len(functional_groups),
        genus_count=0,
        species_count=len(profiles),
        cultivar_count=0,
        source_count=len(sources),
        claim_count=len(claims),
        claim_resolution_count=0,
        published_profile_count=len(profiles),
        confidence_statistics=ClaimConfidenceStatistics(
            claim_count=len(confidences),
            minimum=min(confidences),
            maximum=max(confidences),
            mean=round(sum(confidences) / len(confidences), 6),
        ),
        validation_checksum=_EMPTY_CHECKSUM,
        previous_library_version="1.1.0",
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
