# IrrigationOS v1.0.20 — Shadow Reporting and Commissioning Summary

## Purpose

v1.0.20 turns the immutable evidence produced by v1.0.18 and v1.0.19 into a compact operator-facing commissioning summary. It remains entirely observational and does not change controller behavior.

## Inputs

The report is derived from retained immutable evidence only:

- `irrigationos_shadow_YYYY-MM-DD.jsonl`
- `irrigationos_reconciliation_YYYY-MM-DD.jsonl`

No new controller command path is introduced.

## Summary metrics

The commissioning summary includes:

- total shadow evaluations and nightly evaluations
- total reconciliations and comparable reconciliations
- agreement, partial agreement, disagreement, and insufficient-evidence counts
- skipped planned watering and unexpected observed watering counts
- confidence distribution
- substantive medium/high-confidence disagreement count
- distinct evidence days and targets represented
- agreement rate across comparable evidence
- mean and maximum absolute planned-vs-observed start-time delta
- mean and maximum absolute planned-vs-observed runtime delta

## Evidence states

The operator-facing state is deliberately descriptive rather than promotional:

- `no_evidence` — no retained shadow or reconciliation evidence exists
- `collecting_evidence` — evidence exists but no comparable planned-vs-observed result exists yet
- `evidence_available` — comparable evidence exists without a medium/high-confidence disagreement
- `review_required` — at least one medium/high-confidence disagreement exists

These states do **not** constitute permission to enable Live mode. `promotion_assessment` remains `not_assessed` in this milestone.

## Home Assistant surface

New sensor:

- `sensor.irrigationos_commissioning_summary`

Its state is the evidence state above. Attributes contain only aggregate report metrics; no controller actuation is exposed.

Diagnostics also include the same aggregate commissioning report.

## Safety boundary

v1.0.20 is observation-only. It does not:

- start or stop irrigation
- modify a controller schedule
- create a rain delay
- enable or disable a zone
- promote IrrigationOS into Live mode

Future promotion criteria must be explicit, separately reviewed, and must never be inferred solely from `evidence_available`.
