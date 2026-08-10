"""In-memory Live-mode safety architecture evidence manager."""

from __future__ import annotations

from .engine import build_live_mode_safety_summary


class LiveModeSafetyManager:
    """Maintain derived pre-Live safety evidence without enabling control."""

    def __init__(self) -> None:
        self.summary = build_live_mode_safety_summary(
            readiness_status="insufficient_evidence",
            execution_authorization_status="blocked",
            ownership_confirmed=False,
            boundary_review_acknowledged=False,
        )

    def consider(
        self,
        *,
        readiness_status: str,
        execution_authorization_status: str,
        ownership_confirmed: bool,
        boundary_review_acknowledged: bool,
    ) -> None:
        self.summary = build_live_mode_safety_summary(
            readiness_status=readiness_status,
            execution_authorization_status=execution_authorization_status,
            ownership_confirmed=ownership_confirmed,
            boundary_review_acknowledged=boundary_review_acknowledged,
        )

    def diagnostics(self) -> dict[str, object]:
        return self.summary.to_dict()
