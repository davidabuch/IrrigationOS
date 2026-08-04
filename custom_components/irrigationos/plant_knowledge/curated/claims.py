"""Approved claims for canonical curated plant profiles."""

from __future__ import annotations

from datetime import UTC, datetime

from ..models import (
    ConsumerCapability,
    EvidenceGrade,
    KnowledgeRange,
    KnowledgeUnit,
    PlantKnowledgeClaim,
    RegionalApplicability,
    RegionalScope,
    ReviewState,
)

_CREATED_AT = datetime(2026, 8, 4, 8, 15, tzinfo=UTC)
_REVIEWED_AT = datetime(2026, 8, 4, 8, 30, tzinfo=UTC)
_IDENTITY_CONSUMERS = (
    ConsumerCapability.LEARNING,
    ConsumerCapability.VISUAL_IDENTIFICATION,
)
_POWO_SOURCE_IDS = ("pk.source.kew_powo",)
_UNRESTRICTED_TAXONOMY = RegionalApplicability(scope=RegionalScope.UNRESTRICTED)
_WATER_CREATED_AT = datetime(2026, 8, 4, 9, 15, tzinfo=UTC)
_WATER_REVIEWED_AT = datetime(2026, 8, 4, 9, 45, tzinfo=UTC)
_WATER_CONSUMERS = (ConsumerCapability.WATER_DEMAND,)
_WUCOLS_V_SOURCE_IDS = ("pk.source.wucols_v",)
_CALIFORNIA_SCOPE = RegionalApplicability(
    scope=RegionalScope.REGIONAL,
    countries=("US",),
    states_or_provinces=("California",),
)
_WUCOLS_SOUTH_COASTAL = RegionalApplicability(
    scope=RegionalScope.REGIONAL,
    countries=("US",),
    states_or_provinces=("California",),
    wucols_regions=("3_south_coastal",),
)
_WUCOLS_SOUTHERN_CALIFORNIA = RegionalApplicability(
    scope=RegionalScope.REGIONAL,
    countries=("US",),
    states_or_provinces=("California",),
    wucols_regions=("3_south_coastal", "4_south_inland"),
)


def _scientific_name_claim(
    *,
    claim_id: str,
    scientific_name: str,
) -> PlantKnowledgeClaim:
    return PlantKnowledgeClaim(
        claim_id=claim_id,
        field_path="identity.scientific_name",
        value=scientific_name,
        unit=None,
        regional_applicability=_UNRESTRICTED_TAXONOMY,
        confidence=1.0,
        evidence_grade=EvidenceGrade.HIGH,
        source_ids=_POWO_SOURCE_IDS,
        created_at=_CREATED_AT,
        reviewed_at=_REVIEWED_AT,
        review_state=ReviewState.APPROVED,
        intended_consumer_capabilities=_IDENTITY_CONSUMERS,
        claim_version=1,
        notes="Accepted scientific name verified against Plants of the World Online.",
    )


def _plant_factor_claim(
    *,
    claim_id: str,
    value: float | KnowledgeRange,
    regional_applicability: RegionalApplicability,
    confidence: float,
    evidence_grade: EvidenceGrade,
    notes: str,
) -> PlantKnowledgeClaim:
    return PlantKnowledgeClaim(
        claim_id=claim_id,
        field_path="water.plant_factor",
        value=value,
        unit=KnowledgeUnit.RATIO,
        regional_applicability=regional_applicability,
        confidence=confidence,
        evidence_grade=evidence_grade,
        source_ids=_WUCOLS_V_SOURCE_IDS,
        created_at=_WATER_CREATED_AT,
        reviewed_at=_WATER_REVIEWED_AT,
        review_state=ReviewState.APPROVED,
        intended_consumer_capabilities=_WATER_CONSUMERS,
        claim_version=1,
        notes=notes,
    )


def _wucols_low_range() -> KnowledgeRange:
    return KnowledgeRange(
        minimum=0.1,
        maximum=0.3,
        unit=KnowledgeUnit.RATIO,
    )


def curated_claims() -> tuple[PlantKnowledgeClaim, ...]:
    """Return approved curated claims in deterministic claim-ID order."""
    return (
        _scientific_name_claim(
            claim_id="pk.claim.agave_attenuata.scientific_name",
            scientific_name="Agave attenuata",
        ),
        _plant_factor_claim(
            claim_id="pk.claim.cynodon_dactylon.plant_factor",
            value=0.6,
            regional_applicability=_CALIFORNIA_SCOPE,
            confidence=0.9,
            evidence_grade=EvidenceGrade.HIGH,
            notes=(
                "WUCOLS publishes 0.60 as the optimal-irrigation plant factor for common "
                "bermudagrass; the deficit-irrigation value is intentionally not substituted."
            ),
        ),
        _scientific_name_claim(
            claim_id="pk.claim.cynodon_dactylon.scientific_name",
            scientific_name="Cynodon dactylon",
        ),
        _plant_factor_claim(
            claim_id="pk.claim.dymondia_margaretae.plant_factor",
            value=_wucols_low_range(),
            regional_applicability=_WUCOLS_SOUTHERN_CALIFORNIA,
            confidence=0.85,
            evidence_grade=EvidenceGrade.EXPERT_CONSENSUS,
            notes=(
                "WUCOLS classifies Dymondia margaretae as Low in Regions 3 and 4; the "
                "published 0.10-0.30 plant-factor band is preserved without a midpoint."
            ),
        ),
        _scientific_name_claim(
            claim_id="pk.claim.dymondia_margaretae.scientific_name",
            scientific_name="Dymondia margaretae",
        ),
        _scientific_name_claim(
            claim_id="pk.claim.heteromeles_arbutifolia.scientific_name",
            scientific_name="Heteromeles arbutifolia",
        ),
        _scientific_name_claim(
            claim_id="pk.claim.lagerstroemia_indica.scientific_name",
            scientific_name="Lagerstroemia indica",
        ),
        _plant_factor_claim(
            claim_id="pk.claim.muhlenbergia_rigens.plant_factor",
            value=_wucols_low_range(),
            regional_applicability=_WUCOLS_SOUTHERN_CALIFORNIA,
            confidence=0.85,
            evidence_grade=EvidenceGrade.EXPERT_CONSENSUS,
            notes=(
                "WUCOLS classifies Muhlenbergia rigens as Low in Regions 3 and 4; the "
                "published 0.10-0.30 plant-factor band is preserved without a midpoint."
            ),
        ),
        _scientific_name_claim(
            claim_id="pk.claim.muhlenbergia_rigens.scientific_name",
            scientific_name="Muhlenbergia rigens",
        ),
        _scientific_name_claim(
            claim_id="pk.claim.quercus_agrifolia.scientific_name",
            scientific_name="Quercus agrifolia",
        ),
        _plant_factor_claim(
            claim_id="pk.claim.rhaphiolepis_indica.plant_factor",
            value=_wucols_low_range(),
            regional_applicability=_WUCOLS_SOUTH_COASTAL,
            confidence=0.85,
            evidence_grade=EvidenceGrade.EXPERT_CONSENSUS,
            notes=(
                "WUCOLS classifies Rhaphiolepis indica as Low in Region 3; Region 4's "
                "Moderate classification is not merged into this region-specific claim."
            ),
        ),
        _scientific_name_claim(
            claim_id="pk.claim.rhaphiolepis_indica.scientific_name",
            scientific_name="Rhaphiolepis indica",
        ),
    )
