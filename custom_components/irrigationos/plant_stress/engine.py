"""Deterministic water-deficit plant stress-risk assessment engine."""

from __future__ import annotations

from hashlib import sha256

from ..environment import (
    EnvironmentalSignal,
    EnvironmentalSignalClassification,
    EnvironmentalSignalType,
)
from ..plant_knowledge import (
    EffectivePlantKnowledgeClaim,
    HeatTolerance,
    KnowledgeRange,
    WaterStressSensitivity,
)
from ..plant_water_requirement import PlantWaterRequirementStatus
from .models import (
    PLANT_STRESS_RISK_ALGORITHM_VERSION,
    MissingEvidenceBehavior,
    OverallRiskAggregation,
    PartialEvidenceBehavior,
    PlantStressDimension,
    PlantStressDimensionAssessment,
    PlantStressRiskAssessment,
    PlantStressRiskClassification,
    PlantStressRiskConfidence,
    PlantStressRiskExplanation,
    PlantStressRiskRequest,
    PlantStressRiskStatus,
)

_WATER_STRESS_PATH = "water.water_stress_sensitivity"
_REQUIRED_INPUT_COUNT = 3

_HEAT_TOLERANCE_PATH = "environment.heat_tolerance"
_HEAT_REQUIRED_INPUT_COUNT = 2

_HEAT_BASE_RISK: dict[
    EnvironmentalSignalClassification,
    dict[HeatTolerance, PlantStressRiskClassification],
] = {
    EnvironmentalSignalClassification.NONE: {
        HeatTolerance.LOW: PlantStressRiskClassification.NONE,
        HeatTolerance.MODERATE: PlantStressRiskClassification.NONE,
        HeatTolerance.HIGH: PlantStressRiskClassification.NONE,
    },
    EnvironmentalSignalClassification.LOW: {
        HeatTolerance.LOW: PlantStressRiskClassification.LOW,
        HeatTolerance.MODERATE: PlantStressRiskClassification.NONE,
        HeatTolerance.HIGH: PlantStressRiskClassification.NONE,
    },
    EnvironmentalSignalClassification.MODERATE: {
        HeatTolerance.LOW: PlantStressRiskClassification.MODERATE,
        HeatTolerance.MODERATE: PlantStressRiskClassification.LOW,
        HeatTolerance.HIGH: PlantStressRiskClassification.LOW,
    },
    EnvironmentalSignalClassification.HIGH: {
        HeatTolerance.LOW: PlantStressRiskClassification.HIGH,
        HeatTolerance.MODERATE: PlantStressRiskClassification.MODERATE,
        HeatTolerance.HIGH: PlantStressRiskClassification.LOW,
    },
    EnvironmentalSignalClassification.EXTREME: {
        HeatTolerance.LOW: PlantStressRiskClassification.VERY_HIGH,
        HeatTolerance.MODERATE: PlantStressRiskClassification.HIGH,
        HeatTolerance.HIGH: PlantStressRiskClassification.MODERATE,
    },
}

_BASE_RISK: dict[
    EnvironmentalSignalClassification,
    dict[WaterStressSensitivity, PlantStressRiskClassification],
] = {
    EnvironmentalSignalClassification.STRONGLY_WETTING: {
        WaterStressSensitivity.LOW: PlantStressRiskClassification.NONE,
        WaterStressSensitivity.MODERATE: PlantStressRiskClassification.NONE,
        WaterStressSensitivity.HIGH: PlantStressRiskClassification.LOW,
    },
    EnvironmentalSignalClassification.WETTING: {
        WaterStressSensitivity.LOW: PlantStressRiskClassification.NONE,
        WaterStressSensitivity.MODERATE: PlantStressRiskClassification.LOW,
        WaterStressSensitivity.HIGH: PlantStressRiskClassification.LOW,
    },
    EnvironmentalSignalClassification.BALANCED: {
        WaterStressSensitivity.LOW: PlantStressRiskClassification.LOW,
        WaterStressSensitivity.MODERATE: PlantStressRiskClassification.LOW,
        WaterStressSensitivity.HIGH: PlantStressRiskClassification.MODERATE,
    },
    EnvironmentalSignalClassification.DRYING: {
        WaterStressSensitivity.LOW: PlantStressRiskClassification.LOW,
        WaterStressSensitivity.MODERATE: PlantStressRiskClassification.MODERATE,
        WaterStressSensitivity.HIGH: PlantStressRiskClassification.HIGH,
    },
    EnvironmentalSignalClassification.STRONGLY_DRYING: {
        WaterStressSensitivity.LOW: PlantStressRiskClassification.MODERATE,
        WaterStressSensitivity.MODERATE: PlantStressRiskClassification.HIGH,
        WaterStressSensitivity.HIGH: PlantStressRiskClassification.VERY_HIGH,
    },
}

