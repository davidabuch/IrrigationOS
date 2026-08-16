"""Canonical observational production-recommendation API."""

from .engine import build_production_recommendations
from .models import (
    PRODUCTION_RECOMMENDATION_POLICY_VERSION,
    PRODUCTION_RECOMMENDATION_SCHEMA_VERSION,
    DeliveryReadinessState,
    ProductionAreaRecommendation,
    ProductionRecommendationEvidence,
    ProductionRecommendationSnapshot,
    ProductionRecommendationState,
    RecommendationEvidenceKind,
    RecommendationQuantity,
    RecommendationSchedulingWindow,
    ScientificNeedState,
)

__all__ = [
    "PRODUCTION_RECOMMENDATION_POLICY_VERSION",
    "PRODUCTION_RECOMMENDATION_SCHEMA_VERSION",
    "DeliveryReadinessState",
    "ProductionAreaRecommendation",
    "ProductionRecommendationEvidence",
    "ProductionRecommendationSnapshot",
    "ProductionRecommendationState",
    "RecommendationEvidenceKind",
    "RecommendationQuantity",
    "RecommendationSchedulingWindow",
    "ScientificNeedState",
    "build_production_recommendations",
]
