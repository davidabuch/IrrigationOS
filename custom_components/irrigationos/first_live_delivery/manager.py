"""Release-gated first-live command-delivery manager."""

from __future__ import annotations

from ..live_commissioning.models import LiveCommissioningSummary
from .engine import build_first_live_delivery_summary


class FirstLiveDeliveryManager:
    """Maintain delivery-boundary evidence without exposing an execution entrypoint."""

    def __init__(self, commissioning: LiveCommissioningSummary) -> None:
        self.summary = build_first_live_delivery_summary(commissioning)

    def consider(self, commissioning: LiveCommissioningSummary) -> None:
        """Re-evaluate delivery readiness whenever commissioning evidence changes."""

        self.summary = build_first_live_delivery_summary(commissioning)

    def diagnostics(self) -> dict[str, object]:
        """Return privacy-safe release-gate evidence."""

        return self.summary.to_dict()
