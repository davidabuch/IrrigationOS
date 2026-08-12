"""In-memory integrated six-safeguard commissioning review evidence."""

from __future__ import annotations

from ..live_mode_safety.models import LiveModeSafetySummary
from .engine import build_integrated_safety_review


class IntegratedSafetyReviewManager:
    """Maintain integrated review evidence without enabling controller execution."""

    def __init__(self, live_mode_summary: LiveModeSafetySummary) -> None:
        self.summary = build_integrated_safety_review(live_mode_summary)

    def consider(self, live_mode_summary: LiveModeSafetySummary) -> None:
        """Re-evaluate review eligibility whenever safety prerequisites change."""

        self.summary = build_integrated_safety_review(live_mode_summary)

    def diagnostics(self) -> dict[str, object]:
        """Return privacy-safe integrated review evidence."""

        return self.summary.to_dict()
