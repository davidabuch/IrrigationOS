"""Bounded supervised operational watering boundary."""

from ..const import (
    MANUAL_WATERING_MAX_RUNTIME_SECONDS as SUPERVISED_OPERATION_MAX_RUNTIME_SECONDS,
)
from .models import SupervisedOperationResult, SupervisedOperationStatus
from .operator import (
    SUPERVISED_OPERATION_CONFIRMATION,
    async_run_manual_operation,
    async_run_supervised_operation,
    async_stop_manual_operation,
    evaluate_supervised_operation_blockers,
)

SERVICE_RUN_SUPERVISED_OPERATION = "run_supervised_operation"

__all__ = [
    "SERVICE_RUN_SUPERVISED_OPERATION",
    "SUPERVISED_OPERATION_CONFIRMATION",
    "SUPERVISED_OPERATION_MAX_RUNTIME_SECONDS",
    "SupervisedOperationResult",
    "SupervisedOperationStatus",
    "async_run_manual_operation",
    "async_run_supervised_operation",
    "async_stop_manual_operation",
    "evaluate_supervised_operation_blockers",
]
