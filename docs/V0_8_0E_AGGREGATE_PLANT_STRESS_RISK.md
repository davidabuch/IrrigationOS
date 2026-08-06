# v0.8.0E — Aggregate Plant Stress Risk

This milestone completes the Plant Stress subsystem by combining independent water-deficit, heat,
and freeze dimension assessments into one immutable `PlantStressRiskAssessment`.

The aggregate engine:

- accepts only completed, immutable dimension assessments;
- requires the dimensions to exactly match the policy-enabled dimensions;
- preserves each dimension unchanged and in deterministic order;
- never averages or numerically blends risks;
- reports the highest available categorical risk only when the explicit
  `HIGHEST_AVAILABLE` policy authorizes it;
- identifies every dimension tied for the driving risk;
- combines confidence conservatively and completeness from required-input counts; and
- returns typed partial or unavailable outcomes when dimensions are incomplete.

It does not diagnose plant health, recommend action, plan irrigation, or control hardware.
