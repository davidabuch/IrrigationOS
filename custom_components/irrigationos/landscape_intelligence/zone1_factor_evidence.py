"""Reviewed Zone 1 factor evidence for Landscape Factor Resolution v1."""

from __future__ import annotations

from .factor_resolution import EvidenceClass, FactorRange, PlantFactorEvidence


def zone_1_factor_evidence() -> tuple[PlantFactorEvidence, ...]:
    """Return conservative, source-traceable evidence without invented coefficients."""
    return (
        PlantFactorEvidence(
            "podocarpus",
            EvidenceClass.LANDSCAPE_PLANT_FACTOR,
            0.5,
            "moderate",
            "ucanr.established_landscape_tree_pf",
            "Estimating Tree Water Requirements",
            (
                "https://ucanr.edu/site/center-landscape-urban-horticulture/"
                "estimating-tree-water-requirements"
            ),
            "high",
            True,
            (
                "UC landscape guidance supports PF 0.5 for established landscape trees "
                "and woody plants in most of California."
            ),
        ),
        PlantFactorEvidence(
            "peruvian_lilies",
            EvidenceClass.QUALITATIVE_HORTICULTURE,
            None,
            "low_to_moderate",
            "ucanr.alameda.outstanding_plants.alstroemeria",
            "Outstanding Plants for Alameda County",
            (
                "https://ucanr.edu/site/uc-master-gardener-program-alameda-county/"
                "outstanding-plants-alameda-county"
            ),
            "moderate",
            False,
            (
                "UC guidance supports low-to-moderate water use but does not publish a "
                "numeric landscape PF here."
            ),
        ),
        PlantFactorEvidence(
            "citrus",
            EvidenceClass.AGRICULTURAL_CROP_COEFFICIENT,
            FactorRange(0.65, 0.70),
            None,
            "ucanr.young_orchard_irrigation.citrus",
            "Irrigation and Nutrient Management of Young Orchards",
            (
                "https://www.ccfruitandnuts.ucanr.edu/sites/default/files/2025-05/"
                "Young%20Orchard%20Irrigation%20and%20Nutrient%20Management%20"
                "UCCE%20Handbook%20English.pdf"
            ),
            "high",
            False,
            (
                "Mature citrus Kc is agricultural evidence; young-tree Kc is a "
                "canopy/age-dependent fraction and is not admitted as residential "
                "landscape PF."
            ),
        ),
        PlantFactorEvidence(
            "fig",
            EvidenceClass.AGRICULTURAL_CROP_COEFFICIENT,
            None,
            None,
            "ucanr.fig_crop_water_research",
            "California Agriculture fig irrigation research",
            "https://calag.ucanr.edu/",
            "moderate",
            False,
            (
                "Commercial crop-water evidence is informative but is not directly "
                "admitted as a residential landscape PF."
            ),
        ),
        PlantFactorEvidence(
            "passion_fruit",
            EvidenceClass.UNKNOWN,
            None,
            None,
            "internal.unresolved.passion_fruit",
            "No admitted production-grade factor source",
            "",
            "low",
            False,
            (
                "No sufficiently direct California landscape factor has been admitted "
                "for this milestone."
            ),
        ),
        PlantFactorEvidence(
            "drought_tolerant_ornamentals",
            EvidenceClass.QUALITATIVE_HORTICULTURE,
            FactorRange(0.1, 0.3),
            "low",
            "wucols.low_class_band",
            "WUCOLS V water-use class definitions",
            "https://wucols.ucdavis.edu/",
            "moderate",
            False,
            (
                "The group is not taxonomically resolved; the low class band is retained "
                "as context, not admitted as a group PF."
            ),
        ),
    )
