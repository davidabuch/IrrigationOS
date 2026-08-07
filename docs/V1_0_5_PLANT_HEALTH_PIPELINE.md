# v1.0.5 Plant Health Pipeline Integration

IrrigationOS now executes the frozen Plant Health domain engine inside each synchronized Home Assistant pipeline evaluation.

Plant Health deliberately remains evidence-gated. Aggregate Plant Stress is preserved as context but is not diagnostic evidence. The current Home Assistant pipeline does not yet ingest direct manual, sensor, or visual plant-health observations, so eligible areas receive a canonical `insufficient_direct_evidence` assessment rather than an invented health classification.

This milestone stores immutable per-area Plant Health assessments and exposes truthful stage blockers. Recommendations and all downstream stages remain blocked for later integration milestones. The observation/simulation-only safety boundary is unchanged.
