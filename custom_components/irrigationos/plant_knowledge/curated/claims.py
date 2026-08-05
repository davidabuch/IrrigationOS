"""Approved claims for canonical curated plant profiles."""

from __future__ import annotations

from datetime import UTC, datetime

from ..models import (
    ConsumerCapability,
    EvidenceGrade,
    HeatTolerance,
    KnowledgeRange,
    KnowledgeUnit,
    PlantKnowledgeClaim,
    RegionalApplicability,
    RegionalScope,
    ReviewState,
    WaterStressSensitivity,
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

_STRESS_CREATED_AT = datetime(2026, 8, 5, 18, 0, tzinfo=UTC)
_STRESS_REVIEWED_AT = datetime(2026, 8, 5, 18, 30, tzinfo=UTC)
_STRESS_CONSUMERS = (
    ConsumerCapability.PLANT_HEALTH,
    ConsumerCapability.WATER_DEMAND,
)
_EXTENSION_SOURCE_IDS = ("pk.source.nc_state_plant_toolbox",)
_NATIVE_EXTENSION_SOURCE_IDS = (
    "pk.source.calscape",
    "pk.source.nc_state_plant_toolbox",
)
_SOUTHERN_CALIFORNIA_SCOPE = RegionalApplicability(
    scope=RegionalScope.REGIONAL,
    countries=("US",),
    states_or_provinces=("California",),
    climate_zone_ids=("southern_california_mediterranean",),
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



def _stress_claim(
    *,
    claim_id: str,
    field_path: str,
    value: WaterStressSensitivity | HeatTolerance | float,
    source_ids: tuple[str, ...],
    confidence: float,
    evidence_grade: EvidenceGrade,
    notes: str,
) -> PlantKnowledgeClaim:
    return PlantKnowledgeClaim(
        claim_id=claim_id,
        field_path=field_path,
        value=value,
        unit=(
            KnowledgeUnit.CELSIUS
            if field_path == "environment.minimum_temperature_celsius"
            else None
        ),
        regional_applicability=_SOUTHERN_CALIFORNIA_SCOPE,
        confidence=confidence,
        evidence_grade=evidence_grade,
        source_ids=source_ids,
        created_at=_STRESS_CREATED_AT,
        reviewed_at=_STRESS_REVIEWED_AT,
        review_state=ReviewState.APPROVED,
        intended_consumer_capabilities=_STRESS_CONSUMERS,
        claim_version=1,
        notes=notes,
    )


def _species_stress_claims(
    *,
    species_key: str,
    water_sensitivity: WaterStressSensitivity,
    heat_tolerance: HeatTolerance,
    minimum_temperature_celsius: float,
    source_ids: tuple[str, ...] = _EXTENSION_SOURCE_IDS,
    confidence: float = 0.8,
    evidence_grade: EvidenceGrade = EvidenceGrade.MODERATE,
    notes: str,
) -> tuple[PlantKnowledgeClaim, ...]:
    return (
        _stress_claim(
            claim_id=f"pk.claim.{species_key}.heat_tolerance",
            field_path="environment.heat_tolerance",
            value=heat_tolerance,
            source_ids=source_ids,
            confidence=confidence,
            evidence_grade=evidence_grade,
            notes=notes,
        ),
        _stress_claim(
            claim_id=f"pk.claim.{species_key}.minimum_temperature_celsius",
            field_path="environment.minimum_temperature_celsius",
            value=minimum_temperature_celsius,
            source_ids=source_ids,
            confidence=confidence,
            evidence_grade=evidence_grade,
            notes=notes,
        ),
        _stress_claim(
            claim_id=f"pk.claim.{species_key}.water_stress_sensitivity",
            field_path="water.water_stress_sensitivity",
            value=water_sensitivity,
            source_ids=source_ids,
            confidence=confidence,
            evidence_grade=evidence_grade,
            notes=notes,
        ),
    )


def curated_claims() -> tuple[PlantKnowledgeClaim, ...]:
    """Return approved curated claims in deterministic claim-ID order."""
    base_claims = (
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
    stress_claims = (
        *_species_stress_claims(
            species_key="agave_attenuata",
            water_sensitivity=WaterStressSensitivity.LOW,
            heat_tolerance=HeatTolerance.HIGH,
            minimum_temperature_celsius=-3.9,
            notes=(
                "Normalized from extension guidance describing agaves as drought- and heat-"
                "tolerant and generally hardy from USDA zone 9; the zone 9b lower bound is "
                "stored as -3.9 C for the frost-sensitive foxtail agave."
            ),
        ),
        *_species_stress_claims(
            species_key="cynodon_dactylon",
            water_sensitivity=WaterStressSensitivity.MODERATE,
            heat_tolerance=HeatTolerance.HIGH,
            minimum_temperature_celsius=-12.2,
            notes=(
                "Extension guidance identifies bermudagrass as heat- and drought-tolerant, "
                "while noting winter injury below 10 F; water sensitivity remains moderate "
                "because maintained turf quality declines under sustained deficit."
            ),
        ),
        *_species_stress_claims(
            species_key="dymondia_margaretae",
            water_sensitivity=WaterStressSensitivity.LOW,
            heat_tolerance=HeatTolerance.HIGH,
            minimum_temperature_celsius=-6.7,
            notes=(
                "Normalized from drought-tolerant groundcover guidance and USDA zone 9 "
                "hardiness; the zone 9a lower bound is stored as -6.7 C."
            ),
        ),
        *_species_stress_claims(
            species_key="heteromeles_arbutifolia",
            water_sensitivity=WaterStressSensitivity.LOW,
            heat_tolerance=HeatTolerance.HIGH,
            minimum_temperature_celsius=-17.8,
            source_ids=_NATIVE_EXTENSION_SOURCE_IDS,
            confidence=0.85,
            evidence_grade=EvidenceGrade.EXPERT_CONSENSUS,
            notes=(
                "California native-plant and extension guidance characterize established "
                "toyon as drought- and heat-adapted and hardy through USDA zone 7; the zone "
                "7a lower bound is stored as -17.8 C."
            ),
        ),
        *_species_stress_claims(
            species_key="lagerstroemia_indica",
            water_sensitivity=WaterStressSensitivity.LOW,
            heat_tolerance=HeatTolerance.HIGH,
            minimum_temperature_celsius=-23.3,
            notes=(
                "Extension guidance describes crape myrtle as drought-resistant and dependent "
                "on summer heat, with possible winter injury in zones 5-6; the zone 6a lower "
                "bound is stored as -23.3 C."
            ),
        ),
        *_species_stress_claims(
            species_key="muhlenbergia_rigens",
            water_sensitivity=WaterStressSensitivity.LOW,
            heat_tolerance=HeatTolerance.HIGH,
            minimum_temperature_celsius=-17.8,
            source_ids=_NATIVE_EXTENSION_SOURCE_IDS,
            confidence=0.85,
            evidence_grade=EvidenceGrade.EXPERT_CONSENSUS,
            notes=(
                "California native-plant guidance characterizes deer grass as drought- and "
                "heat-adapted and hardy through USDA zone 7; the zone 7a lower bound is stored "
                "as -17.8 C."
            ),
        ),
        *_species_stress_claims(
            species_key="quercus_agrifolia",
            water_sensitivity=WaterStressSensitivity.LOW,
            heat_tolerance=HeatTolerance.HIGH,
            minimum_temperature_celsius=-12.2,
            source_ids=_NATIVE_EXTENSION_SOURCE_IDS,
            confidence=0.85,
            evidence_grade=EvidenceGrade.EXPERT_CONSENSUS,
            notes=(
                "California native-plant guidance characterizes established coast live oak as "
                "summer-dry and heat-adapted and hardy through USDA zone 8; the zone 8a lower "
                "bound is stored as -12.2 C."
            ),
        ),
        *_species_stress_claims(
            species_key="rhaphiolepis_indica",
            water_sensitivity=WaterStressSensitivity.MODERATE,
            heat_tolerance=HeatTolerance.HIGH,
            minimum_temperature_celsius=-12.2,
            notes=(
                "Extension guidance describes established Indian hawthorn as somewhat drought "
                "tolerant, sun- and heat-adapted, and hardy in zones 8-10; the zone 8a lower "
                "bound is stored as -12.2 C."
            ),
        ),
    )
    return tuple(sorted((*base_claims, *stress_claims), key=lambda claim: claim.claim_id))