_RISK_ORDER = (
    PlantStressRiskClassification.NONE,
    PlantStressRiskClassification.LOW,
    PlantStressRiskClassification.MODERATE,
    PlantStressRiskClassification.HIGH,
    PlantStressRiskClassification.VERY_HIGH,
)


def assess_water_deficit_stress(
    request: PlantStressRiskRequest,
) -> PlantStressRiskAssessment:
    """Assess water-deficit risk from immutable upstream evidence only."""
    if not isinstance(request, PlantStressRiskRequest):
        raise TypeError("request must be a PlantStressRiskRequest")
    if PlantStressDimension.WATER_DEFICIT not in request.policy.enabled_dimensions:
        return _aggregate(
            request,
            _non_success(
                request,
                PlantStressRiskStatus.UNAVAILABLE,
                "water_deficit_dimension_disabled",
                "Water-deficit assessment is disabled by policy.",
                "policy does not enable water_deficit",
            ),
        )

    if request.selected_profile_id is None:
        return _aggregate(
            request,
            _non_success(
                request,
                PlantStressRiskStatus.INSUFFICIENT_PLANT_KNOWLEDGE,
                "plant_profile_unresolved",
                "Plant profile resolution is unavailable.",
                "plant profile was not resolved",
            ),
        )

    sensitivity_claim = _sensitivity_claim(request)
    if sensitivity_claim is None or not isinstance(
        sensitivity_claim.value, WaterStressSensitivity
    ) or sensitivity_claim.value is WaterStressSensitivity.UNKNOWN:
        return _aggregate(
            request,
            _non_success(
                request,
                PlantStressRiskStatus.INSUFFICIENT_PLANT_KNOWLEDGE,
                "water_stress_sensitivity_unavailable",
                "Water-stress sensitivity evidence is unavailable.",
                "approved water.water_stress_sensitivity evidence was not resolved",
            ),
        )
    if sensitivity_claim.conflict_unresolved:
        return _aggregate(
            request,
            _non_success(
                request,
                PlantStressRiskStatus.CONFLICTING_EVIDENCE,
                "water_stress_sensitivity_conflicting",
                "Water-stress sensitivity evidence remains conflicting.",
                "water.water_stress_sensitivity evidence has an unresolved conflict",
                claim=sensitivity_claim,
            ),
        )

    water = request.water_requirement_assessment
    if water.status not in {
        PlantWaterRequirementStatus.AVAILABLE,
        PlantWaterRequirementStatus.PARTIAL,
    } or water.value is None:
        return _aggregate(
            request,
            _non_success(
                request,
                PlantStressRiskStatus.UNAVAILABLE,
                "water_requirement_unavailable",
                "Plant Water Requirement assessment is unavailable.",
                f"water requirement status is {water.status.value}",
                claim=sensitivity_claim,
            ),
        )

    drying_signal = _drying_signal(request)
    if drying_signal is None or drying_signal.classification not in _BASE_RISK:
        return _aggregate(
            request,
            _non_success(
                request,
                PlantStressRiskStatus.INSUFFICIENT_ENVIRONMENTAL_EVIDENCE,
                "drying_signal_unavailable",
                "Environmental drying evidence is unavailable.",
                "environmental report lacks a usable drying signal",
                claim=sensitivity_claim,
            ),
        )

    risk = _BASE_RISK[drying_signal.classification][sensitivity_claim.value]
    risk = _adjust_for_water_requirement(risk, water.value)
    known_inputs = 3
    confidence_value = min(
        sensitivity_claim.confidence,
        water.confidence.confidence,
        drying_signal.confidence.average_confidence,
    )
    incomplete = (
        water.status is PlantWaterRequirementStatus.PARTIAL
        or water.confidence.completeness < 1.0
        or drying_signal.confidence.completeness < 1.0
    )
    below_confidence = confidence_value < request.policy.minimum_confidence
    partial = incomplete or below_confidence
    if (
        partial
        and request.policy.partial_evidence_behavior
        is PartialEvidenceBehavior.REQUIRE_COMPLETE
    ):
        return _aggregate(
            request,
            _non_success(
                request,
                PlantStressRiskStatus.UNAVAILABLE,
                "complete_evidence_required",
                "Complete water-deficit evidence is required by policy.",
                "one or more required inputs are incomplete or below confidence policy",
                claim=sensitivity_claim,
                signal=drying_signal,
            ),
        )

    issues: list[str] = []
    if incomplete:
        issues.append("one or more upstream inputs are incomplete")
    if below_confidence:
        issues.append("combined evidence confidence is below policy")
    status = PlantStressRiskStatus.PARTIAL if partial else PlantStressRiskStatus.AVAILABLE
    dimension = PlantStressDimensionAssessment(
        assessment_id=_dimension_id(request.request_id),
        dimension=PlantStressDimension.WATER_DEFICIT,
        status=status,
        risk=risk,
        confidence=PlantStressRiskConfidence(
            confidence=confidence_value,
            completeness=known_inputs / _REQUIRED_INPUT_COUNT,
            known_required_input_count=known_inputs,
            required_input_count=_REQUIRED_INPUT_COUNT,
        ),
        selected_profile_id=request.selected_profile_id,
        plant_knowledge_claim_ids=(sensitivity_claim.claim_id,),
        plant_knowledge_source_ids=tuple(sorted(sensitivity_claim.source_ids)),
        water_requirement_assessment_id=water.assessment_id,
        environmental_report_id=request.environmental_report.report_id,
        environmental_signal_ids=(drying_signal.signal_id,),
        regional_applicability=sensitivity_claim.regional_applicability,
        policy_id=request.policy.policy_id,
        policy_version=request.policy.policy_version,
        algorithm_version=PLANT_STRESS_RISK_ALGORITHM_VERSION,
        explanation=PlantStressRiskExplanation(
            reason_codes=tuple(
                sorted(
                    {
                        f"drying_{drying_signal.classification.value}",
                        f"sensitivity_{sensitivity_claim.value.value}",
                        "water_requirement_available",
                    }
                )
            ),
            summary=(
                f"Water-deficit risk is {risk.value} from "
                f"{drying_signal.classification.value} conditions and "
                f"{sensitivity_claim.value.value} plant sensitivity."
            ),
        ),
        unresolved_issues=tuple(sorted(issues)),
    )
    return _aggregate(request, dimension)


