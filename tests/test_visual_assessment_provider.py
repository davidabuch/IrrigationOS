"""Tests for the provider-neutral visual-assessment boundary."""

from datetime import UTC, datetime
from typing import Any

import pytest

from tests.helpers import load_integration_module

MODELS = load_integration_module("visual_assessment.models")
PROVIDER_MODELS = load_integration_module("visual_assessment.providers.models")
PROVIDER_BASE = load_integration_module("visual_assessment.providers.base")

AssessmentContextValue = PROVIDER_MODELS.AssessmentContextValue
ProviderCapability = PROVIDER_MODELS.ProviderCapability
ProviderDescriptor = PROVIDER_MODELS.ProviderDescriptor
ProviderErrorCategory = PROVIDER_MODELS.ProviderErrorCategory
ProviderFailure = PROVIDER_MODELS.ProviderFailure
ProviderRetryPolicy = PROVIDER_MODELS.ProviderRetryPolicy
VisualAssessmentProviderResult = PROVIDER_MODELS.VisualAssessmentProviderResult
VisualAssessmentPurpose = PROVIDER_MODELS.VisualAssessmentPurpose
VisualAssessmentRequest = PROVIDER_MODELS.VisualAssessmentRequest
VisualAssessmentProvider = PROVIDER_BASE.VisualAssessmentProvider

PhotoEvidence = MODELS.PhotoEvidence
PhotoEvidenceType = MODELS.PhotoEvidenceType
PhotoSource = MODELS.PhotoSource
PrivacyClassification = MODELS.PrivacyClassification
RetentionPolicy = MODELS.RetentionPolicy
VisualAssessmentSession = MODELS.VisualAssessmentSession
VisualAssessmentSessionState = MODELS.VisualAssessmentSessionState
VisualLandscapeAssessment = MODELS.VisualLandscapeAssessment

NOW = datetime(2026, 8, 3, 18, 0, tzinfo=UTC)


def photo(
    *,
    evidence_id: str = "evidence-1",
    area_id: str = "area-1",
) -> Any:
    """Build safe provider photo evidence."""
    return PhotoEvidence(
        evidence_id=evidence_id,
        area_id=area_id,
        evidence_type=PhotoEvidenceType.AREA_OVERVIEW,
        captured_at=NOW,
        source=PhotoSource.USER_CAPTURE,
        privacy_classification=PrivacyClassification.PRIVATE,
        retention_policy=RetentionPolicy.SESSION,
        content_reference=f"photo-store:{evidence_id}",
    )


def request(**changes: object) -> Any:
    """Build a valid provider request."""
    values: dict[str, object] = {
        "request_id": "request-1",
        "session_id": "session-1",
        "area_id": "area-1",
        "purpose": VisualAssessmentPurpose.INITIAL_LANDSCAPE_SETUP,
        "requested_at": NOW,
        "photo_evidence": (photo(),),
        "required_capabilities": (
            ProviderCapability.IMAGE_ANALYSIS,
            ProviderCapability.STRUCTURED_OUTPUT,
        ),
        "context": (
            AssessmentContextValue(
                key="vendor_zone_name",
                value="Back Garden",
                source="rachio",
            ),
        ),
    }
    values.update(changes)
    return VisualAssessmentRequest(**values)


def assessment() -> Any:
    """Build a minimal valid domain assessment."""
    session = VisualAssessmentSession(
        session_id="session-1",
        area_id="area-1",
        state=VisualAssessmentSessionState.READY_FOR_REVIEW,
        created_at=NOW,
        updated_at=NOW,
        evidence_ids=("evidence-1",),
    )
    return VisualLandscapeAssessment(
        assessment_id="assessment-1",
        session=session,
        assessed_at=NOW,
        photo_evidence=(photo(),),
    )


def test_provider_request_serializes_deterministically() -> None:
    """Requests use stable plain values and opaque photo references."""
    current = request()

    first = current.to_dict()
    second = current.to_dict()

    assert first == second
    assert first["purpose"] == "initial_landscape_setup"
    assert first["required_capabilities"] == [
        "image_analysis",
        "structured_output",
    ]
    assert first["photo_evidence"][0]["content_reference"] == (
        "photo-store:evidence-1"
    )


