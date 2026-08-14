"""One explicit, single-use, bounded unattended canary boundary."""

from .acceptance import (
    UNATTENDED_CANARY_ACCEPTANCE_SCHEMA_VERSION,
    UnattendedCanaryAcceptanceManager,
    UnattendedCanaryAcceptanceRecord,
    UnattendedCanaryAcceptanceStatus,
    build_canary_acceptance_record,
)
from .manager import UnattendedCanaryManager
from .models import (
    UNATTENDED_CANARY_SCHEMA_VERSION,
    UnattendedCanaryApproval,
    UnattendedCanaryApprovalState,
    UnattendedCanaryAuthorizationResult,
    UnattendedCanaryAuthorizationStatus,
    UnattendedCanaryRunResult,
    UnattendedCanaryRunStatus,
)
from .operator import (
    SERVICE_AUTHORIZE_UNATTENDED_CANARY,
    SERVICE_RUN_UNATTENDED_CANARY,
    UNATTENDED_CANARY_APPROVAL_TTL,
    UNATTENDED_CANARY_CONFIRMATION,
    UNATTENDED_CANARY_DEFAULT_RUNTIME_SECONDS,
    UNATTENDED_CANARY_MAX_RUNTIME_SECONDS,
    UNATTENDED_CANARY_MIN_RUNTIME_SECONDS,
    async_authorize_unattended_canary,
    async_run_unattended_canary,
)

__all__ = [
    "SERVICE_AUTHORIZE_UNATTENDED_CANARY",
    "SERVICE_RUN_UNATTENDED_CANARY",
    "UNATTENDED_CANARY_ACCEPTANCE_SCHEMA_VERSION",
    "UNATTENDED_CANARY_APPROVAL_TTL",
    "UNATTENDED_CANARY_CONFIRMATION",
    "UNATTENDED_CANARY_DEFAULT_RUNTIME_SECONDS",
    "UNATTENDED_CANARY_MAX_RUNTIME_SECONDS",
    "UNATTENDED_CANARY_MIN_RUNTIME_SECONDS",
    "UNATTENDED_CANARY_SCHEMA_VERSION",
    "UnattendedCanaryAcceptanceManager",
    "UnattendedCanaryAcceptanceRecord",
    "UnattendedCanaryAcceptanceStatus",
    "UnattendedCanaryApproval",
    "UnattendedCanaryApprovalState",
    "UnattendedCanaryAuthorizationResult",
    "UnattendedCanaryAuthorizationStatus",
    "UnattendedCanaryManager",
    "UnattendedCanaryRunResult",
    "UnattendedCanaryRunStatus",
    "async_authorize_unattended_canary",
    "async_run_unattended_canary",
    "build_canary_acceptance_record",
]
