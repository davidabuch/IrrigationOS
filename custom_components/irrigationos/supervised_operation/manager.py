"""In-memory concurrency boundary for supervised operational watering."""

from __future__ import annotations

import asyncio


class SupervisedOperationManager:
    """Serialize manual dispatch and prevent overlapping IrrigationOS operations."""

    def __init__(self) -> None:
        self.dispatch_lock = asyncio.Lock()
        self.active_operation_id: str | None = None
        self.active_controller_slot: int | None = None
        self.active_area_slot: int | None = None
        self.active_runtime_seconds: int | None = None

    @property
    def in_progress(self) -> bool:
        """Return whether an accepted operation is awaiting terminal observation."""

        return self.active_operation_id is not None

    def mark_dispatched(
        self,
        operation_id: str,
        *,
        controller_slot: int,
        area_slot: int,
        runtime_seconds: int,
    ) -> None:
        """Latch one operation only after its start request is accepted."""

        self.active_operation_id = operation_id
        self.active_controller_slot = controller_slot
        self.active_area_slot = area_slot
        self.active_runtime_seconds = runtime_seconds

    def mark_complete(self, operation_id: str) -> None:
        """Clear only the matching active operation."""

        if self.active_operation_id == operation_id:
            self.active_operation_id = None
            self.active_controller_slot = None
            self.active_area_slot = None
            self.active_runtime_seconds = None

    def diagnostics(self) -> dict[str, object]:
        """Return privacy-safe transient operation state."""

        return {
            "in_progress": self.in_progress,
            "active_operation_id": self.active_operation_id,
            "controller_slot": self.active_controller_slot,
            "area_slot": self.active_area_slot,
            "requested_runtime_seconds": self.active_runtime_seconds,
        }