def test_request_requires_same_area_and_unique_evidence() -> None:
    """A provider cannot receive evidence from an unrelated area."""
    with pytest.raises(ValueError, match="request area"):
        request(photo_evidence=(photo(area_id="area-2"),))

    duplicate = photo()
    with pytest.raises(ValueError, match="must not contain duplicates"):
        request(photo_evidence=(duplicate, duplicate))


def test_request_rejects_duplicate_capabilities_and_context_keys() -> None:
    """Provider requests remain unambiguous."""
    with pytest.raises(ValueError, match="required_capabilities"):
        request(
            required_capabilities=(
                ProviderCapability.IMAGE_ANALYSIS,
                ProviderCapability.IMAGE_ANALYSIS,
            )
        )

    duplicate_context = (
        AssessmentContextValue(key="soil_hint", value="clay", source="user"),
        AssessmentContextValue(key="soil_hint", value="loam", source="dataset"),
    )
    with pytest.raises(ValueError, match="context keys"):
        request(context=duplicate_context)


def test_retry_policy_is_strictly_bounded() -> None:
    """Retries cannot become unbounded background provider traffic."""
    policy = ProviderRetryPolicy(
        maximum_attempts=3,
        initial_delay_seconds=1,
        maximum_delay_seconds=4,
        multiplier=2,
    )
    assert policy.maximum_attempts == 3

    with pytest.raises(ValueError, match="between 1 and 5"):
        ProviderRetryPolicy(maximum_attempts=6)

    with pytest.raises(ValueError, match="cannot be less"):
        ProviderRetryPolicy(
            initial_delay_seconds=5,
            maximum_delay_seconds=1,
        )


def test_provider_failure_is_safe_and_structured() -> None:
    """Provider failures expose stable UI-safe categories."""
    failure = ProviderFailure(
        category=ProviderErrorCategory.RATE_LIMITED,
        message="The assessment provider is temporarily rate limited",
        retryable=True,
        occurred_at=NOW,
        provider_id="provider-test",
        request_id="request-1",
        retry_after_seconds=30,
    )

    assert failure.to_dict()["category"] == "rate_limited"

    with pytest.raises(ValueError, match="only valid for retryable"):
        ProviderFailure(
            category=ProviderErrorCategory.INVALID_REQUEST,
            message="Invalid request",
            retryable=False,
            occurred_at=NOW,
            retry_after_seconds=30,
        )


@pytest.mark.asyncio
async def test_fake_provider_satisfies_protocol_and_returns_domain_assessment() -> None:
    """The boundary can be implemented without provider-specific domain types."""

    class FakeProvider:
        descriptor = ProviderDescriptor(
            provider_id="fake-provider",
            display_name="Fake Visual Provider",
            capabilities=(
                ProviderCapability.IMAGE_ANALYSIS,
                ProviderCapability.STRUCTURED_OUTPUT,
            ),
            supports_cloud_processing=False,
        )

        async def async_assess(
            self,
            current_request: Any,
        ) -> Any:
            return VisualAssessmentProviderResult(
                request_id=current_request.request_id,
                provider_id=self.descriptor.provider_id,
                received_at=NOW,
                assessment=assessment(),
                provider_request_id="fake-request-1",
            )

    provider = FakeProvider()

    assert isinstance(provider, VisualAssessmentProvider)

    result = await provider.async_assess(request())

    assert result.provider_id == "fake-provider"
    assert result.assessment.assessment_id == "assessment-1"
    assert result.request_id == "request-1"


def test_provider_capability_and_error_vocabularies_are_stable() -> None:
    """Critical provider vocabulary remains explicit and testable."""
    assert ProviderCapability.HEALTH_DIAGNOSTICS.value == "health_diagnostics"
    assert ProviderErrorCategory.INVALID_RESPONSE.value == "invalid_response"
    assert VisualAssessmentPurpose.FOLLOW_UP_ASSESSMENT.value == (
        "follow_up_assessment"
    )
