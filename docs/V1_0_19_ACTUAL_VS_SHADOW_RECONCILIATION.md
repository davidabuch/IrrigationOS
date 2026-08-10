# v1.0.19 — Actual-vs-Shadow Reconciliation

## Purpose

v1.0.19 compares what IrrigationOS previously believed should happen with what was later observed to happen. It consumes preserved v1.0.18 shadow evaluations and v1.0.17 watering-session evidence without recalculating historical intent from newer inputs.

## Comparison model

Scheduled irrigation actions are registered from immutable shadow records. Later completed watering sessions are matched by canonical target identity and a conservative timing window. Reconciliation records preserve planned and observed start times, runtimes, timing/runtime deltas, observation quality, timestamp precision, reason codes, outcome, and confidence.

Stable outcomes are `agreement`, `partial`, `disagreement`, and `insufficient_evidence`. Evidence confidence is separately reported as `high`, `medium`, `low`, or `none`.

A watering session is not labeled unexpected when no preceding shadow evaluation exists; that case is explicitly `insufficient_evidence`. A planned watering that is not observed after the comparison grace period is not called a definite skip when current observation quality is not confirmed.

Later shadow evaluations supersede earlier future actions that had not yet begun. This prevents obsolete shadow plans from becoming false skipped-watering findings after a material reevaluation changes the plan.

## Persistence and restart behavior

Comparison evidence is written to:

`/config/irrigationos_logs/irrigationos_reconciliation_YYYY-MM-DD.jsonl`

Files use the Home Assistant local day and retain 30 local calendar days. Pending shadow actions and processed identifiers persist across restart so the same session/action pair is not reconciled repeatedly. On initialization, preserved shadow records are replayed chronologically to reconstruct effective pending intent.

## Safety boundary

v1.0.19 is observation-only. Reconciliation has no controller command path and cannot start/stop zones, actuate valves, issue rain delays, modify provider schedules, or enable Live mode. Comparison evidence is diagnostic/control-readiness evidence only.