def _sensitivity_claim(request: PlantStressRiskRequest) -> EffectivePlantKnowledgeClaim | None:
    return next(
        (
            claim
            for claim in request.knowledge_resolution.effective_claims
            if claim.field_path == _WATER_STRESS_PATH
        ),
        None,
    )


def _drying_signal(request: PlantStressRiskRequest) -> EnvironmentalSignal | None:
    signals = tuple(
        signal
        for signal in request.environmental_report.signals
        if signal.signal_type
        in {
            EnvironmentalSignalType.ATMOSPHERIC_WATER_BALANCE,
            EnvironmentalSignalType.DRYING_TREND,
        }
    )
    if not signals:
        return None
    return sorted(signals, key=lambda signal: (signal.signal_type.value, signal.signal_id))[0]


def _adjust_for_water_requirement(
    risk: PlantStressRiskClassification,
    value: float | KnowledgeRange,
) -> PlantStressRiskClassification:
    if isinstance(value, KnowledgeRange):
        factor = value.typical if value.typical is not None else value.maximum
    else:
        factor = float(value)
    index = _RISK_ORDER.index(risk)
    if factor >= 0.7:
        index = min(index + 1, len(_RISK_ORDER) - 1)
    elif factor <= 0.3:
        index = max(index - 1, 0)
    return _RISK_ORDER[index]


