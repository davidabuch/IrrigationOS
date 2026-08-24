"""Reviewed Zone 1 factor evidence for Landscape Factor Resolution v1."""

from __future__ import annotations

from .factor_resolution import EvidenceClass, FactorRange, PlantFactorEvidence


def zone_1_factor_evidence() -> tuple[PlantFactorEvidence, ...]:
    """Return conservative, source-traceable Zone 1 factor evidence."""
    ucanr_pf_url = (
        "https://ucanr.edu/site/center-landscape-urban-horticulture/"
        "plant-factor-or-crop-coefficient-whats-difference"
    )
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
            "UC landscape guidance supports PF 0.5 for established landscape trees.",
        ),
        PlantFactorEvidence(
            "fig",
            EvidenceClass.URBAN_HORTICULTURE,
            0.8,
            "home_fruit_crop_deciduous",
            "ucanr.residential_pf.home_fruit_deciduous",
            "Plant Factor or Crop Coefficient: What's the difference?",
            ucanr_pf_url,
            "high",
            True,
            "UC residential landscape guidance lists deciduous home fruit crops at PF 0.8.",
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
            "Commercial crop-water evidence remains context only.",
        ),
        PlantFactorEvidence(
            "citrus",
            EvidenceClass.URBAN_HORTICULTURE,
            1.0,
            "home_fruit_crop_evergreen",
            "ucanr.residential_pf.home_fruit_evergreen",
            "Plant Factor or Crop Coefficient: What's the difference?",
            ucanr_pf_url,
            "high",
            True,
            (
                "UC residential landscape guidance lists evergreen home fruit crops at "
                "PF 1.0. Establishment-stage irrigation management remains separate."
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
            "Agricultural young-tree Kc remains context only and cannot authorize landscape PF.",
        ),
        PlantFactorEvidence(
            "passion_fruit",
            EvidenceClass.URBAN_HORTICULTURE,
            0.5,
            "vine",
            "ucanr.residential_pf.vines",
            "Plant Factor or Crop Coefficient: What's the difference?",
            ucanr_pf_url,
            "high",
            True,
            "UC residential landscape guidance lists vines with woody landscape plants at PF 0.5.",
        ),
        PlantFactorEvidence(
            "peruvian_lilies",
            EvidenceClass.URBAN_HORTICULTURE,
            0.5,
            "herbaceous_perennial",
            "ucanr.residential_pf.herbaceous_perennials",
            "Plant Factor or Crop Coefficient: What's the difference?",
            ucanr_pf_url,
            "high",
            True,
            "UC residential landscape guidance lists herbaceous perennials at PF 0.5.",
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
            "Species-oriented low-to-moderate guidance remains supporting evidence.",
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
                "The mixed ornamental group is not taxonomically resolved; its low-water "
                "context is not admitted as one authoritative group PF."
            ),
        ),
    )
