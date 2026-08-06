"""Stable public contracts for deterministic recommendations."""

from .engine import assess_recommendations
from .models import (
    RECOMMENDATION_ALGORITHM_VERSION,
    RECOMMENDATION_SCHEMA_VERSION,
    Recommendation,
    RecommendationAssessment,
    RecommendationCategory,
    RecommendationExplanation,
    RecommendationPolicy,
    RecommendationPriority,
    RecommendationRequest,
    RecommendationSafetyFlag,
    RecommendationStatus,
)

__all__ = (
    "RECOMMENDATION_ALGORITHM_VERSION",
    "RECOMMENDATION_SCHEMA_VERSION",
    "Recommendation",
    "RecommendationAssessment",
    "RecommendationCategory",
    "RecommendationExplanation",
    "RecommendationPolicy",
    "RecommendationPriority",
    "RecommendationRequest",
    "RecommendationSafetyFlag",
    "RecommendationStatus",
    "assess_recommendations",
)
