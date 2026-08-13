"""Coordinator-facing recomputation manager for production readiness."""

from __future__ import annotations

from .engine import evaluate_production_readiness
from .models import ProductionReadinessInputs


class ProductionReadinessManager:
    """Hold only the current recomputed advisory summary."""

    def __init__(self, inputs: ProductionReadinessInputs) -> None:
        self.summary = evaluate_production_readiness(inputs)

    def consider(self, inputs: ProductionReadinessInputs) -> None:
        """Replace stale evidence with one fresh deterministic evaluation."""

        self.summary = evaluate_production_readiness(inputs)

    def diagnostics(self) -> dict[str, object]:
        return self.summary.to_dict()
