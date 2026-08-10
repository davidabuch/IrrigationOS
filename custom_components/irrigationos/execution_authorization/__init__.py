"""Fail-closed execution authorization and safety-gate contracts."""

from .engine import (
    MAX_OBSERVATION_AGE_SECONDS,
    MAX_SINGLE_COMMAND_RUNTIME_SECONDS,
    build_execution_authorization_summary,
)
from .models import ExecutionAuthorizationStatus, ExecutionAuthorizationSummary

__all__ = [
    "MAX_OBSERVATION_AGE_SECONDS",
    "MAX_SINGLE_COMMAND_RUNTIME_SECONDS",
    "ExecutionAuthorizationStatus",
    "ExecutionAuthorizationSummary",
    "build_execution_authorization_summary",
]
