"""Reviewed bibliographic sources for the curated Plant Knowledge library."""

from __future__ import annotations

from datetime import UTC, date, datetime

from ..models import PlantKnowledgeSource, ReviewState, SourceReviewRecord, SourceType

_ACCESSED_DATE = date(2026, 8, 4)
_REVIEW_STARTED = datetime(2026, 8, 4, 7, 0, tzinfo=UTC)
_REVIEW_COMPLETED = datetime(2026, 8, 4, 7, 15, tzinfo=UTC)
_APPROVED_AT = datetime(2026, 8, 4, 7, 30, tzinfo=UTC)
_REVIEWER = "irrigationos.maintainers"


def _approved_review_history() -> tuple[SourceReviewRecord, ...]:
    return (
        SourceReviewRecord(
            state=ReviewState.UNREVIEWED,
            changed_at=_REVIEW_STARTED,
            reviewer=_REVIEWER,
            notes="Source registered for curated-library review.",
        ),
        SourceReviewRecord(
            state=ReviewState.REVIEWED,
            changed_at=_REVIEW_COMPLETED,
            reviewer=_REVIEWER,
            notes="Authority, scope, citation, and reuse boundary reviewed.",
        ),
        SourceReviewRecord(
            state=ReviewState.APPROVED,
            changed_at=_APPROVED_AT,
            reviewer=_REVIEWER,
            notes="Approved as a source for future curated claims within documented scope.",
        ),
    )


def curated_sources() -> tuple[PlantKnowledgeSource, ...]:
    """Return canonical approved sources in deterministic source-ID order."""
    return (
        PlantKnowledgeSource(
            source_id="pk.source.calflora_database",
            organization="Calflora",
            title="Calflora Database of California Wild Plants",
            authors=(),
            publication_date=None,
            accessed_date=_ACCESSED_DATE,
            citation="Calflora. Calflora Database of California Wild Plants.",
            source_type=SourceType.BOTANICAL_INSTITUTION,
            geographic_scope=("California",),
            review_state=ReviewState.APPROVED,
            review_history=_approved_review_history(),
            url="https://www.calflora.org/",
            licensing_notes=(
                "Use bibliographic facts and independently normalized factual claims only; "
                "do not copy photographs, source text, or bulk database content."
            ),
            notes="Intended for California native status, distribution, and identity support.",
        ),
        PlantKnowledgeSource(
            source_id="pk.source.calscape",
            organization="California Native Plant Society",
            title="Calscape California Native Plant Gardening Guide",
            authors=(),
            publication_date=None,
            accessed_date=date(2026, 8, 5),
            citation="California Native Plant Society. Calscape.",
            source_type=SourceType.PROFESSIONAL_SOCIETY,
            geographic_scope=("California",),
            review_state=ReviewState.APPROVED,
            review_history=_approved_review_history(),
            url="https://calscape.org/",
            licensing_notes=(
                "Use independently normalized horticultural facts with attribution; do not "
                "copy photographs, descriptive text, or bulk database content."
            ),
            notes=(
                "Intended for California-native drought adaptation, heat exposure, and "
                "hardiness context used by curated stress-tolerance claims."
            ),
        ),
        PlantKnowledgeSource(
            source_id="pk.source.kew_powo",
            organization="Royal Botanic Gardens, Kew",
            title="Plants of the World Online",
            authors=(),
            publication_date=None,
            accessed_date=_ACCESSED_DATE,
            citation="Royal Botanic Gardens, Kew. Plants of the World Online.",
            source_type=SourceType.BOTANICAL_INSTITUTION,
            geographic_scope=("Global",),
            review_state=ReviewState.APPROVED,
            review_history=_approved_review_history(),
            url="https://powo.science.kew.org/",
            licensing_notes=(
                "Use normalized taxonomic and distribution facts with citation; do not copy "
                "descriptive text or image assets."
            ),
            notes="Intended for accepted scientific names, synonyms, and broad native range.",
        ),
        PlantKnowledgeSource(
            source_id="pk.source.nc_state_plant_toolbox",
            organization="North Carolina State University Extension",
            title="Extension Gardener Plant Toolbox",
            authors=(),
            publication_date=None,
            accessed_date=date(2026, 8, 5),
            citation=(
                "North Carolina State University Extension. Extension Gardener Plant Toolbox."
            ),
            source_type=SourceType.UNIVERSITY_EXTENSION,
            geographic_scope=("United States",),
            review_state=ReviewState.APPROVED,
            review_history=_approved_review_history(),
            url="https://plants.ces.ncsu.edu/",
            licensing_notes=(
                "Use independently normalized horticultural facts with attribution; do not "
                "copy photographs or substantial descriptive text."
            ),
            notes=(
                "Intended for drought and heat tolerance, USDA hardiness context, and explicit "
                "temperature thresholds where published."
            ),
        ),
        PlantKnowledgeSource(
            source_id="pk.source.usda_plants",
            organization=(
                "United States Department of Agriculture, "
                "Natural Resources Conservation Service"
            ),
            title="The PLANTS Database",
            authors=(),
            publication_date=None,
            accessed_date=_ACCESSED_DATE,
            citation=(
                "USDA Natural Resources Conservation Service. The PLANTS Database. "
                "National Plant Data Team, Greensboro, North Carolina."
            ),
            source_type=SourceType.GOVERNMENT_DATABASE,
            geographic_scope=("United States",),
            review_state=ReviewState.APPROVED,
            review_history=_approved_review_history(),
            url="https://plants.usda.gov/",
            licensing_notes=(
                "Use factual identity and distribution records with attribution; do not import "
                "bulk payloads into the curated library."
            ),
            notes="Intended for United States taxonomic, native-status, and distribution support.",
        ),
        PlantKnowledgeSource(
            source_id="pk.source.wucols_iv",
            organization="University of California Agriculture and Natural Resources",
            title="Water Use Classification of Landscape Species IV",
            authors=(),
            publication_date=date(2014, 1, 1),
            accessed_date=_ACCESSED_DATE,
            citation=(
                "University of California Agriculture and Natural Resources and California "
                "Department of Water Resources. Water Use Classification of Landscape Species IV."
            ),
            source_type=SourceType.UNIVERSITY_EXTENSION,
            geographic_scope=("California",),
            review_state=ReviewState.APPROVED,
            review_history=_approved_review_history(),
            url="https://ucanr.edu/sites/WUCOLS/",
            licensing_notes=(
                "Use independently normalized species classifications with citation; do not "
                "reproduce source tables or substantial explanatory text."
            ),
            notes="Intended for California regional landscape water-use classifications.",
        ),
        PlantKnowledgeSource(
            source_id="pk.source.wucols_v",
            organization="University of California, Davis",
            title="Water Use Classification of Landscape Species V",
            authors=(),
            publication_date=date(2025, 1, 1),
            accessed_date=_ACCESSED_DATE,
            citation=(
                "University of California, Davis and California Department of Water Resources. "
                "Water Use Classification of Landscape Species V."
            ),
            source_type=SourceType.UNIVERSITY_EXTENSION,
            geographic_scope=("California",),
            review_state=ReviewState.APPROVED,
            review_history=_approved_review_history(),
            url="https://wucols.ucdavis.edu/",
            licensing_notes=(
                "Use independently normalized plant-factor classifications with citation; do "
                "not reproduce source tables, photographs, or substantial explanatory text."
            ),
            notes=(
                "Intended for current California regional plant-factor classifications and the "
                "published turfgrass factors linked from the WUCOLS site."
            ),
        ),
    )
