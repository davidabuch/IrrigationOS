# v1.0.6 Recommendation Pipeline Integration

## Purpose

v1.0.6 integrates the existing deterministic Recommendation engine into the synchronized Home Assistant evaluation pipeline. It does not create a second recommendation algorithm and does not authorize irrigation hardware control.

## Evidence flow

The Home Assistant pipeline now carries the following per-area evidence chain:

```text
Scientific Inputs
  -> Plant Water Requirement
  -> Plant Stress
  -> Plant Health
  -> Recommendations
```

`pipeline/recommendation.py` is an adapter. It accepts the canonical upstream assessments already produced by the pipeline and passes them to the existing `recommendations.assess_recommendations()` domain engine. Water requirement, stress, and health logic remain authoritative in their existing domain modules.

## Stable pipeline contract

`PipelineEvaluation` now exposes immutable per-area `AreaRecommendationEvaluation` values. Each value contains either a canonical `RecommendationAssessment` or explicit blocker codes when the required upstream assessments do not exist.

Recommendation provenance remains intact through the canonical domain assessment fields:

- Plant Health assessment ID
- aggregate Plant Stress assessment ID
- Plant Water Requirement assessment ID
- recommendation policy ID/version
- recommendation algorithm version

## Direct-health evidence boundary

The Home Assistant pipeline still does not fabricate direct Plant Health observations. When Plant Health returns `INSUFFICIENT_DIRECT_EVIDENCE`, the Recommendation engine may still produce conservative inspection guidance because that behavior is part of the existing domain contract.

Therefore a blocked Plant Health stage does not automatically block Recommendations when a canonical Plant Health assessment exists. In that case Recommendations are exposed as `PARTIAL`, with unresolved evidence and blocker codes preserved.

If a required upstream assessment is absent entirely, the per-area recommendation assessment is `None` and the Recommendation stage remains blocked for that coverage.

## Safety boundary

All recommendations remain advisory. Existing domain safety flags are preserved, including:

- `ADVISORY_ONLY`
- `NO_AUTOMATIC_EXECUTION`

v1.0.6 does not connect recommendations to Planning, Scheduling, Execution, Rachio writes, or any other physical actuation path. Those downstream pipeline stages remain blocked pending their dedicated integration milestones.

## Validation focus

Coverage protects:

- deterministic use of the existing Recommendation engine;
- upstream assessment provenance;
- conservative handling of insufficient direct health evidence;
- explicit blocking when upstream assessments are absent;
- preservation of advisory-only/no-automatic-execution flags; and
- continued blocking of Planning and later stages.
