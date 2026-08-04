"""Behavioral tests for canonical Plant Knowledge records."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timedelta

import pytest

from tests.plant_knowledge_fixtures import NOW, PK, REGION, REVIEWED, approved_source, claim


def test_models_are_frozen_slotted_and_deterministically_serializable() -> None:
    """Records reject mutation, expose no instance dictionary, and serialize plainly."""
    source = approved_source()
    assert not hasattr(source, "__dict__")
    with pytest.raises(FrozenInstanceError):
        source.title = "Changed"
    assert source.to_dict() == source.to_dict()
    assert source.to_dict()["review_history"][0]["state"] == "unreviewed"
    assert source.to_dict()["accessed_date"] == "2026-01-01"


def test_stable_enum_values_and_public_field_contracts() -> None:
    """Stable API values and supported fields remain explicit."""
    assert PK.SourceType.UNIVERSITY_EXTENSION.value == "university_extension"
    assert PK.EvidenceGrade.EXPERT_CONSENSUS.value == "expert_consensus"
    assert PK.ProfileResolutionLevel.UNKNOWN_FALLBACK.value == "unknown_fallback"
    assert PK.ConsumerCapability.IRRIGATION_PLANNING.value == "irrigation_planning"
    assert PK.supported_field_paths() == tuple(sorted(PK.supported_field_paths()))
    contract = PK.get_field_contract("growth.typical_root_depth_meters")
    assert contract.allowed_units == (PK.KnowledgeUnit.METERS,)
    assert contract.range_permitted is True
    enum_contract = PK.get_field_contract("visual.leaf_shape")
    assert enum_contract.to_dict()["enum_type"] == "LeafShape"


@pytest.mark.parametrize(
    "source_id",
    ("synthetic.source", "pk.Source.invalid", "pk.source.mutable name", "pk.source"),
)
def test_stable_source_id_validation(source_id: str) -> None:
    """Canonical IDs use a stable readable pk namespace."""
    with pytest.raises(ValueError, match="stable pk"):
        replace(approved_source(), source_id=source_id)


def test_source_validation_and_immutable_review_transitions() -> None:
    """Sources enforce dates, unique authors, review history, and transitions."""
    source = approved_source()
    with pytest.raises(ValueError, match="publication_date"):
        replace(source, publication_date=date(2027, 1, 1))
    with pytest.raises(ValueError, match="duplicates"):
        replace(source, authors=("Example, Avery", " example,  avery "))
    with pytest.raises(ValueError, match="begin unreviewed"):
        replace(source, review_history=source.review_history[1:])
    invalid_history = (
        source.review_history[0],
        PK.SourceReviewRecord(PK.ReviewState.APPROVED, REVIEWED, "reviewer.synthetic"),
    )
    with pytest.raises(ValueError, match="invalid source review transition"):
        replace(source, review_state=PK.ReviewState.APPROVED, review_history=invalid_history)


def test_sources_reject_embedded_data_and_raw_bytes() -> None:
    """Bibliographic records cannot become document or secret payload storage."""
    with pytest.raises(ValueError, match="must not embed document data"):
        replace(approved_source(), url="data:text/plain,embedded")
    with pytest.raises(ValueError, match="must not be blank"):
        replace(approved_source(), citation=b"document bytes")
    with pytest.raises(ValueError, match="must not be blank"):
        replace(approved_source(), organization={"provider": "payload"})


def test_knowledge_range_ordering_and_finite_values() -> None:
    """Ranges require finite, consistently ordered quantities."""
    valid = PK.KnowledgeRange(1, 3, PK.KnowledgeUnit.METERS, typical=2)
    assert valid.to_dict() == {
        "minimum": 1,
        "maximum": 3,
        "unit": "meters",
        "typical": 2,
    }
    with pytest.raises(ValueError, match="minimum cannot exceed"):
        PK.KnowledgeRange(3, 1, PK.KnowledgeUnit.METERS)
    with pytest.raises(ValueError, match="typical"):
        PK.KnowledgeRange(1, 3, PK.KnowledgeUnit.METERS, typical=4)
    with pytest.raises(ValueError, match="finite"):
        PK.KnowledgeRange(0, float("inf"), PK.KnowledgeUnit.METERS)


def test_claim_field_contract_units_ranges_and_negative_temperature() -> None:
    """Field contracts bind kinds, units, ranges, and negative-value policy."""
    root_depth = claim(
        "pk.claim.synthetic_root_depth",
        "growth.typical_root_depth_meters",
        PK.KnowledgeRange(0.1, 0.3, PK.KnowledgeUnit.METERS, typical=0.2),
        unit=PK.KnowledgeUnit.METERS,
    )
    assert root_depth.unit is PK.KnowledgeUnit.METERS
    temperature = claim(
        "pk.claim.synthetic_temperature",
        "environment.minimum_temperature_celsius",
        PK.KnowledgeRange(-5, 4, PK.KnowledgeUnit.CELSIUS, typical=0),
        unit=PK.KnowledgeUnit.CELSIUS,
    )
    assert temperature.value.minimum == -5
    with pytest.raises(ValueError, match="incompatible"):
        replace(root_depth, unit=PK.KnowledgeUnit.MONTHS)
    with pytest.raises(ValueError, match="negative"):
        replace(
            root_depth,
            value=PK.KnowledgeRange(-1, 1, PK.KnowledgeUnit.METERS),
        )
    with pytest.raises(KeyError, match="unsupported"):
        replace(root_depth, field_path="unsupported.future_field")


def test_claims_validate_confidence_types_timestamps_and_source_review_gate() -> None:
    """Claims reject invalid confidence, payloads, naive times, and weak review records."""
    item = claim(
        "pk.claim.synthetic_name",
        "identity.preferred_common_name",
        "Fictional Plant",
    )
    with pytest.raises(ValueError, match="confidence"):
        replace(item, confidence=1.01)
    with pytest.raises(ValueError, match="timezone-aware"):
        replace(item, created_at=datetime(2026, 1, 1))
    with pytest.raises(ValueError, match="cannot precede"):
        replace(item, reviewed_at=NOW - timedelta(days=1))
    with pytest.raises(ValueError, match="require source IDs"):
        replace(item, source_ids=())
    with pytest.raises((TypeError, ValueError)):
        replace(item, value=b"raw image or document")
    with pytest.raises(ValueError, match="canonical enum"):
        replace(
            item,
            field_path="visual.leaf_shape",
            value="compound",
        )


def test_regional_applicability_requires_explicit_valid_scope() -> None:
    """Regional scope rejects duplicates, invalid ranges, and malformed USDA zones."""
    assert REGION.is_unrestricted is False
    assert PK.RegionalApplicability(scope=PK.RegionalScope.UNRESTRICTED).is_unrestricted is True
    with pytest.raises(ValueError, match="requires at least one explicit constraint"):
        PK.RegionalApplicability(scope=PK.RegionalScope.REGIONAL)
    with pytest.raises(ValueError, match="uppercase two-letter"):
        replace(REGION, countries=("xz",))
    with pytest.raises(ValueError, match="duplicates"):
        replace(REGION, climate_zone_ids=("Synthetic", " synthetic "))
    with pytest.raises(ValueError, match="USDA minimum"):
        replace(REGION, usda_zone_minimum="11a", usda_zone_maximum="10b")
    with pytest.raises(ValueError, match="elevation minimum"):
        replace(REGION, elevation_minimum_meters=600)


def test_profile_identity_alias_and_lifecycle_requirements() -> None:
    """Profile specificity, aliases, timestamps, and supersession remain consistent."""
    base = PK.PlantKnowledgeProfile(
        profile_id="pk.cultivar.example_plant.demo",
        preferred_common_name="Demo Plant",
        scientific_name="Examplegenus ficticia",
        aliases=("Fictional Demo",),
        cultivar="Demo",
        broad_category=PK.PlantCategory.TREE,
        resolution_level=PK.ProfileResolutionLevel.CULTIVAR,
        parent_profile_id=None,
        functional_group_ids=(),
        claim_ids=(),
        regional_applicability=REGION,
        intended_consumer_capabilities=(PK.ConsumerCapability.LEARNING,),
        schema_version=1,
        profile_version=1,
        lifecycle_state=PK.LifecycleState.DRAFT,
        created_at=NOW,
    )
    with pytest.raises(ValueError, match="normalized duplicates"):
        replace(base, aliases=("Fictional Demo", " fictional   demo "))
    with pytest.raises(ValueError, match="namespace"):
        replace(base, profile_id="pk.species.example_plant")
    with pytest.raises(ValueError, match="require cultivar"):
        replace(base, cultivar=None)
    with pytest.raises(ValueError, match="require reviewed_at"):
        replace(base, lifecycle_state=PK.LifecycleState.PUBLISHED)
    with pytest.raises(ValueError, match="require superseded_profile_id"):
        replace(base, lifecycle_state=PK.LifecycleState.SUPERSEDED)


def test_claim_resolution_preserves_competitors_and_validates_selection() -> None:
    """A resolution references immutable competing claims without replacing them."""
    resolution = PK.ClaimResolution(
        resolution_id="pk.resolution.synthetic_visual_conflict",
        field_path="visual.leaf_shape",
        competing_claim_ids=("pk.claim.synthetic_a", "pk.claim.synthetic_b"),
        selected_claim_id="pk.claim.synthetic_b",
        resolved_range=None,
        regional_weights=(PK.RegionalWeight("country", 0.8, "Exact synthetic scope"),),
        resolution_method=PK.ClaimResolutionMethod.REVIEWER_DECISION,
        resolver_identity="reviewer.synthetic",
        confidence=0.85,
        unresolved_issues=("synthetic issue remains",),
        version=1,
        created_at=NOW,
        reviewed_at=REVIEWED,
    )
    assert resolution.competing_claim_ids == (
        "pk.claim.synthetic_a",
        "pk.claim.synthetic_b",
    )
    with pytest.raises(ValueError, match="one of the competing"):
        replace(resolution, selected_claim_id="pk.claim.synthetic_c")
    with pytest.raises(ValueError, match="requires a selected claim"):
        replace(resolution, selected_claim_id=None, resolved_range=None)
