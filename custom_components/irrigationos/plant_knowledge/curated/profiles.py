"""Canonical published profiles in the initial curated plant catalog."""

from __future__ import annotations

from datetime import UTC, datetime

from ..models import (
    PLANT_KNOWLEDGE_SCHEMA_VERSION,
    ConsumerCapability,
    LifecycleState,
    PlantCategory,
    PlantKnowledgeProfile,
    ProfileResolutionLevel,
    RegionalApplicability,
    RegionalScope,
)

_CREATED_AT = datetime(2026, 8, 4, 8, 15, tzinfo=UTC)
_REVIEWED_AT = datetime(2026, 8, 4, 8, 45, tzinfo=UTC)
_IDENTITY_CONSUMERS = (
    ConsumerCapability.LEARNING,
    ConsumerCapability.VISUAL_IDENTIFICATION,
)
_WATER_CONSUMERS = (
    ConsumerCapability.LEARNING,
    ConsumerCapability.VISUAL_IDENTIFICATION,
    ConsumerCapability.WATER_DEMAND,
)
_WATER_REVIEWED_AT = datetime(2026, 8, 4, 10, 0, tzinfo=UTC)
_SOUTHERN_CALIFORNIA_SCOPE = RegionalApplicability(
    scope=RegionalScope.REGIONAL,
    countries=("US",),
    states_or_provinces=("California",),
    climate_zone_ids=("southern_california_mediterranean",),
    notes=(
        "Curated for Southern California identity resolution; this scope does not assert "
        "suitability, water need, or irrigation guidance."
    ),
)


def _published_species_profile(
    *,
    profile_id: str,
    preferred_common_name: str,
    scientific_name: str,
    aliases: tuple[str, ...],
    broad_category: PlantCategory,
    functional_group_ids: tuple[str, ...],
    claim_id: str,
    water_claim_id: str | None = None,
) -> PlantKnowledgeProfile:
    species_key = profile_id.removeprefix("pk.species.")
    stress_claim_ids = (
        f"pk.claim.{species_key}.heat_tolerance",
        f"pk.claim.{species_key}.minimum_temperature_celsius",
        f"pk.claim.{species_key}.water_stress_sensitivity",
    )
    claim_ids = tuple(
        sorted(
            (claim_id, *stress_claim_ids)
            if water_claim_id is None
            else (claim_id, water_claim_id, *stress_claim_ids)
        )
    )
    return PlantKnowledgeProfile(
        profile_id=profile_id,
        preferred_common_name=preferred_common_name,
        scientific_name=scientific_name,
        aliases=aliases,
        cultivar=None,
        broad_category=broad_category,
        resolution_level=ProfileResolutionLevel.SPECIES,
        parent_profile_id=None,
        functional_group_ids=functional_group_ids,
        claim_ids=claim_ids,
        regional_applicability=_SOUTHERN_CALIFORNIA_SCOPE,
        intended_consumer_capabilities=tuple(
            sorted(
                {
                    *_WATER_CONSUMERS,
                    ConsumerCapability.PLANT_HEALTH,
                },
                key=lambda capability: capability.value,
            )
        ),
        schema_version=PLANT_KNOWLEDGE_SCHEMA_VERSION,
        profile_version=3 if water_claim_id is not None else 2,
        lifecycle_state=LifecycleState.PUBLISHED,
        created_at=_CREATED_AT,
        reviewed_at=datetime(2026, 8, 5, 18, 30, tzinfo=UTC),
    )


def curated_profiles() -> tuple[PlantKnowledgeProfile, ...]:
    """Return the initial published species profiles in canonical-ID order."""
    return (
        _published_species_profile(
            profile_id="pk.species.agave_attenuata",
            preferred_common_name="Foxtail agave",
            scientific_name="Agave attenuata",
            aliases=("Fox tail agave",),
            broad_category=PlantCategory.SUCCULENT,
            functional_group_ids=(
                "pk.group.mediterranean_climate",
                "pk.group.succulent",
            ),
            claim_id="pk.claim.agave_attenuata.scientific_name",
        ),
        _published_species_profile(
            profile_id="pk.species.cynodon_dactylon",
            preferred_common_name="Bermudagrass",
            scientific_name="Cynodon dactylon",
            aliases=("Bermuda grass",),
            broad_category=PlantCategory.TURF,
            functional_group_ids=("pk.group.turfgrass",),
            claim_id="pk.claim.cynodon_dactylon.scientific_name",
            water_claim_id="pk.claim.cynodon_dactylon.plant_factor",
        ),
        _published_species_profile(
            profile_id="pk.species.dymondia_margaretae",
            preferred_common_name="Dymondia",
            scientific_name="Dymondia margaretae",
            aliases=("Silver carpet",),
            broad_category=PlantCategory.GROUNDCOVER,
            functional_group_ids=(
                "pk.group.herbaceous.groundcover",
                "pk.group.mediterranean_climate",
            ),
            claim_id="pk.claim.dymondia_margaretae.scientific_name",
            water_claim_id="pk.claim.dymondia_margaretae.plant_factor",
        ),
        _published_species_profile(
            profile_id="pk.species.heteromeles_arbutifolia",
            preferred_common_name="Toyon",
            scientific_name="Heteromeles arbutifolia",
            aliases=("California holly",),
            broad_category=PlantCategory.TREE,
            functional_group_ids=(
                "pk.group.california_native",
                "pk.group.mediterranean_climate",
                "pk.group.woody.tree",
            ),
            claim_id="pk.claim.heteromeles_arbutifolia.scientific_name",
        ),
        _published_species_profile(
            profile_id="pk.species.lagerstroemia_indica",
            preferred_common_name="Crape myrtle",
            scientific_name="Lagerstroemia indica",
            aliases=("Crepe myrtle",),
            broad_category=PlantCategory.TREE,
            functional_group_ids=("pk.group.woody.tree",),
            claim_id="pk.claim.lagerstroemia_indica.scientific_name",
        ),
        _published_species_profile(
            profile_id="pk.species.muhlenbergia_rigens",
            preferred_common_name="Deer grass",
            scientific_name="Muhlenbergia rigens",
            aliases=("Deergrass",),
            broad_category=PlantCategory.HERBACEOUS,
            functional_group_ids=(
                "pk.group.california_native",
                "pk.group.herbaceous.ornamental_grass",
                "pk.group.mediterranean_climate",
            ),
            claim_id="pk.claim.muhlenbergia_rigens.scientific_name",
            water_claim_id="pk.claim.muhlenbergia_rigens.plant_factor",
        ),
        _published_species_profile(
            profile_id="pk.species.quercus_agrifolia",
            preferred_common_name="Coast live oak",
            scientific_name="Quercus agrifolia",
            aliases=("California live oak",),
            broad_category=PlantCategory.TREE,
            functional_group_ids=(
                "pk.group.california_native",
                "pk.group.mediterranean_climate",
                "pk.group.woody.tree",
            ),
            claim_id="pk.claim.quercus_agrifolia.scientific_name",
        ),
        _published_species_profile(
            profile_id="pk.species.rhaphiolepis_indica",
            preferred_common_name="Indian hawthorn",
            scientific_name="Rhaphiolepis indica",
            aliases=("India hawthorn",),
            broad_category=PlantCategory.SHRUB,
            functional_group_ids=(
                "pk.group.mediterranean_climate",
                "pk.group.woody.shrub",
            ),
            claim_id="pk.claim.rhaphiolepis_indica.scientific_name",
            water_claim_id="pk.claim.rhaphiolepis_indica.plant_factor",
        ),
    )
