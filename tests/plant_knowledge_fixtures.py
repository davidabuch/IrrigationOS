"""Obviously fictional Plant Knowledge records shared by behavioral tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Any

from tests.helpers import load_integration_module

PK = load_integration_module("plant_knowledge")

NOW = datetime(2026, 1, 2, 12, 0, tzinfo=UTC)
REVIEWED = datetime(2026, 1, 3, 12, 0, tzinfo=UTC)
REGION = PK.RegionalApplicability(
    scope=PK.RegionalScope.REGIONAL,
    countries=("XZ",),
    states_or_provinces=("Synthetic Province",),
    climate_zone_ids=("synthetic-climate-1",),
    wucols_regions=("synthetic-wucols-1",),
    usda_zone_minimum="9a",
    usda_zone_maximum="10b",
    coastal=PK.CoastalApplicability.APPLIES,
    inland=PK.InlandApplicability.DOES_NOT_APPLY,
    elevation_minimum_meters=0,
    elevation_maximum_meters=500,
    seasons=(PK.Season.SUMMER,),
    notes="Fictional regional scope used only for framework tests.",
)


def approved_source(
    source_id: str = "pk.source.synthetic_approved",
) -> Any:
    """Build a fictional approved source with immutable review history."""
    return PK.PlantKnowledgeSource(
        source_id=source_id,
        organization="Synthetic Evidence Institute",
        title="Fictional Plant Evidence",
        authors=("Example, Avery", "Sample, Rowan"),
        publication_date=date(2025, 1, 1),
        accessed_date=date(2026, 1, 1),
        citation="Synthetic citation; not horticultural guidance.",
        source_type=PK.SourceType.EXPERT_REVIEWED_INTERNAL,
        geographic_scope=("Synthetic Region",),
        review_state=PK.ReviewState.APPROVED,
        review_history=(
            PK.SourceReviewRecord(PK.ReviewState.UNREVIEWED, NOW, "reviewer.synthetic"),
            PK.SourceReviewRecord(PK.ReviewState.REVIEWED, REVIEWED, "reviewer.synthetic"),
            PK.SourceReviewRecord(
                PK.ReviewState.APPROVED,
                datetime(2026, 1, 4, 12, 0, tzinfo=UTC),
                "reviewer.synthetic",
            ),
        ),
        url="https://example.invalid/synthetic-evidence",
        licensing_notes="Fictional test material only.",
    )


def claim(
    claim_id: str,
    field_path: str,
    value: object,
    *,
    unit: Any = None,
    source_ids: tuple[str, ...] = ("pk.source.synthetic_approved",),
    confidence: float = 0.8,
    evidence_grade: Any = None,
    unresolved_conflict: bool = False,
    superseded_claim_id: str | None = None,
) -> Any:
    """Build one fictional approved claim."""
    return PK.PlantKnowledgeClaim(
        claim_id=claim_id,
        field_path=field_path,
        value=value,
        unit=unit,
        regional_applicability=REGION,
        confidence=confidence,
        evidence_grade=evidence_grade or PK.EvidenceGrade.MODERATE,
        source_ids=source_ids,
        created_at=NOW,
        reviewed_at=REVIEWED,
        review_state=PK.ReviewState.APPROVED,
        intended_consumer_capabilities=(PK.ConsumerCapability.VISUAL_IDENTIFICATION,),
        claim_version=1,
        unresolved_conflict=unresolved_conflict,
        superseded_claim_id=superseded_claim_id,
    )


def profile(
    profile_id: str,
    common_name: str,
    resolution_level: Any,
    claim_ids: tuple[str, ...],
    *,
    scientific_name: str | None = None,
    aliases: tuple[str, ...] = (),
    cultivar: str | None = None,
    category: Any = None,
    parent_profile_id: str | None = None,
    functional_group_ids: tuple[str, ...] = (),
    lifecycle_state: Any = None,
    superseded_profile_id: str | None = None,
    region: Any = REGION,
) -> Any:
    """Build one fictional profile."""
    state = lifecycle_state or PK.LifecycleState.PUBLISHED
    return PK.PlantKnowledgeProfile(
        profile_id=profile_id,
        preferred_common_name=common_name,
        scientific_name=scientific_name,
        aliases=aliases,
        cultivar=cultivar,
        broad_category=category or PK.PlantCategory.TREE,
        resolution_level=resolution_level,
        parent_profile_id=parent_profile_id,
        functional_group_ids=functional_group_ids,
        claim_ids=claim_ids,
        regional_applicability=region,
        intended_consumer_capabilities=(PK.ConsumerCapability.VISUAL_IDENTIFICATION,),
        schema_version=1,
        profile_version=1,
        lifecycle_state=state,
        created_at=NOW,
        reviewed_at=REVIEWED
        if state
        in {
            PK.LifecycleState.REVIEWED,
            PK.LifecycleState.PUBLISHED,
        }
        else None,
        superseded_profile_id=superseded_profile_id,
        explanation_metadata=(PK.ProfileExplanationMetadata("dataset", "synthetic-test-only"),),
    )


def base_components() -> dict[str, tuple[Any, ...]]:
    """Return a complete fictional profile hierarchy and fallback set."""
    sources = (approved_source(),)
    claims = tuple(
        sorted(
            (
                claim(
                    "pk.claim.category_identity",
                    "identity.preferred_common_name",
                    "Synthetic tree category",
                ),
                claim(
                    "pk.claim.category_visual",
                    "visual.leaf_shape",
                    PK.LeafShape.UNKNOWN,
                    confidence=0.6,
                ),
                claim(
                    "pk.claim.cultivar_visual",
                    "visual.leaf_shape",
                    PK.LeafShape.COMPOUND,
                    confidence=0.9,
                ),
                claim(
                    "pk.claim.genus_identity",
                    "identity.scientific_name",
                    "Examplegenus",
                ),
                claim(
                    "pk.claim.group_identity",
                    "identity.preferred_common_name",
                    "Synthetic fruit tree group",
                ),
                claim(
                    "pk.claim.species_identity",
                    "identity.scientific_name",
                    "Examplegenus ficticia",
                    confidence=0.95,
                ),
            ),
            key=lambda item: item.claim_id,
        )
    )
    groups = (
        PK.PlantFunctionalGroup(
            group_id="pk.group.synthetic_fruit_membership",
            display_name="Synthetic Fruit Membership",
            description="Fictional grouping with no horticultural meaning.",
            intended_consumer_capabilities=(PK.ConsumerCapability.VISUAL_IDENTIFICATION,),
            lifecycle_state=PK.LifecycleState.PUBLISHED,
            version=1,
            parent_group_id="pk.group.synthetic_woody_membership",
        ),
        PK.PlantFunctionalGroup(
            group_id="pk.group.synthetic_woody_membership",
            display_name="Synthetic Woody Membership",
            description="Fictional parent grouping used only in tests.",
            intended_consumer_capabilities=(PK.ConsumerCapability.VISUAL_IDENTIFICATION,),
            lifecycle_state=PK.LifecycleState.PUBLISHED,
            version=1,
        ),
    )
    profiles = tuple(
        sorted(
            (
                profile(
                    "pk.category.synthetic_tree",
                    "Synthetic Tree",
                    PK.ProfileResolutionLevel.CATEGORY_FALLBACK,
                    ("pk.claim.category_identity", "pk.claim.category_visual"),
                    aliases=("Imaginary Tree Category",),
                ),
                profile(
                    "pk.cultivar.example_plant.demo",
                    "Demo Example Plant",
                    PK.ProfileResolutionLevel.CULTIVAR,
                    ("pk.claim.cultivar_visual",),
                    scientific_name="Examplegenus ficticia",
                    aliases=("Demo Fictional Plant",),
                    cultivar="Demo",
                    parent_profile_id="pk.species.example_plant",
                    functional_group_ids=("pk.group.synthetic_fruit_membership",),
                ),
                profile(
                    "pk.fallback.unknown_tree",
                    "Unknown Synthetic Plant",
                    PK.ProfileResolutionLevel.UNKNOWN_FALLBACK,
                    ("pk.claim.category_identity",),
                    category=PK.PlantCategory.UNKNOWN,
                ),
                profile(
                    "pk.genus.example",
                    "Example Genus",
                    PK.ProfileResolutionLevel.GENUS,
                    ("pk.claim.genus_identity",),
                    scientific_name="Examplegenus",
                    parent_profile_id="pk.category.synthetic_tree",
                ),
                profile(
                    "pk.group.synthetic_fruit_tree",
                    "Synthetic Fruit Tree",
                    PK.ProfileResolutionLevel.FUNCTIONAL_GROUP,
                    ("pk.claim.group_identity",),
                    parent_profile_id="pk.category.synthetic_tree",
                    functional_group_ids=("pk.group.synthetic_fruit_membership",),
                ),
                profile(
                    "pk.species.example_plant",
                    "Example Plant",
                    PK.ProfileResolutionLevel.SPECIES,
                    ("pk.claim.species_identity",),
                    scientific_name="Examplegenus ficticia",
                    aliases=("Fictional Example",),
                    parent_profile_id="pk.group.synthetic_fruit_tree",
                    functional_group_ids=("pk.group.synthetic_fruit_membership",),
                ),
            ),
            key=lambda item: item.profile_id,
        )
    )
    return {
        "sources": sources,
        "claims": claims,
        "claim_resolutions": (),
        "functional_groups": groups,
        "profiles": profiles,
    }


def build_library(**overrides: tuple[Any, ...]) -> Any:
    """Build a valid manifest and library around supplied synthetic components."""
    components = base_components()
    components.update(overrides)
    for key in components:
        identifier = {
            "sources": "source_id",
            "claims": "claim_id",
            "claim_resolutions": "resolution_id",
            "functional_groups": "group_id",
            "profiles": "profile_id",
        }[key]
        components[key] = tuple(sorted(components[key], key=lambda item: getattr(item, identifier)))
    claims = components["claims"]
    profiles = components["profiles"]
    confidences = tuple(item.confidence for item in claims)
    statistics = PK.ClaimConfidenceStatistics(
        claim_count=len(claims),
        minimum=min(confidences) if confidences else None,
        maximum=max(confidences) if confidences else None,
        mean=round(sum(confidences) / len(confidences), 6) if confidences else None,
    )
    applicability = tuple(item.regional_applicability for item in (*profiles, *claims))
    zones = tuple(
        zone
        for item in applicability
        for zone in (item.usda_zone_minimum, item.usda_zone_maximum)
        if zone is not None
    )
    climate_regions = tuple(
        sorted(
            {zone for item in applicability for zone in item.climate_zone_ids},
            key=str.casefold,
        )
    )
    manifest = PK.PlantKnowledgeManifest(
        schema_version=1,
        library_version="1.0.0",
        generated_at=NOW,
        supported_climate_regions=climate_regions,
        usda_zone_minimum=min(zones, key=_zone_key) if zones else None,
        usda_zone_maximum=max(zones, key=_zone_key) if zones else None,
        profile_count=len(profiles),
        category_count=sum(
            item.resolution_level is PK.ProfileResolutionLevel.CATEGORY_FALLBACK
            for item in profiles
        ),
        functional_group_count=len(components["functional_groups"]),
        genus_count=sum(
            item.resolution_level is PK.ProfileResolutionLevel.GENUS for item in profiles
        ),
        species_count=sum(
            item.resolution_level is PK.ProfileResolutionLevel.SPECIES for item in profiles
        ),
        cultivar_count=sum(
            item.resolution_level is PK.ProfileResolutionLevel.CULTIVAR for item in profiles
        ),
        source_count=len(components["sources"]),
        claim_count=len(claims),
        claim_resolution_count=len(components["claim_resolutions"]),
        published_profile_count=sum(
            item.lifecycle_state is PK.LifecycleState.PUBLISHED for item in profiles
        ),
        confidence_statistics=statistics,
        validation_checksum="0" * 64,
    )
    checksum = PK.calculate_library_checksum(manifest=manifest, **components)
    manifest = replace(manifest, validation_checksum=checksum)
    return PK.PlantKnowledgeLibrary(manifest=manifest, **components)


def _zone_key(value: str) -> tuple[int, int]:
    """Sort canonical USDA zone identifiers in synthetic manifests."""
    return int(value[:-1]), 0 if value[-1] == "a" else 1
