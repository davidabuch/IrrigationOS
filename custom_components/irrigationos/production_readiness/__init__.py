"""Fail-closed advisory production-readiness gate."""

from .engine import MAX_PRODUCTION_OBSERVATION_AGE_SECONDS, evaluate_production_readiness
from .manager import ProductionReadinessManager
from .models import (
    PRODUCTION_READINESS_POLICY_VERSION,
    PRODUCTION_READINESS_SCHEMA_VERSION,
    ProductionReadinessInputs,
    ProductionReadinessState,
    ProductionReadinessSummary,
    ProductionTarget,
)

__all__ = [
    "MAX_PRODUCTION_OBSERVATION_AGE_SECONDS",
    "PRODUCTION_READINESS_POLICY_VERSION",
    "PRODUCTION_READINESS_SCHEMA_VERSION",
    "ProductionReadinessInputs",
    "ProductionReadinessManager",
    "ProductionReadinessState",
    "ProductionReadinessSummary",
    "ProductionTarget",
    "evaluate_production_readiness",
]
