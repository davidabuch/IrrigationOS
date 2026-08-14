"""Restart-ephemeral approval and in-progress canary state."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from ..production_readiness.models import ProductionTarget
from .models import (
    UnattendedCanaryApproval,
    UnattendedCanaryApprovalState,
)


class UnattendedCanaryManager:
    """Own exactly one ephemeral approval and one transient canary operation."""

    def __init__(self) -> None:
        self.dispatch_lock = asyncio.Lock()
        self.approval: UnattendedCanaryApproval | None = None
        self.active_canary_id: str | None = None
        self.active_approval_id: str | None = None
        self.active_controller_slot: int | None = None
        self.active_area_slot: int | None = None
        self.active_runtime_seconds: int | None = None
        self.last_audit_error: str | None = None

    @property
    def in_progress(self) -> bool:
        return self.active_canary_id is not None

    def approval_state(
        self, now: datetime | None = None
    ) -> UnattendedCanaryApprovalState:
        if self.approval is None:
            return UnattendedCanaryApprovalState.NONE
        return self.approval.state_at(now or datetime.now(UTC))

    def install_approval(self, approval: UnattendedCanaryApproval) -> None:
        """Install one already-audited explicit approval."""

        self.approval = approval

    def consume_approval(self, approval_id: str, consumed_at: datetime) -> bool:
        """Atomically consume only the currently valid matching approval."""

        approval = self.approval
        if approval is None or approval.approval_id != approval_id:
            return False
        if approval.state_at(consumed_at) is not UnattendedCanaryApprovalState.APPROVED:
            return False
        self.approval = replace(approval, consumed_at=consumed_at)
        return True

    def valid_approval_for(
        self,
        *,
        now: datetime,
        production_targets: tuple[ProductionTarget, ...],
        validated_targets: tuple[ProductionTarget, ...],
    ) -> bool:
        """Return whether approval can satisfy the readiness prerequisite."""

        approval = self.approval
        if approval is None or (
            approval.state_at(now) is not UnattendedCanaryApprovalState.APPROVED
        ):
            return False
        target = ProductionTarget(approval.controller_slot, approval.area_slot)
        return target in production_targets and target in validated_targets

    def mark_dispatched(
        self,
        canary_id: str,
        approval_id: str,
        *,
        controller_slot: int,
        area_slot: int,
        runtime_seconds: int,
    ) -> None:
        self.active_canary_id = canary_id
        self.active_approval_id = approval_id
        self.active_controller_slot = controller_slot
        self.active_area_slot = area_slot
        self.active_runtime_seconds = runtime_seconds

    def mark_complete(self, canary_id: str) -> None:
        if self.active_canary_id != canary_id:
            return
        self.active_canary_id = None
        self.active_approval_id = None
        self.active_controller_slot = None
        self.active_area_slot = None
        self.active_runtime_seconds = None

    def record_audit_result(self, success: bool) -> None:
        self.last_audit_error = None if success else "unattended_canary_audit_write_failed"

    def approval_diagnostics(self, now: datetime | None = None) -> dict[str, Any]:
        evaluated_at = now or datetime.now(UTC)
        if self.approval is None:
            return {
                "state": UnattendedCanaryApprovalState.NONE.value,
                "approval": None,
                "single_use": True,
                "persists_across_restart": False,
            }
        return {
            "state": self.approval.state_at(evaluated_at).value,
            "approval": self.approval.to_dict(evaluated_at),
            "single_use": True,
            "persists_across_restart": False,
        }

    def progress_diagnostics(self) -> dict[str, object]:
        return {
            "in_progress": self.in_progress,
            "active_canary_id": self.active_canary_id,
            "approval_id": self.active_approval_id,
            "controller_slot": self.active_controller_slot,
            "area_slot": self.active_area_slot,
            "runtime_seconds": self.active_runtime_seconds,
            "persists_across_restart": False,
        }

    def diagnostics(self) -> dict[str, Any]:
        return {
            "approval": self.approval_diagnostics(),
            "progress": self.progress_diagnostics(),
            "last_audit_error": self.last_audit_error,
        }