def _non_success(
    request: PlantStressRiskRequest,
    status: PlantStressRiskStatus,
    reason: str,
    summary: str,
    issue: str,
    *,
    claim: EffectivePlantKnowledgeClaim | None = None,
    signal: EnvironmentalSignal | None = None,
) -> PlantStressDimensionAssessment:
    if request.policy.missing_evidence_behavior is MissingEvidenceBehavior.RETURN_UNAVAILABLE:
        status = PlantStressRiskStatus.UNAVAILABLE
    known = (
        int(claim is not None)
        + int(request.water_requirement_assessment.value is not None)
        + int(signal is not None)
    )
    confidence_values = [
        value
        for value in (
            claim.confidence if claim is not None else None,
            request.water_requirement_assessment.confidence.confidence
            if request.water_requirement_assessment.value is not None
            else None,
            signal.confidence.average_confidence if signal is not None else None,
        )
        if value is not None
    ]
    return PlantStressDimensionAssessment(
        assessment_id=_dimension_id(request.request_id),
        dimension=PlantStressDimension.WATER_DEFICIT,
        status=status,
        risk=PlantStressRiskClassification.UNKNOWN,
        confidence=PlantStressRiskConfidence(
            confidence=min(confidence_values) if confidence_values else 0.0,
            completeness=known / _REQUIRED_INPUT_COUNT,
            known_required_input_count=known,
            required_input_count=_REQUIRED_INPUT_COUNT,
        ),
        selected_profile_id=request.selected_profile_id,
        plant_knowledge_claim_ids=(claim.claim_id,) if claim is not None else (),
        plant_knowledge_source_ids=tuple(sorted(claim.source_ids)) if claim is not None else (),
        water_requirement_assessment_id=request.water_requirement_assessment.assessment_id,
        environmental_report_id=request.environmental_report.report_id,
        environmental_signal_ids=(signal.signal_id,) if signal is not None else (),
        regional_applicability=request.context.regional_applicability,
        policy_id=request.policy.policy_id,
        policy_version=request.policy.policy_version,
        algorithm_version=PLANT_STRESS_RISK_ALGORITHM_VERSION,
        explanation=PlantStressRiskExplanation(reason_codes=(reason,), summary=summary),
        unresolved_issues=(issue,),
    )


def _aggregate(
    request: PlantStressRiskRequest,
    dimension: PlantStressDimensionAssessment,
) -> PlantStressRiskAssessment:
    overall_risk = (
        dimension.risk
        if request.policy.overall_risk_aggregation is OverallRiskAggregation.HIGHEST_AVAILABLE
        and dimension.risk is not PlantStressRiskClassification.UNKNOWN
        else None
    )
    return PlantStressRiskAssessment(
        assessment_id=_aggregate_id(request.request_id),
        request_id=request.request_id,
        selected_profile_id=request.selected_profile_id,
        location_id=request.context.location_id,
        analysis_window_id=request.context.analysis_window_id,
        dimensions=(dimension,),
        overall_status=dimension.status,
        overall_risk=overall_risk,
        confidence=dimension.confidence,
        knowledge_resolution_id=request.knowledge_resolution.request_id,
        water_requirement_assessment_id=request.water_requirement_assessment.assessment_id,
        environmental_report_id=request.environmental_report.report_id,
        policy_id=request.policy.policy_id,
        policy_version=request.policy.policy_version,
        algorithm_version=PLANT_STRESS_RISK_ALGORITHM_VERSION,
        explanation=PlantStressRiskExplanation(
            reason_codes=("water_deficit_dimension_assessed",),
            summary="Water-deficit plant stress risk assessment completed.",
        ),
        unresolved_issues=dimension.unresolved_issues,
        created_at=request.created_at,
    )


def _dimension_id(request_id: str) -> str:
    return f"plant-stress.water-deficit.{sha256(request_id.encode()).hexdigest()}"


def _aggregate_id(request_id: str) -> str:
    return f"plant-stress.assessment.{sha256(request_id.encode()).hexdigest()}"


