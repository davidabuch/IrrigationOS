"""Provider protocol for Visual Landscape Intelligence."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import (
    ProviderDescriptor,
    VisualAssessmentProviderResult,
    VisualAssessmentRequest,
)


@runtime_checkable
class VisualAssessmentProvider(Protocol):
    """Provider-neutral asynchronous visual-assessment boundary."""

    @property
    def descriptor(self) -> ProviderDescriptor:
        """Describe provider identity and supported capabilities."""
        ...

    async def async_assess(
        self,
        request: VisualAssessmentRequest,
    ) -> VisualAssessmentProviderResult:
        """Analyze a validated request and return a validated domain assessment."""
        ...
