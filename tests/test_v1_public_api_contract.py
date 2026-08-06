"""Compatibility contracts for the frozen v1.0 domain-layer public APIs."""

from __future__ import annotations

from tests.helpers import load_integration_module

execution = load_integration_module("execution")
planning = load_integration_module("planning")
plant_health = load_integration_module("plant_health")
plant_stress = load_integration_module("plant_stress")
plant_water_requirement = load_integration_module("plant_water_requirement")
recommendations = load_integration_module("recommendations")
runtime_monitoring = load_integration_module("runtime_monitoring")
scheduling = load_integration_module("scheduling")


def test_v1_domain_public_exports_are_frozen() -> None:
    """Protect the public symbols downstream integrations may import."""
    expected = {
        plant_water_requirement: {
            "PLANT_WATER_REQUIREMENT_ALGORITHM_VERSION",
            "PLANT_WATER_REQUIREMENT_SCHEMA_VERSION",
            "PlantWaterRequirementAssessment",
            "PlantWaterRequirementPolicy",
            "PlantWaterRequirementRequest",
            "PlantWaterRequirementStatus",
            "assess_plant_water_requirement",
        },
        plant_stress: {
            "PLANT_STRESS_RISK_ALGORITHM_VERSION",
            "PLANT_STRESS_RISK_SCHEMA_VERSION",
            "PlantStressRiskAssessment",
            "PlantStressRiskPolicy",
            "PlantStressRiskRequest",
            "PlantStressRiskStatus",
            "aggregate_plant_stress",
            "assess_freeze_stress",
            "assess_heat_stress",
            "assess_water_deficit_stress",
        },
        plant_health: {
            "PLANT_HEALTH_ALGORITHM_VERSION",
            "PLANT_HEALTH_SCHEMA_VERSION",
            "PlantHealthAssessment",
            "PlantHealthPolicy",
            "PlantHealthRequest",
            "PlantHealthStatus",
            "assess_plant_health",
        },
        recommendations: {
            "RECOMMENDATION_ALGORITHM_VERSION",
            "RECOMMENDATION_SCHEMA_VERSION",
            "RecommendationAssessment",
            "RecommendationPolicy",
            "RecommendationRequest",
            "RecommendationStatus",
            "assess_recommendations",
        },
        planning: {
            "PLANNING_ALGORITHM_VERSION",
            "PLANNING_SCHEMA_VERSION",
            "IrrigationPlan",
            "PlanningPolicy",
            "PlanningRequest",
            "PlanStatus",
            "build_irrigation_plan",
        },
        scheduling: {
            "SCHEDULING_ALGORITHM_VERSION",
            "SCHEDULING_SCHEMA_VERSION",
            "IrrigationSchedule",
            "SchedulingPolicy",
            "SchedulingRequest",
            "ScheduleStatus",
            "build_irrigation_schedule",
        },
        execution: {
            "EXECUTION_ALGORITHM_VERSION",
            "EXECUTION_SCHEMA_VERSION",
            "ExecutionPlan",
            "ExecutionPolicy",
            "ExecutionRequest",
            "ExecutionPlanStatus",
            "build_execution_plan",
            "evaluate_command_outcome",
        },
        runtime_monitoring: {
            "RUNTIME_MONITORING_ALGORITHM_VERSION",
            "RUNTIME_MONITORING_SCHEMA_VERSION",
            "RuntimeMonitoringRequest",
            "RuntimePolicy",
            "RuntimeReport",
            "RuntimeStatus",
            "build_runtime_report",
        },
    }

    for module, required_symbols in expected.items():
        exported = set(module.__all__)
        assert required_symbols <= exported
        for symbol in required_symbols:
            assert hasattr(module, symbol)


def test_v1_domain_schema_versions_are_explicit() -> None:
    """Require non-empty schema and algorithm versions for every frozen layer."""
    version_pairs = (
        (
            plant_water_requirement.PLANT_WATER_REQUIREMENT_SCHEMA_VERSION,
            plant_water_requirement.PLANT_WATER_REQUIREMENT_ALGORITHM_VERSION,
        ),
        (
            plant_stress.PLANT_STRESS_RISK_SCHEMA_VERSION,
            plant_stress.PLANT_STRESS_RISK_ALGORITHM_VERSION,
        ),
        (
            plant_health.PLANT_HEALTH_SCHEMA_VERSION,
            plant_health.PLANT_HEALTH_ALGORITHM_VERSION,
        ),
        (
            recommendations.RECOMMENDATION_SCHEMA_VERSION,
            recommendations.RECOMMENDATION_ALGORITHM_VERSION,
        ),
        (planning.PLANNING_SCHEMA_VERSION, planning.PLANNING_ALGORITHM_VERSION),
        (scheduling.SCHEDULING_SCHEMA_VERSION, scheduling.SCHEDULING_ALGORITHM_VERSION),
        (execution.EXECUTION_SCHEMA_VERSION, execution.EXECUTION_ALGORITHM_VERSION),
        (
            runtime_monitoring.RUNTIME_MONITORING_SCHEMA_VERSION,
            runtime_monitoring.RUNTIME_MONITORING_ALGORITHM_VERSION,
        ),
    )

    for schema_version, algorithm_version in version_pairs:
        assert schema_version
        assert algorithm_version
