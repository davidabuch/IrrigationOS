"""Approved identity claims for canonical curated plant profiles."""

from __future__ import annotations

from datetime import UTC, datetime

from ..models import (
    ConsumerCapability,
    EvidenceGrade,
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


def curated_claims() -> tuple[PlantKnowledgeClaim, ...]:
    """Return approved identity claims in deterministic claim-ID order."""
    return (
        _scientific_name_claim(
            claim_id="pk.claim.agave_attenuata.scientific_name",
            scientific_name="Agave attenuata",
        ),
        _scientific_name_claim(
            claim_id="pk.claim.cynodon_dactylon.scientific_name",
            scientific_name="Cynodon dactylon",
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
        _scientific_name_claim(
            claim_id="pk.claim.muhlenbergia_rigens.scientific_name",
            scientific_name="Muhlenbergia rigens",
        ),
        _scientific_name_claim(
            claim_id="pk.claim.quercus_agrifolia.scientific_name",
            scientific_name="Quercus agrifolia",
        ),
        _scientific_name_claim(
            claim_id="pk.claim.rhaphiolepis_indica.scientific_name",
            scientific_name="Rhaphiolepis indica",
        ),
    )
