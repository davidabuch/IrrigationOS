# v1.0.7 Planning Pipeline Integration

## Purpose

v1.0.7 integrates the existing deterministic Planning engine into the synchronized Home Assistant evaluation pipeline. It does not create a second planning algorithm, schedule watering, or authorize irrigation hardware control.

## Evidence flow

The Home Assistant pipeline now carries the following per-area chain:

```text
Scientific Inputs
  -> Plant Water Requirement
  -> Plant Stress
  -> Plant Health
  -> Recommendations
  -> Planning
```

`pipeline/planning.py` is an adapter. It passes canonical `RecommendationAssessment` values into the existing `planning.build_irrigation_plan()` domain engine. Recommendation and upstream scientific logic remain authoritative in their existing domain modules.

## Stable pipeline contract

`PipelineEvaluation` now exposes immutable per-area `AreaPlanningEvaluation` values. Each value contains either a canonical `IrrigationPlan` or explicit blocker codes when the required Recommendation assessment does not exist.

Plan actions preserve the recommendation ID and supporting upstream assessment IDs supplied by the Recommendation engine.

## No invented planning directives

The synchronized Home Assistant pipeline does not currently possess an authoritative source for target, irrigation quantity, calculated runtime, cycle count, or soak duration. v1.0.7 therefore supplies no `PlanningDirective` values.

The existing Planning engine remains responsible for interpreting that absence. Irrigation actions that require missing quantitative inputs remain blocked, while non-irrigation advisory actions may remain machine-readable and manual-only.

## Safety boundary

Recommendation safety flags are preserved in planning actions. In particular, `NO_AUTOMATIC_EXECUTION` causes an otherwise complete action to remain `MANUAL_ONLY`.

v1.0.7 does not connect Planning to Scheduling, Execution, Rachio writes, or any other physical actuation path. Scheduling, Execution, and Runtime Monitoring remain blocked pending their dedicated integration milestones.

## Validation focus

Coverage protects:

- deterministic use of the existing Planning engine;
- Recommendation-to-Plan provenance;
- no fabrication of directives or quantitative irrigation inputs;
- preservation of manual-only/no-automatic-execution safety behavior;
- explicit blocking when Recommendation assessments are absent; and
- continued blocking of Scheduling and later stages.
