"""In-memory concurrency boundary for supervised operational watering."""

from __future__ import annotations

import asyncio


class SupervisedOperationManager:
    """Serialize manual dispatch and prevent overlapping IrrigationOS operations."""

    def __init__(self) -> None:
        self.dispatch_lock = asyncio.Lock()
        self.active_operation_id: str | None = None

    @property
    def in_progress(self) -> bool:
        """Return whether an accepted operation is awaiting terminal observation."""

        return self.active_operation_id is not None

    def mark_dispatched(self, operation_id: str) -> None:
        """Latch one active operation after durable intent is recorded."""

        self.active_operation_id = operation_id

    def mark_complete(self, operation_id: str) -> None:
        """Clear only the matching active operation."""

        if self.active_operation_id == operation_id:
            self.active_operation_id = None

    def diagnostics(self) -> dict[str, object]:
        """Return privacy-safe transient operation state."""

        return {
            "in_progress": self.in_progress,
            "active_operation_id": self.active_operation_id,
        }