def assess_heat_stress(request: PlantStressRiskRequest) -> PlantStressRiskAssessment:
    """Assess heat-stress risk from immutable plant tolerance and heat exposure."""
    if not isinstance(request, PlantStressRiskRequest):
        raise TypeError("request must be a PlantStressRiskRequest")
    if PlantStressDimension.HEAT not in request.policy.enabled_dimensions:
        return _heat_aggregate(
            request,
            _heat_non_success(
                request,
                PlantStressRiskStatus.UNAVAILABLE,
                "heat_dimension_disabled",
                "Heat-stress assessment is disabled by policy.",
                "policy does not enable heat",
            ),
        )
    if request.selected_profile_id is None:
        return _heat_aggregate(
            request,
            _heat_non_success(
                request,
                PlantStressRiskStatus.INSUFFICIENT_PLANT_KNOWLEDGE,
                "plant_profile_unresolved",
                "Plant profile resolution is unavailable.",
                "plant profile was not resolved",
            ),
        )

    tolerance_claim = _heat_tolerance_claim(request)
    if tolerance_claim is None or not isinstance(tolerance_claim.value, HeatTolerance) or (
        tolerance_claim.value is HeatTolerance.UNKNOWN
    ):
        return _heat_aggregate(
            request,
            _heat_non_success(
                request,
                PlantStressRiskStatus.INSUFFICIENT_PLANT_KNOWLEDGE,
                "heat_tolerance_unavailable",
                "Heat-tolerance evidence is unavailable.",
                "approved environment.heat_tolerance evidence was not resolved",
            ),
        )
    if tolerance_claim.conflict_unresolved:
        return _heat_aggregate(
            request,
            _heat_non_success(
                request,
                PlantStressRiskStatus.CONFLICTING_EVIDENCE,
                "heat_tolerance_conflicting",
                "Heat-tolerance evidence remains conflicting.",
                "environment.heat_tolerance evidence has an unresolved conflict",
                claim=tolerance_claim,
            ),
        )

    heat_signal = _heat_signal(request)
    if heat_signal is None or heat_signal.classification not in _HEAT_BASE_RISK:
        return _heat_aggregate(
            request,
            _heat_non_success(
                request,
                PlantStressRiskStatus.INSUFFICIENT_ENVIRONMENTAL_EVIDENCE,
                "heat_signal_unavailable",
                "Environmental heat-exposure evidence is unavailable.",
                "environmental report lacks a usable heat-exposure signal",
                claim=tolerance_claim,
            ),
        )

    risk = _HEAT_BASE_RISK[heat_signal.classification][tolerance_claim.value]
    confidence_value = min(
        tolerance_claim.confidence,
        heat_signal.confidence.average_confidence,
    )
    incomplete = heat_signal.confidence.completeness < 1.0
    below_confidence = confidence_value < request.policy.minimum_confidence
    partial = incomplete or below_confidence
    if (
        partial
        and request.policy.partial_evidence_behavior
        is PartialEvidenceBehavior.REQUIRE_COMPLETE
    ):
        return _heat_aggregate(
            request,
            _heat_non_success(
                request,
                PlantStressRiskStatus.UNAVAILABLE,
                "complete_evidence_required",
                "Complete heat-stress evidence is required by policy.",
                "one or more required inputs are incomplete or below confidence policy",
                claim=tolerance_claim,
                signal=heat_signal,
            ),
        )

    issues: list[str] = []
    if incomplete:
        issues.append("environmental heat evidence is incomplete")
    if below_confidence:
        issues.append("combined evidence confidence is below policy")
    status = PlantStressRiskStatus.PARTIAL if partial else PlantStressRiskStatus.AVAILABLE
    dimension = PlantStressDimensionAssessment(
        assessment_id=_heat_dimension_id(request.request_id),
        dimension=PlantStressDimension.HEAT,
        status=status,
        risk=risk,
        confidence=PlantStressRiskConfidence(
            confidence=confidence_value,
            completeness=1.0,
            known_required_input_count=_HEAT_REQUIRED_INPUT_COUNT,
            required_input_count=_HEAT_REQUIRED_INPUT_COUNT,
        ),
        selected_profile_id=request.selected_profile_id,
        plant_knowledge_claim_ids=(tolerance_claim.claim_id,),
        plant_knowledge_source_ids=tuple(sorted(tolerance_claim.source_ids)),
        water_requirement_assessment_id=None,
        environmental_report_id=request.environmental_report.report_id,
        environmental_signal_ids=(heat_signal.signal_id,),
        regional_applicability=tolerance_claim.regional_applicability,
        policy_id=request.policy.policy_id,
        policy_version=request.policy.policy_version,
        algorithm_version=PLANT_STRESS_RISK_ALGORITHM_VERSION,
        explanation=PlantStressRiskExplanation(
            reason_codes=tuple(
                sorted(
                    {
                        f"heat_exposure_{heat_signal.classification.value}",
                        f"heat_tolerance_{tolerance_claim.value.value}",
                    }
                )
            ),
            summary=(
                f"Heat-stress risk is {risk.value} from "
                f"{heat_signal.classification.value} heat exposure and "
                f"{tolerance_claim.value.value} plant heat tolerance."
            ),
        ),
        unresolved_issues=tuple(sorted(issues)),
    )
    return _heat_aggregate(request, dimension)


