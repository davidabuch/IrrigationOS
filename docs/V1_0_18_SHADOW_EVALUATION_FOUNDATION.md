# v1.0.18 — Shadow Evaluation Foundation

## Purpose

v1.0.18 creates immutable, point-in-time evidence of what IrrigationOS believed should happen while preserving the existing observation-only commissioning boundary. These records are the future evidence source for actual-vs-shadow reconciliation; they are not execution authorization.

## Cadence

IrrigationOS produces one authoritative nightly shadow evaluation at 8:00 PM Home Assistant local time. Normal five-minute polling and accepted realtime refreshes continue to rebuild the in-memory deterministic pipeline, but they do not automatically create immutable records.

Between nightly evaluations, a candidate reevaluation is considered after a successful canonical refresh. Material categories include completed watering, landscape-profile changes, scientific-input changes, observation changes, confidence/readiness changes, and decision changes. Semantic deduplication compares the meaningful decision payload. If the resulting recommendation/plan/schedule/execution-simulation meaning is unchanged, the reevaluation is counted but a redundant full immutable record is not written.

The first valid evaluation after startup is eligible when persisted deduplication state is missing. Home Assistant restart alone does not manufacture a new record when restored state is current and the decision remains semantically unchanged.

## Immutable record

Each persisted record contains:

- schema version and stable SHA-256 evaluation ID;
- UTC and Home Assistant local timestamps;
- evaluation reason;
- IrrigationOS and pipeline algorithm versions;
- decision fingerprint;
- stage readiness and blockers;
- scientific-input snapshot and provenance available to the pipeline;
- canonical observation and landscape context with provider secrets removed;
- water requirements, plant stress, plant health, recommendations, plans, schedules, and execution-simulation outputs.

Records are written to:

`/config/irrigationos_logs/irrigationos_shadow_YYYY-MM-DD.jsonl`

The filename uses the Home Assistant local day. Retention is 30 local calendar days. The JSONL record itself preserves the original point-in-time inputs and conclusions; later data never rewrites or retrospectively recalculates an earlier record.

## Safety boundary

v1.0.18 remains observation-only. The shadow subsystem has no controller adapter command path and does not start or stop zones, actuate valves, create rain delays, modify provider schedules, or enable Live mode. Existing pipeline execution output remains simulation-only. A recommendation or simulated execution plan is evidence, not permission to actuate.

## Future use

v1.0.19 can consume these preserved records alongside v1.0.17 watering-session evidence to compare planned zones, runtimes, timing, skipped or unexpected watering, evidence completeness, and agreement confidence without reconstructing historical intent from newer data.
