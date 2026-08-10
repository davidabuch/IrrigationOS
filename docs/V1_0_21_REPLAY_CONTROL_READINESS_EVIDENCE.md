# IrrigationOS v1.0.21 — Replay and Control-Readiness Evidence

## Purpose

v1.0.21 adds a deterministic replay and explicit readiness-evidence layer on top of the immutable shadow and actual-vs-shadow records introduced in v1.0.18 through v1.0.20.

This milestone remains observation-only. It cannot authorize, enable, schedule, or execute live irrigation commands.

## Historical replay

Retained reconciliation records are reclassified from their preserved point-in-time inputs using the current deterministic reconciliation rules. Replay compares the recomputed result with the immutable stored outcome, confidence, reason codes, and available deltas.

Records that do not contain enough historical inputs are reported as not replayable rather than guessed. In particular, legacy skipped-watering records that predate preservation of contemporaneous observation quality remain explicit coverage gaps.

Beginning with v1.0.21, new skipped-watering reconciliation evidence preserves the observation-quality value used by the original classification so that future replay can be complete.

## Golden scenarios

A fixed canonical scenario suite exercises:

- exact event-bounded agreement
- timing-difference partial agreement
- runtime-difference partial agreement
- partial/incomplete observation confidence downgrade
- unexpected observed watering with partial evidence

Golden scenarios are deterministic code-level guards and are not substitutes for real-world commissioning evidence.

## Explicit readiness criteria

The derived readiness report evaluates all of the following:

- at least 14 distinct evidence days
- at least 20 comparable reconciliations
- at least 80% strict agreement
- zero substantive medium/high-confidence disagreements
- no more than 20% insufficient-evidence records
- at least 90% historical replay coverage
- 100% match rate among replayable records
- all golden scenarios passing

The report can reach `criteria_met`, but that means only that the defined evidence thresholds are satisfied. It does **not** enable Live mode.

`live_control_authorized` is hard-coded `false` in this milestone. A future explicit architecture and safety milestone is required before any command path can be commissioned.

## Home Assistant exposure

`sensor.irrigationos_control_readiness_evidence` exposes:

- replay status and coverage
- replay matches and mismatches
- golden-scenario results
- per-criterion pass/fail state
- threshold values
- readiness state
- promotion assessment
- the explicit `live_control_authorized: false` safety field

Diagnostics expose the same privacy-safe aggregate evidence.