def _heat_tolerance_claim(
    request: PlantStressRiskRequest,
) -> EffectivePlantKnowledgeClaim | None:
    return next(
        (
            claim
            for claim in request.knowledge_resolution.effective_claims
            if claim.field_path == _HEAT_TOLERANCE_PATH
        ),
        None,
    )


def _heat_signal(request: PlantStressRiskRequest) -> EnvironmentalSignal | None:
    signals = tuple(
        signal
        for signal in request.environmental_report.signals
        if signal.signal_type is EnvironmentalSignalType.HEAT_EXPOSURE
    )
    if not signals:
        return None
    return sorted(signals, key=lambda signal: signal.signal_id)[0]


def _heat_non_success(
    request: PlantStressRiskRequest,
    status: PlantStressRiskStatus,
    reason: str,
    summary: str,
    issue: str,
    *,
    claim: EffectivePlantKnowledgeClaim | None = None,
    signal: EnvironmentalSignal | None = None,
) -> PlantStressDimensionAssessment:
    if request.policy.missing_evidence_behavior is MissingEvidenceBehavior.RETURN_UNAVAILABLE:
        status = PlantStressRiskStatus.UNAVAILABLE
    known = int(claim is not None) + int(signal is not None)
    confidence_values = [
        value
        for value in (
            claim.confidence if claim is not None else None,
            signal.confidence.average_confidence if signal is not None else None,
        )
        if value is not None
    ]
    return PlantStressDimensionAssessment(
        assessment_id=_heat_dimension_id(request.request_id),
        dimension=PlantStressDimension.HEAT,
        status=status,
        risk=PlantStressRiskClassification.UNKNOWN,
        confidence=PlantStressRiskConfidence(
            confidence=min(confidence_values) if confidence_values else 0.0,
            completeness=known / _HEAT_REQUIRED_INPUT_COUNT,
            known_required_input_count=known,
            required_input_count=_HEAT_REQUIRED_INPUT_COUNT,
        ),
        selected_profile_id=request.selected_profile_id,
        plant_knowledge_claim_ids=(claim.claim_id,) if claim is not None else (),
        plant_knowledge_source_ids=tuple(sorted(claim.source_ids)) if claim is not None else (),
        water_requirement_assessment_id=None,
        environmental_report_id=request.environmental_report.report_id,
        environmental_signal_ids=(signal.signal_id,) if signal is not None else (),
        regional_applicability=request.context.regional_applicability,
        policy_id=request.policy.policy_id,
        policy_version=request.policy.policy_version,
        algorithm_version=PLANT_STRESS_RISK_ALGORITHM_VERSION,
        explanation=PlantStressRiskExplanation(reason_codes=(reason,), summary=summary),
        unresolved_issues=(issue,),
    )


def _heat_aggregate(
    request: PlantStressRiskRequest,
    dimension: PlantStressDimensionAssessment,
) -> PlantStressRiskAssessment:
    overall_risk = (
        dimension.risk
        if request.policy.overall_risk_aggregation is OverallRiskAggregation.HIGHEST_AVAILABLE
        and dimension.risk is not PlantStressRiskClassification.UNKNOWN
        else None
    )
    return PlantStressRiskAssessment(
        assessment_id=_heat_aggregate_id(request.request_id),
        request_id=request.request_id,
        selected_profile_id=request.selected_profile_id,
        location_id=request.context.location_id,
        analysis_window_id=request.context.analysis_window_id,
        dimensions=(dimension,),
        overall_status=dimension.status,
        overall_risk=overall_risk,
        confidence=dimension.confidence,
        knowledge_resolution_id=request.knowledge_resolution.request_id,
        water_requirement_assessment_id=request.water_requirement_assessment.assessment_id,
        environmental_report_id=request.environmental_report.report_id,
        policy_id=request.policy.policy_id,
        policy_version=request.policy.policy_version,
        algorithm_version=PLANT_STRESS_RISK_ALGORITHM_VERSION,
        explanation=PlantStressRiskExplanation(
            reason_codes=("heat_dimension_assessed",),
            summary="Heat plant stress risk assessment completed.",
        ),
        unresolved_issues=dimension.unresolved_issues,
        created_at=request.created_at,
    )


def _heat_dimension_id(request_id: str) -> str:
    return f"plant-stress.heat.{sha256(request_id.encode()).hexdigest()}"


def _heat_aggregate_id(request_id: str) -> str:
    return f"plant-stress.heat-assessment.{sha256(request_id.encode()).hexdigest()}"
